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
    HumanMessage,
    AIMessage,
)

from app.graph.state import ChatState

from app.prompts.chat import CHAT_SYSTEM_PROMPT

from app.graph.tool_node import llm_with_tools

from app.core.retriever import thread_document_metadata
from app.memory.postgres_memory import checkpointer, get_thread_summary
from app.db.connection_adapter import get_db_connection
from app.utils.logger import logger


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
    user_id = None

    if config and isinstance(config, dict):
        configurable = config.get("configurable", {})
        thread_id = configurable.get("thread_id")
        user_id = configurable.get("user_id")

    # If user_id not explicitly in config, look up the authentic thread owner
    if not user_id and thread_id:
        try:
            with get_db_connection() as _conn:
                cursor = _conn.cursor()
                cursor.execute("SELECT user_id FROM threads WHERE thread_id = ?", (thread_id,))
                row = cursor.fetchone()
            if row:
                user_id = row[0]
        except Exception as e:
            logger.warning(f"Could not resolve user_id for thread '{thread_id}': {e}")

    summary = state.get("summary", "")
    if not summary and thread_id:
        summary = get_thread_summary(thread_id, user_id=user_id) or ""

    if summary:
       messages1.append(
          SystemMessage(
              content=f"""Conversation summary from earlier messages:

{summary}"""
          )
        )

    # Identify user query and active message IDs/contents to exclude from historical retrieval
    user_query = ""
    exclude_message_ids = set()
    exclude_contents = set()
    for msg in state.get("messages", []):
        mid = getattr(msg, "id", None)
        if mid:
            exclude_message_ids.add(str(mid))
        role = None
        if isinstance(msg, HumanMessage) or getattr(msg, "type", None) == "human":
            role = "user"
            raw = getattr(msg, "content", "")
            if isinstance(raw, str):
                user_query = raw
            elif isinstance(raw, list):
                user_query = " ".join([b.get("text", "") if isinstance(b, dict) else str(b) for b in raw])
            else:
                user_query = str(raw)
        elif isinstance(msg, AIMessage) or getattr(msg, "type", None) == "ai":
            role = "assistant"

        if role:
            raw = getattr(msg, "content", "")
            if isinstance(raw, str):
                c_str = raw
            elif isinstance(raw, list):
                c_str = " ".join([b.get("text", "") if isinstance(b, dict) else str(b) for b in raw])
            else:
                c_str = str(raw)
            exclude_contents.add((role, c_str))

    # Retrieve relevant historical messages from SQLite (if enabled)
    if thread_id and user_id and user_query:
        try:
            from app.memory.historical_retriever import (
                retrieve_historical_context,
                format_historical_context,
            )
            hist_messages = retrieve_historical_context(
                query=user_query,
                thread_id=thread_id,
                user_id=user_id,
                exclude_message_ids=exclude_message_ids,
                exclude_contents=exclude_contents,
            )
            if hist_messages:
                hist_text = format_historical_context(hist_messages)
                if hist_text:
                    messages1.append(SystemMessage(content=hist_text))
        except Exception as e:
            logger.warning(f"Historical context retrieval failed in chat_node: {e}")

    # Avoid injecting duplicate summary or historical context system messages if already present in state
    clean_state_messages = [
        msg for msg in state.get("messages", [])
        if not (
            isinstance(msg, SystemMessage)
            and (
                "Conversation summary from earlier messages" in getattr(msg, "content", "")
                or "Relevant earlier conversation context" in getattr(msg, "content", "")
            )
        )
    ]
    messages1.extend(
        clean_state_messages
    )

    last_message = (
        state["messages"][-1]
        if state["messages"]
        else None
    )
    configurable = config.get("configurable", {}) if config and isinstance(config, dict) else {}
    selected_doc_ids = configurable.get("selected_doc_ids")
    raw_metadata = thread_document_metadata(
        thread_id=thread_id,
        selected_doc_ids=selected_doc_ids
    )

    sources_list = raw_metadata.get("sources", []) if isinstance(raw_metadata, dict) else []
    if sources_list:
        docs_lines = [
            f"- [{s.get('type', 'document').upper()}] {s.get('name', 'Untitled')} (ID: {s.get('doc_id')})"
            for s in sources_list
        ]
        metadata_str = (
            f"Total attached documents: {len(sources_list)}\n"
            + "\n".join(docs_lines)
            + "\n\nCRITICAL INSTRUCTION: The user has attached the above sources to this conversation thread. "
            "When the user asks any question about them, you MUST call `unified_rag_tool` to retrieve the relevant content before answering. "
            "NEVER claim that you cannot access them or that no document is attached."
        )
    else:
        metadata_str = "No documents currently attached to this thread."

    system_message = SystemMessage(
        content=CHAT_SYSTEM_PROMPT.format(
            metadata=metadata_str,
            thread_id=thread_id or "unknown",
        )
    )

    messages = [
        system_message,
        *messages1
    ]

    logger.info(f"[CHAT NODE] Calling LLM with {len(messages)} messages (thread_id={thread_id})")

    response = llm_with_tools.invoke(
        messages,
        config=config
    )

    logger.info(f"[CHAT NODE] LLM with tools responded: type={type(response)}")

    return {
        "messages": [response]
    }




