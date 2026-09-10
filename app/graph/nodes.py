from __future__ import annotations

import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../..")
    )
)

from langchain_core.messages import (
    ToolMessage,
    SystemMessage,
)

from app.graph.state import ChatState
from app.llm.llm_config import llm

from app.tools.python_executor import python_executor
from app.tools.calculator_tool import calculator
from app.prompts.chat import CHAT_SYSTEM_PROMPT
from app.tools.unified_rag_tool import unified_rag_tool
from app.tools.search_tool import search_tool
from app.tools.stock_tool import get_stock_price
from langchain_core.messages.utils import trim_messages,count_tokens_approximately

from app.core.retriever import thread_document_metadata
from app.memory.sqlite_memory import checkpointer
from app.utils.logger import logger

from langgraph.prebuilt import ToolNode

MAX_TOKEN=500


def chat_node(state: ChatState, config=None):
    messages1=[]
    """
    Main LLM node.

    First pass:
        LLM can decide whether a tool is required.

    After unified_rag_tool:
        Do NOT call tools again.
        Generate the final answer using the normal LLM.
    """

    thread_id = None

    if config and isinstance(config, dict):
        thread_id = (
            config
            .get("configurable", {})
            .get("thread_id")
        )


    summary = state.get("summary", "")

    if summary:
       messages1.append(
          SystemMessage(
              content=f"""
        Conversation summary from earlier messages:

        {summary}
          """
          )
        )

    messages1.extend(
     state.get("messages", [])
    )

    last_message = (
        state["messages"][-1]
        if state["messages"]
        else None
    )

    print("\n"+"="*80)
    print("[CHAT NODE]")
    print("=" * 80)

    print("Thread ID:", thread_id)
    print("Last message:", last_message)
    print("\n"+"="*80)
    print("Here is all messages from start to end ",*state["messages"])
    print("\n"+"="*80)


    metadata = thread_document_metadata(
        thread_id=thread_id
    )



    system_message = SystemMessage(
        content=CHAT_SYSTEM_PROMPT.format(
          metadata=metadata,
          thread_id=thread_id,
        )   
          )


    messages = [
        system_message,
        *messages1
    ]

    print(
        "[CHAT NODE] Calling LLM with tools."
    )
    print("\n ================================================================================")
    print("Here is the messagees that given to LLM tool node ",messages)
    print("\n ================================================================================")


    response = llm_with_tools.invoke(
        messages,
        config=config
    )

    print(
        "[CHAT NODE] LLM with tools  response:",
        response
    )

    return {
        "messages": [response]
    }


tools = [
    search_tool,
    get_stock_price,
    calculator,
    unified_rag_tool,
    python_executor,
]



llm_with_tools = llm.bind_tools(tools)


tool_node = ToolNode(tools)