# Natural Language SQL Chatbot with GenAI

Unlock the power of your structured data with natural language queries. Whether you're exploring vast data lakes or querying relational databases, this NLQ data analyst Gen AI Agent provides an intuitive interface for data discovery and analysis.
The agent automatically converts natural language queries into SQL to extract insights from structured data sources.

## Key Features

- Query structured data using natural language
- Supports multiple data sources:
  - Amazon S3 data lakes including JSON, CSV, Parquet etc. file formats (via Amazon Athena and AWS Glue)
  - SQL databases (MySQL, PostgreSQL, etc.)
  - Data warehouses
- Powered by Amazon Bedrock LLMs
- Interactive UI built with Chainlit
- Flexible agent architecture using LangChain/LangGraph
    - Real-time query generation & execution
    - Transparency with Agent chain of thought and steps
- Automatic data source schema inference and mapping


## Example
![Example](./example.png)

#### Transparency of SQL Generated
![Example2](./example2.png)

I.e.
```
SELECT publisher, SUM(global_sales) AS total_sales
FROM video_game_sales
WHERE year BETWEEN '2000' AND '2010'
GROUP BY publisher
ORDER BY total_sales DESC
LIMIT 5;
```

## How It Works

1. Users input natural language queries through the Chainlit UI
2. The LangChain/LangGraph agent, powered by Amazon Bedrock, interprets the query
3. The agent determines the appropriate data source(s) to query
4. It generates the necessary SQL to retrieve data to answer the user's question
5. Results are processed and presented back to the user in a readable format

## Benefits

- Democratize data access across your organization
- Reduce dependency on data analysts for simple queries
- Accelerate data-driven decision making
- Seamlessly integrate with existing AWS infrastructure
- Scale effortlessly with serverless architecture

## AWS Deployment Instructions
### Pre-requisites

1. Docker Installed. See here for installation instructions: https://docs.docker.com/desktop/ 
2. Amazon Bedrock model access enabled: 
   - (Requried) Follow the [instructions here on enabling model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-modify.html). By default need to enable at least `Claude Haiku 3.5` in `us-west-2`. 
   - (Optional) You can change the Amazon Bedrock inference region in `cdk/app.py`. I.e. you may deploy the application infrastructure (ECS, VPC etc.) in ap-southeast-2 but use us-west-2 for Amazon Bedrock inference. See [here](https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html) for model region availability
   
- AWS CLI Credentials - see [here](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html) for instructions
- AWS CDK CLI installed: https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html 
- (Optional) Add your own datasets or more  from Kaggle. Follow Instructions under the `Adding Your Own Data to the S3 Data Lake` section. Otherwise only the `windfarm` dataset is included. Can add after deployment too. 

### Deployment
1. Change to the cdk directory:
   ```bash
   cd cdk
   ```

2. Extract the example-data.zip to a folder specifically named 'example-data':
   - MacOS/Linux
      ```bash
      unzip example-data.zip
      ```
   
   - Windows 
      ```
      # (Command Prompt):
      expand example-data.zip -F:*
      # or 
      tar -xf example-data.zip

      # (PowerShell):
      Expand-Archive -Path example-data.zip -DestinationPath .
      ```

3. Create a virtualenv:
   ```bash
   python -m venv .venv
   ```

4. Activate the virtualenv:
   - MacOS/Linux:
     ```bash
     source .venv/bin/activate
     ```
   - Windows:
     ```bash
     # In cmd.exe
     .venv\Scripts\activate.bat

     or 

     # In PowerShell
     .venv\Scripts\Activate.ps1
     ```

5. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

