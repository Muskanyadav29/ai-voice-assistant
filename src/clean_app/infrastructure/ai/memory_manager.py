"""Conversation session history and memory manager backed by SQLite database."""

import sqlite3
from pathlib import Path


class MemoryManager:
    """Manages multi-turn conversation memory, persisted to a SQLite database."""

    def __init__(self, db_path: str = "./data/app.db") -> None:
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the chat history table if it does not exist."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add a message turn to the session history and trim older messages."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content)
            )
            conn.commit()
            
            # Keep sliding window of last 20 messages to prevent bloated LLM contexts
            conn.execute("""
                DELETE FROM chat_history 
                WHERE id NOT IN (
                    SELECT id FROM chat_history 
                    WHERE session_id = ? 
                    ORDER BY id DESC LIMIT 20
                ) AND session_id = ?
            """, (session_id, session_id))
            conn.commit()

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        """Retrieve recent conversation history for a session."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "SELECT role, content FROM chat_history WHERE session_id = ? ORDER BY id ASC",
                (session_id,)
            )
            return [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]

    def get_history_for_llm(self, session_id: str, limit: int = 10) -> list[dict[str, str]]:
        """Format history for OpenAI completions."""
        history = self.get_history(session_id)
        return history[-limit:]

    def clear_history(self, session_id: str) -> None:
        """Reset the conversation memory for a session."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
            conn.commit()
