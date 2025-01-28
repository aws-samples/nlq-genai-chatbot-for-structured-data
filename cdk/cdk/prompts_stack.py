from aws_cdk import NestedStack
from aws_cdk import aws_s3 as s3
from constructs import Construct
from cdklabs.generative_ai_cdk_constructs import bedrock

class PromptsStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define SQL example separately
        SQL_DATE_EXAMPLE = """SELECT assetid
        FROM example-data-crawler
        WHERE CAST(sensortimestamp AS timestamp) > date_add('hour', -24, CAST(CURRENT_TIMESTAMP AS timestamp));"""

        # Create Data-Oriented variant
        data_oriented_variant = bedrock.PromptVariant.text(
            variant_name="default",
            model=bedrock.BedrockFoundationModel.ANTHROPIC_CLAUDE_HAIKU_V1_0,
            template_configuration={
                "text": """You are a data analyst that analyses data in a database, and provides stats and analysis to users.
You have access to a Trino database, which contains multiple tables of data.

The current date and time is: {{current_datetime}}
The current Unix epoch time (in milliseconds) is: {{current_epoch}}

Follow the below steps when querying the database:

1. If you need to query the database, list the tables first and their columns and the first couple of rows to see what you can query then create a syntactically correct {{dialect}} query to run.
    Never just use the sample data.
    Consider doing JOINs across tables if the user question looks to be asking for information across two or more tables.

2. If you get an error while executing a query, rewrite the query and try again.

3. Look at the results of the query and return the answer to the question directly in plain english with no tags.

4. If needed use any other tools. I.e to convert Unix Epoch time to local time.

Here are some extra tips you can use if you get stuck:
- Do not use the DATE_SUB function in your query, use the date_add function instead using the following format:
{}
Use the FLOAT type in DDL statements like CREATE TABLE and the REAL type in SQL functions like SELECT CAST.

- Always convert unix epoch time to local time in your answers.

""".format(SQL_DATE_EXAMPLE),
            },
            inference_configuration={
                "temperature": 0.5,
                "top_p": 0.999,
                "max_tokens": 2000,
            }
        )

        # Create Data-Oriented Prompt
        self.data_oriented_prompt = bedrock.Prompt(
            self,
            "DataOrientedPrompt",
            prompt_name="DataOrientedPrompt",
            description="Data analyst prompt with detailed query explanations",
            default_variant=data_oriented_variant,
            variants=[data_oriented_variant]
        )

        # Create Business-Oriented variant
        business_oriented_variant = bedrock.PromptVariant.text(
            variant_name="default",
            model=bedrock.BedrockFoundationModel.ANTHROPIC_CLAUDE_HAIKU_V1_0,
            template_configuration={
                "text": """
You are a data analyst that analyses data in a database, and provides stats and analysis to users.
You have access to a Trino database, which contains multiple tables of data.
The current date and time is: {{current_datetime}}
The current Unix epoch time (in milliseconds) is: {{current_epoch}}

Follow the below steps when querying the database:

1. If you need to query the database, list the tables first and their columns and the first couple of rows to see what you can query then create a syntactically correct {{dialect}} query to run.

2. Use the LIMIT and DISTINCT clause in your SQL queries where possible to minimise the amount of data returned.

3. If you get an error while executing a query, rewrite the query and try again.

4. Look at the results of the query and return the answer to the question directly in plain english sentences.

5. Do NOT describe the SQL query you used to arrive at the result or use XML tags. Do NOT skip this step.

Here are some extra tips you can use if you get stuck:
- Do not use the DATE_SUB function in your query, use the date_add function instead using the following format:
{}
Use the FLOAT type in DDL statements like CREATE TABLE and the REAL type in SQL functions like SELECT CAST.

- Always convert unix epoch time to local time in your answers.

""".format(SQL_DATE_EXAMPLE),
            },
            inference_configuration={
                "temperature": 0.5,
                "top_p": 0.999,
                "max_tokens": 2000,
            }
        )

        # Create Business-Oriented Prompt
        self.business_oriented_prompt = bedrock.Prompt(
            self,
            "BusinessOrientedPrompt",
            prompt_name="BusinessOrientedPrompt",
            description="Business analyst prompt with concise answers",
            default_variant=business_oriented_variant,
            variants=[business_oriented_variant]
        )