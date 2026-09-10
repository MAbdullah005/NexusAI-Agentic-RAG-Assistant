from app.graph.state import ChatState
from langchain_core.messages import SystemMessage
from app.llm.llm_config import llm
from app.prompts.rag import RAG_FINAL_ANSWER_PROMPT
def final_answer_node(state: ChatState, config=None):
    """
    Generate the final answer after RAG retrieval.

    This node uses the normal LLM WITHOUT tools,
    so the model cannot call unified_rag_tool again.
    """

    messages = []

    summary = state.get("summary", "")

    if summary:

        messages.append(
            SystemMessage(
                content=f"""
Conversation summary from earlier messages:

{summary}
"""
            )
        )

    messages.append(
        SystemMessage(
            content=RAG_FINAL_ANSWER_PROMPT
        )
    )


    messages.extend(
        state.get("messages", [])
    )

    print("\n" + "=" * 80)
    print("[FINAL ANSWER NODE]")
    print("Generating final answer from RAG context")
    print("=" * 80)

    response = llm.invoke(
        messages,
        config=config
    )

    return {
        "messages": [response]
    }