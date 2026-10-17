import asyncio
import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from fastapi import HTTPException
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage, SystemMessage

import app.api.routes as routes_module
import app.memory.sqlite_memory as memory_module
import app.memory.stm as stm_module
from app.memory.config import (
    get_recent_message_window,
    get_summarization_threshold,
    get_memory_config,
    DEFAULT_RECENT_MESSAGE_WINDOW,
    DEFAULT_MAX_MESSAGES_BEFORE_SUMMARY,
)
from app.memory.sqlite_memory import (
    init_db,
    save_message,
    get_thread_messages,
    save_thread_summary,
    get_thread_summary,
    verify_thread_ownership,
    backfill_thread_messages_from_checkpoint,
)
from app.schemas.resume_chat import HITLResumeRequest
from app.graph.nodes import chat_node
from app.graph.agent_graph import should_summarize


class TestPhase3Memory(unittest.TestCase):
    def setUp(self):
        """
        Create an isolated temporary SQLite database for Phase 3 tests.
        Redirects routes_module.conn and memory_module.conn to the temporary database.
        """
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_phase3.db")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        init_db(target_conn=self.conn)

        # Store originals to restore in tearDown
        self.orig_routes_conn = routes_module.conn
        self.orig_memory_conn = memory_module.conn

        routes_module.conn = self.conn
        memory_module.conn = self.conn

        # Seed test users
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO users (user_id, email, password_hash, is_verified) VALUES (?, ?, ?, ?)",
            (1, "alice@example.com", "hash_alice", 1)
        )
        cursor.execute(
            "INSERT INTO users (user_id, email, password_hash, is_verified) VALUES (?, ?, ?, ?)",
            (2, "bob@example.com", "hash_bob", 1)
        )

        # Seed test threads
        cursor.execute(
            "INSERT INTO threads (thread_id, user_id, title) VALUES (?, ?, ?)",
            ("thread-alice-1", 1, "Alice Thread 1")
        )
        cursor.execute(
            "INSERT INTO threads (thread_id, user_id, title) VALUES (?, ?, ?)",
            ("thread-bob-1", 2, "Bob Thread 1")
        )
        self.conn.commit()

        self.alice = {"user_id": 1, "email": "alice@example.com"}
        self.bob = {"user_id": 2, "email": "bob@example.com"}

    def tearDown(self):
        """
        Restore connection references, clean env vars, close DB and remove temporary directory.
        """
        routes_module.conn = self.orig_routes_conn
        memory_module.conn = self.orig_memory_conn
        self.conn.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

        for key in [
            "MEMORY_RECENT_MESSAGE_WINDOW",
            "RECENT_MESSAGES_WINDOW",
            "MEMORY_MAX_MESSAGES_BEFORE_SUMMARY",
            "MAX_MESSAGES_BEFORE_SUMMARY",
        ]:
            os.environ.pop(key, None)

    def test_01_summary_persistence_and_loading_across_resumption(self):
        """
        Test that summaries are persisted in SQLite, loaded when conversations resume,
        and injected into chat_node LLM context without duplication.
        """
        thread_id = "thread-alice-1"
        initial_summary = "User discussed quarterly sales targets."

        # Save summary to SQLite
        success = save_thread_summary(thread_id, initial_summary, user_id=1, target_conn=self.conn)
        self.assertTrue(success)

        # Retrieve summary directly
        loaded = get_thread_summary(thread_id, user_id=1, target_conn=self.conn)
        self.assertEqual(loaded, initial_summary)

        # Check that get_thread_details returns the summary
        details = routes_module.get_thread_details(thread_id, current_user=self.alice)
        self.assertEqual(details["summary"], initial_summary)

        # Verify chat_node loads summary from SQLite when state has no summary
        state = {
            "messages": [HumanMessage(content="What were those targets again?", id="msg-q1")],
            "summary": ""  # empty in state to test loading from SQLite
        }
        config = {"configurable": {"thread_id": thread_id}}

        with patch("app.graph.nodes.llm_with_tools.invoke") as mock_invoke, \
             patch("app.graph.nodes.thread_document_metadata", return_value=""):
            mock_invoke.return_value = AIMessage(content="The target was $500k.")
            chat_node(state, config=config)

            # Inspect messages sent to LLM
            sent_messages = mock_invoke.call_args[0][0]
            summary_messages = [
                m for m in sent_messages
                if isinstance(m, SystemMessage) and "Conversation summary from earlier messages" in m.content
            ]
            self.assertEqual(len(summary_messages), 1)
            self.assertIn(initial_summary, summary_messages[0].content)

    def test_02_summary_updates_after_configured_threshold(self):
        """
        Test that memory summarization triggers when message count exceeds the configured threshold,
        and incrementally updates and persists the summary in SQLite.
        """
        thread_id = "thread-alice-1"
        os.environ["MEMORY_MAX_MESSAGES_BEFORE_SUMMARY"] = "4"
        os.environ["MEMORY_RECENT_MESSAGE_WINDOW"] = "2"

        # Initially 4 messages (not exceeding threshold of 4)
        messages = [
            HumanMessage(content="Msg 1", id="h1"),
            AIMessage(content="Reply 1", id="a1"),
            HumanMessage(content="Msg 2", id="h2"),
            AIMessage(content="Reply 2", id="a2"),
        ]
        state = {"messages": messages, "summary": ""}
        self.assertEqual(should_summarize(state), "end")

        # Add 5th message (exceeds threshold 4)
        messages.append(HumanMessage(content="Msg 3", id="h3"))
        messages.append(AIMessage(content="Reply 3", id="a3"))
        state = {"messages": messages, "summary": "Old overview"}
        self.assertEqual(should_summarize(state), "summarize_memory")

        # Mock LLM summary update
        mock_summary_response = MagicMock(content="Updated conversation summary covering msgs 1-2.")
        config = {"configurable": {"thread_id": thread_id}}

        with patch("app.memory.stm.llm.invoke", return_value=mock_summary_response):
            result = stm_module.summarize_memory(state, config=config)

        self.assertIn("summary", result)
        self.assertEqual(result["summary"], "Updated conversation summary covering msgs 1-2.")

        # Check SQLite updated
        persisted = get_thread_summary(thread_id, user_id=1, target_conn=self.conn)
        self.assertEqual(persisted, "Updated conversation summary covering msgs 1-2.")

    def test_03_recent_message_retention(self):
        """
        Test that summarize_memory retains exactly the configured recent message window
        in active state and emits RemoveMessage for older messages.
        """
        os.environ["MEMORY_RECENT_MESSAGE_WINDOW"] = "4"

        messages = [
            HumanMessage(content="Msg 1", id="h1"),
            AIMessage(content="Reply 1", id="a1"),
            HumanMessage(content="Msg 2", id="h2"),
            AIMessage(content="Reply 2", id="a2"),
            HumanMessage(content="Msg 3", id="h3"),
            AIMessage(content="Reply 3", id="a3"),
        ]
        state = {"messages": messages, "summary": ""}
        mock_resp = MagicMock(content="Summary of 1 and 2.")

        with patch("app.memory.stm.llm.invoke", return_value=mock_resp):
            result = stm_module.summarize_memory(state, config=None)

        removed_ids = [m.id for m in result["messages"] if isinstance(m, RemoveMessage)]
        # The oldest 2 messages (6 total - 4 kept = 2 removed) should be deleted from active state
        self.assertEqual(set(removed_ids), {"h1", "a1"})

    def test_04_preservation_of_all_permanent_messages_after_summarization(self):
        """
        Test that removing messages from active LangGraph state during summarization
        NEVER deletes or corrupts durable records in the SQLite messages table.
        """
        thread_id = "thread-alice-1"
        user_id = 1

        # Save 6 messages into SQLite
        for i in range(1, 4):
            save_message(thread_id, user_id, "user", f"Question {i}", message_id=f"u{i}", target_conn=self.conn)
            save_message(thread_id, user_id, "assistant", f"Answer {i}", message_id=f"a{i}", target_conn=self.conn)

        all_stored_before = get_thread_messages(thread_id, user_id, target_conn=self.conn)
        self.assertEqual(len(all_stored_before), 6)

        # Simulate summarization with keep_recent=2, removing u1, a1, u2, a2 from LangGraph state
        os.environ["MEMORY_RECENT_MESSAGE_WINDOW"] = "2"
        graph_messages = [
            HumanMessage(content=f"Question {i}", id=f"u{i}") for i in range(1, 4)
        ] + [
            AIMessage(content=f"Answer {i}", id=f"a{i}") for i in range(1, 4)
        ]
        # Interleave in chronological order
        ordered_messages = [
            HumanMessage(content="Question 1", id="u1"),
            AIMessage(content="Answer 1", id="a1"),
            HumanMessage(content="Question 2", id="u2"),
            AIMessage(content="Answer 2", id="a2"),
            HumanMessage(content="Question 3", id="u3"),
            AIMessage(content="Answer 3", id="a3"),
        ]
        state = {"messages": ordered_messages, "summary": ""}

        with patch("app.memory.stm.llm.invoke", return_value=MagicMock(content="Summary")):
            stm_module.summarize_memory(state, config={"configurable": {"thread_id": thread_id}})

        # Verify durable SQLite messages table is completely unaffected!
        all_stored_after = get_thread_messages(thread_id, user_id, target_conn=self.conn)
        self.assertEqual(len(all_stored_after), 6)
        self.assertEqual([m["content"] for m in all_stored_after], [
            "Question 1", "Answer 1", "Question 2", "Answer 2", "Question 3", "Answer 3"
        ])

    def test_05_recovery_when_summary_generation_fails(self):
        """
        Test that if LLM summary generation fails, the system safely preserves the existing
        summary, does NOT prune messages from active state, and continues without raising.
        """
        thread_id = "thread-alice-1"
        save_thread_summary(thread_id, "Pre-existing valid summary", user_id=1, target_conn=self.conn)

        messages = [
            HumanMessage(content=f"Msg {i}", id=f"m{i}")
            for i in range(10)
        ]
        state = {"messages": messages, "summary": "Pre-existing valid summary"}
        config = {"configurable": {"thread_id": thread_id}}

        with patch("app.memory.stm.llm.invoke", side_effect=RuntimeError("LLM API Outage")):
            res = stm_module.summarize_memory(state, config=config)

        # Preserves previous valid summary
        self.assertEqual(res["summary"], "Pre-existing valid summary")
        # Does NOT delete messages from active state when summarization fails
        self.assertNotIn("messages", res)

        # Database still has the valid summary
        persisted = get_thread_summary(thread_id, user_id=1, target_conn=self.conn)
        self.assertEqual(persisted, "Pre-existing valid summary")

    def test_06_thread_and_user_isolation_for_summaries(self):
        """
        Test that users cannot read or overwrite conversation summaries for threads they do not own.
        """
        alice_thread = "thread-alice-1"
        save_thread_summary(alice_thread, "Alice secret summary", user_id=1, target_conn=self.conn)

        # Bob attempts to read Alice's summary via helper
        with self.assertRaises(ValueError):
            get_thread_summary(alice_thread, user_id=2, target_conn=self.conn)

        # Bob attempts to overwrite Alice's summary via helper
        with self.assertRaises(ValueError):
            save_thread_summary(alice_thread, "Bob tampered summary", user_id=2, target_conn=self.conn)

        # Bob attempts to get thread details via API route
        with self.assertRaises(HTTPException) as ctx:
            routes_module.get_thread_details(alice_thread, current_user=self.bob)
        self.assertEqual(ctx.exception.status_code, 404)

        # Alice's original summary is untampered
        alice_sum = get_thread_summary(alice_thread, user_id=1, target_conn=self.conn)
        self.assertEqual(alice_sum, "Alice secret summary")

    def test_07_hitl_continuity_with_summaries(self):
        """
        Test that HITL interrupt preserves the user message and does not prematurely trigger summarization,
        and subsequent resumption updates and persists the summary on completion.
        """
        thread_id = "thread-alice-1"
        user_message = "Search web for current news"

        mock_interrupt = {
            "__interrupt__": [
                MagicMock(value={"question": "Approve web search?", "message": "Approval needed"})
            ]
        }

        with patch("app.api.routes.chatbot.invoke", return_value=mock_interrupt):
            res_interrupt = asyncio.run(routes_module.chat_endpoint(
                {"message": user_message, "thread_id": thread_id, "client_message_id": "hitl-u1"},
                current_user=self.alice
            ))

        self.assertEqual(res_interrupt["status"], "human-approval")

        # Resume execution
        mock_resume_result = {
            "messages": [
                HumanMessage(content=user_message, id="hitl-u1"),
                AIMessage(content="Here are the top news headlines.", id="hitl-a1")
            ],
            "summary": "User searched for current news headlines."
        }

        with patch("app.api.routes.chatbot.invoke", return_value=mock_resume_result):
            res_resume = routes_module.resume_chat(
                HITLResumeRequest(thread_id=thread_id, decision="yes", message_id="hitl-resume-1"),
                current_user=self.alice
            )

        self.assertEqual(res_resume["status"], "completed")

        # Verify summary is persisted upon resumption
        persisted_summary = get_thread_summary(thread_id, user_id=1, target_conn=self.conn)
        self.assertEqual(persisted_summary, "User searched for current news headlines.")

    def test_08_legacy_backfill_when_some_sqlite_messages_already_exist(self):
        """
        Test that when a thread already has some SQLite messages, any additional older
        recoverable messages from checkpoint are backfilled without duplicating existing messages.
        """
        thread_id = "thread-alice-1"
        user_id = 1

        # Pre-existing message in SQLite (Turn 2 only)
        save_message(thread_id, user_id, "user", "Turn 2 question", message_id="turn-2-u", target_conn=self.conn)
        save_message(thread_id, user_id, "assistant", "Turn 2 answer", message_id="turn-2-a", target_conn=self.conn)

        initial_stored = get_thread_messages(thread_id, user_id, target_conn=self.conn)
        self.assertEqual(len(initial_stored), 2)

        # Checkpoint contains Turn 1 (older) AND Turn 2 (already stored in SQLite)
        checkpoint_messages = [
            HumanMessage(content="Turn 1 question", id="turn-1-u"),
            AIMessage(content="Turn 1 answer", id="turn-1-a"),
            HumanMessage(content="Turn 2 question", id="turn-2-u"),
            AIMessage(content="Turn 2 answer", id="turn-2-a"),
        ]

        # Mock chatbot.get_state returning these checkpoint messages
        mock_state = MagicMock()
        mock_state.values = {"messages": checkpoint_messages}

        with patch("app.api.routes.chatbot.get_state", return_value=mock_state):
            details = routes_module.get_thread_details(thread_id, current_user=self.alice)

        # All 4 messages should now be present in details
        self.assertEqual(len(details["messages"]), 4)
        contents = [m["content"] for m in details["messages"]]
        self.assertIn("Turn 1 question", contents)
        self.assertIn("Turn 1 answer", contents)
        self.assertIn("Turn 2 question", contents)
        self.assertIn("Turn 2 answer", contents)

        # Ensure SQLite has exactly 4 records (no duplicates of Turn 2)
        final_stored = get_thread_messages(thread_id, user_id, target_conn=self.conn)
        self.assertEqual(len(final_stored), 4)

    def test_09_backward_compatibility_and_config_validation(self):
        """
        Test configuration parsing with invalid values, schema initialization idempotency,
        and API response shape compatibility.
        """
        # Test invalid values fallback
        os.environ["MEMORY_RECENT_MESSAGE_WINDOW"] = "invalid_string"
        self.assertEqual(get_recent_message_window(), DEFAULT_RECENT_MESSAGE_WINDOW)

        os.environ["MEMORY_RECENT_MESSAGE_WINDOW"] = "1"  # must be >= 2
        self.assertEqual(get_recent_message_window(), DEFAULT_RECENT_MESSAGE_WINDOW)

        os.environ["MEMORY_RECENT_MESSAGE_WINDOW"] = "4"
        os.environ["MEMORY_MAX_MESSAGES_BEFORE_SUMMARY"] = "3"  # must be > recent window
        self.assertEqual(get_summarization_threshold(), DEFAULT_MAX_MESSAGES_BEFORE_SUMMARY)

        # Test valid configuration
        os.environ["MEMORY_RECENT_MESSAGE_WINDOW"] = "8"
        os.environ["MEMORY_MAX_MESSAGES_BEFORE_SUMMARY"] = "16"
        cfg = get_memory_config()
        self.assertEqual(cfg["recent_messages_to_retain"], 8)
        self.assertEqual(cfg["summarization_threshold"], 16)

        # Test init_db idempotency
        init_db(target_conn=self.conn)
        init_db(target_conn=self.conn)

        # Verify threads table columns include summary
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(threads)")
        cols = {row[1] for row in cursor.fetchall()}
        self.assertIn("summary", cols)
        self.assertIn("thread_id", cols)
        self.assertIn("user_id", cols)
        self.assertIn("title", cols)


if __name__ == "__main__":
    unittest.main()

