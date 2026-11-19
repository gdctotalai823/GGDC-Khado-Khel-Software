"""
GGDC Khado Khel - Fee Management: data layer (SQLite)

Hardened version: foreign keys enforced, atomic transactions with rollback,
thread-safe access, input validation, indexes, and a few handy queries.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date as _date
from pathlib import Path
from typing import Iterable, Iterator, Optional

log = logging.getLogger(__name__)

VALID_STATUSES = ("Pending", "Paid")
_REQUIRED = ("name", "father_name", "program_type", "current_class",
             "session", "fee_type", "academic_period", "amount")


class FeeDatabaseManager:
    def __init__(self, db_name: str = "college_fees.db", folder: str = "database"):
        self.db_path = Path(folder)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.db_file = self.db_path / db_name

        self._lock = threading.RLock()
        # check_same_thread=False is safe because every access goes through _lock.
        self.conn = sqlite3.connect(self.db_file, timeout=10, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 10000")
        self._create_tables()

    # ------------------------------------------------------------------ infra
    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """Locked transaction: commit on success, roll back on any error."""
        with self._lock:
            try:
                yield self.conn
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def _create_tables(self) -> None:
        with self._tx() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS fee_students (
                    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    roll_no TEXT,
                    student_name TEXT NOT NULL,
                    father_name TEXT,
                    program_type TEXT,
                    current_class TEXT,
                    session TEXT,
                    contact_no TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS institutional_fees (
                    fee_challan_no INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    fee_type TEXT NOT NULL,        -- 'Admission Fee', 'Promotion Fee', 'Semester Fee'
                    academic_period TEXT NOT NULL, -- e.g. '1st Year', '2nd Year', '2nd Semester'
                    amount REAL NOT NULL CHECK (amount >= 0),
                    date TEXT,
                    status TEXT DEFAULT 'Pending' CHECK (status IN ('Pending', 'Paid')),
                    FOREIGN KEY (student_id) REFERENCES fee_students (student_id)
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_fees_student ON institutional_fees (student_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_fees_status ON institutional_fees (status)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_students_roll ON fee_students (roll_no)")

    @staticmethod
    def _clean(payload: dict) -> dict:
        """Validate and normalise a payload; raises ValueError with a clear message."""
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        missing = [k for k in _REQUIRED if payload.get(k) in (None, "")]
        if missing:
            raise ValueError(f"Missing required field(s): {', '.join(missing)}")
        try:
            amount = float(payload["amount"])
        except (TypeError, ValueError):
            raise ValueError(f"Invalid amount: {payload['amount']!r}") from None
        if amount < 0 or amount != amount:  # negative or NaN
            raise ValueError(f"Amount must be a non-negative number, got {amount}")

        text = lambda k: str(payload.get(k) or "").strip()
        return {
            "roll_no": text("roll_no"),
            "name": text("name"),
            "father_name": text("father_name"),
            "program_type": text("program_type"),
            "current_class": text("current_class"),
            "session": text("session"),
            "contact": text("contact"),
            "fee_type": text("fee_type"),
            "academic_period": text("academic_period"),
            "amount": amount,
            "date": text("date") or _date.today().isoformat(),
        }

    # ------------------------------------------------------------------- CRUD
    def insert_fee_record(self, payload: dict) -> int:
        """Insert student + fee atomically. Returns the new challan number."""
        p = self._clean(payload)
        with self._tx() as c:
            cur = c.execute("""
                INSERT INTO fee_students
                    (roll_no, student_name, father_name, program_type, current_class, session, contact_no)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (p["roll_no"], p["name"], p["father_name"], p["program_type"],
                  p["current_class"], p["session"], p["contact"]))
            student_id = cur.lastrowid
            cur = c.execute("""
                INSERT INTO institutional_fees
                    (student_id, fee_type, academic_period, amount, date, status)
                VALUES (?, ?, ?, ?, ?, 'Pending')
            """, (student_id, p["fee_type"], p["academic_period"], p["amount"], p["date"]))
            return cur.lastrowid

    def get_fee_record(self, challan_no: int) -> Optional[dict]:
        with self._lock:
            row = self.conn.execute("""
                SELECT f.fee_challan_no, s.roll_no, s.student_name, s.father_name,
                       s.program_type, s.current_class, s.session, s.contact_no,
                       f.fee_type, f.amount, f.date, f.status, f.student_id, f.academic_period
                  FROM institutional_fees f
                  LEFT JOIN fee_students s ON f.student_id = s.student_id
                 WHERE f.fee_challan_no = ?
            """, (challan_no,)).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "roll_no": row[1] or "",
            "name": row[2] or "",
            "father_name": row[3] or "",
            "program_type": row[4] or "",
            "current_class": row[5] or "",
            "session": row[6] or "",
            "contact": row[7] or "",
            "fee_type": row[8] or "",
            "amount": row[9] or 0.0,
            "date": row[10] or "",
            "status": row[11] or "Pending",
            "student_id": row[12],
            "academic_period": row[13] or "",
        }

    def update_fee_record(self, challan_no: int, payload: dict) -> bool:
        """Update student + fee atomically. Returns False if the challan doesn't exist."""
        p = self._clean(payload)
        with self._tx() as c:
            row = c.execute(
                "SELECT student_id FROM institutional_fees WHERE fee_challan_no = ?",
                (challan_no,)).fetchone()
            if not row:
                return False
            c.execute("""
                UPDATE fee_students
                   SET roll_no = ?, student_name = ?, father_name = ?,
                       program_type = ?, current_class = ?, session = ?, contact_no = ?
                 WHERE student_id = ?
            """, (p["roll_no"], p["name"], p["father_name"], p["program_type"],
                  p["current_class"], p["session"], p["contact"], row[0]))
            c.execute("""
                UPDATE institutional_fees
                   SET fee_type = ?, academic_period = ?, amount = ?
                 WHERE fee_challan_no = ?
            """, (p["fee_type"], p["academic_period"], p["amount"], challan_no))
            return True

    def update_fee_status_bulk(self, challan_nos: Iterable[int], status: str) -> int:
        """Set status for many challans. Returns the number of rows actually changed."""
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status!r}")
        ids = [(status, int(n)) for n in challan_nos]
        if not ids:
            return 0
        with self._tx() as c:
            before = c.total_changes
            c.executemany(
                "UPDATE institutional_fees SET status = ? WHERE fee_challan_no = ?", ids)
            return c.total_changes - before

    def delete_fee_record(self, challan_no: int) -> bool:
        """Delete a challan; also removes the student if they have no other fees."""
        with self._tx() as c:
            row = c.execute(
                "SELECT student_id FROM institutional_fees WHERE fee_challan_no = ?",
                (challan_no,)).fetchone()
            if not row:
                return False
            c.execute("DELETE FROM institutional_fees WHERE fee_challan_no = ?", (challan_no,))
            if row[0] is not None:
                c.execute("""
                    DELETE FROM fee_students
                     WHERE student_id = ?
                       AND NOT EXISTS (SELECT 1 FROM institutional_fees WHERE student_id = ?)
                """, (row[0], row[0]))
            return True

    # ---------------------------------------------------------------- queries
    def fetch_all_fees(self, search: str = "", status: Optional[str] = None):
        """All fee rows, newest first. Optional search (name/roll/father/challan) and status filter."""
        sql = """
            SELECT f.fee_challan_no, s.roll_no, s.student_name, s.current_class,
                   f.fee_type, f.amount, f.date, f.status
              FROM institutional_fees f
              LEFT JOIN fee_students s ON f.student_id = s.student_id
             WHERE 1 = 1
        """
        args: list = []
        if search.strip():
            like = f"%{search.strip()}%"
            sql += """ AND (s.student_name LIKE ? OR s.roll_no LIKE ?
                            OR s.father_name LIKE ? OR CAST(f.fee_challan_no AS TEXT) LIKE ?)"""
            args += [like, like, like, like]
        if status:
            if status not in VALID_STATUSES:
                raise ValueError(f"Invalid status: {status!r}")
            sql += " AND f.status = ?"
            args.append(status)
        sql += " ORDER BY f.fee_challan_no DESC"
        with self._lock:
            return self.conn.execute(sql, args).fetchall()

    def get_summary(self) -> dict:
        """Counts and totals for Paid / Pending fees."""
        with self._lock:
            rows = self.conn.execute("""
                SELECT status, COUNT(*), COALESCE(SUM(amount), 0)
                  FROM institutional_fees GROUP BY status
            """).fetchall()
        summary = {s: {"count": 0, "total": 0.0} for s in VALID_STATUSES}
        for status, count, total in rows:
            summary[status] = {"count": count, "total": float(total)}
        return summary

    def backup(self, dest: str | Path) -> Path:
        """Consistent online backup of the database to `dest`."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            target = sqlite3.connect(dest)
            try:
                self.conn.backup(target)
            finally:
                target.close()
        return dest

    # -------------------------------------------------------------- lifecycle
    def close(self) -> None:
        with self._lock:
            try:
                self.conn.close()
            except sqlite3.ProgrammingError:
                pass  # already closed

    def __enter__(self) -> "FeeDatabaseManager":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
