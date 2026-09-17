from __future__ import annotations

from app.graph.state import ChatState
from app.llm.llm_config import llm
from app.prompts.rag import CRAG_RELEVANCE_PROMPT

from langchain_core.messages import HumanMessage, ToolMessage


def crag_relevance_grader(state: ChatState):
    """
    Evaluate whether the retrieved RAG context is relevant
    to the user's question.
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

    if not user_question or not rag_result:
        return {
            "rag_grade": "IRRELEVANT"
        }

    # ---------------------------------------------------------
    # Build grader prompt
    # ---------------------------------------------------------

    grader_prompt = f"""
{CRAG_RELEVANCE_PROMPT}

USER QUESTION:
{user_question}

RETRIEVED CONTEXT:
{rag_result}
"""

    print("\n" + "=" * 80)
    print("[CRAG GRADER]")
    print("=" * 80)

    print("[CRAG] User question:")
    print(user_question)

    print("\n[CRAG] Evaluating retrieved context...")

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

    grade = response.content.strip().upper()

    if grade.startswith("GOOD"):
      grade = "GOOD"

    elif grade.startswith("PARTIAL"):
      grade = "PARTIAL"

    elif grade.startswith("IRRELEVANT"):
      grade = "IRRELEVANT"

    else:
      grade = "IRRELEVANT"

    print(f"[CRAG] Grade: {grade}")
    print("=" * 80)

    return {
        "rag_grade": grade
    }