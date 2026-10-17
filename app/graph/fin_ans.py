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
                content=f"""Conversation summary from earlier messages:

{summary}"""
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
    # EXTRACT USER QUESTION & RAG TOOL CONTEXT
    # ========================================================

    user_query = ""
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            raw = getattr(message, "content", "")
            if isinstance(raw, str):
                user_query = raw
            elif isinstance(raw, list):
                user_query = " ".join([b.get("text", "") if isinstance(b, dict) else str(b) for b in raw])
            else:
                user_query = str(raw)
            break

    rag_content = ""
    for message in reversed(state.get("messages", [])):
        if isinstance(message, ToolMessage) and message.name == "unified_rag_tool":
            rag_content = getattr(message, "content", "")
            break

    # Format retrieved context and question into a clean, properly structured human message
    prompt_payload = f"""RETRIEVED SOURCE CONTEXT:
{rag_content if rag_content else 'No context retrieved from sources.'}

USER QUESTION:
{user_query}

INSTRUCTIONS:
1. Ground your answer strictly in the retrieved source context above.
2. If the context does not contain enough information to answer the question, clearly state: "The provided sources do not contain enough information to answer this question."
3. Cite sources directly inline where relevant using these exact formats:
   - For PDF documents: [Document: filename.pdf, Page: X]
   - For YouTube videos: [YouTube: URL, Timestamp: MM:SS]
   - For Web articles: [Source: URL, Title: title]
4. At the end of your response, include a brief "Sources & References" section listing all cited materials.
5. Do not speculate or use ungrounded external assumptions for document-specific claims."""

    messages.append(HumanMessage(content=prompt_payload))

    # ========================================================
    # FINAL LLM CALL
    # ========================================================

    print(
        f" ---------- [FINAL ANSWER] Invoking LLM with grounded RAG context ----------- "
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