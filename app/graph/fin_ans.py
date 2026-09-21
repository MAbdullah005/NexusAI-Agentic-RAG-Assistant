from __future__ import annotations

from app.graph.state import ChatState
from app.llm.llm_config import llm
from app.prompts.rag import RAG_FINAL_ANSWER_PROMPT

from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    ToolMessage,
)


def final_answer_node(
    state: ChatState,
    config=None
):

    print("\n" + "=" * 80)
    print("[FINAL ANSWER NODE]")
    print("[FINAL ANSWER] Source: RAG")
    print("=" * 80)

    messages = []

    # ========================================================
    # SUMMARY
    # ========================================================

    summary = state.get(
        "summary",
        ""
    )

    if summary:

        messages.append(
            SystemMessage(
                content=f"""
Conversation summary from earlier messages:

{summary}
"""
            )
        )

    # ========================================================
    # RAG SYSTEM PROMPT
    # ========================================================

    messages.append(
        SystemMessage(
            content=RAG_FINAL_ANSWER_PROMPT
        )
    )

    # ========================================================
    # CURRENT USER QUESTION
    # ========================================================

    user_message = None

    for message in reversed(
        state.get("messages", [])
    ):

        if isinstance(
            message,
            HumanMessage
        ):

            user_message = message
            break

    if user_message:

        messages.append(
            user_message
        )

    # ========================================================
    # ONLY RAG TOOL RESULT
    # ========================================================

    for message in reversed(
        state.get("messages", [])
    ):

        if isinstance(
            message,
            ToolMessage
        ):

            if message.name == "unified_rag_tool":

                messages.append(
                    message
                )

                break

    # ========================================================
    # FINAL LLM CALL
    # ========================================================

    print(
        "[FINAL ANSWER] Sending RAG context to LLM"
    )

    response = llm.invoke(
        messages,
        config=config
    )

    print(
        "[FINAL ANSWER] Response generated"
    )

    return {
        "messages": [response]
    }