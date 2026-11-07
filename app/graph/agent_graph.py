from __future__ import annotations

import uuid
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

from langchain_core.messages import ToolMessage, HumanMessage, AIMessage

from app.memory.postgres_memory import checkpointer
from app.memory.stm import summarize_memory
from app.llm.llm_config import llm
from app.core.retriever import thread_document_metadata

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

    if message_count > max_threshold:
        logger.info("[MEMORY] Conversation too large -> summarizing")
        return "summarize_memory"

    logger.info("[MEMORY] Conversation size OK -> END")
    return "end"


def route_after_hitl(state: ChatState):
    """
    Route after user responds to the HITL approval prompt.
    """
    decision = state.get("hitl_decision", "no")
    decision = str(decision).lower().strip()

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
# CRAG RETRY NODE
# ============================================================

def rag_retry_node(state: ChatState, config=None):
    """
    CRAG Retry Node:
    When initial retrieval returns IRRELEVANT context, reformulate the query
    using conversation history and document metadata, and perform a second retrieval attempt.
    """
    messages = state.get("messages", [])
    user_question = ""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            user_question = message.content
            break

    # Extract recent conversation turns to resolve coreferences
    prev_turns = []
    conv_history = [
        m for m in messages
        if isinstance(m, (HumanMessage, AIMessage)) and not getattr(m, "tool_calls", None)
    ]
    for m in conv_history[-4:-1]:
        role = "User" if isinstance(m, HumanMessage) else "Assistant"
        raw_c = getattr(m, "content", "")
        c_text = raw_c if isinstance(raw_c, str) else str(raw_c)
        if c_text.strip():
            prev_turns.append(f"{role}: {c_text[:120].strip()}")
    history_str = "\n".join(prev_turns) if prev_turns else "None"

    # Get attached documents metadata if available
    configurable = config.get("configurable", {}) if config and isinstance(config, dict) else {}
    thread_id = configurable.get("thread_id")
    selected_doc_ids = configurable.get("selected_doc_ids")
    doc_meta = thread_document_metadata(thread_id, selected_doc_ids=selected_doc_ids) if thread_id else {}
    sources = doc_meta.get("sources", [])
    doc_titles = [s.get("name") or s.get("title") for s in sources if s.get("name") or s.get("title")]
    doc_context = f"Attached document titles: {', '.join(doc_titles)}" if doc_titles else ""

    rephrase_prompt = f"""You are a search query reformulation expert for a RAG system.
An initial search for the user's question yielded no relevant results.
Your task is to rewrite the question into an optimal, self-contained search query for retrieving relevant chunks from the uploaded document.

CONVERSATION HISTORY:
{history_str}

DOCUMENT INFO:
{doc_context}

ORIGINAL QUESTION:
{user_question}

Rules:
- Resolve any pronouns ("it", "they", "this", "that", "the author", "the model").
- Include key domain keywords, technical concepts, or section topics.
- Output ONLY the rephrased search query string. Do not include quotes, explanations, or formatting.
"""
    try:
        rephrase_resp = llm.invoke([HumanMessage(content=rephrase_prompt)])
        rephrased_query = (rephrase_resp.content if hasattr(rephrase_resp, "content") else str(rephrase_resp)).strip()
        rephrased_query = rephrased_query.strip('"\'')
        if not rephrased_query or len(rephrased_query) < 3:
            rephrased_query = user_question
    except Exception as e:
        logger.warning(f"[RAG RETRY] Query reformulation failed: {e}. Falling back to original.")
        rephrased_query = user_question

    logger.info(f"[RAG RETRY] Original: '{user_question}' -> Rephrased: '{rephrased_query}'")

    # Execute retrieval using unified_rag_tool
    try:
        from app.tools.unified_rag_tool import unified_rag_tool
        tool_res = unified_rag_tool.invoke({"query": rephrased_query}, config=config)
    except Exception as e:
        logger.error(f"[RAG RETRY] Retrieval invocation failed: {e}")
        tool_res = f"❌ Retry retrieval failed: {e}"

    tool_msg = ToolMessage(
        content=str(tool_res),
        name="unified_rag_tool",
        tool_call_id=f"retry_{uuid.uuid4().hex[:8]}"
    )

    current_retries = state.get("rag_retry_count", 0)
    return {
        "messages": [tool_msg],
        "rag_retry_count": current_retries + 1,
    }


