from __future__ import annotations

from langgraph.types import interrupt

from app.graph.state import ChatState


def human_approval_node(state: ChatState):
    """
    Pause the graph and ask the user whether web search
    should be performed.

    This node is triggered when CRAG determines that the
    uploaded documents do not contain enough information
    to answer the question.
    """

    print("\n" + "=" * 80)
    print("[HITL]")
    print("=" * 80)

    # --------------------------------------------------------
    # Get the original user question
    # --------------------------------------------------------

    messages = state.get("messages", [])

    user_question = ""

    for message in reversed(messages):

        # HumanMessage has a type of "human"
        if getattr(message, "type", None) == "human":
            user_question = message.content
            break

    # --------------------------------------------------------
    # Get CRAG result
    # --------------------------------------------------------

    rag_grade = state.get(
        "rag_grade",
        "IRRELEVANT"
    )

    print(
        f"[HITL] CRAG grade: {rag_grade}"
    )

    print(
        f"[HITL] Question: {user_question}"
    )

    # --------------------------------------------------------
    # Pause the graph
    # --------------------------------------------------------

    decision = interrupt(
        {
            "type": "human_approval",

            "message": (
                "I couldn't find enough information "
                "to answer this question from your "
                "uploaded documents."
            ),

            "question": user_question,

            "rag_grade": rag_grade,

            "options": {
                "yes": "Search the web",
                "no": "Don't search the web",
            },
        }
    )

    # --------------------------------------------------------
    # Graph resumes here after user responds
    # --------------------------------------------------------

    print(
        f"[HITL] User decision: {decision}"
    )

    return {
        "hitl_decision": decision
    }