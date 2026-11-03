import sqlite3
import logging

logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self, db_path="micp_60.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS micp_signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        instrument TEXT,
                        signal TEXT,
                        confidence REAL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Database error: {e}")

    def save_signal(self, instrument, signal, confidence):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO micp_signals (instrument, signal, confidence) VALUES (?, ?, ?)",
                    (instrument, signal, confidence)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save signal: {e}")
