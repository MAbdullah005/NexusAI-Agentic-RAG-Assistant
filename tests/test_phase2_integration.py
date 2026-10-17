import asyncio
import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from fastapi import HTTPException
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

import app.api.routes as routes_module
import app.memory.sqlite_memory as memory_module
from app.memory.sqlite_memory import (
    init_db,
    save_message,
    get_thread_messages,
    verify_thread_ownership,
    backfill_thread_messages_from_checkpoint,
)
from app.schemas.resume_chat import HITLResumeRequest


class TestPhase2Integration(unittest.TestCase):
    def setUp(self):
        """
        Create an isolated temporary SQLite database for Phase 2 integration tests.
        Redirects routes_module.conn and memory_module.conn to the temporary database.
        """
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_phase2.db")
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
        Restore connection references, close DB and remove temporary directory.
        """
        routes_module.conn = self.orig_routes_conn
        memory_module.conn = self.orig_memory_conn
        self.conn.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_normal_chat_turn_persists_user_and_assistant(self):
        """
        Test that a normal /chat turn persists both user message and assistant response
        to SQLite in chronological order.
        """
        thread_id = "thread-alice-1"
        user_message = "What is the capital of France?"
        ai_reply = "The capital of France is Paris."

        mock_response = {
            "messages": [
                HumanMessage(content=user_message),
                AIMessage(content=ai_reply)
            ]
        }

        with patch("app.api.routes.chatbot.invoke", return_value=mock_response):
            payload = {
                "message": user_message,
                "thread_id": thread_id,
                "client_message_id": "alice-msg-001"
            }
            res = asyncio.run(routes_module.chat_endpoint(payload, current_user=self.alice))

        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["response"], ai_reply)
        self.assertEqual(res["thread_id"], thread_id)

        # Check SQLite durable storage
        messages = get_thread_messages(thread_id, self.alice["user_id"], target_conn=self.conn)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], user_message)
        self.assertEqual(messages[0]["message_id"], "alice-msg-001")

        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], ai_reply)
        self.assertEqual(messages[1]["message_id"], "resp_alice-msg-001")

    def test_02_interrupted_chat_turn_persists_only_user_message(self):
        """
        Test that when /chat triggers a human approval interrupt,
        the user message is persisted to SQLite, but no incomplete assistant answer is saved.
        """
        thread_id = "thread-alice-1"
        user_message = "Search private medical records."

        mock_interrupt_response = {
            "__interrupt__": [
                MagicMock(value={"question": "Approve web search?", "message": "Approval needed"})
            ]
        }

        with patch("app.api.routes.chatbot.invoke", return_value=mock_interrupt_response):
            payload = {
                "message": user_message,
                "thread_id": thread_id,
                "client_message_id": "alice-hitl-msg-001"
            }
            res = asyncio.run(routes_module.chat_endpoint(payload, current_user=self.alice))

        self.assertEqual(res["status"], "human-approval")
        self.assertEqual(res["thread_id"], thread_id)
        self.assertIn("interrupt", res)

        # Verify only user message was persisted
        messages = get_thread_messages(thread_id, self.alice["user_id"], target_conn=self.conn)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], user_message)

    def test_03_resume_chat_persists_assistant_without_duplicate_user(self):
        """
        Test that resuming an interrupted chat turn via /chat/resume:
        - Persists the final assistant response.
        - Does NOT create a second user message.
        - Results in exactly 1 user message and 1 assistant message in history.
        """
        thread_id = "thread-alice-1"
        user_message = "What are the latest updates on Project X?"
        ai_final_reply = "Project X was successfully released yesterday."

        # Simulate user message already saved from previous interrupted turn
        save_message(
            thread_id=thread_id,
            user_id=self.alice["user_id"],
            role="user",
            content=user_message,
            message_id="alice-resume-turn-user",
            target_conn=self.conn
        )

        mock_resume_result = {
            "messages": [
                HumanMessage(content=user_message),
                AIMessage(content=ai_final_reply)
            ]
        }

        with patch("app.api.routes.chatbot.invoke", return_value=mock_resume_result):
            req = HITLResumeRequest(
                thread_id=thread_id,
                decision="yes",
                message_id="resume-001"
            )
            res = routes_module.resume_chat(req, current_user=self.alice)

        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["thread_id"], thread_id)

        # Check total messages in SQLite: exactly 1 user + 1 assistant
        messages = get_thread_messages(thread_id, self.alice["user_id"], target_conn=self.conn)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], user_message)
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], ai_final_reply)
        self.assertEqual(messages[1]["message_id"], "resp_resume-001")

    def test_04_idempotent_retry_does_not_duplicate_messages(self):
        """
        Test that retrying /chat with the same client_message_id is idempotent:
        - Returns cached response.
        - Does NOT re-invoke the graph or insert duplicate rows.
        """
        thread_id = "thread-alice-1"
        user_message = "Generate monthly summary report"
        ai_reply = "Here is the summary report for October."
        client_mid = "idempotent-msg-key-999"

        mock_response = {
            "messages": [
                HumanMessage(content=user_message),
                AIMessage(content=ai_reply)
            ]
        }

        # First request
        with patch("app.api.routes.chatbot.invoke", return_value=mock_response) as mock_invoke:
            payload = {
                "message": user_message,
                "thread_id": thread_id,
                "client_message_id": client_mid
            }
            res1 = asyncio.run(routes_module.chat_endpoint(payload, current_user=self.alice))
            self.assertEqual(mock_invoke.call_count, 1)

        self.assertEqual(res1["status"], "completed")
        self.assertEqual(res1["response"], ai_reply)

        # Second request (retry with exact same client_message_id)
        with patch("app.api.routes.chatbot.invoke") as mock_invoke_retry:
            res2 = asyncio.run(routes_module.chat_endpoint(payload, current_user=self.alice))
            # Chatbot should NOT have been invoked on retry!
            mock_invoke_retry.assert_not_called()

        self.assertEqual(res2["status"], "completed")
        self.assertEqual(res2["response"], ai_reply)

        # Verify exactly 2 rows exist (1 user, 1 assistant)
        messages = get_thread_messages(thread_id, self.alice["user_id"], target_conn=self.conn)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["message_id"], client_mid)
        self.assertEqual(messages[1]["message_id"], f"resp_{client_mid}")

    def test_05_reused_message_id_with_conflicting_attributes_is_rejected(self):
        """
        Test that reusing an existing message ID with conflicting content or attributes
        raises an error and is rejected (cannot corrupt existing records).
        """
        thread_id = "thread-alice-1"
        fixed_id = "stable-id-xyz"

        # First valid insert
        save_message(
            thread_id=thread_id,
            user_id=self.alice["user_id"],
            role="user",
            content="Original content",
            message_id=fixed_id,
            target_conn=self.conn
        )

        # Attempt to reuse fixed_id with different content in strict mode
        with self.assertRaises(ValueError):
            save_message(
                thread_id=thread_id,
                user_id=self.alice["user_id"],
                role="user",
                content="Tampered conflicting content",
                message_id=fixed_id,
                strict=True,
                target_conn=self.conn
            )

        # Attempt to reuse fixed_id for a different thread
        with self.assertRaises(ValueError):
            save_message(
                thread_id="thread-bob-1",
                user_id=self.bob["user_id"],
                role="user",
                content="Original content",
                message_id=fixed_id,
                target_conn=self.conn
            )

        # Attempt via chat endpoint with conflicting content
        payload = {
            "message": "Different conflicting content",
            "thread_id": thread_id,
            "client_message_id": fixed_id
        }
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(routes_module.chat_endpoint(payload, current_user=self.alice))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_06_user_isolation_blocks_cross_user_access(self):
        """
        Test that users cannot read or post messages to threads belonging to other users.
        """
        alice_thread = "thread-alice-1"

        # Bob attempts to read Alice's thread details
        with self.assertRaises(HTTPException) as ctx:
            routes_module.get_thread_details(alice_thread, current_user=self.bob)
        self.assertEqual(ctx.exception.status_code, 404)

        # Bob attempts to post a message to Alice's thread
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(routes_module.chat_endpoint(
                {"message": "Injected message", "thread_id": alice_thread},
                current_user=self.bob
            ))
        self.assertEqual(ctx.exception.status_code, 404)

        # Bob attempts to resume Alice's thread
        with self.assertRaises(HTTPException) as ctx:
            routes_module.resume_chat(
                HITLResumeRequest(thread_id=alice_thread, decision="yes"),
                current_user=self.bob
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_07_internal_tool_messages_and_artifacts_excluded_from_history(self):
        """
        Test that internal ToolMessage instances, function calls, and tool artifacts
        are never included in visible chat history.
        """
        thread_id = "thread-alice-1"
        user_id = self.alice["user_id"]

        # Simulate checkpoint messages containing internal tool execution artifacts
        checkpoint_messages = [
            HumanMessage(content="Find PDF sales figures"),
            AIMessage(
                content="",
                tool_calls=[{"name": "pdf_search", "args": {"query": "sales"}, "id": "tc_1"}]
            ),
            ToolMessage(content="[INTERNAL] Raw retrieved vector text chunk 123", tool_call_id="tc_1"),
            AIMessage(content="Total sales for Q3 were $1.2M.")
        ]

        # Backfill
        backfilled = backfill_thread_messages_from_checkpoint(
            thread_id=thread_id,
            user_id=user_id,
            checkpoint_messages=checkpoint_messages,
            target_conn=self.conn
        )

        # Ensure only 2 messages (HumanMessage and final AIMessage) were persisted
        self.assertEqual(len(backfilled), 2)
        self.assertEqual(backfilled[0]["role"], "user")
        self.assertEqual(backfilled[0]["content"], "Find PDF sales figures")

        self.assertEqual(backfilled[1]["role"], "assistant")
        self.assertEqual(backfilled[1]["content"], "Total sales for Q3 were $1.2M.")

        # Ensure no tool messages or tool calls are in SQLite
        history = get_thread_messages(thread_id, user_id, target_conn=self.conn)
        for msg in history:
            self.assertIn(msg["role"], ("user", "assistant"))
            self.assertNotIn("[INTERNAL]", msg["content"])

    def test_08_legacy_thread_details_retrieval_and_backfill(self):
        """
        Test that calling /thread/{thread_id}/details on a legacy thread
        (messages in checkpoint but none in SQLite messages table)
        safely backfills into SQLite messages table and returns the exact expected response contract.
        """
        thread_id = "thread-alice-1"
        user_id = self.alice["user_id"]

        # Ensure messages table is currently empty for this thread
        initial_messages = get_thread_messages(thread_id, user_id, target_conn=self.conn)
        self.assertEqual(len(initial_messages), 0)

        # Mock LangGraph get_state returning checkpoint messages
        mock_state = MagicMock()
        mock_state.values = {
            "messages": [
                HumanMessage(content="Legacy question from last week"),
                AIMessage(content="Legacy answer from last week")
            ]
        }

        with patch("app.api.routes.chatbot.get_state", return_value=mock_state):
            details = routes_module.get_thread_details(thread_id, current_user=self.alice)

        # Verify response structure and contents
        self.assertEqual(details["thread_id"], thread_id)
        self.assertEqual(details["title"], "Alice Thread 1")
        self.assertEqual(len(details["messages"]), 2)
        self.assertEqual(details["messages"][0], {"role": "user", "content": "Legacy question from last week"})
        self.assertEqual(details["messages"][1], {"role": "assistant", "content": "Legacy answer from last week"})
        self.assertIn("documents", details)

        # Verify that SQLite messages table now durably stores these messages
        stored = get_thread_messages(thread_id, user_id, target_conn=self.conn)
        self.assertEqual(len(stored), 2)
        self.assertEqual(stored[0]["content"], "Legacy question from last week")
        self.assertEqual(stored[1]["content"], "Legacy answer from last week")

        # Second call to get_thread_details should read directly from SQLite without invoking chatbot.get_state
        with patch("app.api.routes.chatbot.get_state") as mock_get_state:
            details_cached = routes_module.get_thread_details(thread_id, current_user=self.alice)
            mock_get_state.assert_not_called()
            self.assertEqual(len(details_cached["messages"]), 2)


if __name__ == "__main__":
    unittest.main()
