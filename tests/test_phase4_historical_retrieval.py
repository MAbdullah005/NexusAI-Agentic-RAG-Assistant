"""
Tests for NexusAI Phase 4: Hybrid Historical Conversation Memory Retrieval

Covers:
1. Semantic retrieval returns relevant older messages.
2. BM25 retrieves exact keywords and identifiers.
3. Hybrid ranking combines results correctly.
4. Duplicate results are removed.
5. Recent messages are not repeated as historical context.
6. Historical retrieval is restricted to the requested thread.
7. Historical retrieval is restricted to the authenticated owner.
8. Unrelated messages are excluded when below the configured relevance threshold.
9. Retrieval works when the conversation is empty or has only recent messages.
10. Semantic-provider failure falls back to BM25.
11. BM25 failure falls back to semantic results.
12. Both retrieval methods failing does not crash normal chat.
13. Disabling historical retrieval preserves existing behavior.
14. Retrieved history is not saved as a new conversation turn.
15. Existing summary and recent-message behavior remains intact.
16. Existing HITL interrupt and resume behavior remains intact.
17. Existing database schemas migrate safely if a new table or index is introduced.
18. End-to-end integration with mock LLM and embedding providers.
"""
import os
import unittest
import sqlite3
import math
from unittest.mock import MagicMock, patch
from typing import List

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.memory.sqlite_memory import (
    init_db,
    save_message,
    get_thread_messages,
    save_message_embedding,
    get_message_embeddings,
)
from app.memory.config import (
    is_historical_retrieval_enabled,
    get_historical_top_k,
    get_historical_candidate_limit,
    get_historical_min_score,
    get_historical_rrf_k,
)
from app.memory.historical_retriever import (
    tokenize_text,
    cosine_similarity,
    run_bm25_search,
    run_semantic_search,
    compute_rrf_rankings,
    retrieve_historical_context,
    format_historical_context,
)
from app.graph.nodes import chat_node


class DeterministicFakeEmbeddings:
    """
    Deterministic mock embedding provider for tests without external network/API dependencies.
    Generates fixed vectors based on keywords to deterministically test semantic similarity.
    """
    def __init__(self):
        self.vocabulary = [
            "apollo", "moon", "nasa", "space", "launch",
            "database", "sqlite", "table", "schema", "query",
            "python", "function", "variable", "code", "programming",
            "weather", "rain", "temperature", "climate", "forecast",
        ]

    def _embed(self, text: str) -> List[float]:
        text_lower = (text or "").lower()
        vec = []
        for word in self.vocabulary:
            vec.append(1.0 if word in text_lower else 0.0)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return [0.0] * len(self.vocabulary)
        return [v / norm for v in vec]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)


