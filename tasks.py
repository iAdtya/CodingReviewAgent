from celery import Celery
from langchain.prompts import PromptTemplate
from langchain_openai import OpenAI
from pydantic import SecretStr
from dotenv import load_dotenv
import os
import json

load_dotenv()

api_key_str = os.getenv("OPENAI_API_KEY")
api_key: SecretStr | None = SecretStr(api_key_str) if api_key_str else None

app = Celery("tasks", backend="rpc://", broker="pyamqp://")


@app.task
def review_code(context: str):
    llm = OpenAI(api_key=api_key)
    prompt_template = """
    You are a coding assistant which reviews the code submitted in the pull requests and analyses that code and suggests if it was a good code, and how it could be made better:

    Context: {context}

    Only return the helpful answer. Answer must be detailed and well explained.
    Helpful answer:
    """
    # Create a prompt using the template
    prompt = PromptTemplate(
        input_variables=["context"],
        template=prompt_template,
    )

    answer = llm(prompt.format(context=context))
    return json.dumps({"review": answer})