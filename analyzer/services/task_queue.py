import sqlite3
import json
import threading
import time
import logging
from datetime import datetime, timedelta, timezone

from django.conf import settings

logger = logging.getLogger(__name__)

class UniversalTaskQueue:
    def __init__(self, db_path=None, worker_count=3):
        # Use BASE_DIR / 'tasks.db' if none provided
        if db_path is None:
            self.db_path = settings.BASE_DIR / 'tasks.db'
        else:
            self.db_path = db_path
            
        self._init_db()
        self.running = True
        
        # Start Workers
        for i in range(worker_count):
            threading.Thread(target=self._worker, name=f"Worker-{i}", daemon=True).start()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_name TEXT,
                    func_name TEXT,
                    args_json TEXT,
                    status TEXT DEFAULT 'PENDING',
                    retries INTEGER DEFAULT 0,
                    next_run TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def enqueue(self, func, *args, delay_seconds=0):
        """Saves task to DB. Works with any top-level function."""
        module_name = func.__module__
        func_name = func.__name__
        args_json = json.dumps(args)
        next_run = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO tasks (module_name, func_name, args_json, next_run) VALUES (?, ?, ?, ?)",
                (module_name, func_name, args_json, next_run.strftime('%Y-%m-%d %H:%M:%S'))
            )
        logger.info(f"Enqueued {func_name} for {next_run}")

    def _worker(self):
        while self.running:
            task = self._fetch_next_task()
            if not task:
                time.sleep(1)  # Back off if no tasks
                continue

            task_id, mod_name, func_name, args_json, retries = task
            
            try:
                # Dynamic Import: This makes it 'Universal'
                module = __import__(mod_name, fromlist=[func_name])
                func = getattr(module, func_name)
                args = json.loads(args_json)

                func(*args)
                self._update_status(task_id, "COMPLETED")
                logger.info(f"Task {task_id} ({func_name}) finished.")

            except Exception as e:
                new_retries = retries + 1
                if new_retries < 5:
                    wait = 2 ** new_retries
                    self._update_status(task_id, "PENDING", new_retries, wait)
                    logger.error(f"Task {task_id} failed: {e}. Retrying in {wait}s")
                else:
                    self._update_status(task_id, "FAILED")
                    logger.critical(f"Task {task_id} permanently failed.")

    def _fetch_next_task(self):
        """Atomic fetch: Finds a task and marks it as PROCESSING so workers don't collide."""
        try:
            with sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None) as conn:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.cursor()
                # Find a pending task whose time has come
                cursor.execute("""
                    SELECT id, module_name, func_name, args_json, retries FROM tasks 
                    WHERE status = 'PENDING' AND next_run <= CURRENT_TIMESTAMP 
                    LIMIT 1
                """)
                row = cursor.fetchone()
                if row:
                    cursor.execute("UPDATE tasks SET status = 'PROCESSING' WHERE id = ?", (row[0],))
                    conn.execute("COMMIT")
                    return row
                else:
                    conn.execute("ROLLBACK")
        except sqlite3.OperationalError:
            # If the database is locked, back off and try again later
            pass
        return None

    def _update_status(self, task_id, status, retries=None, delay=0):
        next_run = datetime.now(timezone.utc) + timedelta(seconds=delay)
        with sqlite3.connect(self.db_path, timeout=5.0) as conn:
            if retries is not None:
                conn.execute("UPDATE tasks SET status=?, retries=?, next_run=? WHERE id=?", 
                            (status, retries, next_run.strftime('%Y-%m-%d %H:%M:%S'), task_id))
            else:
                conn.execute("UPDATE tasks SET status=? WHERE id=?", (status, task_id))

# Global instance initialized when this file is imported
# This will start the workers in the background
background_queue = UniversalTaskQueue()
