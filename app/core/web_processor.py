from __future__ import annotations

import os

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from app.llm.embeddings import get_embeddings
from app.services.web_loader import load_webpage
import hashlib

def ingest_web(
    url: str,
    doc_id: str,
    thread_id
) -> dict:
    """
    Load website content, split it into chunks,
    create embeddings and save a FAISS vectorstore.

    Returns:
        {
            "vectorstore_path": "...",
            "title": "...",
            "content": "..."
        }
    """

    # =========================================================
    # 1. LOAD WEBSITE CONTENT
    # =========================================================

    print("\n" + "=" * 80)
    print("[WEB INGESTION]")
    print("=" * 80)

    print(f"[WEB] Loading URL: {url}")

    result = load_webpage(url)

    content = result.page_content
    title = result.metadata.get("title", url)
    source = result.metadata.get("source",[])
    type = result.metadata.get("type",[])

    if not content:
        raise ValueError(
            "No readable content extracted from website."
        )

    print(
        f"[WEB] Extracted characters: {len(content)}"
    )

    print(
        f"[WEB] Title: {title}"
    )
    content_hash = hashlib.sha256(
    content.encode("utf-8")
    ).hexdigest()

    # 2. CREATE LANGCHAIN DOCUMENT

    document = Document(
        page_content=content[:3000],
        metadata={
            "doc_id": doc_id,
            "source": url,
            "filename": title or url,
            "type": "web"
        }
    )

    # 3. SPLIT INTO CHUNKS

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            ""
        ]
    )

    chunks = splitter.split_documents(
        [document]
    )

    if not chunks:

        raise ValueError(
            "No chunks created from website content."
        )

    print(
        f"[WEB] Total chunks: {len(chunks)}"
    )

    # Ensure metadata exists on every chunk

    for chunk in chunks:

        chunk.metadata["doc_id"] = doc_id
        chunk.metadata["source"] = url
        chunk.metadata["filename"] = title or url
        chunk.metadata["type"] = "web"

    # 4. LOAD EMBEDDINGS

    embeddings = get_embeddings()

    # 5. CREATE FAISS VECTORSTORE

    vectorstore = FAISS.from_documents(
        chunks,
        embeddings
    )

    # 6. SAVE VECTORSTORE

    save_path = os.path.join(
        "data",
        f"web/{title or url}",
        "vectorstores",
        doc_id
    )

    os.makedirs(
        save_path,
        exist_ok=True
    )

    vectorstore.save_local(
        save_path
    )

    print(
        f"[WEB] Vectorstore saved: {save_path}"
    )

    print("=" * 80 + "\n")

    # 7. RETURN METADATA

    return {
        "vectorstore_path": save_path,
        "title": title or url,
        "source":source,
        "doc_id":doc_id,
        "thread_id":thread_id,
        "type":type,
        "content_hash":content_hash,
        "content": content[:3000]
    }