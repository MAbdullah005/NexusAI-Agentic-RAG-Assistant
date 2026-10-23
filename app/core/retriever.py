from __future__ import annotations

import os
import sqlite3
import hashlib
from typing import Dict, Any, List

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from app.llm.embeddings import get_embeddings
from app.db.session import checkpointer
from rank_bm25 import BM25Okapi
from app.utils.logger import logger
from app.memory.config import get_rag_top_k, get_rag_min_score
from app.memory.historical_retriever import tokenize_text
from app.db.connection_adapter import get_db_connection

DB_PATH = "database/chatbot_conv.db"

#  CACHE 
_THREAD_CACHE: Dict[str, Any] = {}


# MAIN RETRIEVER
def get_thread_retriever(
    thread_id: str,
    source_type: str | None = None,
    selected_doc_ids: list[str] | None = None,
):
    """
    Load all vectorstores linked to a thread, optionally restricted to selected_doc_ids.
    """
    sorted_ids = ",".join(sorted(selected_doc_ids)) if selected_doc_ids else "all"
    cache_key = f"{thread_id}:{sorted_ids}"
    if source_type:
        cache_key += f":{source_type}"

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
    print("Selected doc IDs:", selected_doc_ids)

    # DATABASE
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if selected_doc_ids:
            placeholders = ",".join(["?"] * len(selected_doc_ids))
            cursor.execute(
                f"""
                SELECT
                    d.doc_id,
                    d.vectorstore_path,
                    d.filename,
                    d.source,
                    d.type
                FROM documents AS d
                INNER JOIN thread_documents AS td
                    ON d.doc_id = td.doc_id
                WHERE td.thread_id = ? AND d.doc_id IN ({placeholders})
                """,
                [thread_id] + list(selected_doc_ids)
            )
        else:
            cursor.execute(
                """
                SELECT
                    d.doc_id,
                    d.vectorstore_path,
                    d.filename,
                    d.source,
                    d.type
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
    repo_retrievers = []

    for doc_id, path, filename, doc_source, doc_type in rows:
        if doc_type in ("github", "repo"):
            try:
                from app.repocore.github import parse_github_url
                info = parse_github_url(doc_source)
                repo_retrievers.append(
                    RepoRetriever(
                        owner=info["owner"],
                        repo_name=info["repo"],
                        github_url=doc_source,
                        doc_id=doc_id,
                    )
                )
                print(f"[RETRIEVER] Loaded GitHub repo retriever: {info['owner']}/{info['repo']}")
            except Exception as e:
                print(f"[RETRIEVER] Failed to initialize RepoRetriever for {doc_source}: {e}")
            continue

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
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata["doc_id"] = doc_id
                if filename and not doc.metadata.get("filename"):
                    doc.metadata["filename"] = filename
                elif not doc.metadata.get("filename"):
                    doc.metadata["filename"] = os.path.basename(doc_source) if doc_source else doc_id

                if doc_source and (not doc.metadata.get("source") or doc.metadata.get("source") == "unknown"):
                    doc.metadata["source"] = doc_source

                if doc_type and (not doc.metadata.get("type") or doc.metadata.get("type") in ("document", "unknown")):
                    doc.metadata["type"] = doc_type

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
        f"{len(vectorstores)} vectorstore(s) and {len(repo_retrievers)} repo retriever(s)"
    )

    if not vectorstores and not repo_retrievers:

        print(
            "❌ No vectorstores or repo retrievers could be loaded."
        )

        return None

    # BUILD COMBINED RETRIEVER (SMART + REPO)

    retrievers = []
    if vectorstores:
        try:
            retrievers.append(SmartRetriever(vectorstores))
        except Exception as e:
            print(f"[RETRIEVER] SmartRetriever creation failed: {e}")

    if repo_retrievers:
        retrievers.extend(repo_retrievers)

    if not retrievers:
        print("[RETRIEVER] No vectorstores or repo retrievers could be loaded.")
        return None

    if len(retrievers) == 1:
        retriever = retrievers[0]
    else:
        retriever = CompositeRetriever(retrievers)

    # CACHE
    _THREAD_CACHE[cache_key] = retriever

    print("[RETRIEVER] Retriever created successfully.")
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
    conn = get_db_connection()
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
        for key in list(_THREAD_CACHE.keys())
        if key == thread_id or key.startswith(f"{thread_id}:") or key.startswith(f"{thread_id}_")
    ]

    for key in keys_to_remove:
        del _THREAD_CACHE[key]

    print(
        f"[CACHE] Cleared {len(keys_to_remove)} "
        f"retriever(s) for thread {thread_id}"
    )
        

def thread_document_metadata(thread_id: str, selected_doc_ids: list[str] | None = None) -> dict:

    if not thread_id:
        return {}

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if selected_doc_ids:
            placeholders = ",".join(["?"] * len(selected_doc_ids))
            cursor.execute(f"""
                SELECT
                    d.doc_id,
                    d.type,
                    d.source,
                    d.filename
                FROM documents AS d
                INNER JOIN thread_documents AS td
                    ON d.doc_id = td.doc_id
                WHERE td.thread_id = ? AND d.doc_id IN ({placeholders})
                ORDER BY d.created_at ASC
            """, [thread_id] + list(selected_doc_ids))
        else:
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

            name = source if (source and source.startswith("http")) else f"https://www.youtube.com/watch?v={source}"

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


class RepoRetriever:
    """
    Hybrid retriever for GitHub repositories indexed via RepoGuide.
    Queries pgvector chunks with reciprocal rank fusion (vector + full-text search + filename match),
    neighbor expansion, and Jina reranking.
    """
    def __init__(self, owner: str, repo_name: str, github_url: str, doc_id: str):
        self.owner = owner
        self.repo_name = repo_name
        self.github_url = github_url
        self.doc_id = doc_id

    def invoke(self, query: str) -> List[Any]:
        from langchain_core.documents import Document
        try:
            from app.repocore.rag import (
                build_search_query, rrf_fuse, find_neighbors_sync,
                MAX_RERANK
            )
            from app.repocore.vector_storage import (
                query_chunks_sync, keyword_search_sync, match_file_paths_sync
            )
            from app.repocore.reranking import sync_rerank
            from app.repocore.embeddings import embed_batch

            search_query = build_search_query(query, None)
            qvec = embed_batch([search_query])[0]

            v_docs, v_metas, _ = query_chunks_sync(self.owner, self.repo_name, qvec, 10)
            k_docs, k_metas = keyword_search_sync(self.owner, self.repo_name, search_query, 10)
            f_docs, f_metas = match_file_paths_sync(self.owner, self.repo_name, search_query, 10)
            docs, metas = rrf_fuse([(v_docs, v_metas), (k_docs, k_metas), (f_docs, f_metas)])
            if not docs:
                return []

            n_docs, n_metas = find_neighbors_sync(metas, self.owner, self.repo_name)
            docs = docs + n_docs
            metas = metas + n_metas
            seen = set()
            deduped_docs, deduped_metas = [], []
            for d, m in zip(docs, metas):
                key = (m["file_path"], m["start_line"], m["end_line"])
                if key in seen:
                    continue
                seen.add(key)
                deduped_docs.append(d)
                deduped_metas.append(m)
            deduped_docs = deduped_docs[:MAX_RERANK]
            deduped_metas = deduped_metas[:MAX_RERANK]
            reranked = sync_rerank(query, deduped_docs, len(deduped_docs))
            ordered_docs = [deduped_docs[i] for i, _ in reranked]
            ordered_metas = [deduped_metas[i] for i, _ in reranked]
            docs = ordered_docs[:8]
            metas = ordered_metas[:8]

            lc_docs = []
            for d, m in zip(docs, metas):
                c_sha = m.get("commit_sha", "main")
                f_path = m.get("file_path", "")
                s_line = m.get("start_line", 1)
                e_line = m.get("end_line", 1)
                source_link = f"{self.github_url}/blob/{c_sha}/{f_path}#L{s_line}-L{e_line}"
                lc_docs.append(Document(
                    page_content=d,
                    metadata={
                        "doc_id": self.doc_id,
                        "type": "github",
                        "source": self.github_url,
                        "filename": f"{self.owner}/{self.repo_name}",
                        "file_path": f_path,
                        "start_line": s_line,
                        "end_line": e_line,
                        "commit_sha": c_sha,
                        "source_link": source_link,
                    }
                ))
            return lc_docs
        except Exception as e:
            logger.error(f"[REPO RETRIEVER] Retrieval error for {self.owner}/{self.repo_name}: {e}", exc_info=True)
            return []


class CompositeRetriever:
    """Combines results from multiple retrievers (e.g. SmartRetriever for PDFs/Web + RepoRetriever for GitHub repos)."""
    def __init__(self, retrievers: list):
        self.retrievers = retrievers

    def invoke(self, query: str) -> List[Any]:
        combined_docs: List[Any] = []
        for r in self.retrievers:
            try:
                res = r.invoke(query)
                if res:
                    combined_docs.extend(res)
            except Exception as e:
                logger.error(f"[COMPOSITE RETRIEVER] Sub-retriever error: {e}", exc_info=True)
        return combined_docs


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
        dense_k_per_document=None,
        sparse_k_per_document=None,
        max_chunks_per_document=None,
        min_chunks_per_document=1,
        max_total_chunks=None,
    ):
        self.stores = stores

        configured_top_k = get_rag_top_k()
        self.dense_k_per_document = dense_k_per_document or max(4, configured_top_k)
        self.sparse_k_per_document = sparse_k_per_document or max(4, configured_top_k)
        self.max_chunks_per_document = max_chunks_per_document or max(4, configured_top_k)
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
            tokenize_text(doc.page_content) or ["__empty__"]
            for doc in self.all_documents
        ]

        if self.bm25_docs and any(t != ["__empty__"] for t in self.bm25_docs):

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
        Unique key for a chunk combining document identity and normalized content hash.
        """
        metadata = doc.metadata or {}
        chunk_id = metadata.get("chunk_id")
        if chunk_id:
            return str(chunk_id)

        document_key = self._document_key(doc)
        content = (
            doc.page_content
            or ""
        ).strip()
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

        return f"{document_key}_{content_hash}"

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

        tokenized_query = tokenize_text(query)
        if not tokenized_query:
            tokenized_query = [w.lower() for w in query.split() if w.strip()]

        if not tokenized_query:
            return sparse_results

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

    # RECIPROCAL RANK FUSION (RRF) & MERGE RESULTS

    def _merge_results(
        self,
        dense_results,
        sparse_results
    ):
        """
        Merge dense and sparse results using Reciprocal Rank Fusion (RRF).
        RRF(d) = sum_{m in {dense, bm25}} 1 / (60 + rank_m(d))
        Applies content deduplication and minimum score filtering.
        """
        unique_docs = {}

        # 1. Rank dense results
        dense_candidates = []
        for doc in dense_results:
            key = self._chunk_key(doc)
            dist = doc.metadata.get("dense_score")
            sim = 1.0 / (1.0 + float(dist)) if dist is not None else 0.0
            doc.metadata["dense_sim"] = sim
            dense_candidates.append((key, doc, sim))

        dense_candidates.sort(key=lambda x: x[2], reverse=True)
        dense_ranks = {}
        for rank, (key, doc, sim) in enumerate(dense_candidates, start=1):
            if key not in dense_ranks:
                dense_ranks[key] = rank
            if key not in unique_docs:
                unique_docs[key] = doc
            else:
                existing_sim = unique_docs[key].metadata.get("dense_sim", 0.0)
                if sim > existing_sim:
                    unique_docs[key].metadata["dense_sim"] = sim
                    unique_docs[key].metadata["dense_score"] = doc.metadata.get("dense_score")

        # 2. Rank sparse results
        sparse_candidates = []
        for doc in sparse_results:
            key = self._chunk_key(doc)
            score = float(doc.metadata.get("bm25_score", 0.0))
            if score > 0:
                sparse_candidates.append((key, doc, score))

        sparse_candidates.sort(key=lambda x: x[2], reverse=True)
        sparse_ranks = {}
        for rank, (key, doc, score) in enumerate(sparse_candidates, start=1):
            if key not in sparse_ranks:
                sparse_ranks[key] = rank
            if key not in unique_docs:
                unique_docs[key] = doc
            else:
                existing_score = float(unique_docs[key].metadata.get("bm25_score", 0.0))
                if score > existing_score:
                    unique_docs[key].metadata["bm25_score"] = score

        # 3. Compute RRF score
        rrf_constant = 60.0
        min_score = get_rag_min_score()

        documents = []
        for key, doc in unique_docs.items():
            r_dense = dense_ranks.get(key)
            r_sparse = sparse_ranks.get(key)

            rrf_score = 0.0
            if r_dense is not None:
                rrf_score += 1.0 / (rrf_constant + r_dense)
            if r_sparse is not None:
                rrf_score += 1.0 / (rrf_constant + r_sparse)

            # Small dense similarity bonus for deterministic tie-breaking
            dense_sim = doc.metadata.get("dense_sim", 0.0)
            final_score = rrf_score + (0.001 * dense_sim)

            doc.metadata["rrf_score"] = rrf_score
            doc.metadata["hybrid_score"] = final_score

            if min_score > 0 and final_score < min_score:
                continue

            documents.append(doc)

        # Sort by hybrid score descending
        documents.sort(
            key=lambda doc: doc.metadata.get("hybrid_score", 0.0),
            reverse=True
        )

        # 4. Content-level deduplication
        seen_contents = set()
        deduped = []
        for doc in documents:
            clean_content = " ".join((doc.page_content or "").strip().split()).lower()
            if not clean_content:
                continue
            content_hash = hashlib.sha256(clean_content.encode("utf-8")).hexdigest()
            if content_hash in seen_contents:
                continue
            seen_contents.add(content_hash)
            deduped.append(doc)

        return deduped

    # RELEVANCE-FIRST BALANCED MULTI-DOCUMENT SELECTION

    def _balanced_selection(
        self,
        documents,
        query
    ):
        """
        Select relevant chunks across documents.
        Prioritizes query-relevant documents and prevents irrelevant attached documents
        from choking the context of relevant documents, while ensuring balanced
        representation when multiple documents are genuinely relevant.
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

        # Sort chunks inside each document by hybrid score descending
        for document_key in grouped:
            grouped[document_key].sort(
                key=lambda doc: doc.metadata.get(
                    "hybrid_score",
                    0.0
                ),
                reverse=True
            )

        document_count = len(grouped)
        top_overall_score = documents[0].metadata.get("hybrid_score", 0.0) if documents else 0.0

        print(
            f"\n[BALANCED] Documents found: {document_count}, Top score: {top_overall_score:.4f}"
        )

        # Filter candidate documents for query relevance:
        # A document is considered relevant if its top chunk has a positive BM25 score
        # OR its hybrid score is at least 45% of the highest scored chunk across all documents.
        relevant_groups = {}
        for document_key, docs in grouped.items():
            if not docs:
                continue
            best_chunk = docs[0]
            best_score = best_chunk.metadata.get("hybrid_score", 0.0)
            bm25_score = best_chunk.metadata.get("bm25_score", 0.0)

            if top_overall_score <= 0 or (best_score >= 0.45 * top_overall_score) or (bm25_score > 0):
                relevant_groups[document_key] = docs
            else:
                print(f"[BALANCED] Document '{document_key}' filtered out as irrelevant (score: {best_score:.4f} vs top {top_overall_score:.4f}, BM25: {bm25_score})")

        # Fallback: if strict filtering excluded all documents, keep original grouping
        active_groups = relevant_groups if relevant_groups else grouped
        active_doc_count = len(active_groups)

        # Dynamic final context size respecting configured RAG top_k
        configured_top_k = get_rag_top_k()
        if self.max_total_chunks is not None:
            total_limit = self.max_total_chunks
        else:
            total_limit = max(configured_top_k, active_doc_count)

        # Maximum chunks per document
        if active_doc_count <= 1:
            max_per_document = total_limit
        else:
            # Allow flexible allocation so relevant documents are not starved
            max_per_document = max(2, (total_limit + active_doc_count - 1) // active_doc_count)

        print(
            f"[BALANCED] Active relevant documents: {active_doc_count}/{document_count}"
        )
        print(
            f"[BALANCED] Total chunk limit: {total_limit}, Max chunks/document: {max_per_document}"
        )

        selected = []
        selected_keys = set()

        # Pass 1: Give every relevant document its best chunk
        for document_key, docs in active_groups.items():
            if not docs:
                continue
            best_doc = docs[0]
            cand_key = self._chunk_key(best_doc)
            selected.append(best_doc)
            selected_keys.add(cand_key)

        # Pass 2: Round-robin additional chunks across relevant documents up to max_per_document
        current_round = 2
        while len(selected) < total_limit:
            added_this_round = False
            for document_key, docs in active_groups.items():
                if len(selected) >= total_limit:
                    break

                current_count = sum(
                    1
                    for doc in selected
                    if self._document_key(doc) == document_key
                )

                if current_count >= max_per_document:
                    continue
                if current_count >= len(docs):
                    continue

                candidate = docs[current_count]
                candidate_key = self._chunk_key(candidate)
                if candidate_key in selected_keys:
                    continue

                selected.append(candidate)
                selected_keys.add(candidate_key)
                added_this_round = True

            if not added_this_round:
                break
            current_round += 1

        # Pass 3: If still under total_limit, fill remaining capacity from best remaining chunks
        if len(selected) < total_limit:
            remaining_candidates = []
            for document_key, docs in active_groups.items():
                for doc in docs:
                    cand_key = self._chunk_key(doc)
                    if cand_key not in selected_keys:
                        remaining_candidates.append(doc)

            remaining_candidates.sort(
                key=lambda doc: doc.metadata.get("hybrid_score", 0.0),
                reverse=True
            )

            for candidate in remaining_candidates:
                if len(selected) >= total_limit:
                    break
                cand_key = self._chunk_key(candidate)
                if cand_key not in selected_keys:
                    selected.append(candidate)
                    selected_keys.add(cand_key)

        # Final global ordering by relevance
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
            distribution[key] = distribution.get(key, 0) + 1

        print("\n[BALANCED] Final distribution:")
        for key, count in distribution.items():
            print(f"    {key}: {count} chunks")
        print(f"[BALANCED] Final chunks: {len(selected)}")

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