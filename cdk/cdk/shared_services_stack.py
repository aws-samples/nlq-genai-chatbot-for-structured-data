from aws_cdk import (
    NestedStack,
    aws_ec2 as ec2,
)
from constructs import Construct


class SharedServicesStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create VPC
        self.vpc = ec2.Vpc(
            self, "VPC",
            max_azs=2,
            nat_gateways=1,
        )
