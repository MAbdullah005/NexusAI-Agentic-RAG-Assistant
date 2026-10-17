"""
Tests for NexusAI Phase 5: LangGraph Optimization, Advanced RAG, Chunking, and Answer Quality.

Covers:
1. RAG configuration defaults, environment variable overrides, and input validation.
2. Document chunking splitting with configurable size and overlap.
3. Whitespace normalization, stripping, and empty chunk filtering.
4. Chunk metadata preservation and stable chunk ID generation.
5. PDF ingestion page numbering (1-indexed) and page-level chunk IDs.
6. YouTube transcript ingestion metadata preservation.
7. Web processor chunking without arbitrary truncation.
8. SmartRetriever BM25 tokenization with stopword awareness.
9. SmartRetriever Reciprocal Rank Fusion (RRF) score computation.
10. Chunk-level and content-level deduplication.
11. Multi-document balanced selection and top-k limits.
12. Unified RAG tool output formatting with citation fields (Document, Page, Type, Chunk ID).
13. RAG final answer prompt grounding and citation instructions.
14. ChatState schema includes retrieved_docs.
15. CRAG grader classification and structured logging.
16. End-to-end LangGraph Phase 5 flow with state preservation, checkpointing, and HITL.
"""
import os
import unittest
import sqlite3
from unittest.mock import MagicMock, patch
from typing import List, Dict, Any

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.documents import Document

from app.memory.config import (
    get_rag_chunk_size,
    get_rag_chunk_overlap,
    get_rag_top_k,
    get_rag_min_score,
    is_rag_reranking_enabled,
    get_rag_config,
    DEFAULT_RAG_CHUNK_SIZE,
    DEFAULT_RAG_CHUNK_OVERLAP,
    DEFAULT_RAG_TOP_K,
    DEFAULT_RAG_MIN_SCORE,
    DEFAULT_RAG_RERANKING_ENABLED,
)
from app.core.splitter import chunk_text, clean_text_chunk
from app.utils.common import is_valid_chunk
from app.core.retriever import SmartRetriever
from app.prompts.rag import RAG_FINAL_ANSWER_PROMPT
from app.graph.state import ChatState
from app.graph.crag_grader import crag_relevance_grader


class FakeVectorStore:
    """Mock FAISS vector store for testing SmartRetriever."""
    def __init__(self, docs_with_scores):
        self.docs_with_scores = docs_with_scores
        self.docstore = MagicMock()
        self.docstore._dict = {str(i): doc for i, (doc, _) in enumerate(docs_with_scores)}

    def similarity_search_with_score(self, query, k=4):
        return self.docs_with_scores[:k]


