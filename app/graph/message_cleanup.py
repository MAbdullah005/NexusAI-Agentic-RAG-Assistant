from __future__ import annotations

from typing import List

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    BaseMessage,
)

from app.graph.state import ChatState


def _is_persistable_message(message: BaseMessage) -> bool:
    """
    Persist only normal conversation messages.

    Keep:
        HumanMessage
        AIMessage without tool calls

    Remove:
        ToolMessage
        AI tool-call messages
        SystemMessage
        other internal workflow messages
    """

    # --------------------------------------------------------
    # User message
    # --------------------------------------------------------

    if isinstance(message, HumanMessage):
        return True

    # --------------------------------------------------------
    # Assistant message
    # --------------------------------------------------------

    if isinstance(message, AIMessage):

        tool_calls = getattr(
            message,
            "tool_calls",
            None
        )

        invalid_tool_calls = getattr(
            message,
            "invalid_tool_calls",
            None
        )

        additional_kwargs = getattr(
            message,
            "additional_kwargs",
            {}
        )

        function_call = additional_kwargs.get(
            "function_call"
        )

        # AI message that exists only to request a tool
        if tool_calls:
            return False

        if invalid_tool_calls:
            return False

        if function_call:
            return False

        return True

    # --------------------------------------------------------
    # Everything else is internal
    # --------------------------------------------------------

    return False


def cleanup_messages(state: ChatState,config=None):
    """
    Remove internal tool/retrieval/HITL workflow messages
    from persisted conversation history.

    Final state should contain only:

        HumanMessage
        AIMessage
    """

    messages = state.get(
        "messages",
        []
    )

    remove_messages: List[RemoveMessage] = []

    for message in messages:

        if not _is_persistable_message(message):

            if getattr(message, "id", None):

                remove_messages.append(
                    RemoveMessage(
                        id=message.id
                    )
                )

    print("\n" + "=" * 80)
    print("[MESSAGE CLEANUP]")
    print("=" * 80)

    print(
        f"[CLEANUP] Total messages: {len(messages)}"
    )

    print(
        f"[CLEANUP] Removing internal messages: "
        f"{len(remove_messages)}"
    )

    return {
        "messages": remove_messages,

        # Clear workflow-only fields after a completed turn.
        "rag_grade": "",
        "hitl_decision": "",
        "answer_source": "",
    }