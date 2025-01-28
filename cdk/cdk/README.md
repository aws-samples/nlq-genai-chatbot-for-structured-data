# Stack Structure

The CDK application is organized into nested stacks:

```
MainStack
├── SharedServicesStack (VPC)
├── StorageStack (S3 buckets)
├── AnalyticsStack (Glue, Athena)
├── PromptsStack (Bedrock)
└── FargateStack (ECS Fargate, Cognito)
```

- `SharedServicesStack`: Contains shared infrastructure (VPC) used by other stacks
- `StorageStack`: Manages S3 buckets for data storage
- `AnalyticsStack`: Sets up Glue & Athena for data analytics
- `PromptsStack`: Manages Bedrock prompts
- `FargateStack`: Deploys chatbot application using ECS Fargate and Cognito

All stacks are nested under MainStack to ensure proper dependency management and resource sharing.