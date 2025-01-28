import boto3
import chainlit as cl
import os
import uuid
import pytz
from chainlit.input_widget import Switch, Select
from datetime import datetime
from langchain.schema.runnable.config import RunnableConfig
from langchain_aws import ChatBedrock
from langchain_core.messages import SystemMessage
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
from langgraph.prebuilt import create_react_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langgraph.checkpoint.memory import MemorySaver
from utils.message_trimming import modify_state_messages
from utils.token_counter import TokenCounter
from langchain_core.tools import tool
from typing import Dict, Optional


memory = MemorySaver()

# NOTE: currently the datetime is hardcoded to Sydney/Australia timezone. Please change to your own.
# Get current datetime in timezone
TIMEZONE = pytz.timezone("Australia/Sydney")

# Environment Variables
prompt_id_1 = os.environ['BEDROCK_PROMPT_ID_1']  # Data oriented prompt
prompt_id_2 = os.environ['BEDROCK_PROMPT_ID_2']  # Business oriented prompt
connection_string = os.environ['ATHENA_CONNECTION_STRING']
region = os.environ['AWS_REGION_FOR_BEDROCK_INFERENCE']

bedrock_runtime = boto3.client(
    service_name="bedrock-runtime",
    region_name=region
)

bedrock_agent_client = boto3.client(
    service_name="bedrock-agent",
)

QUESTIONS = [
    "How many turbines are in the database and what are their asset ids?",
    "Which of these turbines has had the highest average temperature and what was it?",
    "How was this average temp determined?"
]


@ cl.oauth_callback
def oauth_callback(
    provider_id: str,
    token: str,
    raw_user_data: Dict[str, str],
    default_user: cl.User,
) -> Optional[cl.User]:
    return default_user


@ cl.on_chat_start
async def start():
    thread_id = str(uuid.uuid4())
    cl.user_session.set("thread_id", thread_id)
    cl.user_session.set("token_counter", TokenCounter())

    # Fetch both prompts
    response1 = bedrock_agent_client.get_prompt(
        promptIdentifier=prompt_id_1)  # Data oriented
    response2 = bedrock_agent_client.get_prompt(
        promptIdentifier=prompt_id_2)  # Business oriented

    def get_prompt_text(response):
        default_variant = response['defaultVariant']
        for variant in response['variants']:
            if variant['name'] == default_variant:
                return variant['templateConfiguration']['text']['text']
        return None

    # Store prompts in session using their names from the response
    prompts = {
        response1['name']: get_prompt_text(response1),  # Data oriented
        response2['name']: get_prompt_text(response2)   # Business oriented
    }
    cl.user_session.set("prompts", prompts)

    # Get the business prompt name for default
    business_prompt_name = response2['name']

    # Set default settings using the business prompt
    default_settings = {
        "ShowTokenCount": False,
        "EnableTrimming": True,
        "ModelID": "anthropic.claude-3-5-haiku-20241022-v1:0",
        "EnableFixedQuestions": False,
        "SelectedPrompt": business_prompt_name  # Default to business prompt
    }
    cl.user_session.set("settings", default_settings)

    # Get list of prompt names and find index of business prompt
    prompt_names = list(prompts.keys())
    business_prompt_index = prompt_names.index(business_prompt_name)

    await cl.ChatSettings([
        Select(
            id="SelectedPrompt",
            label="Select Prompt",
            values=prompt_names,
            initial_index=business_prompt_index  # Set initial index to business prompt
        ),
        Switch(id="EnableFixedQuestions",
               label="Enable Fixed Questions", initial=False),
        Select(
            id="ModelID",
            label="Select Model",
            values=["anthropic.claude-3-5-haiku-20241022-v1:0",
                    "anthropic.claude-3-5-sonnet-20241022-v2:0",
                    "anthropic.claude-3-haiku-20240307-v1:0",
                    "anthropic.claude-3-sonnet-20240229-v1:0",
                    "anthropic.claude-3-5-sonnet-20240620-v1:0"],
            initial_index=0
        ),
        Switch(id="ShowTokenCount", label="Show Token Count", initial=False),
        Switch(id="EnableTrimming", label="Enable Message Trimming", initial=True),
    ]).send()

    await setup_agent(default_settings)
    if default_settings["EnableFixedQuestions"]:
        await ask_fixed_question()


