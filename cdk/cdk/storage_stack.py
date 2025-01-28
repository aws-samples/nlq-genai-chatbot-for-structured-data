from aws_cdk import NestedStack, RemovalPolicy, PhysicalName
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct
import os


class StorageStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, bucket_name: str = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create access logs bucket first
        self.access_logs_bucket = s3.Bucket(
            self,
            "AccessLogsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL
        )

        if bucket_name:
            self.data_bucket = s3.Bucket.from_bucket_name(
                self, "DataBucket", bucket_name)
        else:
            # Create main data bucket with server access logging enabled
            self.data_bucket = s3.Bucket(
                self,
                "DataBucket",
                # bucket_name=PhysicalName.GENERATE_IF_NEEDED,
                removal_policy=RemovalPolicy.DESTROY,
                auto_delete_objects=True,
                enforce_ssl=True,
                server_access_logs_bucket=self.access_logs_bucket,
                server_access_logs_prefix="data-bucket-access-logs/",
                encryption=s3.BucketEncryption.S3_MANAGED,
                versioned=True,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL
            )

            bucket_name = self.data_bucket.bucket_name

            current_dir = os.path.dirname(os.path.realpath(__file__))
            example_data_dir = os.path.abspath(
                os.path.join(current_dir, '..', 'example-data'))

            # Deploy the 'example-data' folder to the S3 bucket
            s3deploy.BucketDeployment(
                self, "DeployFolder",
                sources=[s3deploy.Source.asset(example_data_dir)],
                destination_bucket=self.data_bucket,
                retain_on_delete=False
            )

        # Create an S3 bucket for Athena query results with proper security settings
        self.athena_results_bucket = s3.Bucket(
            self, "AthenaResultsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            server_access_logs_bucket=self.access_logs_bucket,
            server_access_logs_prefix="athena-results-bucket-access-logs/"
        )
