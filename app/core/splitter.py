import re
from typing import Optional, Dict, Any, List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.utils.common import is_valid_chunk
from app.utils.logger import logger
from app.memory.config import get_rag_chunk_size, get_rag_chunk_overlap


def clean_text_chunk(text: str) -> str:
    """
    Remove excessive repeated whitespace, control characters, and normalize spaces.
    """
    if not text:
        return ""
    # Normalize excessive newlines (max 2 consecutive) and excessive horizontal whitespace
    cleaned = re.sub(r"[ \t]+", " ", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def chunk_text(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    doc_id: Optional[str] = None,
) -> List[Document]:
    """
    Split text into retrieval-ready document chunks with stable IDs and preserved metadata.
    """
    if not text or not text.strip():
        return []

    c_size = chunk_size if chunk_size is not None else get_rag_chunk_size()
    c_overlap = chunk_overlap if chunk_overlap is not None else get_rag_chunk_overlap()

    # Safety check: overlap must be strictly less than chunk_size
    if c_overlap >= c_size:
        c_overlap = max(0, c_size // 5)

    base_metadata = dict(metadata or {})
    target_doc_id = doc_id or base_metadata.get("doc_id", "doc")

    logger.info(
        f"[SPLITTER] Chunking text (length: {len(text)}) | "
        f"chunk_size={c_size}, chunk_overlap={c_overlap}"
    )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=c_size,
        chunk_overlap=c_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    raw_docs = splitter.create_documents([text])

    chunks: List[Document] = []
    chunk_index = 0

    for doc in raw_docs:
        cleaned_content = clean_text_chunk(doc.page_content)
        if not cleaned_content:
            continue
        if not is_valid_chunk(cleaned_content):
            continue

        chunk_meta = dict(base_metadata)
        chunk_meta["chunk_id"] = f"{target_doc_id}_chunk_{chunk_index}"
        chunk_meta["doc_id"] = target_doc_id
        chunk_meta["chunk_index"] = chunk_index

        chunks.append(
            Document(
                page_content=cleaned_content,
                metadata=chunk_meta
            )
        )
        chunk_index += 1

    # Record total chunks in all chunk metadata
    for c in chunks:
        c.metadata["total_chunks"] = len(chunks)

    logger.info(f"[SPLITTER] Produced {len(chunks)} valid chunks")
    return chunks