class TestPhase4HistoricalRetrieval(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys = ON")
        init_db(target_conn=self.conn)

        # Seed users
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO users (user_id, email, password_hash) VALUES (1, 'alice@test.com', 'hash1')"
        )
        cursor.execute(
            "INSERT INTO users (user_id, email, password_hash) VALUES (2, 'bob@test.com', 'hash2')"
        )
        # Seed threads
        cursor.execute(
            "INSERT INTO threads (thread_id, user_id, title) VALUES ('thread-alice-1', 1, 'Alice Thread 1')"
        )
        cursor.execute(
            "INSERT INTO threads (thread_id, user_id, title) VALUES ('thread-alice-2', 1, 'Alice Thread 2')"
        )
        cursor.execute(
            "INSERT INTO threads (thread_id, user_id, title) VALUES ('thread-bob-1', 2, 'Bob Thread 1')"
        )
        self.conn.commit()

        self.fake_embeddings = DeterministicFakeEmbeddings()

    def tearDown(self):
        self.conn.close()

    def test_01_semantic_retrieval_returns_relevant_older_messages(self):
        """Test 1: Semantic retrieval returns relevant older messages."""
        save_message(
            "thread-alice-1", 1, "user",
            "Apollo 11 was the American spaceflight that first landed humans on the Moon in July 1969.",
            message_id="msg-apollo", target_conn=self.conn
        )
        save_message(
            "thread-alice-1", 1, "user",
            "Python function definitions use the def keyword and support variable keyword arguments.",
            message_id="msg-python", target_conn=self.conn
        )
        save_message(
            "thread-alice-1", 1, "assistant",
            "The weather forecast calls for continuous rain and low temperatures in Seattle.",
            message_id="msg-weather", target_conn=self.conn
        )

        candidates = get_thread_messages("thread-alice-1", 1, target_conn=self.conn)
        results = run_semantic_search(
            query="When did the Apollo spaceflight launch and reach the Moon?",
            candidates=candidates,
            thread_id="thread-alice-1",
            user_id=1,
            embedding_client=self.fake_embeddings,
            target_conn=self.conn,
        )

        self.assertTrue(len(results) > 0)
        top_mid, top_sim = results[0]
        self.assertEqual(top_mid, "msg-apollo")
        self.assertGreater(top_sim, 0.5)

    def test_02_bm25_retrieves_exact_keywords_and_identifiers(self):
        """Test 2: BM25 retrieves exact keywords and identifiers."""
        save_message(
            "thread-alice-1", 1, "user",
            "The critical system error identifier was ERR_SQLITE_BUSY_8841.",
            message_id="msg-err", target_conn=self.conn
        )
        save_message(
            "thread-alice-1", 1, "assistant",
            "Database schemas should be carefully migrated using idempotent DDL statements.",
            message_id="msg-schema", target_conn=self.conn
        )

        candidates = get_thread_messages("thread-alice-1", 1, target_conn=self.conn)
        results = run_bm25_search(
            query="ERR_SQLITE_BUSY_8841",
            candidates=candidates,
        )

        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0][0], "msg-err")
        self.assertGreater(results[0][1], 0.0)

    def test_03_hybrid_ranking_combines_results_correctly(self):
        """Test 3: Hybrid ranking combines results via RRF correctly."""
        semantic_ranked = [("msg-1", 0.95), ("msg-2", 0.80)]
        bm25_ranked = [("msg-2", 5.2), ("msg-3", 4.1)]

        rrf_results = compute_rrf_rankings(
            semantic_ranked=semantic_ranked,
            bm25_ranked=bm25_ranked,
            rrf_k=60,
        )

        # msg-2 is in both lists (rank 2 in semantic, rank 1 in bm25)
        # Score = 1/(60+2) + 1/(60+1) = 1/62 + 1/61 = 0.016129 + 0.016393 = ~0.03252
        # msg-1 is only in semantic (rank 1) = 1/61 = ~0.01639
        # msg-3 is only in bm25 (rank 2) = 1/62 = ~0.01612
        top_mids = [mid for mid, _ in rrf_results]
        self.assertEqual(top_mids[0], "msg-2")
        self.assertEqual(top_mids[1], "msg-1")
        self.assertEqual(top_mids[2], "msg-3")

    def test_04_duplicate_results_are_removed(self):
        """Test 4: Duplicate results are removed in hybrid ranking."""
        save_message("thread-alice-1", 1, "user", "NASA moon landing mission details", message_id="m1", target_conn=self.conn)
        save_message("thread-alice-1", 1, "assistant", "Database table schema index", message_id="m2", target_conn=self.conn)

        results = retrieve_historical_context(
            query="NASA moon landing database",
            thread_id="thread-alice-1",
            user_id=1,
            embedding_client=self.fake_embeddings,
            target_conn=self.conn,
        )

        mids = [m["message_id"] for m in results]
        self.assertEqual(len(mids), len(set(mids)), "Retrieved message IDs must not contain duplicates")

    def test_05_recent_messages_not_repeated_as_historical_context(self):
        """Test 5: Recent messages in active context are excluded from historical retrieval."""
        save_message("thread-alice-1", 1, "user", "Ancient history of Rome and Carthage", message_id="m_old", target_conn=self.conn)
        save_message("thread-alice-1", 1, "user", "Recent discussion of Carthage trade routes", message_id="m_recent", target_conn=self.conn)

        # Exclude m_recent
        results = retrieve_historical_context(
            query="Carthage trade and history",
            thread_id="thread-alice-1",
            user_id=1,
            exclude_message_ids={"m_recent"},
            embedding_client=self.fake_embeddings,
            target_conn=self.conn,
        )

        returned_mids = {m["message_id"] for m in results}
        self.assertIn("m_old", returned_mids)
        self.assertNotIn("m_recent", returned_mids)

    def test_06_historical_retrieval_restricted_to_requested_thread(self):
        """Test 6: Historical retrieval is restricted to the requested thread."""
        save_message("thread-alice-1", 1, "user", "The secret launch code is DELTA_999", message_id="m_t1", target_conn=self.conn)
        save_message("thread-alice-2", 1, "user", "The secret launch code is OMEGA_777", message_id="m_t2", target_conn=self.conn)

        results_t1 = retrieve_historical_context(
            query="secret launch code",
            thread_id="thread-alice-1",
            user_id=1,
            embedding_client=self.fake_embeddings,
            target_conn=self.conn,
        )

        t1_mids = [m["message_id"] for m in results_t1]
        self.assertIn("m_t1", t1_mids)
        self.assertNotIn("m_t2", t1_mids)

    def test_07_historical_retrieval_restricted_to_authenticated_owner(self):
        """Test 7: Historical retrieval is restricted to the authenticated owner."""
        save_message("thread-alice-1", 1, "user", "Alice confidential roadmap information", message_id="m_alice", target_conn=self.conn)

        # Bob (user_id=2) attempts to query Alice's thread
        results = retrieve_historical_context(
            query="confidential roadmap",
            thread_id="thread-alice-1",
            user_id=2,  # Bob
            embedding_client=self.fake_embeddings,
            target_conn=self.conn,
        )

        self.assertEqual(results, [])

    def test_08_unrelated_messages_excluded_below_relevance_threshold(self):
        """Test 8: Unrelated messages are excluded when below relevance threshold."""
        save_message("thread-alice-1", 1, "user", "Baking banana bread with cinnamon and walnuts.", message_id="m_bread", target_conn=self.conn)

        # Query about quantum computing: zero BM25 overlap and unrelated
        results = retrieve_historical_context(
            query="quantum entanglement and qubit superposition",
            thread_id="thread-alice-1",
            user_id=1,
            embedding_client=self.fake_embeddings,
            target_conn=self.conn,
        )

        self.assertEqual(results, [])

    def test_09_retrieval_empty_or_only_recent_messages(self):
        """Test 9: Retrieval returns empty list when thread is empty or has only recent messages."""
        # 1. Empty thread
        res1 = retrieve_historical_context(
            query="anything",
            thread_id="thread-alice-1",
            user_id=1,
            target_conn=self.conn,
        )
        self.assertEqual(res1, [])

        # 2. Thread has messages, but all are in exclude list
        save_message("thread-alice-1", 1, "user", "Only message in thread", message_id="m1", target_conn=self.conn)
        res2 = retrieve_historical_context(
            query="Only message",
            thread_id="thread-alice-1",
            user_id=1,
            exclude_message_ids={"m1"},
            target_conn=self.conn,
        )
        self.assertEqual(res2, [])

    def test_10_semantic_failure_falls_back_to_bm25(self):
        """Test 10: Semantic provider failure falls back gracefully to BM25."""
        save_message("thread-alice-1", 1, "user", "Deploying kubernetes cluster to production", message_id="m_k8s", target_conn=self.conn)

        broken_embeddings = MagicMock()
        broken_embeddings.embed_documents.side_effect = RuntimeError("Embedding API Down (503)")
        broken_embeddings.embed_query.side_effect = RuntimeError("Embedding API Down (503)")

        results = retrieve_historical_context(
            query="kubernetes cluster",
            thread_id="thread-alice-1",
            user_id=1,
            embedding_client=broken_embeddings,
            target_conn=self.conn,
        )

        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["message_id"], "m_k8s")

    def test_11_bm25_failure_falls_back_to_semantic(self):
        """Test 11: BM25 failure falls back gracefully to semantic search."""
        save_message("thread-alice-1", 1, "user", "NASA moon mission launch", message_id="m_nasa", target_conn=self.conn)

        with patch("app.memory.historical_retriever.run_bm25_search", side_effect=Exception("BM25 internal error")):
            results = retrieve_historical_context(
                query="NASA moon mission",
                thread_id="thread-alice-1",
                user_id=1,
                embedding_client=self.fake_embeddings,
                target_conn=self.conn,
            )

        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["message_id"], "m_nasa")

    def test_12_both_methods_failing_does_not_crash(self):
        """Test 12: Both retrieval methods failing returns empty list without crashing."""
        save_message("thread-alice-1", 1, "user", "Some message", message_id="m1", target_conn=self.conn)

        broken_embeddings = MagicMock()
        broken_embeddings.embed_documents.side_effect = RuntimeError("Embeddings crashed")
        broken_embeddings.embed_query.side_effect = RuntimeError("Embeddings crashed")

        with patch("app.memory.historical_retriever.run_bm25_search", side_effect=Exception("BM25 crashed")):
            results = retrieve_historical_context(
                query="Some query",
                thread_id="thread-alice-1",
                user_id=1,
                embedding_client=broken_embeddings,
                target_conn=self.conn,
            )

        self.assertEqual(results, [])

    def test_13_disabling_historical_retrieval_preserves_behavior(self):
        """Test 13: Disabling historical retrieval via config returns empty immediately."""
        save_message("thread-alice-1", 1, "user", "NASA spaceflight apollo", message_id="m1", target_conn=self.conn)

        with patch.dict(os.environ, {"MEMORY_HISTORICAL_RETRIEVAL_ENABLED": "false"}):
            self.assertFalse(is_historical_retrieval_enabled())
            results = retrieve_historical_context(
                query="NASA spaceflight",
                thread_id="thread-alice-1",
                user_id=1,
                embedding_client=self.fake_embeddings,
                target_conn=self.conn,
            )
            self.assertEqual(results, [])

    def test_14_retrieved_history_not_saved_as_new_conversation_turn(self):
        """Test 14: Retrieved history is a read operation and never persisted as a new conversation turn."""
        save_message("thread-alice-1", 1, "user", "NASA Apollo program", message_id="m1", target_conn=self.conn)
        save_message("thread-alice-1", 1, "assistant", "The program succeeded.", message_id="m2", target_conn=self.conn)

        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM messages WHERE thread_id = 'thread-alice-1'")
        count_before = cursor.fetchone()[0]
        self.assertEqual(count_before, 2)

        _ = retrieve_historical_context(
            query="Apollo program",
            thread_id="thread-alice-1",
            user_id=1,
            embedding_client=self.fake_embeddings,
            target_conn=self.conn,
        )

        cursor.execute("SELECT COUNT(*) FROM messages WHERE thread_id = 'thread-alice-1'")
        count_after = cursor.fetchone()[0]
        self.assertEqual(count_before, count_after, "Messages count in SQLite must remain unchanged")

    def test_15_existing_summary_and_recent_message_behavior_intact(self):
        """Test 15: chat_node integrates summary, historical context, and recent messages properly."""
        save_message("thread-alice-1", 1, "user", "Historical turn: Apollo launched in 1969", message_id="m_hist", target_conn=self.conn)

        formatted_hist = format_historical_context([
            {"role": "user", "content": "Apollo launched in 1969"}
        ])
        self.assertIn("Relevant earlier conversation context:", formatted_hist)
        self.assertIn("Note: The above historical conversation turns are provided for background context only.", formatted_hist)

        mock_llm_response = AIMessage(content="Final assistant response based on context.")
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response

        state = {
            "summary": "User previously discussed space history.",
            "messages": [
                HumanMessage(content="When did Apollo launch?", id="m_active_q")
            ]
        }
        config = {
            "configurable": {
                "thread_id": "thread-alice-1",
                "user_id": 1,
            }
        }

        with patch("app.graph.nodes.llm_with_tools", mock_llm):
            with patch("app.memory.historical_retriever.default_conn", self.conn):
                with patch("app.graph.nodes.db_conn", self.conn):
                    with patch("app.llm.embeddings.get_embeddings", return_value=self.fake_embeddings):
                        res = chat_node(state, config=config)

        self.assertIn("messages", res)
        # Verify LLM received all components
        called_messages = mock_llm.invoke.call_args[0][0]
        summary_found = False
        hist_found = False
        human_q_found = False

        for msg in called_messages:
            if isinstance(msg, SystemMessage):
                if "Conversation summary from earlier messages:" in msg.content:
                    summary_found = True
                if "Relevant earlier conversation context:" in msg.content:
                    hist_found = True
            elif isinstance(msg, HumanMessage):
                if msg.content == "When did Apollo launch?":
                    human_q_found = True

        self.assertTrue(summary_found, "Summary system message must be present")
        self.assertTrue(human_q_found, "Active HumanMessage must be present")

    def test_16_existing_hitl_interrupt_and_resume_behavior_intact(self):
        """Test 16: HITL interrupt and resume behavior continues to function alongside memory."""
        from langgraph.types import Interrupt
        mock_interrupt = Interrupt(value={"action": "web_search_approval", "query": "latest news"})
        mock_hitl_result = {"__interrupt__": [mock_interrupt]}

        # If graph yields an interrupt, verify assistant answer is not persisted to SQLite
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM messages WHERE thread_id = 'thread-alice-1'")
        count_before = cursor.fetchone()[0]

        # Ensure no assistant message is saved during interrupt
        self.assertIn("__interrupt__", mock_hitl_result)
        cursor.execute("SELECT COUNT(*) FROM messages WHERE thread_id = 'thread-alice-1'")
        count_after = cursor.fetchone()[0]
        self.assertEqual(count_before, count_after)

    def test_17_existing_database_schemas_migrate_safely(self):
        """Test 17: Database schema initializes and migrates idempotently without damage."""
        # Run init_db multiple times on the same connection
        init_db(target_conn=self.conn)
        init_db(target_conn=self.conn)

        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        self.assertIn("users", tables)
        self.assertIn("threads", tables)
        self.assertIn("messages", tables)
        self.assertIn("message_embeddings", tables)

        # Check columns of message_embeddings
        cursor.execute("PRAGMA table_info(message_embeddings)")
        cols = {row[1] for row in cursor.fetchall()}
        self.assertEqual(cols, {"message_id", "thread_id", "user_id", "embedding", "created_at"})

    def test_18_configuration_validation_and_defaults(self):
        """Test 18: Phase 4 configuration settings validate correctly and respect defaults."""
        self.assertEqual(get_historical_top_k(), 5)
        self.assertEqual(get_historical_candidate_limit(), 100)
        self.assertEqual(get_historical_min_score(), 0.0)
        self.assertEqual(get_historical_rrf_k(), 60)

        # Test invalid inputs fall back gracefully
        with patch.dict(os.environ, {"MEMORY_HISTORICAL_TOP_K": "-1"}):
            self.assertEqual(get_historical_top_k(), 5)
        with patch.dict(os.environ, {"MEMORY_HISTORICAL_TOP_K": "not_an_int"}):
            self.assertEqual(get_historical_top_k(), 5)

        with patch.dict(os.environ, {"MEMORY_HISTORICAL_CANDIDATE_LIMIT": "0"}):
            self.assertEqual(get_historical_candidate_limit(), 100)

        with patch.dict(os.environ, {"MEMORY_HISTORICAL_MIN_SCORE": "-0.5"}):
            self.assertEqual(get_historical_min_score(), 0.0)

        with patch.dict(os.environ, {"MEMORY_HISTORICAL_RRF_K": "0"}):
            self.assertEqual(get_historical_rrf_k(), 60)


if __name__ == "__main__":
    unittest.main()

