"""
Deep Research Graph (LangGraph).
Coordinates multi-step investigative research: planning, multi-source searching
(Web, arXiv, local documents), content extraction, relevance filtering, and report generation.
"""

from __future__ import annotations

from typing import (
    TypedDict,
    List,
    Dict,
    Any,
    Optional,
)
import json
import re

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage

from app.llm.llm_config import llm
from app.services.research.web_search import search_web
from app.services.research.arxiv_search import search_arxiv
from app.services.research.extractor import extract_page_content
from app.services.research.filter import filter_and_rank_evidence
from app.core.retriever import get_thread_retriever, thread_document_metadata
from app.utils.logger import get_logger

logger = get_logger(__name__)


# =====================================================================
# 1. RESEARCH STATE
# =====================================================================

class ResearchState(TypedDict, total=False):
    query: str
    thread_id: str
    user_id: int
    selected_doc_ids: Optional[List[str]]
    config: Dict[str, Any]
    sub_queries: List[str]
    current_iteration: int
    raw_sources: List[Dict[str, Any]]
    extracted_content: List[Dict[str, Any]]
    filtered_evidence: List[Dict[str, Any]]
    final_report: str
    stage: str
    stage_message: str
    sources_summary: List[Dict[str, Any]]


# =====================================================================
# 2. NODES
# =====================================================================

def plan_research_node(state: ResearchState) -> Dict[str, Any]:
    """
    Generate focused sub-queries based on the main research question.
    """
    query = state.get("query", "").strip()
    config = state.get("config", {}) or {}
    subqueries_count = int(config.get("subqueries_count", 3))
    subqueries_count = max(1, min(5, subqueries_count))
    user_instructions = config.get("instructions", "").strip()

    logger.info(f"[RESEARCH GRAPH] Planning for query: '{query}'")

    system_prompt = (
        "You are an expert research planner. Given a primary research question, generate "
        f"exactly {subqueries_count} distinct, highly focused research sub-queries. "
        "Each sub-query should investigate a distinct aspect (e.g., core fundamentals/mechanisms, "
        "recent breakthroughs/papers, empirical benchmarks/practical trade-offs). "
        "Output ONLY a valid JSON list of strings, with no additional commentary or markdown wrappers.\n"
        "Example output: [\"sub query 1\", \"sub query 2\", \"sub query 3\"]"
    )

    user_prompt = f"Primary Research Question: {query}"
    if user_instructions:
        user_prompt += f"\nAdditional User Instructions: {user_instructions}"

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        content = response.content.strip() if hasattr(response, "content") else str(response)

        # Parse JSON array
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                sub_queries = [s.strip() for s in parsed if s.strip()][:subqueries_count]
            else:
                sub_queries = []
        else:
            sub_queries = []
    except Exception as e:
        logger.warning(f"[RESEARCH GRAPH] LLM query planning failed: {e}; falling back to heuristics")
        sub_queries = []

    # Fallback heuristic queries if LLM parsing failed
    if not sub_queries:
        sub_queries = [
            query,
            f"{query} state of the art research papers arXiv",
            f"{query} architectural comparison advantages limitations"
        ][:subqueries_count]

    logger.info(f"[RESEARCH GRAPH] Generated sub-queries: {sub_queries}")

    return {
        "sub_queries": sub_queries,
        "current_iteration": 1,
        "stage": "planning",
        "stage_message": f"Generated {len(sub_queries)} targeted research sub-queries",
    }


def search_node(state: ResearchState) -> Dict[str, Any]:
    """
    Search Web, arXiv, and local thread documents for all sub-queries.
    """
    query = state.get("query", "")
    sub_queries = state.get("sub_queries", [query])
    config = state.get("config", {}) or {}
    search_count = int(config.get("search_count", 10))
    thread_id = state.get("thread_id")
    selected_doc_ids = state.get("selected_doc_ids")
    existing_sources = state.get("raw_sources", []) or []

    per_query_web_limit = max(3, search_count // max(1, len(sub_queries)))
    per_query_arxiv_limit = max(2, search_count // (max(1, len(sub_queries)) * 2))

    discovered_sources = list(existing_sources)
    seen_urls = {s.get("url", "").lower().rstrip("/") for s in discovered_sources if s.get("url")}

    # 1. Search Web and arXiv for each sub-query
    for sq in sub_queries:
        # Web Search
        try:
            web_results = search_web(sq, max_results=per_query_web_limit)
            for item in web_results:
                u = item.get("url", "").lower().rstrip("/")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    discovered_sources.append(item)
        except Exception as e:
            logger.warning(f"[RESEARCH GRAPH] Web search error for '{sq}': {e}")

        # arXiv Search
        try:
            arxiv_results = search_arxiv(sq, max_results=per_query_arxiv_limit)
            for item in arxiv_results:
                u = item.get("url", "").lower().rstrip("/")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    discovered_sources.append(item)
        except Exception as e:
            logger.warning(f"[RESEARCH GRAPH] arXiv search error for '{sq}': {e}")

    # 2. Search local documents attached to thread (if any exist)
    if thread_id:
        try:
            metadata = thread_document_metadata(thread_id, selected_doc_ids=selected_doc_ids)
            if metadata and metadata.get("total_docs", 0) > 0:
                retriever = get_thread_retriever(thread_id, selected_doc_ids=selected_doc_ids)
                if retriever:
                    for sq in [query] + sub_queries[:2]:
                        docs = retriever.invoke(sq)
                        for doc in docs or []:
                            doc_meta = getattr(doc, "metadata", {}) or {}
                            source_name = doc_meta.get("source") or doc_meta.get("filename") or "Local Document"
                            doc_content = getattr(doc, "page_content", "") or ""
                            doc_key = f"doc:{source_name}:{doc_content[:40]}"
                            if doc_key not in seen_urls and len(doc_content.strip()) > 30:
                                seen_urls.add(doc_key)
                                discovered_sources.append({
                                    "title": f"Attached Document: {source_name}",
                                    "url": f"document://{source_name}",
                                    "snippet": doc_content[:600],
                                    "text": doc_content,
                                    "source_type": "document",
                                    "published_date": None,
                                    "authors": [],
                                    "score": 0.9,
                                })
        except Exception as e:
            logger.warning(f"[RESEARCH GRAPH] Local document search error: {e}")

    # Build sources summary for frontend tracking
    sources_summary = [
        {
            "title": s.get("title", "Source"),
            "url": s.get("url", ""),
            "source_type": s.get("source_type", "web"),
            "published_date": s.get("published_date"),
            "authors": s.get("authors") or []
        }
        for s in discovered_sources
    ]

    return {
        "raw_sources": discovered_sources,
        "sources_summary": sources_summary,
        "stage": "searching",
        "stage_message": f"Discovered {len(discovered_sources)} sources from Web, arXiv, and local documents",
    }


def extract_content_node(state: ResearchState) -> Dict[str, Any]:
    """
    Extract article content from web URLs and format academic/document text.
    """
    raw_sources = state.get("raw_sources", [])
    extracted_sources = []

    # Limit full web extraction to top 12 sources to keep latency reasonable
    for idx, src in enumerate(raw_sources[:15]):
        source_type = src.get("source_type", "web")
        url = src.get("url", "")
        snippet = src.get("snippet", "")
        existing_text = src.get("text")

        if existing_text:
            # Already extracted (e.g. from local documents)
            extracted_sources.append(src)
            continue

        if source_type == "web" and url.startswith("http"):
            # Web extraction via BeautifulSoup
            result = extract_page_content(url, fallback_snippet=snippet, timeout=4)
            cleaned_text = result.get("text") or snippet
            extracted_sources.append({
                **src,
                "text": cleaned_text,
            })
        elif source_type == "arxiv":
            # arXiv abstract is high-value structured summary
            extracted_sources.append({
                **src,
                "text": snippet,
            })
        else:
            extracted_sources.append({
                **src,
                "text": snippet,
            })

    return {
        "extracted_content": extracted_sources,
        "stage": "extracting",
        "stage_message": f"Extracted and cleaned content from {len(extracted_sources)} sources",
    }


def filter_evidence_node(state: ResearchState) -> Dict[str, Any]:
    """
    Filter, deduplicate, and score evidence chunks for high relevance.
    """
    query = state.get("query", "")
    sub_queries = state.get("sub_queries", [])
    extracted_content = state.get("extracted_content", [])
    curr_iter = state.get("current_iteration", 1)

    filtered_evidence = filter_and_rank_evidence(
        sources=extracted_content,
        research_query=query,
        sub_queries=sub_queries,
        max_evidence_chunks=16,
        max_total_chars=18000
    )

    return {
        "filtered_evidence": filtered_evidence,
        "current_iteration": curr_iter + 1,
        "stage": "filtering",
        "stage_message": f"Curated {len(filtered_evidence)} high-relevance evidence passages",
    }


def should_iterate(state: ResearchState) -> str:
    """
    Decide whether to execute another research round or generate the report.
    """
    config = state.get("config", {}) or {}
    max_iterations = int(config.get("iterations", 2))
    current_iter = state.get("current_iteration", 1)
    evidence = state.get("filtered_evidence", [])

    # If configured for > 1 iterations and we have fewer than 5 evidence pieces on first round, iterate
    if current_iter <= max_iterations and len(evidence) < 6:
        logger.info(f"[RESEARCH GRAPH] Iterating: round {current_iter} of {max_iterations}")
        return "search_more"

    return "generate_report"


def generate_report_node(state: ResearchState) -> Dict[str, Any]:
    """
    Generate a comprehensive, structured research report with traceable citations.
    """
    query = state.get("query", "")
    evidence = state.get("filtered_evidence", [])
    config = state.get("config", {}) or {}
    report_length = str(config.get("report_length", "long")).lower()
    citation_style = str(config.get("citation_style", "APA")).upper()
    user_instructions = config.get("instructions", "").strip()

    logger.info(f"[RESEARCH GRAPH] Generating report (length={report_length}, style={citation_style})")

    # Word count targets
    if report_length == "short":
        word_guide = "approximately 1,000 words"
    elif report_length == "medium":
        word_guide = "approximately 2,000 words"
    else:
        word_guide = "a comprehensive, detailed report (target 3,000 - 4,000 words)"

    # Citation style guidance
    if citation_style == "MLA":
        in_text_example = "(Author Page) or (Title)"
        ref_example = "Author. \"Title.\" Source/Publisher, Year, URL."
    elif citation_style == "Harvard":
        in_text_example = "(Author, Year)"
        ref_example = "Author (Year) 'Title', Source. Available at: URL."
    else:  # APA
        in_text_example = "(Author, Year) or (Title, Year)"
        ref_example = "Author, A. A. (Year). Title of work. Publisher/Source. URL"

    # Format evidence blocks
    evidence_text_blocks = []
    sources_catalog = []

    for idx, ev in enumerate(evidence, start=1):
        title = ev.get("title", "Source")
        url = ev.get("url", "")
        authors = ", ".join(ev.get("authors") or []) or "Unknown Author"
        year = ev.get("published_date") or "n.d."
        text = ev.get("text", "").strip()

        evidence_text_blocks.append(
            f"--- EVIDENCE [{idx}] ---\n"
            f"Title: {title}\n"
            f"Authors: {authors}\n"
            f"Date/Year: {year}\n"
            f"Source URL: {url}\n"
            f"Content:\n{text}\n"
        )

        sources_catalog.append({
            "index": idx,
            "title": title,
            "authors": authors,
            "year": year,
            "url": url,
        })

    evidence_context = "\n".join(evidence_text_blocks)

    system_prompt = f"""You are NexusAI's Principal Deep Research Scientist.
Your task is to write an exhaustive, rigorous, and highly structured research report answering the user's research question based on the collected evidence.

FORMAT SPECIFICATIONS:
- Target Length: {word_guide}. Be thorough, analytical, and complete. Avoid filler, repetition, or superficial summaries.
- Citation Style: {citation_style}.
  - In-text citation format: Use {in_text_example} when referencing facts.
  - References section format: Follow {ref_example}.
- Every factual claim based on external sources MUST include an in-text citation pointing to a verifiable source from the provided evidence.
- TRACEABILITY MANDATE: NEVER invent references, paper authors, publication dates, or URLs. Only cite and link to the genuine sources provided in the Evidence below.

REQUIRED REPORT STRUCTURE:
Your report MUST contain all 9 numbered sections below using Markdown headings:

# [Descriptive Research Title]

## 1. Executive Summary
Provide a high-level synthesis of the key findings, conclusions, and strategic takeaways.

## 2. Introduction and Background
Set the context, define core concepts, describe historical development, and state the research scope.

## 3. Main Research Findings
Present the primary discoveries, architectural mechanisms, methodologies, or benchmark results discovered across the web and academic papers.

## 4. Detailed Analysis with Supporting Evidence
Provide an in-depth, rigorous technical examination. Group related themes logically, analyze empirical data, provide structured Markdown comparison tables where applicable, and thoroughly substantiate every claim with citations.

## 5. Conflicting Information or Different Perspectives
Discuss competing viewpoints, alternative paradigms, theoretical debates, trade-offs, or discrepancies observed across sources.

## 6. Limitations or Information Gaps
Highlight what remains unresolved, methodology limitations in the reviewed literature, or areas requiring further empirical validation.

## 7. Conclusion
Summarize the synthesis, future outlook, and actionable implications.

## 8. References and Source Links
List all cited sources in proper {citation_style} format. Make the source URL clickable using Markdown link syntax: [Title or URL](URL).
"""

    user_prompt = f"""Research Question: {query}
"""
    if user_instructions:
        user_prompt += f"\nSpecific User Directives:\n{user_instructions}\n"

    user_prompt += f"""
Collected Evidence Catalog:
{evidence_context}

Please generate the complete, exhaustive research report following all 9 sections above. Ensure all citations and links are fully traceable to the evidence catalog.
"""

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        final_report = response.content.strip() if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error(f"[RESEARCH GRAPH] Report generation failed: {e}")
        final_report = (
            f"# Research Report: {query}\n\n"
            f"## Executive Summary\nAn error occurred while generating the detailed report: {e}\n\n"
            f"## Collected Sources\n" + "\n".join(f"- [{s['title']}]({s['url']})" for s in sources_catalog if s['url'])
        )

    return {
        "final_report": final_report,
        "stage": "completed",
        "stage_message": "Deep Research report successfully generated",
    }


# =====================================================================
# 3. BUILD AND COMPILE GRAPH
# =====================================================================

def build_research_graph():
    """
    Constructs the LangGraph state graph for Deep Research Mode.
    """
    workflow = StateGraph(ResearchState)

    # Add nodes
    workflow.add_node("plan_research", plan_research_node)
    workflow.add_node("search", search_node)
    workflow.add_node("extract_content", extract_content_node)
    workflow.add_node("filter_evidence", filter_evidence_node)
    workflow.add_node("generate_report", generate_report_node)

    # Add edges
    workflow.add_edge(START, "plan_research")
    workflow.add_edge("plan_research", "search")
    workflow.add_edge("search", "extract_content")
    workflow.add_edge("extract_content", "filter_evidence")

    # Conditional edge for research iteration
    workflow.add_conditional_edges(
        "filter_evidence",
        should_iterate,
        {
            "search_more": "search",
            "generate_report": "generate_report",
        }
    )

    workflow.add_edge("generate_report", END)

    return workflow.compile()


# Global compiled instance
research_graph = build_research_graph()

