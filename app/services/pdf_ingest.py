from __future__ import annotations

import os
import tempfile
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS

from app.llm.embeddings import get_embeddings
from app.core.splitter import clean_text_chunk
from app.utils.common import is_valid_chunk
from app.memory.config import get_rag_chunk_size, get_rag_chunk_overlap


def extract_pdf_chunks(
    docs: list,
    doc_id: str,
    filename: Optional[str] = None,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> list:
    """
    Split loaded PDF pages into clean chunks preserving 1-indexed page numbers and metadata.
    """
    c_size = chunk_size if chunk_size is not None else get_rag_chunk_size()
    c_overlap = chunk_overlap if chunk_overlap is not None else get_rag_chunk_overlap()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=c_size,
        chunk_overlap=c_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    raw_chunks = splitter.split_documents(docs)
    chunks = []
    for idx, chunk in enumerate(raw_chunks):
        content = clean_text_chunk(chunk.page_content)
        if not content or not is_valid_chunk(content):
            continue
        chunk.page_content = content
        raw_page = chunk.metadata.get("page", 0)
        page_num = int(raw_page) + 1 if isinstance(raw_page, (int, str)) and str(raw_page).isdigit() else 1
        chunk.metadata["page"] = page_num
        chunk.metadata["source"] = filename or "pdf"
        chunk.metadata["filename"] = filename or "Document"
        chunk.metadata["title"] = filename or "Document"
        chunk.metadata["doc_id"] = doc_id
        chunk.metadata["type"] = "pdf"
        chunk.metadata["chunk_id"] = f"{doc_id}_p{page_num}_c{idx}"
        chunks.append(chunk)

    for c in chunks:
        c.metadata["total_chunks"] = len(chunks)

    return chunks


def ingest_pdf(file_bytes: bytes, filename: Optional[str], doc_id: str) -> str:
    """
    Build and SAVE vectorstore for PDF (ONLY ONCE)

    Returns:
        vectorstore_path
    """
    if not file_bytes:
        raise ValueError("No file bytes received for PDF ingestion.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(file_bytes)
        temp_path = temp_file.name

    try:
        loader = PyPDFLoader(temp_path)
        docs = loader.load()

        if not docs:
            raise ValueError("No pages could be extracted from the uploaded PDF.")

        # Check for unreadable/scanned/image-only PDFs
        total_text = "".join((d.page_content or "").strip() for d in docs)
        if len(total_text) < 20:
            raise ValueError(
                "The uploaded PDF does not contain extractable text. "
                "It may be a scanned or image-only document without an embedded text layer."
            )

        chunks = extract_pdf_chunks(docs, doc_id=doc_id, filename=filename)

        if not chunks:
            raise ValueError(
                "No valid text chunks could be extracted from the PDF. "
                "The document may contain only headers or empty pages."
            )

        # Embeddings
        embeddings = get_embeddings()

        # Vectorstore
        vector_store = FAISS.from_documents(chunks, embeddings)

        # SAVE VECTORSTORE
        save_path = os.path.join("data/pdf/vectorstores", doc_id)
        os.makedirs(save_path, exist_ok=True)

        vector_store.save_local(save_path)

        return save_path

    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass