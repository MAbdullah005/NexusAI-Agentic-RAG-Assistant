from __future__ import annotations

import os
import re
import hashlib

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from app.llm.embeddings import get_embeddings
from app.services.web_loader import load_webpage
from app.core.splitter import clean_text_chunk
from app.utils.common import is_valid_chunk
from app.memory.config import get_rag_chunk_size, get_rag_chunk_overlap

def process_web_document(
    content: str,
    doc_id: str,
    url: str,
    title: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list:
    """
    Split webpage text into retrieval-ready document chunks with preserved metadata.
    """
    max_content_len = 100_000
    safe_content = content[:max_content_len]

    document = Document(
        page_content=safe_content,
        metadata={
            "doc_id": doc_id,
            "source": url,
            "filename": title or url,
            "title": title or url,
            "type": "web"
        }
    )

    c_size = chunk_size if chunk_size is not None else get_rag_chunk_size()
    c_overlap = chunk_overlap if chunk_overlap is not None else get_rag_chunk_overlap()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=c_size,
        chunk_overlap=c_overlap,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            ""
        ]
    )

    raw_chunks = splitter.split_documents([document])
    chunks = []
    for idx, c in enumerate(raw_chunks):
        cleaned = clean_text_chunk(c.page_content)
        if not cleaned or not is_valid_chunk(cleaned):
            continue
        c.page_content = cleaned
        c.metadata["doc_id"] = doc_id
        c.metadata["source"] = url
        c.metadata["filename"] = title or url
        c.metadata["title"] = title or url
        c.metadata["type"] = "web"
        c.metadata["chunk_id"] = f"{doc_id}_web_c{idx}"
        chunks.append(c)

    for c in chunks:
        c.metadata["total_chunks"] = len(chunks)

    return chunks


def ingest_web(
    url: str,
    doc_id: str,
    thread_id: str
) -> dict:
    """
    Load website content, split it into chunks,
    create embeddings and save a FAISS vectorstore.

    Returns:
        {
            "vectorstore_path": "...",
            "title": "...",
            "content": "...",
            "content_hash": "...",
            "type": "web",
            "source": "..."
        }
    """
    if not url:
        raise ValueError("URL cannot be empty.")

    print("\n" + "=" * 80)
    print("[WEB INGESTION]")
    print("=" * 80)
    print(f"[WEB] Loading URL: {url}")

    result = load_webpage(url)

    content = result.page_content
    title = result.metadata.get("title", url)
    source = result.metadata.get("source", url)
    doc_type = result.metadata.get("type", "web")

    if not content or len(content.strip()) < 50:
        raise ValueError("No readable article content could be extracted from website.")

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    print(f"[WEB] Extracted characters: {len(content)}")
    print(f"[WEB] Title: {title}")

    chunks = process_web_document(
        content=content,
        doc_id=doc_id,
        url=url,
        title=title
    )

    if not chunks:
        raise ValueError("No valid chunks created from website content.")

    print(f"[WEB] Total chunks: {len(chunks)}")

    embeddings = get_embeddings()

    vectorstore = FAISS.from_documents(
        chunks,
        embeddings
    )

    clean_title = re.sub(r'[\\/*?:"<>|]', "_", (title or "webpage"))[:40].strip()
    save_path = os.path.join(
        "data",
        "web",
        clean_title,
        doc_id
    )

    os.makedirs(save_path, exist_ok=True)
    vectorstore.save_local(save_path)

    print(f"[WEB] Vectorstore saved: {save_path}")
    print("=" * 80 + "\n")

    return {
        "vectorstore_path": save_path,
        "title": title or url,
        "source": source,
        "doc_id": doc_id,
        "thread_id": thread_id,
        "type": doc_type,
        "content_hash": content_hash,
        "content": content[:3000]
    }