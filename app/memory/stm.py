from app.graph.state import ChatState

from langchain_core.messages import (
    HumanMessage,
    ToolMessage,
    SystemMessage,
)
from app.prompts.mem import MEMORY_INITIAL_PROMPT,MEMORY_UPDATE_PROMPT

from langchain_core.messages import RemoveMessage

from app.llm.llm_config import llm


KEEP_RECENT_MESSAGES = 4


def summarize_memory(state: ChatState):

    """
    Summarize older conversation messages and remove them
    from the active LangGraph state.

    The summary remains in state["summary"].
    """

    messages = state.get("messages", [])

    existing_summary = state.get("summary", "")

    print("\n" + "=" * 80)
    print("[MEMORY] SUMMARIZATION STARTED")
    print("=" * 80)

    print(
        f"[MEMORY] Total messages: {len(messages)}"
    )

    if existing_summary:

       prompt = MEMORY_UPDATE_PROMPT.format(
         existing_summary=existing_summary
        )

    else:

       prompt = MEMORY_INITIAL_PROMPT


    messages_for_summary = []

    for message in messages:

        # Skip raw tool output
        if isinstance(message, ToolMessage):

            continue

        messages_for_summary.append(message)



    messages_for_summary.append(
        HumanMessage(
            content=prompt
        )
    )



    response = llm.invoke(
        messages_for_summary
    )

    print("\n" + "-" * 80)
    print("[MEMORY] NEW SUMMARY")
    print(response.content)
    print("-" * 80)


    messages_to_delete = messages[
        :-KEEP_RECENT_MESSAGES
    ]

    print(
        f"[MEMORY] Messages deleted: "
        f"{len(messages_to_delete)}"
    )

    print(
        f"[MEMORY] Messages kept: "
        f"{KEEP_RECENT_MESSAGES}"
    )

    print("=" * 80 + "\n")


    return {

        "summary": response.content,

        "messages": [
            RemoveMessage(id=message.id)
            for message in messages_to_delete
        ]
    }