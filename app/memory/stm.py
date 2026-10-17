from __future__ import annotations

from app.graph.state import ChatState
from app.llm.llm_config import llm
from app.prompts.mem import (
    MEMORY_INITIAL_PROMPT,
    MEMORY_UPDATE_PROMPT,
)
from app.memory.config import get_recent_message_window
from app.memory.sqlite_memory import save_thread_summary, get_thread_summary
from app.utils.logger import get_logger

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
)

logger = get_logger(__name__)


def is_conversation_message(message) -> bool:
    """
    Only these messages belong to user-facing conversation history:

    KEEP:
        HumanMessage
        AIMessage containing a normal final answer

    REMOVE/IGNORE:
        ToolMessage
        AI tool-call AIMessage
        SystemMessage
        other internal messages
    """

    # --------------------------------------------------------
    # USER MESSAGE
    # --------------------------------------------------------

    if isinstance(message, HumanMessage):
        return True

    # --------------------------------------------------------
    # ASSISTANT MESSAGE
    # --------------------------------------------------------

    if isinstance(message, AIMessage):

        # AI message that requested a tool
        if getattr(message, "tool_calls", None):
            return False

        # Invalid tool call
        if getattr(message, "invalid_tool_calls", None):
            return False

        # Some providers store function calls here
        additional_kwargs = getattr(
            message,
            "additional_kwargs",
            {}
        )

        if additional_kwargs.get("function_call"):
            return False

        # Normal final assistant response
        return True

    # --------------------------------------------------------
    # SYSTEM / TOOL / OTHER INTERNAL MESSAGE
    # --------------------------------------------------------

    return False


def summarize_memory(state: ChatState, config=None):
    thread_id = None
    if config and isinstance(config, dict):
        thread_id = (
            config
            .get("configurable", {})
            .get("thread_id")
        )

    messages = state.get(
        "messages",
        []
    )

    existing_summary = state.get(
        "summary",
        ""
    )
    if not existing_summary and thread_id:
        existing_summary = get_thread_summary(thread_id) or ""

    keep_recent = get_recent_message_window()

    print("\n" + "=" * 80)
    print("[MEMORY] SUMMARIZATION STARTED")
    print("=" * 80)

    print(
        f"[MEMORY] Raw graph messages: {len(messages)}"
    )

    # ========================================================
    # EXTRACT ONLY REAL CONVERSATION MESSAGES
    # ========================================================

    conversation_messages = [
        message
        for message in messages
        if is_conversation_message(message)
    ]

    print(
        f"[MEMORY] Conversation messages: "
        f"{len(conversation_messages)}"
    )

    # Nothing to summarize
    if len(conversation_messages) <= keep_recent:

        print(
            f"[MEMORY] Conversation messages ({len(conversation_messages)}) "
            f"<= keep_recent ({keep_recent}); skipping summarization."
        )

        return {}

    # ========================================================
    # SPLIT OLD VS RECENT
    # ========================================================

    old_messages = conversation_messages[
        :-keep_recent
    ]

    recent_messages = conversation_messages[
        -keep_recent:
    ]

    print(
        f"[MEMORY] Messages going into summary: "
        f"{len(old_messages)}"
    )

    print(
        f"[MEMORY] Recent messages being kept: "
        f"{len(recent_messages)}"
    )

    # ========================================================
    # BUILD SUMMARY INPUT
    # ========================================================

    summary_messages = []

    if existing_summary:

        summary_prompt = (
            MEMORY_UPDATE_PROMPT.format(
                existing_summary=existing_summary
            )
        )

    else:

        summary_prompt = MEMORY_INITIAL_PROMPT

    summary_messages.append(
        SystemMessage(
            content=summary_prompt
        )
    )

    # Only old real conversation messages
    summary_messages.extend(
        old_messages
    )

    # ========================================================
    # GENERATE SUMMARY WITH RECOVERY ON FAILURE
    # ========================================================

    try:
        response = llm.invoke(
            summary_messages
        )
        new_summary = response.content if hasattr(response, "content") else str(response)

        # Persist summary to SQLite
        if thread_id and new_summary:
            save_thread_summary(thread_id, new_summary)
            logger.info(f"[MEMORY] Persisted summary for thread {thread_id} in SQLite")

    except Exception as e:
        logger.error(f"[MEMORY] Summary generation failed: {e}. Preserving previous summary.")
        print(f"[MEMORY] Summary generation failed: {e}. Preserving previous summary.")
        # Return previous valid summary without deleting active messages
        return {
            "summary": existing_summary
        }

    print("\n" + "-" * 80)
    print("[MEMORY] NEW SUMMARY")
    print(new_summary)
    print("-" * 80)

    # ========================================================
    # KEEP ONLY THE CONFIGURED RECENT CONVERSATION MESSAGES
    # REMOVE EVERYTHING ELSE FROM ACTIVE GRAPH STATE
    # ========================================================

    recent_ids = {
        message.id
        for message in recent_messages
        if getattr(message, "id", None)
    }

    messages_to_delete = []

    for message in messages:

        message_id = getattr(
            message,
            "id",
            None
        )

        if message_id and message_id not in recent_ids:

            messages_to_delete.append(
                RemoveMessage(
                    id=message_id
                )
            )

    print(
        f"[MEMORY] Messages removed from graph state: "
        f"{len(messages_to_delete)}"
    )

    print(
        "[MEMORY] Messages remaining as active history: "
        f"{keep_recent}"
    )

    print("=" * 80 + "\n")

    return {
        "summary": new_summary,
        "messages": messages_to_delete,
    }