from __future__ import annotations

import os
import sqlite3
from typing import Dict, Any

from langchain_community.vectorstores import FAISS
from app.llm.embeddings import get_embeddings
from app.memory.sqlite_memory import checkpointer
from rank_bm25 import BM25Okapi
DB_PATH = "database/chatbot_conv.db"

# 🔥 CACHE (VERY IMPORTANT)
_THREAD_CACHE: Dict[str, Any] = {}


# ==============================
# MAIN RETRIEVER (FINAL VERSION)a
# ==============================
def get_thread_retriever(
    thread_id: str,
    source_type: str | None = None
):
    """
    Load all vectorstores linked to a thread.
    """

    cache_key = f"{thread_id}:{source_type}"

    # ============================================================
    # CACHE
    # ============================================================

    if cache_key in _THREAD_CACHE:

        print(
            f"[RETRIEVER] Using cached retriever: {cache_key}"
        )

        return _THREAD_CACHE[cache_key]

    print("\n" + "=" * 80)
    print("[RETRIEVER] BUILDING THREAD RETRIEVER")
    print("=" * 80)

    print("Thread ID:", thread_id)
    print("Source type:", source_type)

    # ============================================================
    # DATABASE
    # ============================================================

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:

        if source_type:

            cursor.execute(
                """
                SELECT
                    d.doc_id,
                    d.vectorstore_path
                FROM documents AS d
                INNER JOIN thread_documents AS td
                    ON d.doc_id = td.doc_id
                WHERE td.thread_id = ?
                  AND d.type = ?
                """,
                (
                    thread_id,
                    source_type
                )
            )

        else:

            cursor.execute(
                """
                SELECT
                    d.doc_id,
                    d.vectorstore_path
                FROM documents AS d
                INNER JOIN thread_documents AS td
                    ON d.doc_id = td.doc_id
                WHERE td.thread_id = ?
                """,
                (thread_id,)
            )

        rows = cursor.fetchall()

    finally:

        conn.close()

    print("[RETRIEVER] Database rows:")
    print(rows)

    if not rows:

        print(
            "[RETRIEVER] No vectorstores found."
        )

        return None

    # ============================================================
    # EMBEDDINGS
    # ============================================================

    print(
        "[RETRIEVER] Loading embeddings..."
    )

    embeddings = get_embeddings()

    print(
        "[RETRIEVER] Embeddings loaded."
    )

    # ============================================================
    # LOAD ALL VECTORSTORES
    # ============================================================

    vectorstores = []

    for doc_id, path in rows:

        print("\n" + "-" * 60)
        print("Loading document:")
        print("doc_id:", doc_id)
        print("path:", path)
        print("-" * 60)

        if not os.path.exists(path):

            print(
                f"⚠️ Vectorstore does not exist: {path}"
            )

            continue

        try:

            vs = FAISS.load_local(
                path,
                embeddings,
                allow_dangerous_deserialization=True
            )

            print(
                f"✅ Loaded vectorstore: {doc_id}"
            )

            vectorstores.append(vs)

        except Exception as e:

            print(
                f"❌ Failed loading vectorstore:"
                f" {doc_id}"
            )

            print(
                f"Path: {path}"
            )

            import traceback
            traceback.print_exc()

    # ============================================================
    # CHECK
    # ============================================================

    print(
        f"\n[RETRIEVER] Successfully loaded "
        f"{len(vectorstores)} vectorstore(s)"
    )

    if not vectorstores:

        print(
            "❌ No vectorstores could be loaded."
        )

        return None

    # ============================================================
    # SMART RETRIEVER
    # ============================================================

    try:

        retriever = SmartRetriever(
            vectorstores
        )

    except Exception as e:

        print(
            "❌ SmartRetriever creation failed"
        )

        import traceback
        traceback.print_exc()

        raise

    # ============================================================
    # CACHE
    # ============================================================

    _THREAD_CACHE[cache_key] = retriever

    print(
        "[RETRIEVER] Retriever created successfully."
    )

    print("=" * 80 + "\n")

    return retriever


# ==============================
# OPTIONAL HELPERS (CLEAN)
# ==============================

def retrieve_all_threads():
    """
    Get all thread IDs from memory checkpoints
    """
    all_threads = set()

    for checkpoint in checkpointer.list(None):
        all_threads.add(
            checkpoint.config["configurable"]["thread_id"]
        )

    return list(all_threads)


def thread_has_document(thread_id: str) -> bool:
    """
    Check if thread has any documents in DB
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT 1 FROM thread_documents WHERE thread_id=? LIMIT 1
    """, (thread_id,))

    return cursor.fetchone() is not None


