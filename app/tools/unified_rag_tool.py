from langchain.tools import tool
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from langchain_core.runnables import RunnableConfig
import traceback
from app.core.retriever import get_thread_retriever
from app.llm.llm_config import llm
from langchain_core.tools import InjectedToolArg
from typing import Annotated
from app.core.retriever import thread_document_metadata
from app.core.source_router import detect_source

@tool
def unified_rag_tool(query: str, config:Annotated[RunnableConfig,InjectedToolArg]) -> str:
    """
    Search and answer questions from. ALL uploaded PDFs,
    resumes, documents, files, and YouTube videos
    attached to the current thread.

    Use this tool whenever the user asks about
    uploaded content, summaries or summarys, information contained
    in documents, resumes, reports, or videos.

    Do NOT use for internet searches or current events.
    """

    try:
        thread_id = config.get("configurable", {}).get("thread_id")

        if not thread_id:
            return "⚠️ Missing thread_id"
        
        metadata = thread_document_metadata(thread_id)

        if not metadata:
           return "⚠️ No documents attached to this thread."

        available_types = {
         source["type"]
         for source in metadata["sources"]
          }
        
        print(
    f"[ROUTER] Available Sources: {available_types}"
      )

        if len(available_types)==1:
            source_type=list(available_types)[0]

        else:
            source_type=detect_source(query=query)

            print(
              f"[ROUTER] source_type={source_type}"
)

        retriever = get_thread_retriever(thread_id,source_type=source_type)

        if not retriever:
            return "⚠️ No documents loaded for this thread."

        docs = retriever.invoke(query)

        print(f"[RAG] Thread: {thread_id}")
        print(f"[RAG] Docs retrieved: {len(docs) if docs else 0}")

        if not docs:
            return "❌ No relevant information found."

        context_parts = []
 
        for i, doc in enumerate(docs[:8], start=1):

           doc_id = doc.metadata.get(
           "doc_id",
           "unknown"
         )

           source = doc.metadata.get(
          "source",
          "unknown"
         )

           pdf_name = os.path.basename(source)

           context_parts.append(
            f"""
            --- Retrieved Chunk {i} ---
            Document ID: {doc_id}
            Document: {pdf_name}

            {doc.page_content}
               """
            )

        context = "\n".join(context_parts)

        print("/n \n here is docs context which get from retriver /n",context)

        return f"""
You are answering ONLY from the retrieved context.

Rules:

- Never use outside knowledge.
- If information is missing, say so.
- Do not invent facts.
- Do not merge unrelated chunks.
- Treat each document as a separate source.
- If the question refers to a specific document, answer only from that document.
- If multiple documents contain relevant information, clearly distinguish them.
- If the user asks about a document that is not represented in the retrieved context, say that the relevant information was not found.
- If summarizing a document or video, summarize only the retrieved content.

Available source type:
{source_type}

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

      return f"❌ RAG tool error: {str(e)}"
