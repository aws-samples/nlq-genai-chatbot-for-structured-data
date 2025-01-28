from aws_cdk import NestedStack, RemovalPolicy, CfnOutput, Fn
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import SecretValue
from aws_cdk.aws_ecr_assets import DockerImageAsset
from constructs import Construct
import os


class FargateStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc,
                 access_logs_bucket, data_bucket, athena_results_bucket, athena_connection_string: str,
                 athena_workgroup_name: str, athena_database_name: str, data_oriented_prompt_id: str, business_oriented_prompt_id: str,
                 aws_region_for_bedrock_inference: str = 'us-west-2', ** kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Build the Docker image
        image = DockerImageAsset(
            self, "DockerImage",
            directory=os.path.join(os.path.dirname(__file__), "..", ".."),
            file="Dockerfile",
        )

        # Create an IAM role for the Fargate task with specific permissions
        task_role = iam.Role(
            self, "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )

        # Add specific permissions to the role
        task_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                # Bedrock permissions
                "bedrock:GetPrompt",
                "bedrock:InvokeModel",
                # Athena permissions
                "athena:Get*",
                "athena:List*",
                "athena:StartQueryExecution",
                "athena:StopQueryExecution",
                "athena:BatchGetQueryExecution",
                # S3 permissions
                "s3:GetBucketLocation",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:ListBucketMultipartUploads",
                "s3:ListMultipartUploadParts",
                "s3:AbortMultipartUpload",
                "s3:PutObject",
                # Glue permissions
                "glue:Get*",
                "glue:BatchGetPartition"
            ],
            resources=[
                # Bedrock resources for Claude Haiku model and prompts
                "arn:aws:bedrock:*::foundation-model/*",
                f"arn:aws:bedrock:{self.region}:{self.account}:prompt/{data_oriented_prompt_id}",
                f"arn:aws:bedrock:{self.region}:{self.account}:prompt/{business_oriented_prompt_id}",

                # # Athena results bucket
                f"arn:aws:s3:::{athena_results_bucket.bucket_name}",
                f"arn:aws:s3:::{athena_results_bucket.bucket_name}/*",

                # # Glue catalog resources
                f"""
                    arn:aws:glue:{self.region}:{self.account}:catalog
                """.strip(),
                f"""
                    arn:aws:glue:{self.region}:{self.account}:database/{athena_database_name}
                """.strip(),
                f"""
                    arn:aws:glue:{self.region}:{self.account}:table/{athena_database_name}/*
                """.strip(),

                # Athena workgroup and datacatalog resources
                f"""
                    arn:aws:athena:{self.region}:{self.account}:workgroup/{athena_workgroup_name}
                """.strip(),
                f"""
                    arn:aws:athena:{self.region}:{self.account}:datacatalog/*
                """.strip()
            ]
        )

        # Policy for read operations on data bucket
        data_bucket_read_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:ListBucket"],
            resources=[
                f"arn:aws:s3:::{data_bucket.bucket_name}",
                f"arn:aws:s3:::{data_bucket.bucket_name}/*"
            ]
        )

        task_role.add_to_policy(task_policy)
        task_role.add_to_policy(data_bucket_read_policy)

        # Create a secret using the existing CHAINLIT_AUTH_SECRET value in .env
        chainlit_secret = secretsmanager.Secret(
            self, "ChainlitSecret",
            secret_name=f"{self.stack_name}-chainlit-secret",
            description="Auth secret for Chainlit",
            secret_string_value=SecretValue.unsafe_plain_text(
                os.getenv('CHAINLIT_AUTH_SECRET'))
        )

        # Update task role permissions to allow access to just this secret
        task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                resources=[chainlit_secret.secret_arn]
            )
        )

        # Create Fargate service with mixed environment configuration
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "GenAIService",
            memory_limit_mib=2048,
            cpu=1024,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_docker_image_asset(image),
                container_port=8080,
                task_role=task_role,
                environment={
                    # Non-sensitive values as regular environment variables
                    "ATHENA_CONNECTION_STRING": athena_connection_string,
                    "BEDROCK_PROMPT_ID_1": data_oriented_prompt_id,
                    "BEDROCK_PROMPT_ID_2": business_oriented_prompt_id,
                    "AWS_REGION_FOR_BEDROCK_INFERENCE": aws_region_for_bedrock_inference
                },
                secrets={
                    # Use the existing secret value
                    "CHAINLIT_AUTH_SECRET": ecs.Secret.from_secrets_manager(chainlit_secret)
                }
            ),
            desired_count=1,
            vpc=vpc,
            public_load_balancer=True,
            # Configure deployment circuit breaker
            circuit_breaker=ecs.DeploymentCircuitBreaker(
                rollback=True  # Enable rollback on failures
            )
        )

        # Enable load balancer access logs
        fargate_service.load_balancer.log_access_logs(
            access_logs_bucket, 'alb-access-logs')

        # Add load balancer attributes to drop invalid headers
        fargate_service.load_balancer.set_attribute(
            "routing.http.drop_invalid_header_fields.enabled",
            "true"
        )

        # Create CloudFront distribution
        self.distribution = cloudfront.Distribution(
            self, "GenAIDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.LoadBalancerV2Origin(
                    fargate_service.load_balancer,
                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
            ),
            additional_behaviors={
                "/auth/*": cloudfront.BehaviorOptions(
                    origin=origins.LoadBalancerV2Origin(
                        fargate_service.load_balancer,
                        protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER
                )
            }
        )

        # Create User Pool with enhanced password policy
        self.user_pool = cognito.UserPool(
            self, "GenAIUserPool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(
                email=True
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True
            ),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(
                    required=True,
                    mutable=True
                )
            ),
            removal_policy=RemovalPolicy.DESTROY
        )

        # Add domain prefix to user pool
        self.domain = self.user_pool.add_domain(
            "CognitoDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"demo-app-{self.account}"
            )
        )

        # Create User Pool Client with CloudFront callback URL
        self.client = self.user_pool.add_client(
            "GenAIClient",
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True
                ),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE
                ],
                callback_urls=[
                    f"https://{self.distribution.distribution_domain_name}",
                    f"https://{self.distribution.distribution_domain_name}/auth/oauth/aws-cognito/callback",
                    f"https://{self.distribution.distribution_domain_name}/oauth2/idpresponse",
                    "http://localhost:8000",
                    "http://localhost:8000/auth/oauth/aws-cognito/callback",
                    "http://localhost:8000/oauth2/idpresponse",
                    "http://localhost:8080",
                    "http://localhost:8080/auth/oauth/aws-cognito/callback",
                    "http://localhost:8080/oauth2/idpresponse",
                ]
            ),
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO
            ],
            generate_secret=True
        )

        # Create the Cognito User Pool Client secret
        cognito_secret = secretsmanager.Secret(
            self, "CognitoClientSecret",
            secret_name=f"{self.stack_name}-cognito-secret",
            description="Cognito Client Secret",
            secret_string_value=self.client.user_pool_client_secret
        )

        # Update task role to access the secret
        task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                resources=[cognito_secret.secret_arn]
            )
        )

        # Update Fargate task definition with environment variables and secret
        task_def = fargate_service.task_definition.default_container
        task_def.add_environment(
            "OAUTH_COGNITO_CLIENT_ID", self.client.user_pool_client_id)
        task_def.add_secret(
            "OAUTH_COGNITO_CLIENT_SECRET",
            ecs.Secret.from_secrets_manager(cognito_secret)
        )
        task_def.add_environment(
            "OAUTH_COGNITO_DOMAIN",
            f"{self.domain.domain_name}.auth.{self.region}.amazoncognito.com"
        )
        task_def.add_environment(
            "CHAINLIT_URL",
            f"https://{self.distribution.distribution_domain_name}"
        )
