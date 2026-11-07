from __future__ import annotations

import re
from app.graph.state import ChatState
from app.llm.llm_config import llm
from app.prompts.rag import CRAG_RELEVANCE_PROMPT

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from app.utils.logger import get_logger

logger = get_logger(__name__)


def crag_relevance_grader(state: ChatState):
    """
    Evaluate whether the retrieved RAG context is relevant
    to the user's question, with full awareness of recent conversation context.
    """

    messages = state.get("messages", [])

    if not messages:
        return {
            "rag_grade": "IRRELEVANT"
        }

    # ---------------------------------------------------------
    # Find the latest user question
    # ---------------------------------------------------------

    user_question = None

    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            user_question = message.content
            break

    # ---------------------------------------------------------
    # Find the latest RAG result
    # ---------------------------------------------------------

    rag_result = None

    for message in reversed(messages):
        if isinstance(message, ToolMessage):
            if message.name == "unified_rag_tool":
                rag_result = message.content
                break

    rag_str = str(rag_result or "").strip()
    if not user_question or not rag_str or rag_str.startswith("⚠️") or rag_str.startswith("❌"):
        logger.info("[CRAG GRADER] Empty or error RAG result -> early return IRRELEVANT")
        return {
            "rag_grade": "IRRELEVANT"
        }

    # ---------------------------------------------------------
    # Extract recent conversation turns for coreference resolution
    # ---------------------------------------------------------
    context_turns = []
    conv_history = [
        m for m in messages
        if isinstance(m, (HumanMessage, AIMessage)) and not getattr(m, "tool_calls", None)
    ]
    # Include up to last 4 conversation messages before the current question
    for m in conv_history[-4:-1]:
        role = "User" if isinstance(m, HumanMessage) else "Assistant"
        raw_c = getattr(m, "content", "")
        c_text = raw_c if isinstance(raw_c, str) else str(raw_c)
        if c_text.strip():
            context_turns.append(f"{role}: {c_text[:160].strip()}")
    context_str = "\n".join(context_turns) if context_turns else "None (first turn)"

    # ---------------------------------------------------------
    # Build grader prompt
    # ---------------------------------------------------------

    grader_prompt = f"""
{CRAG_RELEVANCE_PROMPT}

CONVERSATION CONTEXT (use this to resolve pronouns like 'it', 'they', 'this', or follow-up references):
{context_str}

USER QUESTION:
{user_question}

RETRIEVED CONTEXT:
{rag_result}
"""

    logger.info(f"[CRAG GRADER] Evaluating retrieved context for user question: {user_question[:80]}")

    # ---------------------------------------------------------
    # Call LLM WITHOUT tools
    # ---------------------------------------------------------

    response = llm.invoke(
        [
            HumanMessage(
                content=grader_prompt
            )
        ]
    )

    raw_content = ""
    if isinstance(response.content, str):
        raw_content = response.content
    elif isinstance(response.content, list):
        for block in response.content:
            if isinstance(block, dict) and "text" in block:
                raw_content += block["text"] + " "
            elif isinstance(block, str):
                raw_content += block + " "
    else:
        raw_content = str(response.content)

    logger.info(f"[CRAG] Raw LLM response: {repr(raw_content)}")

    cleaned = raw_content.strip().upper()
    if re.search(r"\bGOOD\b", cleaned):
        grade = "GOOD"
    elif re.search(r"\bPARTIAL\b", cleaned):
        grade = "PARTIAL"
    elif re.search(r"\bIRRELEVANT\b", cleaned):
        grade = "IRRELEVANT"
    elif "GOOD" in cleaned:
        grade = "GOOD"
    elif "PARTIAL" in cleaned:
        grade = "PARTIAL"
    else:
        grade = "IRRELEVANT"

    logger.info(f"[CRAG] Evaluation complete -> Grade: {grade}")
    print(f"[CRAG] Grade: {grade}")
    print("=" * 80)

    return {
        "rag_grade": grade
    }