async def ask_fixed_question():
    actions = [
        cl.Action(name=f"question_{i}", value=str(i), label=question)
        for i, question in enumerate(QUESTIONS)
    ]

    res = await cl.AskActionMessage(
        content="Please select a question or type your own:",
        actions=actions,
        timeout=5000,
    ).send()

    if res:
        question_index = int(res["value"])
        await process_question(QUESTIONS[question_index])
    else:
        # If no predefined question is selected, assume the user wants to ask their own
        await cl.Message(content="Please type your question:").send()


async def process_question(question):
    message = cl.Message(content=question)
    await on_message(message)


@ cl.on_settings_update
async def on_settings_update(settings):
    cl.user_session.set("settings", settings)
    await setup_agent(settings)

    # if enablefixedquestions is enabled, ask a question
    if settings["EnableFixedQuestions"]:
        await ask_fixed_question()


async def setup_agent(settings):
    cl.user_session.set("show_token_count", settings["ShowTokenCount"])
    cl.user_session.set("enable_trimming", settings["EnableTrimming"])

    model_id = settings["ModelID"]
    selected_prompt = settings["SelectedPrompt"]

    current_datetime = datetime.now(TIMEZONE)

    # Format datetime as string
    formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S %Z")

    # Get Unix epoch time in milliseconds
    epoch_time = int(current_datetime.timestamp() * 1000)

    prompts = cl.user_session.get("prompts")
    system_prompt = prompts[selected_prompt]
    system_message = SystemMessage(
        content=system_prompt.format(
            # Change if not using trino based Athena queries
            dialect="trino",
            current_datetime=formatted_datetime,
            current_epoch=epoch_time
        )
    )
    cl.user_session.set("system_message", system_message)

    # DB Connection and tools
    engine_athena = create_engine(connection_string, echo=False)
    db = SQLDatabase(engine_athena)

    # Model configuration
    model_kwargs = {
        "max_tokens": 4096, "temperature": 0.1,
        "top_k": 250, "top_p": 0.9, "stop_sequences": ["\n\nHuman"],
    }
    model = ChatBedrock(
        client=bedrock_runtime,
        model_id=model_id,
        model_kwargs=model_kwargs,
    )

    toolkit = SQLDatabaseToolkit(db=db, llm=model)
    sql_tools = toolkit.get_tools()

    # Create the epoch conversion tool

    @ tool
    def epoch_to_local(epoch_time: int):
        """Use this to convert Unix epoch time (in milliseconds) to local time."""
        try:
            # Convert milliseconds to seconds
            epoch_seconds = epoch_time / 1000
            local_time = datetime.fromtimestamp(epoch_seconds, TIMEZONE)
            return f"The local time for epoch {epoch_time} (milliseconds) in {TIMEZONE} is {local_time}"
        except ValueError:
            return "Invalid epoch time provided. Please provide a valid integer representing milliseconds since the Unix epoch."

    tools = sql_tools + [epoch_to_local]

    def state_modifier(state):
        return modify_state_messages(state, model, cl.user_session.get("system_message"))

    agent_executor = create_react_agent(
        model,
        tools,
        state_modifier=state_modifier,
        checkpointer=memory
    )

    cl.user_session.set("runnable", agent_executor)


@ cl.on_message
async def on_message(message: cl.Message):
    agent_executor = cl.user_session.get("runnable")
    thread_id = cl.user_session.get("thread_id")
    token_counter = cl.user_session.get("token_counter")

    async for chunk in agent_executor.astream(
        {"messages": [("human", message.content)]},
        config=RunnableConfig(callbacks=[cl.LangchainCallbackHandler()], recursion_limit=50, configurable={
            "thread_id": thread_id,
            "enable_trimming": cl.user_session.get("enable_trimming", True),
        }),
    ):
        if isinstance(chunk, dict) and 'agent' in chunk:
            final_result = chunk
            usage = chunk['agent']['messages'][-1].additional_kwargs.get(
                'usage', {})
            token_counter.update_tokens(usage)

    await cl.Message(content=final_result['agent']['messages'][-1].content).send()

    if cl.user_session.get("show_token_count"):
        await cl.Message(
            content=token_counter.get_token_usage_content(),
            author="System (Token Usage)"
        ).send()

    if cl.user_session.get("settings")["EnableFixedQuestions"]:
        await ask_fixed_question()  # Ask for the next question only if enabled

if __name__ == "__main__":
    cl.run()
