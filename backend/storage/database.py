"""SQLite: signals aur unke natije (live accuracy track karne ke liye). Thread-safe (lock)."""
import sqlite3
import threading
import time
import config


class DB:
    def __init__(self, path=None):
        self.lock = threading.Lock()
        self.c = sqlite3.connect(path or config.DB_PATH, check_same_thread=False)
        with self.lock:
            self.c.execute("""CREATE TABLE IF NOT EXISTS signals(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created REAL, symbol TEXT, direction TEXT, confidence REAL,
                target_time TEXT, entry REAL, status TEXT DEFAULT 'PENDING',
                exit_price REAL, win INTEGER)""")
            self.c.commit()

    def add_signal(self, symbol, direction, conf, target_time, entry):
        with self.lock:
            cur = self.c.execute(
                "INSERT INTO signals(created,symbol,direction,confidence,target_time,entry) VALUES(?,?,?,?,?,?)",
                (time.time(), symbol, direction, conf, str(target_time), entry))
            self.c.commit()
            return cur.lastrowid

    def pending(self, symbol):
        with self.lock:
            return self.c.execute(
                "SELECT id,direction,target_time,entry FROM signals WHERE status='PENDING' AND symbol=?",
                (symbol,)).fetchall()

    def resolve(self, sid, exit_price, win):
        with self.lock:
            self.c.execute("UPDATE signals SET status='DONE', exit_price=?, win=? WHERE id=?",
                           (exit_price, None if win is None else int(win), sid))
            self.c.commit()

    def recent_stats(self, n=100):
        with self.lock:
            rows = self.c.execute(
                "SELECT win FROM signals WHERE status='DONE' AND win IS NOT NULL ORDER BY id DESC LIMIT ?",
                (n,)).fetchall()
        return len(rows), sum(r[0] for r in rows)

    def totals(self, symbol=None):
        q, a = "SELECT COUNT(*), SUM(win IS NOT NULL AND win=1), SUM(win IS NOT NULL AND win=0) FROM signals", ()
        if symbol:
            q, a = q + " WHERE symbol=?", (symbol,)
        with self.lock:
            n, w, l = self.c.execute(q, a).fetchone()
        return n or 0, w or 0, l or 0

    def last_signal(self, symbol):
        with self.lock:
            return self.c.execute(
                "SELECT direction,confidence,target_time,status,win FROM signals WHERE symbol=? ORDER BY id DESC LIMIT 1",
                (symbol,)).fetchone()