def clear_thread_cache(thread_id: str):

    keys_to_delete = [
        key
        for key in _THREAD_CACHE
        if key.startswith(f"{thread_id}:")
    ]

    for key in keys_to_delete:
        del _THREAD_CACHE[key]
        

def thread_document_metadata(thread_id: str) -> dict:

    if not thread_id:
        return {}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                d.doc_id,
                d.type,
                d.source,
                d.filename
            FROM documents AS d
            INNER JOIN thread_documents AS td
                ON d.doc_id = td.doc_id
            WHERE td.thread_id = ?
            ORDER BY d.created_at ASC
        """, (thread_id,))

        rows = cursor.fetchall()

    finally:
        conn.close()

    if not rows:
        return {}

    sources = []

    for doc_id, doc_type, source, filename in rows:

        if doc_type == "pdf":

            name = filename or os.path.basename(source)

        elif doc_type == "youtube":

            name = f"https://www.youtube.com/watch?v={source}"

        else:

            name = filename or source

        sources.append({
            "doc_id": doc_id,
            "type": doc_type,
            "name": name
        })

    return {
        "total_docs": len(sources),
        "sources": sources
    }


class SmartRetriever:

    def __init__(self, stores):

        self.stores = stores

        self.all_documents = []

        # ========================================================
        # LOAD DOCUMENTS FROM ALL VECTORSTORES
        # ========================================================

        for store_index, vs in enumerate(stores):

            try:

                docs = list(
                    vs.docstore._dict.values()
                )

                print(
                    f"[BM25] Vectorstore {store_index + 1}: "
                    f"{len(docs)} documents"
                )

                self.all_documents.extend(
                    docs
                )

            except Exception as e:

                print(
                    f"❌ BM25 load error "
                    f"for vectorstore {store_index + 1}: {e}"
                )

                import traceback
                traceback.print_exc()

        print(
            f"[BM25] Total documents: "
            f"{len(self.all_documents)}"
        )

        # ========================================================
        # TOKENIZE
        # ========================================================

        self.bm25_docs = [
            doc.page_content.split()
            for doc in self.all_documents
        ]

        # ========================================================
        # BM25
        # ========================================================

        if self.bm25_docs:

            self.bm25 = BM25Okapi(
                self.bm25_docs
            )

        else:

            self.bm25 = None

    def invoke(self, query):

        dense_results = []
        sparse_results = []

        # ========================================================
        # DENSE SEARCH — ALL PDF VECTORSTORES
        # ========================================================

        for vs in self.stores:

            try:

                docs = vs.similarity_search_with_score(
                    query,
                    k=4
                )

                for doc, score in docs:

                    doc.metadata["dense_score"] = float(
                        score
                    )

                    dense_results.append(
                        doc
                    )

            except Exception as e:

                print(
                    f"❌ Dense retrieval error: {e}"
                )

                import traceback
                traceback.print_exc()

        # ========================================================
        # BM25
        # ========================================================

        if self.bm25:

            tokenized_query = query.split()

            bm25_scores = self.bm25.get_scores(
                tokenized_query
            )

            scored_docs = list(
                zip(
                    self.all_documents,
                    bm25_scores
                )
            )

            scored_docs.sort(
                key=lambda x: x[1],
                reverse=True
            )

            top_sparse = scored_docs[:4]

            for doc, score in top_sparse:

                doc.metadata["bm25_score"] = float(
                    score
                )

                sparse_results.append(
                    doc
                )

        # ========================================================
        # MERGE
        # ========================================================

        combined = (
            dense_results +
            sparse_results
        )

        # ========================================================
        # REMOVE DUPLICATES
        # ========================================================

        unique_docs = []
        seen = set()

        for doc in combined:

            content = doc.page_content.strip()

            if not content:
                continue

            # Include source/doc ID if available
            source = doc.metadata.get(
                "source",
                ""
            )

            unique_key = (
                source,
                content
            )

            if unique_key not in seen:

                seen.add(
                    unique_key
                )

                unique_docs.append(
                    doc
                )

        # ========================================================
        # RERANK
        # ========================================================

        def final_score(doc):

            dense = doc.metadata.get(
                "dense_score",
                1000
            )

            bm25 = doc.metadata.get(
                "bm25_score",
                0
            )

            dense_part = 1 / (
                1 + dense
            )

            return (
                dense_part +
                (0.3 * bm25)
            )

        unique_docs.sort(
            key=final_score,
            reverse=True
        )

        return unique_docs[:5]