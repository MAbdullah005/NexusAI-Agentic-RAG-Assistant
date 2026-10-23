from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg
from app.prompts.rag import RAG_CONTEXT_PROMPT
from typing import Annotated
import sys
import os
import traceback

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../..")
    )
)

from app.core.retriever import (
    get_thread_retriever,
    thread_document_metadata
)
from app.memory.config import get_rag_top_k
from app.utils.logger import logger


@tool
def unified_rag_tool(
    query: str,
    config: Annotated[RunnableConfig, InjectedToolArg]
) -> str:
    """
    Search documents attached to the current thread.

    Use this tool whenever the user asks about attached sources:
    - PDFs & reports
    - resumes & documents
    - YouTube videos & transcripts
    - Web articles & blog URLs
    - GitHub repositories & codebases

    This tool searches across the active documents attached to the
    current thread and does not restrict retrieval to one
    source type.

    Do NOT use for general open internet searches; use search_tool for open internet queries.
    """

    try:
        configurable = config.get("configurable", {})
        thread_id = configurable.get("thread_id")
        selected_doc_ids = configurable.get("selected_doc_ids")

        if not thread_id:
            return "⚠️ Missing thread_id"

        metadata = thread_document_metadata(thread_id, selected_doc_ids=selected_doc_ids)

        if not metadata:
            return (
                "⚠️ No documents attached "
                "to this thread."
            )

        print("\n" + "=" * 80)
        print("[RAG] UNIFIED RAG TOOL")
        print("=" * 80)

        print(f"[RAG] Thread ID: {thread_id}")
        print(f"[RAG] Selected doc IDs: {selected_doc_ids}")
        print(
            f"[RAG] Total documents: "
            f"{metadata.get('total_docs', 0)}"
        )

        print(
            f"[RAG] Sources: "
            f"{metadata.get('sources', [])}"
        )

        retriever = get_thread_retriever(
            thread_id,
            selected_doc_ids=selected_doc_ids
        )

        if not retriever:
            return (
                "⚠️ No documents loaded "
                "for this thread."
            )

        docs = retriever.invoke(query)

        print(
            f"[RAG] Docs retrieved: "
            f"{len(docs) if docs else 0}"
        )

        if not docs:
            return (
                "❌ No relevant information "
                "found in the uploaded documents."
            )

        top_k = get_rag_top_k()
        context_parts = []

        for i, doc in enumerate(
            docs[:top_k],
            start=1
        ):
            metadata = doc.metadata or {}
            doc_id = metadata.get(
                "doc_id",
                "unknown"
            )

            filename = metadata.get(
                "filename"
            )

            source = metadata.get(
                "source",
                "unknown"
            )

            page = metadata.get("page")
            doc_type = metadata.get("type", "document").lower()
            chunk_id = metadata.get("chunk_id", f"{doc_id}_{i}")

            if doc_type == "youtube":
                source_url = source if (source and source.startswith("http")) else (f"https://www.youtube.com/watch?v={source}" if source and source != "unknown" else "")
                display_name = filename or f"YouTube Video ({source})"
                header = f"""--- Retrieved Chunk {i} ---
Type: YouTube Video
Video: {display_name}
URL: {source_url}
Document ID: {doc_id}
Chunk ID: {chunk_id}"""

            elif doc_type == "web":
                source_url = source if (source and source != "unknown") else ""
                display_name = filename or source_url or "Web Article"
                header = f"""--- Retrieved Chunk {i} ---
Type: Web Article
Title: {display_name}
URL: {source_url}
Document ID: {doc_id}
Chunk ID: {chunk_id}"""

            elif doc_type in ("github", "repo"):
                file_path = metadata.get("file_path", "")
                start_line = metadata.get("start_line", "")
                end_line = metadata.get("end_line", "")
                commit_sha = metadata.get("commit_sha", "")
                github_url = metadata.get("github_url", source)
                source_link = metadata.get("source_link") or (
                    f"{github_url}/blob/{commit_sha}/{file_path}#L{start_line}-L{end_line}"
                    if commit_sha and file_path else github_url
                )
                display_name = filename or github_url
                line_info = f" (lines {start_line}-{end_line})" if start_line and end_line else ""
                header = f"""--- Retrieved Chunk {i} ---
Type: GitHub Repository Code
Repository: {display_name}
File: {file_path}{line_info}
Source Link: {source_link}
Document ID: {doc_id}
Chunk ID: {chunk_id}"""

            else:
                display_name = filename or (os.path.basename(source) if source != "unknown" else doc_id)
                page_line = f"\nPage: {page}" if page is not None else ""
                header = f"""--- Retrieved Chunk {i} ---
Type: PDF Document
Document: {display_name}{page_line}
Document ID: {doc_id}
Chunk ID: {chunk_id}"""

            context_parts.append(
                f"""{header}

Content:
{doc.page_content}
"""
            )

        context = "\n".join(
            context_parts
        )

        logger.info(f"[RAG] Successfully compiled {len(context_parts)} context chunk(s) for query: {query[:80]}")

        return f"Retrieved source context:\n\n{context}"

    except Exception as e:
        logger.error(f"[RAG] Unified RAG tool error: {e}", exc_info=True)
        return (
            f"❌ RAG tool error: {str(e)}"
        )
