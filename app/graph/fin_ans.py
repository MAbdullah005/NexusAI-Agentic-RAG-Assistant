from __future__ import annotations

from app.graph.state import ChatState
from app.llm.llm_config import llm

from app.prompts.rag import (
    RAG_FINAL_ANSWER_PROMPT,
    WEB_FINAL_ANSWER_PROMPT,
)

from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    ToolMessage,
)


def final_answer_node(
    state: ChatState,
    config=None
):

    source = state.get(
        "answer_source",
        "rag"
    )

    print("\n" + "=" * 80)
    print("[FINAL ANSWER NODE]")
    print(f"[FINAL ANSWER] Source: {source}")
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
    # SYSTEM PROMPT
    # ========================================================

    if source == "web":

        messages.append(
            SystemMessage(
                content=WEB_FINAL_ANSWER_PROMPT
            )
        )

    else:

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
    # ONLY ADD RELEVANT TOOL RESULT
    # ========================================================

    relevant_tool_message = None

    for message in reversed(
        state.get("messages", [])
    ):

        if isinstance(
            message,
            ToolMessage
        ):

            if source == "web":

                if (
                    message.name
                    == "web_search"
                ):

                    relevant_tool_message = message
                    break

            else:

                if (
                    message.name
                    == "unified_rag_tool"
                ):

                    relevant_tool_message = message
                    break

    if relevant_tool_message:

        messages.append(
            relevant_tool_message
        )

    # ========================================================
    # GENERATE ANSWER
    # ========================================================

    print("Here is the final message go to LLM after ",source," this is final NODE ANSWER \n /n ",messages, " \n /n")

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