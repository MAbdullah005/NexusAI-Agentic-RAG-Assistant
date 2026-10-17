from __future__ import annotations


from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition

from app.graph.state import ChatState

from app.graph.nodes import chat_node
from app.graph.tool_node import tool_node
from app.graph.not_found import not_found_answer_node
from app.graph.web_serach import web_search_node
from app.graph.message_cleanup import cleanup_messages
from app.graph.fin_ans import final_answer_node
from app.graph.crag_grader import crag_relevance_grader
from app.graph.hitl import human_approval_node

from langchain_core.messages import ToolMessage

from app.memory.sqlite_memory import checkpointer
from app.memory.stm import summarize_memory

from app.utils.logger import get_logger


from app.memory.config import get_summarization_threshold

logger = get_logger(__name__)


def should_summarize(state: ChatState):
    """
    Decide whether conversation memory should be summarized based on configured threshold.
    """

    messages = state.get("messages", [])

    message_count = len(messages)
    max_threshold = get_summarization_threshold()

    logger.info(
        f"[MEMORY] Current message count: {message_count} (threshold: {max_threshold})"
    )

    print(
        f"[MEMORY] Current message count: {message_count} (threshold: {max_threshold})"
    )

    if message_count > max_threshold:

        logger.info(
            "[MEMORY] Conversation too large -> summarizing"
        )

        print(
            "[MEMORY] Conversation too large -> summarizing"
        )

        return "summarize_memory"

    logger.info(
        "[MEMORY] Conversation size OK -> END"
    )

    print(
        "[MEMORY] Conversation size OK -> END"
    )

    return "end"


# route after Hitl 

def route_after_hitl(state: ChatState):

    decision = state.get(
        "hitl_decision",
        "no"
    )

    decision = str(
        decision
    ).lower().strip()

    logger.info(f"[HITL ROUTER] Decision: {decision}")

    if decision in ("yes", "approve", "true", "1"):
        logger.info("[HITL ROUTER] YES -> web_search")
        return "web_search"

    # If decision is 'no', check if we have any valid RAG context to answer with
    messages = state.get("messages", [])
    has_rag_context = any(
        isinstance(m, ToolMessage)
        and m.name == "unified_rag_tool"
        and m.content
        and not str(m.content).startswith("⚠️")
        and not str(m.content).startswith("❌")
        for m in messages
    )

    if has_rag_context:
        logger.info("[HITL ROUTER] NO -> final_answer (answering with available context)")
        return "final_answer"

    logger.info("[HITL ROUTER] NO -> not_found_answer")
    return "not_found_answer"


def route_after_chat(state: ChatState):
    """
    Decide whether the LLM wants to call a tool.
    Guards against accidental tool calling loops.
    """
    messages = state.get("messages", [])

    # Count tool executions since the last HumanMessage
    from langchain_core.messages import HumanMessage
    tool_count = 0
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            break
        if isinstance(m, ToolMessage):
            tool_count += 1

    MAX_TOOL_CALLS = 5
    if tool_count >= MAX_TOOL_CALLS:
        logger.warning(f"[ROUTER] Tool call limit reached ({tool_count} >= {MAX_TOOL_CALLS}). Forcing termination to memory_check.")
        return "memory_check"

    result = tools_condition(state)

    if result == "tools":
        logger.info("[ROUTER] LLM requested tool -> tools")
        return "tools"

    logger.info("[ROUTER] No tool requested -> memory_check")
    return "memory_check"




def route_after_tools(state: ChatState):
    """
    Decide what happens after tool execution.

    RAG:
        → CRAG grader

    Other tools:
        → chat_node
    """

    messages = state.get("messages", [])

    if not messages:
        return "chat_node"

    for message in reversed(messages):

        if isinstance(message, ToolMessage):
            logger.info(f"[ROUTER] Tool executed: {message.name}")

            if message.name == "unified_rag_tool":
                logger.info("[ROUTER] RAG tool detected -> CRAG grader")
                return "crag_grader"

            logger.info("[ROUTER] Other tool detected -> chat_node")
            return "chat_node"

    return "chat_node"


# ============================================================
# ROUTE AFTER CRAG
# ============================================================

def route_after_crag(state: ChatState):
    """
    Route based on CRAG relevance grade.

    GOOD:
        → final_answer

    PARTIAL:
        → human_approval

    IRRELEVANT:
        → human_approval
    """

    grade = state.get(
        "rag_grade",
        "IRRELEVANT"
    )

    logger.info(f"[CRAG ROUTER] Grade received: {grade}")

    if grade == "GOOD":
        logger.info("[CRAG ROUTER] GOOD -> final_answer")
        return "final_answer"

    if grade == "PARTIAL":
        logger.info("[CRAG ROUTER] PARTIAL -> human_approval")
        return "human_approval"

    if grade == "IRRELEVANT":
        logger.info("[CRAG ROUTER] IRRELEVANT -> human_approval")
        return "human_approval"

    logger.warning(f"[CRAG ROUTER] Unknown grade '{grade}' -> human_approval")
    return "human_approval"


# rag asnwer source 

def rag_answer_source_node(state: ChatState):

    grade = state.get(
            "rag_grade",
            "IRRELEVANT"
        )

    if grade=="RELEVANT" or grade=="GOOD" or grade=="PARTIAL":
        return {"answer_source":"rag"}
    elif grade=="IRRELEVANT":
        return {"answer_source":"web"}
        
    else:
        return {"answer_source":"web"}


graph = StateGraph(ChatState)



graph.add_node(
    "chat_node",
    chat_node
)


graph.add_node(
    "tools",
    tool_node
)


graph.add_node(
    "crag_grader",
    crag_relevance_grader
)


graph.add_node(
    "human_approval",
    human_approval_node
)

graph.add_node(
    "web_search",
    web_search_node
)


graph.add_node(
    "not_found_answer",
    not_found_answer_node
)


graph.add_node(
    "final_answer",
    final_answer_node
)


graph.add_node(
    "summarize_memory",
    summarize_memory
)

graph.add_node(
    "rag_answer_source",
    rag_answer_source_node
)



graph.add_node(
    "memory_check",
    cleanup_messages
)



graph.add_edge(
    START,
    "chat_node"
)


graph.add_conditional_edges(
    "chat_node",
    route_after_chat,
    {
        "tools": "tools",
        "memory_check": "memory_check",
    }
)


graph.add_conditional_edges(
    "tools",
    route_after_tools,
    {
        "crag_grader": "crag_grader",
        "chat_node": "chat_node",
    }
)


# ============================================================
# CRAG → FINAL ANSWER / HITL
# ============================================================


graph.add_edge(
    "crag_grader",
    "rag_answer_source"
)

graph.add_conditional_edges(
    "rag_answer_source",
    route_after_crag,
    {
        "final_answer": "final_answer",
        "human_approval": "human_approval",
    }
)


graph.add_conditional_edges(
    "human_approval",
    route_after_hitl,
    {
        "web_search": "web_search",
        "final_answer": "final_answer",
        "not_found_answer": "not_found_answer",
    }
)


graph.add_edge(
    "web_search",
    "memory_check"
)

graph.add_edge(
    "not_found_answer",
    "memory_check"
)


graph.add_edge(
    "final_answer",
    "memory_check"
)



graph.add_conditional_edges(
    "memory_check",
    should_summarize,
    {
        "summarize_memory": "summarize_memory",
        "end": END,
    }
)



graph.add_edge(
    "summarize_memory",
    END
)


chatbot = graph.compile(
    checkpointer=checkpointer
)