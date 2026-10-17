import os
import shutil
import sqlite3
import tempfile
import unittest

from app.memory.sqlite_memory import (
    init_db,
    save_message,
    get_thread_messages,
    verify_thread_ownership,
    retrieve_all_threads,
)


class TestMemoryPersistence(unittest.TestCase):
    def setUp(self):
        """
        Creates an isolated temporary SQLite database for each test.
        """
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_memory.db")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        init_db(target_conn=self.conn)

        # Seed initial test data
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO users (user_id, email, password_hash, is_verified) VALUES (?, ?, ?, ?)",
            (1, "alice@example.com", "hash1", 1)
        )
        cursor.execute(
            "INSERT INTO users (user_id, email, password_hash, is_verified) VALUES (?, ?, ?, ?)",
            (2, "bob@example.com", "hash2", 1)
        )
        cursor.execute(
            "INSERT INTO threads (thread_id, user_id, title) VALUES (?, ?, ?)",
            ("thread-alice-1", 1, "Alice Thread 1")
        )
        cursor.execute(
            "INSERT INTO threads (thread_id, user_id, title) VALUES (?, ?, ?)",
            ("thread-alice-2", 1, "Alice Thread 2")
        )
        cursor.execute(
            "INSERT INTO threads (thread_id, user_id, title) VALUES (?, ?, ?)",
            ("thread-bob-1", 2, "Bob Thread 1")
        )
        self.conn.commit()

    def tearDown(self):
        """
        Closes connection and cleans up temporary database directory.
        """
        self.conn.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_table_creation_and_repeated_initialization(self):
        """
        Test that init_db creates all required tables and indexes idempotently without error.
        """
        # Run initialization repeatedly to ensure idempotency
        init_db(target_conn=self.conn)
        init_db(target_conn=self.conn)

        cursor = self.conn.cursor()

        # Verify messages table columns
        cursor.execute("PRAGMA table_info(messages)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        self.assertIn("message_id", columns)
        self.assertIn("thread_id", columns)
        self.assertIn("user_id", columns)
        self.assertIn("role", columns)
        self.assertIn("content", columns)
        self.assertIn("created_at", columns)

        # Verify indexes exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='messages'")
        indexes = [row[0] for row in cursor.fetchall()]
        self.assertIn("idx_messages_thread_created", indexes)
        self.assertIn("idx_messages_user_thread", indexes)

    def test_save_and_retrieve_messages_chronological(self):
        """
        Test saving user and assistant messages and retrieving them in chronological order.
        """
        thread_id = "thread-alice-1"
        user_id = 1

        msg1 = save_message(
            thread_id=thread_id,
            user_id=user_id,
            role="user",
            content="Hello, can you help me with Python?",
            target_conn=self.conn
        )
        self.assertIsNotNone(msg1)
        self.assertEqual(msg1["role"], "user")
        self.assertEqual(msg1["content"], "Hello, can you help me with Python?")
        self.assertEqual(msg1["thread_id"], thread_id)
        self.assertEqual(msg1["user_id"], user_id)

        msg2 = save_message(
            thread_id=thread_id,
            user_id=user_id,
            role="assistant",
            content="Of course! What Python topic would you like to explore?",
            target_conn=self.conn
        )
        self.assertIsNotNone(msg2)
        self.assertEqual(msg2["role"], "assistant")

        msg3 = save_message(
            thread_id=thread_id,
            user_id=user_id,
            role="user",
            content="Tell me about list comprehensions.",
            target_conn=self.conn
        )
        self.assertIsNotNone(msg3)

        msg4 = save_message(
            thread_id=thread_id,
            user_id=user_id,
            role="assistant",
            content="List comprehensions provide a concise way to create lists.",
            target_conn=self.conn
        )
        self.assertIsNotNone(msg4)

        # Retrieve all messages
        history = get_thread_messages(thread_id, user_id, target_conn=self.conn)
        self.assertEqual(len(history), 4)
        self.assertEqual([m["role"] for m in history], ["user", "assistant", "user", "assistant"])
        self.assertEqual(history[0]["content"], "Hello, can you help me with Python?")
        self.assertEqual(history[3]["content"], "List comprehensions provide a concise way to create lists.")

        # Test limit option (most recent 2 messages, ordered chronologically)
        recent_two = get_thread_messages(thread_id, user_id, limit=2, target_conn=self.conn)
        self.assertEqual(len(recent_two), 2)
        self.assertEqual(recent_two[0]["content"], "Tell me about list comprehensions.")
        self.assertEqual(recent_two[1]["content"], "List comprehensions provide a concise way to create lists.")

    def test_duplicate_message_id_handling(self):
        """
        Test that retrying with the same stable message ID is idempotent and does not create duplicate rows.
        """
        thread_id = "thread-alice-1"
        user_id = 1
        fixed_id = "fixed-msg-uuid-001"

        first_save = save_message(
            thread_id=thread_id,
            user_id=user_id,
            role="user",
            content="Original question",
            message_id=fixed_id,
            target_conn=self.conn
        )
        self.assertEqual(first_save["message_id"], fixed_id)
        self.assertEqual(first_save["content"], "Original question")

        # Retry with same message_id
        second_save = save_message(
            thread_id=thread_id,
            user_id=user_id,
            role="user",
            content="Retried question",
            message_id=fixed_id,
            target_conn=self.conn
        )
        self.assertEqual(second_save["message_id"], fixed_id)
        self.assertEqual(second_save["content"], "Original question")  # Original preserved

        # Ensure total row count for this thread is exactly 1
        messages = get_thread_messages(thread_id, user_id, target_conn=self.conn)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["message_id"], fixed_id)

    def test_reject_unauthorized_user_access(self):
        """
        Test that users cannot save or read messages from threads they do not own.
        """
        alice_thread = "thread-alice-1"
        bob_user_id = 2

        # Bob attempts to save to Alice's thread
        with self.assertRaises(ValueError):
            save_message(
                thread_id=alice_thread,
                user_id=bob_user_id,
                role="user",
                content="Intruder message",
                target_conn=self.conn
            )

        # Bob attempts to read Alice's thread
        with self.assertRaises(ValueError):
            get_thread_messages(
                thread_id=alice_thread,
                user_id=bob_user_id,
                target_conn=self.conn
            )

        # Ownership helper should return False
        self.assertFalse(verify_thread_ownership(alice_thread, bob_user_id, target_conn=self.conn))

    def test_isolation_between_threads_and_users(self):
        """
        Test that messages are isolated across different threads of the same user and across users.
        """
        # User 1, Thread 1
        save_message("thread-alice-1", 1, "user", "Alice Thread 1 Msg", target_conn=self.conn)
        save_message("thread-alice-1", 1, "assistant", "Alice Thread 1 Reply", target_conn=self.conn)

        # User 1, Thread 2
        save_message("thread-alice-2", 1, "user", "Alice Thread 2 Msg", target_conn=self.conn)

        # User 2, Thread 1 (Bob)
        save_message("thread-bob-1", 2, "user", "Bob Thread 1 Msg", target_conn=self.conn)

        alice_t1 = get_thread_messages("thread-alice-1", 1, target_conn=self.conn)
        alice_t2 = get_thread_messages("thread-alice-2", 1, target_conn=self.conn)
        bob_t1 = get_thread_messages("thread-bob-1", 2, target_conn=self.conn)

        self.assertEqual(len(alice_t1), 2)
        self.assertEqual([m["content"] for m in alice_t1], ["Alice Thread 1 Msg", "Alice Thread 1 Reply"])

        self.assertEqual(len(alice_t2), 1)
        self.assertEqual(alice_t2[0]["content"], "Alice Thread 2 Msg")

        self.assertEqual(len(bob_t1), 1)
        self.assertEqual(bob_t1[0]["content"], "Bob Thread 1 Msg")

    def test_role_validation(self):
        """
        Test that only 'user' and 'assistant' roles are allowed for visible conversation history.
        """
        with self.assertRaises(ValueError):
            save_message("thread-alice-1", 1, "system", "System injected", target_conn=self.conn)

        with self.assertRaises(ValueError):
            save_message("thread-alice-1", 1, "tool", "Tool output", target_conn=self.conn)

        with self.assertRaises(ValueError):
            save_message("thread-alice-1", 1, "invalid_role", "Bad role", target_conn=self.conn)

    def test_retrieve_all_threads_parameterized(self):
        """
        Test that retrieve_all_threads correctly filters by user using parameterized queries.
        """
        alice_threads = retrieve_all_threads(1, target_conn=self.conn)
        bob_threads = retrieve_all_threads(2, target_conn=self.conn)
        unknown_threads = retrieve_all_threads(999, target_conn=self.conn)

        self.assertEqual(set(alice_threads), {"thread-alice-1", "thread-alice-2"})
        self.assertEqual(set(bob_threads), {"thread-bob-1"})
        self.assertEqual(unknown_threads, [])


if __name__ == "__main__":
    unittest.main()