# ============================================================
# ROUTE AFTER CRAG
# ============================================================

def route_after_crag(state: ChatState):
    """
    Route based on CRAG relevance grade and retry status:
    - GOOD -> final_answer (directly synthesize grounded answer)
    - PARTIAL -> final_answer (directly synthesize grounded answer with supported facts)
    - IRRELEVANT and retry_count == 0 -> rag_retry (attempts query reformulation & second retrieval)
    - IRRELEVANT and retry_count >= 1 -> human_approval (offers web search fallback)
    """
    grade = state.get("rag_grade", "IRRELEVANT")
    retry_count = state.get("rag_retry_count", 0)

    logger.info(f"[CRAG ROUTER] Grade received: {grade}, retry_count: {retry_count}")

    if grade in ("GOOD", "PARTIAL"):
        logger.info(f"[CRAG ROUTER] {grade} -> final_answer")
        return "final_answer"

    # grade == "IRRELEVANT"
    if retry_count < 1:
        logger.info("[CRAG ROUTER] IRRELEVANT (attempt 1 failed) -> rag_retry")
        return "rag_retry"

    logger.info("[CRAG ROUTER] IRRELEVANT (retries exhausted) -> human_approval")
    return "human_approval"


def rag_answer_source_node(state: ChatState):
    grade = state.get("rag_grade", "IRRELEVANT")
    if grade in ("RELEVANT", "GOOD", "PARTIAL"):
        return {"answer_source": "rag"}
    return {"answer_source": "web"}


# ============================================================
# BUILD LANGGRAPH WORKFLOW
# ============================================================

graph = StateGraph(ChatState)

graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)
graph.add_node("crag_grader", crag_relevance_grader)
graph.add_node("rag_retry", rag_retry_node)
graph.add_node("human_approval", human_approval_node)
graph.add_node("web_search", web_search_node)
graph.add_node("not_found_answer", not_found_answer_node)
graph.add_node("final_answer", final_answer_node)
graph.add_node("summarize_memory", summarize_memory)
graph.add_node("rag_answer_source", rag_answer_source_node)
graph.add_node("memory_check", cleanup_messages)

# Start edge
graph.add_edge(START, "chat_node")

# Conditional edges after chat_node
graph.add_conditional_edges(
    "chat_node",
    route_after_chat,
    {
        "tools": "tools",
        "memory_check": "memory_check",
    }
)

# Conditional edges after tools
graph.add_conditional_edges(
    "tools",
    route_after_tools,
    {
        "crag_grader": "crag_grader",
        "chat_node": "chat_node",
    }
)

# CRAG Grader -> Answer source -> Decision router
graph.add_edge("crag_grader", "rag_answer_source")

graph.add_conditional_edges(
    "rag_answer_source",
    route_after_crag,
    {
        "final_answer": "final_answer",
        "rag_retry": "rag_retry",
        "human_approval": "human_approval",
    }
)

# Retry edge: retry re-runs retriever and routes back to crag_grader
graph.add_edge("rag_retry", "crag_grader")

# HITL routing
graph.add_conditional_edges(
    "human_approval",
    route_after_hitl,
    {
        "web_search": "web_search",
        "final_answer": "final_answer",
        "not_found_answer": "not_found_answer",
    }
)

# Terminal cleanup edges
graph.add_edge("web_search", "memory_check")
graph.add_edge("not_found_answer", "memory_check")
graph.add_edge("final_answer", "memory_check")

# Memory check and summarization
graph.add_conditional_edges(
    "memory_check",
    should_summarize,
    {
        "summarize_memory": "summarize_memory",
        "end": END,
    }
)

graph.add_edge("summarize_memory", END)

chatbot = graph.compile(
    checkpointer=checkpointer
)
