from constructs import Construct
from aws_cdk import (
    Stack,
    CfnOutput,
    Fn,
)
from .shared_services_stack import SharedServicesStack
from dotenv import load_dotenv
from .storage_stack import StorageStack
from .analytics_stack import AnalyticsStack
from .prompts_stack import PromptsStack
from .fargate_stack import FargateStack
# Load environment variables from .env file
load_dotenv()


class MainStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, bucket_name: str,
                 aws_region_for_bedrock_inference: str = 'us-west-2', **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Shared Services Stack
        shared_services = SharedServicesStack(
            self, "SharedServicesStack",
        )

        # Storage Stack
        storage = StorageStack(
            self, "StorageStack",
            bucket_name=bucket_name,
        )

        # Analytics Stack
        analytics = AnalyticsStack(
            self, "AnalyticsStack",
            data_bucket=storage.data_bucket,
            athena_results_bucket=storage.athena_results_bucket,
        )

        # Bedrock Prompts Stack
        prompts = PromptsStack(
            self, "PromptsStack",
        )

        # Calculate Athena connection string
        athena_staging_dir = f"s3://{storage.athena_results_bucket.bucket_name}/athena-results/"
        athena_connection_string = f"awsathena+rest://@athena.{self.region}.amazonaws.com:443/{analytics.athena_database_name}?s3_staging_dir={athena_staging_dir}&work_group={analytics.athena_workgroup_name}"

        # ECS Fargate Stack
        fargate = FargateStack(
            self, "FargateStack",
            vpc=shared_services.vpc,
            access_logs_bucket=storage.access_logs_bucket,
            data_bucket=storage.data_bucket,
            athena_results_bucket=storage.athena_results_bucket,
            db_connection_string=athena_connection_string,
            athena_workgroup_name=analytics.athena_workgroup_name,
            athena_database_name=analytics.athena_database_name,
            data_oriented_prompt_id=prompts.data_oriented_prompt.prompt_id,
            business_oriented_prompt_id=prompts.business_oriented_prompt.prompt_id,
            aws_region_for_bedrock_inference=aws_region_for_bedrock_inference,
        )

        # Output important values as stack outputs - Useful for local development
        CfnOutput(
            self, "AthenaConnectionString",
            value=athena_connection_string,
            description="The Athena connection string"
        )

        CfnOutput(
            self, "BEDROCK_PROMPT_ID_1",
            value=prompts.data_oriented_prompt.prompt_id,
            description="The prompt id for data oriented prompt"
        )
        CfnOutput(
            self, "BEDROCK_PROMPT_ID_2",
            value=prompts.business_oriented_prompt.prompt_id,
            description="The prompt id for business oriented prompt"
        )

        CfnOutput(self, "OAUTH_COGNITO_CLIENT_ID",
                  value=fargate.client.user_pool_client_id)

        CfnOutput(self, "OAUTH_COGNITO_CLIENT_SECRET",
                  value=fargate.client.user_pool_client_secret.unsafe_unwrap())

        CfnOutput(self, "OAUTH_COGNITO_DOMAIN", value=f"""{
                  fargate.domain.domain_name}.auth.{self.region}.amazoncognito.com""")

        CfnOutput(self, "CloudFrontDomain",
                  value=f"https://{fargate.distribution.distribution_domain_name}")

        CfnOutput(
            self, "CognitoUserPoolConsoleLink",
            value=Fn.sub(
                'https://${AWS::Region}.console.aws.amazon.com/cognito/v2/idp/user-pools/${userPoolId}/users?region=${AWS::Region}',
                variables={
                    "userPoolId": fargate.user_pool.user_pool_id}
            ),
            description="Console link to the Cognito User Pool"
        )
