#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk.main_stack import MainStack


app = cdk.App()

# Add tags at app level - will apply to all stacks
# cdk.Tags.of(app).add('project', 'nlq-genai')

# If data already exists in bucket, add the bucket name here.
MainStack(app, "NLQGenAI",
          bucket_name="",
          aws_region_for_bedrock_inference="us-west-2",
          # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html,

          env=cdk.Environment(
              # or hardcode i.e. 'us-east-1'
              account=os.getenv('CDK_DEFAULT_ACCOUNT'),
              region=os.getenv('CDK_DEFAULT_REGION')
          ),
          )

app.synth()
