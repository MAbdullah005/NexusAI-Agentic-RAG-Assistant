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


@tool
def unified_rag_tool(
    query: str,
    config: Annotated[RunnableConfig, InjectedToolArg]
) -> str:
    """
    Search ALL documents attached to the current thread.

    Use this tool whenever the user asks about uploaded:
    - PDFs
    - resumes
    - documents
    - reports
    - YouTube videos

    This tool searches across ALL documents attached to the
    current thread and does not restrict retrieval to one
    source type.

    Do NOT use for internet searches or current events.
    """

    try:

        thread_id = config.get(
            "configurable",
            {}
        ).get("thread_id")

        if not thread_id:
            return "⚠️ Missing thread_id"


        metadata = thread_document_metadata(thread_id)

        if not metadata:

            return (
                "⚠️ No documents attached "
                "to this thread."
            )

        print("\n" + "=" * 80)
        print("[RAG] UNIFIED RAG TOOL")
        print("=" * 80)

        print(f"[RAG] Thread ID: {thread_id}")
        print(
            f"[RAG] Total documents: "
            f"{metadata.get('total_docs', 0)}"
        )

        print(
            f"[RAG] Sources: "
            f"{metadata.get('sources', [])}"
        )

        retriever = get_thread_retriever(
            thread_id
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


        context_parts = []

        for i, doc in enumerate(
            docs[:8],
            start=1
        ):

            doc_id = doc.metadata.get(
                "doc_id",
                "unknown"
            )

            filename = doc.metadata.get(
                "filename"
            )

            source = doc.metadata.get(
                "source",
                "unknown"
            )

            # Prefer filename
            if not filename:

                filename = os.path.basename(
                    source
                )

            context_parts.append(
                f"""
--- Retrieved Chunk {i} ---

Document ID:
{doc_id}

Document:
{filename}

Content:
{doc.page_content}
"""
            )

        context = "\n".join(
            context_parts
        )


        print(
            "\n[RAG] Retrieved document context:"
        )

        print(context)

        print("=" * 80)
        print()


        return f"""
{RAG_CONTEXT_PROMPT}

Retrieved context:

{context}

Question:

{query}
"""
    
    except Exception as e:

        print("\n" + "=" * 80)
        print("❌ UNIFIED RAG TOOL ERROR")
        print("=" * 80)

        traceback.print_exc()

        print("=" * 80 + "\n")

        return (
            f"❌ RAG tool error: {str(e)}"
        )