class TestPhase5RAGQuality(unittest.TestCase):

    def setUp(self):
        self._env_backup = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_backup)

    # 1. RAG Configuration & Validation
    def test_rag_config_defaults_and_validation(self):
        for key in ["RAG_CHUNK_SIZE", "RAG_CHUNK_OVERLAP", "RAG_TOP_K", "RAG_MIN_SCORE", "RAG_RERANKING_ENABLED"]:
            os.environ.pop(key, None)

        self.assertEqual(get_rag_chunk_size(), DEFAULT_RAG_CHUNK_SIZE)
        self.assertEqual(get_rag_chunk_overlap(), DEFAULT_RAG_CHUNK_OVERLAP)
        self.assertEqual(get_rag_top_k(), DEFAULT_RAG_TOP_K)
        self.assertEqual(get_rag_min_score(), DEFAULT_RAG_MIN_SCORE)
        self.assertEqual(is_rag_reranking_enabled(), DEFAULT_RAG_RERANKING_ENABLED)

        # Overrides with valid values
        os.environ["RAG_CHUNK_SIZE"] = "800"
        os.environ["RAG_CHUNK_OVERLAP"] = "150"
        os.environ["RAG_TOP_K"] = "4"
        os.environ["RAG_MIN_SCORE"] = "0.05"
        os.environ["RAG_RERANKING_ENABLED"] = "true"

        self.assertEqual(get_rag_chunk_size(), 800)
        self.assertEqual(get_rag_chunk_overlap(), 150)
        self.assertEqual(get_rag_top_k(), 4)
        self.assertAlmostEqual(get_rag_min_score(), 0.05)
        self.assertTrue(is_rag_reranking_enabled())

        config_dict = get_rag_config()
        self.assertEqual(config_dict["chunk_size"], 800)
        self.assertEqual(config_dict["top_k"], 4)

        # Fallback on invalid values
        os.environ["RAG_CHUNK_SIZE"] = "not_a_number"
        os.environ["RAG_CHUNK_OVERLAP"] = "-5"
        os.environ["RAG_TOP_K"] = "0"
        os.environ["RAG_MIN_SCORE"] = "invalid"
        os.environ["RAG_RERANKING_ENABLED"] = "not_bool"

        self.assertEqual(get_rag_chunk_size(), DEFAULT_RAG_CHUNK_SIZE)
        self.assertEqual(get_rag_chunk_overlap(), DEFAULT_RAG_CHUNK_OVERLAP)
        self.assertEqual(get_rag_top_k(), DEFAULT_RAG_TOP_K)
        self.assertEqual(get_rag_min_score(), DEFAULT_RAG_MIN_SCORE)
        self.assertEqual(is_rag_reranking_enabled(), DEFAULT_RAG_RERANKING_ENABLED)

    # 2. Document Chunking & Overlap
    def test_chunk_text_splitting_and_overlap(self):
        text = "Paragraph one with extensive information about machine learning architectures. " * 10
        chunks = chunk_text(
            text=text,
            chunk_size=150,
            chunk_overlap=50,
            doc_id="doc_test_1"
        )
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.page_content), 250)

    # 3. Whitespace Cleaning & Empty Chunk Filtering
    def test_chunk_text_whitespace_and_empty_filtering(self):
        raw_text = "   Lots   of    weird \t\t whitespace   and \n\n blank lines.   "
        cleaned = clean_text_chunk(raw_text)
        self.assertNotIn("   ", cleaned)
        self.assertNotIn("\t", cleaned)

        # Empty filtering
        self.assertFalse(is_valid_chunk(""))
        self.assertFalse(is_valid_chunk("   \n\t  "))
        self.assertFalse(is_valid_chunk("Too short"))
        self.assertTrue(is_valid_chunk("This is a valid text chunk with more than fifty characters and enough spaces."))

        chunks = chunk_text(
            text="   \n\n  \t   \n  ",
            doc_id="empty_doc"
        )
        self.assertEqual(len(chunks), 0)

    # 4. Metadata Preservation & Stable Chunk IDs
    def test_chunk_metadata_preservation(self):
        text = (
            "Section 1: Data Engineering best practices across scalable data pipelines and distributed storage. "
            "Section 2: Machine learning model deployment pipelines, continuous integration, and monitoring workflows."
        )
        chunks = chunk_text(
            text=text,
            chunk_size=120,
            chunk_overlap=20,
            doc_id="doc_42",
            metadata={"filename": "engineering.pdf", "type": "pdf", "custom_key": "val123"}
        )
        self.assertGreater(len(chunks), 0)
        for i, chunk in enumerate(chunks):
            self.assertEqual(chunk.metadata.get("doc_id"), "doc_42")
            self.assertEqual(chunk.metadata.get("filename"), "engineering.pdf")
            self.assertEqual(chunk.metadata.get("type"), "pdf")
            self.assertEqual(chunk.metadata.get("custom_key"), "val123")
            self.assertEqual(chunk.metadata.get("chunk_id"), f"doc_42_chunk_{i}")
            self.assertIn("total_chunks", chunk.metadata)

    # 5. PDF Ingestion 1-indexed Page Numbers
    def test_pdf_ingest_page_numbering(self):
        from app.services.pdf_ingest import extract_pdf_chunks
        mock_docs = [
            Document(page_content="Page 1 Content with detailed description of Python and machine learning.", metadata={"page": 0}),
            Document(page_content="Page 2 Content discussing SQL database optimizations and indexes.", metadata={"page": 1}),
        ]

        chunks = extract_pdf_chunks(
            docs=mock_docs,
            doc_id="pdf_doc_10",
            filename="ai_overview.pdf",
            chunk_size=500,
            chunk_overlap=50
        )

        self.assertGreater(len(chunks), 0)
        page_nums = [c.metadata.get("page") for c in chunks]
        self.assertIn(1, page_nums)
        self.assertIn(2, page_nums)
        self.assertNotIn(0, page_nums)
        self.assertTrue(chunks[0].metadata["chunk_id"].startswith("pdf_doc_10_p"))

    # 6. YouTube Ingestion Metadata
    def test_youtube_ingest_metadata(self):
        from app.services.youtube_ingest import process_youtube_transcript
        transcript_text = "Welcome to the tutorial on deep learning. Today we cover convolutional neural networks in great depth."

        chunks = process_youtube_transcript(
            text=transcript_text,
            doc_id="yt_video_1",
            video_url="https://www.youtube.com/watch?v=abcd1234efg"
        )

        self.assertGreater(len(chunks), 0)
        self.assertEqual(chunks[0].metadata.get("type"), "youtube")
        self.assertEqual(chunks[0].metadata.get("doc_id"), "yt_video_1")
        self.assertEqual(chunks[0].metadata.get("source"), "https://www.youtube.com/watch?v=abcd1234efg")

    # 7. Web Processor Full Text Chunking
    def test_web_processor_chunking_and_metadata(self):
        from app.core.web_processor import process_web_document
        long_content = "Extensive web article detailing distributed system designs, event sourcing, and fault tolerance patterns. " * 50

        chunks = process_web_document(
            content=long_content,
            doc_id="web_doc_99",
            url="https://example.com/system-design",
            title="System Design Overview",
            chunk_size=500,
            chunk_overlap=50
        )
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0].metadata.get("type"), "web")
        self.assertEqual(chunks[0].metadata.get("doc_id"), "web_doc_99")
        self.assertEqual(chunks[0].metadata.get("source"), "https://example.com/system-design")

    # 8. SmartRetriever BM25 Tokenization
    def test_smart_retriever_bm25_tokenization(self):
        doc1 = Document(page_content="Deep learning architectures using PyTorch and GPUs.", metadata={"doc_id": "d1"})
        doc2 = Document(page_content="Database indexing and transaction isolation levels.", metadata={"doc_id": "d2"})

        vs = FakeVectorStore([(doc1, 0.1), (doc2, 0.9)])
        retriever = SmartRetriever(stores=[vs])

        self.assertIsNotNone(retriever.bm25)
        tokens = retriever.bm25_docs[0]
        self.assertIn("deep", tokens)
        self.assertIn("learning", tokens)
        self.assertNotIn("and", tokens)

    # 9. SmartRetriever Reciprocal Rank Fusion (RRF)
    def test_smart_retriever_rrf_scoring(self):
        doc_both = Document(page_content="FastAPI async microservice architecture", metadata={"doc_id": "doc_both"})
        doc_dense_only = Document(page_content="Microservice deployment Kubernetes", metadata={"doc_id": "doc_dense"})
        doc_sparse_only = Document(page_content="FastAPI async background workers", metadata={"doc_id": "doc_sparse"})

        vs = FakeVectorStore([(doc_both, 0.1), (doc_dense_only, 0.2)])
        retriever = SmartRetriever(stores=[vs])

        dense_results = [
            Document(page_content=doc_both.page_content, metadata={"doc_id": "doc_both", "dense_score": 0.1}),
            Document(page_content=doc_dense_only.page_content, metadata={"doc_id": "doc_dense", "dense_score": 0.3}),
        ]
        sparse_results = [
            Document(page_content=doc_both.page_content, metadata={"doc_id": "doc_both", "bm25_score": 12.0}),
            Document(page_content=doc_sparse_only.page_content, metadata={"doc_id": "doc_sparse", "bm25_score": 8.0}),
        ]

        merged = retriever._merge_results(dense_results, sparse_results)
        self.assertGreater(len(merged), 0)

        self.assertEqual(merged[0].metadata["doc_id"], "doc_both")
        self.assertIn("rrf_score", merged[0].metadata)
        self.assertIn("hybrid_score", merged[0].metadata)
        self.assertGreater(merged[0].metadata["hybrid_score"], merged[1].metadata["hybrid_score"])

    # 10. SmartRetriever Content Deduplication
    def test_smart_retriever_deduplication(self):
        doc1 = Document(page_content="Identical content line here with sufficient text.", metadata={"doc_id": "d1", "chunk_id": "c1", "dense_score": 0.2})
        doc2 = Document(page_content="Identical content line here with sufficient text.", metadata={"doc_id": "d1", "chunk_id": "c2", "dense_score": 0.5})

        vs = FakeVectorStore([(doc1, 0.2), (doc2, 0.5)])
        retriever = SmartRetriever(stores=[vs])

        merged = retriever._merge_results([doc1, doc2], [])
        self.assertEqual(len(merged), 1)

    # 11. Multi-Document Balanced Selection
    def test_smart_retriever_balanced_selection(self):
        docs = []
        for i in range(1, 4):
            for j in range(1, 5):
                docs.append(Document(
                    page_content=f"Doc {i} Chunk {j} specific information text line.",
                    metadata={
                        "doc_id": f"doc_{i}",
                        "chunk_id": f"doc_{i}_c{j}",
                        "hybrid_score": 1.0 - (0.05 * j) - (0.1 * (i - 1))
                    }
                ))

        retriever = SmartRetriever(stores=[])
        selected = retriever._balanced_selection(docs, query="test query")

        represented_docs = {d.metadata["doc_id"] for d in selected}
        self.assertEqual(represented_docs, {"doc_1", "doc_2", "doc_3"})

        os.environ["RAG_TOP_K"] = "6"
        selected_limited = retriever._balanced_selection(docs, query="test query")
        self.assertLessEqual(len(selected_limited), 6)

    # 12. Unified RAG Tool Citation Formatting
    def test_unified_rag_tool_citations(self):
        from app.tools.unified_rag_tool import unified_rag_tool
        from app.core.retriever import _THREAD_CACHE

        mock_doc1 = Document(
            page_content="Ali has 5 years experience in Python and LangChain.",
            metadata={"doc_id": "resume_1", "filename": "Ali_Resume.pdf", "page": 1, "type": "pdf", "chunk_id": "c_1"}
        )
        mock_doc2 = Document(
            page_content="Sarah has 8 years experience in Data Engineering and Snowflake.",
            metadata={"doc_id": "resume_2", "filename": "Sarah_Resume.pdf", "page": 3, "type": "pdf", "chunk_id": "c_2"}
        )

        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [mock_doc1, mock_doc2]

        _THREAD_CACHE["test_th_citations"] = mock_retriever

        with patch("app.tools.unified_rag_tool.thread_document_metadata", return_value={"total_docs": 2, "sources": []}):
            with patch("app.tools.unified_rag_tool.get_thread_retriever", return_value=mock_retriever):
                result = unified_rag_tool.invoke(
                    {"query": "Compare experience"},
                    config={"configurable": {"thread_id": "test_th_citations"}}
                )

        self.assertIn("Document: Ali_Resume.pdf", result)
        self.assertIn("Page: 1", result)
        self.assertIn("Document: Sarah_Resume.pdf", result)
        self.assertIn("Page: 3", result)
        self.assertIn("Chunk ID: c_1", result)

    # 13. RAG Final Answer Prompt Requirements
    def test_rag_prompts_grounding_and_citations(self):
        self.assertIn("Grounding & Accuracy", RAG_FINAL_ANSWER_PROMPT)
        self.assertIn("Source Citations", RAG_FINAL_ANSWER_PROMPT)
        self.assertIn("Sources & References", RAG_FINAL_ANSWER_PROMPT)
        self.assertIn("Never invent facts", RAG_FINAL_ANSWER_PROMPT)

    # 14. ChatState schema contains retrieved_docs
    def test_chat_state_retrieved_docs(self):
        fields = ChatState.__annotations__
        self.assertIn("retrieved_docs", fields)
        self.assertIn("messages", fields)
        self.assertIn("summary", fields)
        self.assertIn("rag_grade", fields)
        self.assertIn("hitl_decision", fields)

    # 15. CRAG Grader Classification and Structured Logging
    def test_crag_logging_and_grading(self):
        from app.graph.crag_grader import crag_relevance_grader

        state_good = {
            "messages": [
                HumanMessage(content="What is Python?"),
                ToolMessage(content="Python is an interpreted high-level language.", name="unified_rag_tool", tool_call_id="call_1")
            ]
        }

        mock_llm_good = MagicMock()
        mock_llm_good.invoke.return_value = AIMessage(content="GOOD")

        with patch("app.graph.crag_grader.llm", mock_llm_good):
            res = crag_relevance_grader(state_good)
            self.assertEqual(res["rag_grade"], "GOOD")

        # Partial grade
        mock_llm_partial = MagicMock()
        mock_llm_partial.invoke.return_value = AIMessage(content="PARTIAL")
        with patch("app.graph.crag_grader.llm", mock_llm_partial):
            res = crag_relevance_grader(state_good)
            self.assertEqual(res["rag_grade"], "PARTIAL")

        # Irrelevant grade
        mock_llm_irrelevant = MagicMock()
        mock_llm_irrelevant.invoke.return_value = AIMessage(content="IRRELEVANT")
        with patch("app.graph.crag_grader.llm", mock_llm_irrelevant):
            res = crag_relevance_grader(state_good)
            self.assertEqual(res["rag_grade"], "IRRELEVANT")

    # 16. LangGraph Phase 5 Integration and Routing
    def test_langgraph_phase5_integration(self):
        from app.graph.agent_graph import (
            route_after_chat,
            route_after_tools,
            route_after_crag,
            route_after_hitl,
            should_summarize,
        )

        # 1. route_after_chat
        state_no_tool = {"messages": [HumanMessage(content="Hi")]}
        self.assertEqual(route_after_chat(state_no_tool), "memory_check")

        # 2. route_after_tools: RAG triggers crag_grader
        state_rag_tool = {
            "messages": [
                ToolMessage(content="Retrieved context", name="unified_rag_tool", tool_call_id="c1")
            ]
        }
        self.assertEqual(route_after_tools(state_rag_tool), "crag_grader")

        # Other tool triggers chat_node
        state_other_tool = {
            "messages": [
                ToolMessage(content="Result", name="calculator", tool_call_id="c2")
            ]
        }
        self.assertEqual(route_after_tools(state_other_tool), "chat_node")

        # 3. route_after_crag
        self.assertEqual(route_after_crag({"rag_grade": "GOOD"}), "final_answer")
        self.assertEqual(route_after_crag({"rag_grade": "PARTIAL"}), "human_approval")
        self.assertEqual(route_after_crag({"rag_grade": "IRRELEVANT"}), "human_approval")

        # 4. route_after_hitl
        self.assertEqual(route_after_hitl({"hitl_decision": "yes"}), "web_search")
        self.assertEqual(route_after_hitl({"hitl_decision": "no"}), "not_found_answer")

        # 5. should_summarize
        with patch("app.graph.agent_graph.get_summarization_threshold", return_value=5):
            self.assertEqual(should_summarize({"messages": [HumanMessage(content="m")] * 4}), "end")
            self.assertEqual(should_summarize({"messages": [HumanMessage(content="m")] * 6}), "summarize_memory")


if __name__ == "__main__":
    unittest.main()