6. Generate the chainlit auth secret (required for Cognito Auth). Follow either of these approaches:

   #### Option A - Automatic Approach 
   Run the respective command to automatically generate and save the secret:
   
   ```bash
   # Linux/Mac
   chainlit create-secret | grep "CHAINLIT_AUTH_SECRET" > .env
   ```
   ```bash
   # Windows
   chainlit create-secret | Select-String "CHAINLIT_AUTH_SECRET" | Out-File -FilePath ".env" -Encoding utf8NoBOM
   ```

   NOTE: Ignore any warnings/errors like below:
   ```
   WARNING: All log messages before absl::InitializeLog() is called are written to STDERR
   E0000 00:00:1738205048.894250    2795 init.cc:232] grpc_wait_for_shutdown_with_timeout() timed out.
   ```

   #### Option B - Manual Approach (If Option A fails):
   1. If it exists, delete the existing `cdk/.env` file 
   1. Generate the secret:
      ```bash
      chainlit create-secret
      ```

   2. Copy only the line containing the generated secret (i.e. CHAINLIT_AUTH_SECRET="XXXXX")

   3. Create a new file at `cdk/.env` and paste the secret into it. 
   
   **Important**: The .env file should be placed directly in the top level `cdk` folder you are currently in, not in `cdk/cdk`.

7. Bootstrap (Only required on first run):
   ```
   cdk bootstrap
   ```

8. Update the CDK generated ECR Repo. Change the tag immutability setting to `mutable`:
   ```
   aws ecr put-image-tag-mutability --repository-name $(aws ecr describe-repositories --query 'repositories[?contains(repositoryName, `cdk-hnb659fds-container-assets`)].repositoryName' --output text) --image-tag-mutability MUTABLE
   ```
   see here for more info - https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-tag-mutability.html

9. Deploy (10-15 mins):
   ```
   cdk deploy
   ```
   You may need to accept IAM statement changes by entering `y` or `n`. 

### Post Deployment Steps (Required)
1. Run the Glue Crawler in the AWS Console: https://console.aws.amazon.com/glue/home#/v2/data-catalog/crawlers 

2. In order to access the site, create a Cognito user via the CognitoUserPoolConsoleLink in the CloudFormation Outputs. 

3. Access the chatbot at the CloudFrontDomain in the CloudFormation outputs.

4. Ask questions of the chatbot! Examples include:

   - How many turbines are in the database and what are their asset ids?
      - Which of these turbines has had the highest average temperature and what was it?
      - How was this average temp determined?
   - Which turbine has the highest vibration value, and when was it recorded?
      - Is this statistically anomalous, compared to the average value for turbine3?
      - Why would a turbine be producing more vibrations than usual?
      - When was the turbine last serviced?
      - What city would turbine3 be located in, based on long and lat values for the turbine?

## Cleanup Instructions
Note: This will delete all resources within the stacks, including S3 buckets and all data included inside them. 
1. From the `~/cdk` folder, run:
   ```
   cdk destroy --all
   ```

## Adding Your Own Data to the S3 Data Lake

1. Create a folder in the `example-data` folder with your chosen table name:
   ```
   mkdir cdk/example-data/<new-table-name>
   ```

2. Add your CSV, JSON Lines etc. within this new folder. I.e. `~/cdk/example-data/health-data/heath-stats.csv`.
   
   Note: it doesn't have to be a single file, it could be multiple (i.e. Parquet) files in the folder. Similar to the wind farm data. 

3. Re-run CDK Deploy:
   ```
   cdk deploy
   ```

4. Re-run the crawler to automatically create your tables: https://console.aws.amazon.com/glue/home#/v2/data-catalog/crawlers 

### Example datasets to try: 
Download one or all of the below Kaggle datasets and add a folder like so:
```
mkdir cdk/example-data/video-game-sales/video-game-sales.csv
```

