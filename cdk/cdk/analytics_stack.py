import json
from aws_cdk import NestedStack, Fn
from aws_cdk import aws_iam as iam
from aws_cdk import aws_glue as glue
from aws_cdk import aws_athena as athena
from aws_cdk import aws_s3 as s3
from constructs import Construct


class AnalyticsStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, data_bucket: s3.IBucket, athena_results_bucket: s3.IBucket, ** kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define constant values
        self.athena_database_name = "example_glue_database_" + self.account.lower()
        self.athena_workgroup_name = "primary_workgroup" + self.account.lower()

        # Create Glue crawler role with specific permissions
        crawler_role = iam.Role(
            self,
            "GlueCrawlerRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
        )

        crawler_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSGlueServiceRole")
        )

        data_bucket.grant_read(crawler_role)

        # Create a Glue database
        glue_database = glue.CfnDatabase(
            self, "GlueDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=self.athena_database_name
            )
        )

        # Create a Glue crawler
        glue_crawler = glue.CfnCrawler(
            self, "ExampleGlueCrawler",
            name="example-data-crawler",
            role=crawler_role.role_arn,
            database_name=self.athena_database_name,
            targets=glue.CfnCrawler.TargetsProperty(
                s3_targets=[glue.CfnCrawler.S3TargetProperty(
                    path=Fn.join("", ["s3://", data_bucket.bucket_name, "/"]),
                    exclusions=["**.DS_Store"],
                )]
            ),
            schema_change_policy=glue.CfnCrawler.SchemaChangePolicyProperty(
                update_behavior="UPDATE_IN_DATABASE",
                delete_behavior="DELETE_FROM_DATABASE"
            ),
            schedule=glue.CfnCrawler.ScheduleProperty(
                schedule_expression="cron(0 * * * ? *)"
            ),
            configuration=json.dumps({
                "Version": 1.0,
                "Grouping": {
                    "TableGroupingPolicy": "CombineCompatibleSchemas",
                    "TableLevelConfiguration": 2
                },
                "CrawlerOutput": {
                    "Partitions": {
                        "AddOrUpdateBehavior": "InheritFromTable"
                    }
                }
            })
        )

        glue_crawler.add_dependency(glue_database)

        # Create Athena workgroup with encryption
        self.athena_workgroup = athena.CfnWorkGroup(
            self, "AthenaWorkgroup",
            name=self.athena_workgroup_name,
            recursive_delete_option=True,
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                enforce_work_group_configuration=True,
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{athena_results_bucket.bucket_name}/athena-results/",
                    encryption_configuration=athena.CfnWorkGroup.EncryptionConfigurationProperty(
                        encryption_option="SSE_S3"  # This ensures encryption is enabled
                    )
                ),
            )
        )
