from __future__ import annotations

import os
import sqlite3
from typing import Dict, Any

from langchain_community.vectorstores import FAISS
from app.llm.embeddings import get_embeddings
from app.memory.sqlite_memory import checkpointer
from rank_bm25 import BM25Okapi
from app.utils.logger import logger
DB_PATH = "database/chatbot_conv.db"

#  CACHE 
_THREAD_CACHE: Dict[str, Any] = {}


# MAIN RETRIEVER
def get_thread_retriever(
    thread_id: str,
    source_type: str | None = None
):
    """
    Load all vectorstores linked to a thread.
    """

    cache_key = f"{thread_id}"

    # CACHE

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

    # DATABASE

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:


        cursor.execute(
                """
                SELECT
                    d.doc_id,
                    d.vectorstore_path,
                    d.filename
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

    # EMBEDDINGS

    print(
        "[RETRIEVER] Loading embeddings..."
    )

    embeddings = get_embeddings()

    print(
        "[RETRIEVER] Embeddings loaded."
    )

    # LOAD ALL VECTORSTORES

    vectorstores = []

    for doc_id, path,filename in rows:

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

            for doc in vs.docstore._dict.values():
                doc.metadata["doc_id"]=doc_id
                if filename:
                    doc.metadata["filename"]=filename

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

    # CHECK

    print(
        f"\n[RETRIEVER] Successfully loaded "
        f"{len(vectorstores)} vectorstore(s)"
    )

    if not vectorstores:

        print(
            "❌ No vectorstores could be loaded."
        )

        return None

    # SMART RETRIEVER

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

    # CACHE

    _THREAD_CACHE[cache_key] = retriever

    print(
        "[RETRIEVER] Retriever created successfully."
    )

    print("=" * 80 + "\n")

    return retriever


# OPTIONAL HELPERS (CLEAN)

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


def clear_thread_retriever_cache(thread_id: str):
    """
    Remove cached retrievers for a thread.
    Call this after adding/removing documents.
    """

    keys_to_remove = [
        key
        for key in _THREAD_CACHE
        if key.startswith(f"{thread_id}:")
    ]

    for key in keys_to_remove:
        del _THREAD_CACHE[key]

    print(
        f"[CACHE] Cleared {len(keys_to_remove)} "
        f"retriever(s) for thread {thread_id}"
    )
        

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
    """
    Hybrid retriever using:

    1. FAISS dense retrieval
    2. BM25 sparse retrieval
    3. Hybrid scoring
    4. Balanced multi-document selection

    The retriever is designed for threads containing
    multiple PDFs/resumes/documents.

    Important:
    - Retriever construction happens once and is cached.
    - invoke(query) performs retrieval once for each query.
    """

    def __init__(
        self,
        stores,
        dense_k_per_document=4,
        sparse_k_per_document=4,
        max_chunks_per_document=4,
        min_chunks_per_document=1,
        max_total_chunks=None,
    ):
        self.stores = stores

        self.dense_k_per_document = dense_k_per_document
        self.sparse_k_per_document = sparse_k_per_document

        self.max_chunks_per_document = max_chunks_per_document
        self.min_chunks_per_document = min_chunks_per_document

        # If None, calculate dynamically based on number of documents.
        self.max_total_chunks = max_total_chunks

        # ---------------------------------------------------------
        # COLLECT ALL DOCUMENT CHUNKS
        # ---------------------------------------------------------

        self.all_documents = []

        for store_index, vs in enumerate(stores):

            try:
                docs = list(vs.docstore._dict.values())

                print(
                    f"[BM25] Vectorstore {store_index + 1}: "
                    f"{len(docs)} documents"
                )

                for doc in docs:

                    # Make sure metadata exists
                    if doc.metadata is None:
                        doc.metadata = {}

                    # Store which vectorstore this chunk came from
                    doc.metadata.setdefault(
                        "store_index",
                        store_index
                    )

                    self.all_documents.append(doc)

            except Exception as e:

                print(
                    f"❌ BM25 load error for vectorstore "
                    f"{store_index + 1}: {e}"
                )

                import traceback
                traceback.print_exc()

        print(
            f"[BM25] Total documents/chunks: "
            f"{len(self.all_documents)}"
        )

        # GROUP DOCUMENTS BY SOURCE/DOCUMENT ID

        self.documents_by_source = {}

        for doc in self.all_documents:

            doc_id = doc.metadata.get("doc_id")

            source = doc.metadata.get("source")

            filename = doc.metadata.get("filename")

            # Prefer doc_id because it uniquely identifies
            # the uploaded document.
            document_key = (
                doc_id
                or source
                or filename
                or f"unknown_{id(doc)}"
            )

            if document_key not in self.documents_by_source:

                self.documents_by_source[document_key] = []

            self.documents_by_source[document_key].append(doc)

        print(
            "[RETRIEVER] Documents available for balanced retrieval:"
        )

        for key, docs in self.documents_by_source.items():

            print(
                f"    {key}: {len(docs)} chunks"
            )

        # BUILD BM25

        self.bm25_docs = [
            doc.page_content.split()
            for doc in self.all_documents
        ]

        if self.bm25_docs:

            self.bm25 = BM25Okapi(
                self.bm25_docs
            )

        else:

            self.bm25 = None

    # DOCUMENT IDENTIFICATION

    def _document_key(self, doc):
        """
        Return stable identifier for the document.
        """

        metadata = doc.metadata or {}

        return (
            metadata.get("doc_id")
            or metadata.get("source")
            or metadata.get("filename")
            or f"unknown_{id(doc)}"
        )

    # CHUNK IDENTIFICATION

    def _chunk_key(self, doc):
        """
        Unique key for a chunk.
        """

        document_key = self._document_key(doc)

        content = (
            doc.page_content
            or ""
        ).strip()

        return (
            document_key,
            content
        )

    # DENSE RETRIEVAL

    def _dense_retrieval(self, query):

        dense_results = []

        print("\n[DENSE] Starting dense retrieval...")

        for store_index, vs in enumerate(self.stores):

            try:

                results = vs.similarity_search_with_score(
                    query,
                    k=self.dense_k_per_document
                )

                print(
                    f"[DENSE] Store {store_index + 1}: "
                    f"{len(results)} results"
                )

                for doc, distance in results:

                    if doc.metadata is None:
                        doc.metadata = {}

                    # FAISS distance:
                    # lower = better
                    doc.metadata["dense_score"] = float(
                        distance
                    )

                    dense_results.append(doc)

            except Exception as e:

                print(
                    f"❌ Dense retrieval error "
                    f"in store {store_index + 1}: {e}"
                )

                import traceback
                traceback.print_exc()

        print(
            f"[DENSE] Total dense chunks: "
            f"{len(dense_results)}"
        )

        return dense_results

    # SPARSE BM25 RETRIEVAL

    def _sparse_retrieval(self, query):

        sparse_results = []

        if not self.bm25:

            print("[BM25] BM25 is not available.")

            return sparse_results

        print("\n[BM25] Starting sparse retrieval...")

        tokenized_query = query.split()

        scores = self.bm25.get_scores(
            tokenized_query
        )

        # Group BM25 scores by document

        scored_by_document = {}

        for index, score in enumerate(scores):

            doc = self.all_documents[index]

            document_key = self._document_key(doc)

            if document_key not in scored_by_document:

                scored_by_document[document_key] = []

            scored_by_document[document_key].append(
                (doc, float(score))
            )

        # Top BM25 chunks PER DOCUMENT

        for document_key, scored_docs in scored_by_document.items():

            scored_docs.sort(
                key=lambda x: x[1],
                reverse=True
            )

            top_docs = scored_docs[
                :self.sparse_k_per_document
            ]

            for doc, score in top_docs:

                if doc.metadata is None:
                    doc.metadata = {}

                doc.metadata["bm25_score"] = score

                sparse_results.append(doc)

            print(
                f"[BM25] {document_key}: "
                f"{len(top_docs)} chunks"
            )

        print(
            f"[BM25] Total sparse chunks: "
            f"{len(sparse_results)}"
        )

        return sparse_results

    # HYBRID SCORE

    def _hybrid_score(self, doc):

        metadata = doc.metadata or {}

        dense_distance = metadata.get(
            "dense_score"
        )

        bm25_score = metadata.get(
            "bm25_score",
            0.0
        )

        # Dense score
        #
        # FAISS distance:
        # lower = better
        #
        # Convert it into a similarity-like value.

        if dense_distance is None:

            dense_similarity = 0.0

        else:

            dense_similarity = (
                1.0 / (1.0 + float(dense_distance))
            )

        # BM25

        bm25_component = float(
            bm25_score
        )

        # Hybrid score
        #
        # Dense = main signal
        # BM25  = lexical boost

        score = (
            dense_similarity
            +
            (0.30 * bm25_component)
        )

        return score

    # MERGE RESULTS

    def _merge_results(
        self,
        dense_results,
        sparse_results
    ):

        combined = (
            dense_results
            +
            sparse_results
        )

        unique_docs = {}

        for doc in combined:

            content = (
                doc.page_content
                or ""
            ).strip()

            if not content:
                continue

            key = self._chunk_key(doc)

            if key not in unique_docs:

                unique_docs[key] = doc

            else:

                # If the same chunk was found by both
                # dense and BM25 retrieval, keep the
                # strongest scores from both.

                existing = unique_docs[key]

                existing_dense = existing.metadata.get(
                    "dense_score"
                )

                new_dense = doc.metadata.get(
                    "dense_score"
                )

                if (
                    new_dense is not None
                    and (
                        existing_dense is None
                        or new_dense < existing_dense
                    )
                ):

                    existing.metadata[
                        "dense_score"
                    ] = new_dense

                existing_bm25 = existing.metadata.get(
                    "bm25_score",
                    0.0
                )

                new_bm25 = doc.metadata.get(
                    "bm25_score",
                    0.0
                )

                if new_bm25 > existing_bm25:

                    existing.metadata[
                        "bm25_score"
                    ] = new_bm25

        documents = list(
            unique_docs.values()
        )

        # Calculate final hybrid score

        for doc in documents:

            doc.metadata[
                "hybrid_score"
            ] = self._hybrid_score(doc)

        # Highest hybrid score first

        documents.sort(
            key=lambda doc: doc.metadata.get(
                "hybrid_score",
                0.0
            ),
            reverse=True
        )

        return documents

    # BALANCED MULTI-DOCUMENT SELECTION

    def _balanced_selection(
        self,
        documents,
        query
    ):
        """
        Select relevant chunks while preventing one document
        from dominating the final context.

        The method is relevance-aware rather than blindly
        allocating equal numbers to every document.
        """

        if not documents:

            return []

        # Group candidate chunks by document

        grouped = {}

        for doc in documents:

            document_key = self._document_key(doc)

            if document_key not in grouped:

                grouped[document_key] = []

            grouped[document_key].append(doc)

        # Sort chunks inside every document

        for document_key in grouped:

            grouped[document_key].sort(
                key=lambda doc: doc.metadata.get(
                    "hybrid_score",
                    0.0
                ),
                reverse=True
            )

        document_count = len(grouped)

        print(
            f"\n[BALANCED] Documents found: "
            f"{document_count}"
        )

        # Dynamic final context size

        if self.max_total_chunks is not None:

            total_limit = self.max_total_chunks

        else:

            if document_count <= 2:

                total_limit = 8

            elif document_count <= 4:

                total_limit = document_count * 3

            elif document_count <= 6:

                total_limit = document_count * 3

            elif document_count <= 10:

                total_limit = document_count * 2

            else:

                total_limit = min(
                    document_count * 2,
                    30
                )

        # Maximum chunks per document

        max_per_document = min(
            self.max_chunks_per_document,
            max(
                1,
                total_limit // document_count
            )
        )

        print(
            f"[BALANCED] Total chunk limit: "
            f"{total_limit}"
        )

        print(
            f"[BALANCED] Max chunks/document: "
            f"{max_per_document}"
        )

        # First pass:
        #
        # Give every document at least one relevant chunk
        # when available.

        selected = []

        selected_keys = set()

        for document_key, docs in grouped.items():

            if not docs:
                continue

            best_doc = docs[0]

            selected.append(best_doc)

            selected_keys.add(
                self._chunk_key(best_doc)
            )

        # Second pass:
        #
        # Round-robin additional chunks.
        #
        # This prevents the first document from taking
        # the entire context.

        current_round = 2

        while len(selected) < total_limit:

            added_this_round = False

            for document_key, docs in grouped.items():

                if len(selected) >= total_limit:
                    break

                # How many chunks from this document
                # are already selected?
                current_count = sum(
                    1
                    for doc in selected
                    if self._document_key(doc)
                    == document_key
                )

                if current_count >= max_per_document:
                    continue

                if current_count >= len(docs):
                    continue

                candidate = docs[current_count]

                candidate_key = self._chunk_key(
                    candidate
                )

                if candidate_key in selected_keys:
                    continue

                selected.append(candidate)

                selected_keys.add(
                    candidate_key
                )

                added_this_round = True

            if not added_this_round:
                break

            current_round += 1

        # Final global ordering
        #
        # Important:
        # We balance selection first, then order by relevance.

        selected.sort(
            key=lambda doc: doc.metadata.get(
                "hybrid_score",
                0.0
            ),
            reverse=True
        )

        # Print distribution

        distribution = {}

        for doc in selected:

            key = self._document_key(doc)

            distribution[key] = (
                distribution.get(key, 0)
                + 1
            )

        print(
            "\n[BALANCED] Final distribution:"
        )

        for key, count in distribution.items():

            print(
                f"    {key}: {count} chunks"
            )

        print(
            f"[BALANCED] Final chunks: "
            f"{len(selected)}"
        )

        return selected

    # PUBLIC RETRIEVAL METHOD

    def invoke(self, query):

        print("\n" + "=" * 80)
        print("[SMART RETRIEVER]")
        print("=" * 80)

        print(
            "[QUERY]",
            query
        )

        # 1. Dense retrieval

        dense_results = self._dense_retrieval(
            query
        )

        # 2. BM25 retrieval

        sparse_results = self._sparse_retrieval(
            query
        )

        # 3. Merge + hybrid scoring

        combined_documents = self._merge_results(
            dense_results,
            sparse_results
        )

        print(
            f"\n[HYBRID] Unique candidate chunks: "
            f"{len(combined_documents)}"
        )

        # 4. Balanced selection

        final_documents = self._balanced_selection(
            combined_documents,
            query
        )

        # 5. Debug final results

        print("\n[FINAL RETRIEVAL RESULTS]")

        for index, doc in enumerate(
            final_documents,
            start=1
        ):

            metadata = doc.metadata or {}

            print(
                "\n"
                + "-" * 70
            )

            print(
                f"Rank: {index}"
            )

            print(
                "Document ID:",
                metadata.get(
                    "doc_id",
                    "unknown"
                )
            )

            print(
                "Filename:",
                metadata.get(
                    "filename",
                    "unknown"
                )
            )

            print(
                "Hybrid Score:",
                metadata.get(
                    "hybrid_score",
                    0
                )
            )

            print(
                "Dense Distance:",
                metadata.get(
                    "dense_score",
                    "N/A"
                )
            )

            print(
                "BM25 Score:",
                metadata.get(
                    "bm25_score",
                    0
                )
            )

            print(
                "Content:",
                doc.page_content[:500]
            )

        print("\n" + "=" * 80)

        return final_documents