From Kaggle: 
1. [Video Game Sales Data](https://www.kaggle.com/datasets/gregorut/videogamesales)
2. [Student's Performance in Exams](https://www.kaggle.com/datasets/spscientist/students-performance-in-exams)
3. [Titanic](https://www.kaggle.com/competitions/titanic/overview)

Already included:
1. Synthetic Wind Farm Turbines Data

(Kaggle Dataset Questions)
- who were the biggest game publishers in the decade 2000-2010? And give me the total sales
- what years were the biggest sales for nintendo?
   - and list the biggest game for each year. put this all in table format
- on the titanic, for each class what was the percentage of passengers who survived? 
- what were the latest turbine temps?
- what was the average temp for turbine 1 on 20 August?

## Connecting to RDS Database
### Required Steps:
1. Update the `db_connection_string` parameter in `cdk/cdk/main_stack.py`. [Click here to go to the specific line](cdk/cdk/main_stack.py#56)
2. Update `dialect` to your DB's dialect in `chainlit-app.py`. [Click here to go to the specific line](chainlit-app.py#186)
3. Ensure the Fargate task has necessary IAM permissions and networking to access your RDS instance
4. Configure RDS security groups to allow access from the Fargate service 
5. Re-deploy using `cdk deploy`

The connection string follows this format:
```
{dialect}://{username}:{password}@{host}:{port}/{database_name}
```

Example:
```python
db_connection_string = "postgresql://myuser:mypassword@my-database.xxxxx.region.rds.amazonaws.com:5432/mydatabase"
```

### Security Considerations:
1. **Never commit credentials to version control**
2. Use AWS Secrets Manager for storing database credentials
3. Ensure your RDS security group allows inbound traffic from the Fargate service's security group
4. Use SSL/TLS for database connections when possible
5. Consider using [IAM Authentication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.Connecting.html)


### Supported Database Types:
- PostgreSQL
- MySQL
- Amazon Aurora
- Other SQL databases supported by SQLAlchemy

## Prompt Engineering
The LLM system prompts are generalised to work with any dataset - howver you may find it beneficial to customise the prompts to your dataset.

Edit the prompts in eihter:
- The `cdk/prompts_stack.py` and redeploy with `cdk deploy` (Recommended)
- The [AWS Console under Bedrock Prompt Management](https://console.aws.amazon.com/bedrock/home#/prompt-management)

## Local Development

1. From the root folder of the project repository, install requirements.
```
pip install -r requirements.txt
```

2. Create a `.env` file in the top level folder. You can find the required environment variables from the CloudFormation Outputs.

```
ATHENA_CONNECTION_STRING="<PASTE_ATHENA_CONNECTION_STRING_HERE>"
BEDROCK_PROMPT_ID_1="ABC123456" 
BEDROCK_PROMPT_ID_2="XYZ123456"
AWS_DEFAULT_REGION="<REGION>"
OAUTH_COGNITO_CLIENT_ID="<CLIEN_ID>"
OAUTH_COGNITO_CLIENT_SECRET ="<CLIENT_SECRET>"
OAUTH_COGNITO_DOMAIN="<COGNITO_DOMAIN>"
CHAINLIT_AUTH_SECRET="<CHAINLIT_SECRET>"
```

3. Run Chainlit App
```
chainlit run -w chainlit-app.py
```

## Architecture
![Architecture](./architecture.png)

### AWS Services:
  - Amazon S3 for data storage
  - AWS Glue for data cataloging and ETL
  - Amazon Athena for querying data lakes
  - Amazon Elastic Container Service (ECS) Fargate for scalable, serverless deployment
  - Amazon Elastic Container Registry (ECR) for registering Docker images
  - Amazon Bedrock for Large Language Model's (LLM) on-demand
  - Application Load Balancer 
  - Amazon CloudFront
  - Amazon Cognito for user management
  - Amazon CloudWatch for logging
  - AWS Identity and Access Management (IAM) for access controls 
  - AWS Secrets Manager 
  - Amazon Virtual Private Cloud (VPC)
  - CDK generated resources:
      - AWS Lambda
  
#### NOTES: 
1. Customers should consider using [AWS WAF](https://aws.amazon.com/waf/) with Amazon CloudFront and their Application Load Balancers (ALB), it is a web application firewall that helps protect web applications from attacks by allowing you to configure rules that allow, block, or monitor (count) web requests.