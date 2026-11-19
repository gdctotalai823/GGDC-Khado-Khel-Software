"""
GGDC Khado Khel - Fine Management: data layer (SQLite)

Clean, indexed, migration-safe storage for fine / challan records.
Public method names and return shapes used by the controller are unchanged,
with a few additions (get_record, get_status_stats, update_status_bulk,
delete_record, close) and a challan-number aware search.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

STATUS_PENDING = "Pending"
STATUS_PAID = "Paid"
VALID_STATUSES = (STATUS_PENDING, STATUS_PAID)

# Column aliases used for every DataFrame / Excel export (single source of truth)
_EXPORT_SELECT = """
    SELECT challan_no  AS 'Challan ID',
           student_name AS 'Student Name',
           father_name  AS 'Father Name',
           class        AS 'Class',
           roll_no      AS 'Roll No',
           program      AS 'Program',
           session      AS 'Session',
           fine_type    AS 'Fine Category',
           reason       AS 'Reason / Description',
           amount       AS 'Amount (Rs.)',
           date         AS 'Collection Date',
           status       AS 'Payment Status'
    FROM fine_records
"""


class DatabaseManager:
    def __init__(self, db_name: str = "fines_module.db", folder: str = "database"):
        self.db_path = Path(folder)                 # kept for backward compatibility
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.db_file = self.db_path / db_name       # full path to the .db file

        self.conn = sqlite3.connect(self.db_file)
        self.cursor = self.conn.cursor()
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self._create_tables()

    # ───────────────────────── schema ─────────────────────────
    def _create_tables(self) -> None:
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS fine_records (
                challan_no   INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                father_name  TEXT,
                class        TEXT,
                roll_no      TEXT,
                program      TEXT,
                session      TEXT,
                fine_type    TEXT,
                reason       TEXT,
                amount       REAL,
                date         TEXT,
                status       TEXT DEFAULT 'Pending'
            )
        """)

        # Migrate older databases that were created without the status column
        columns = {row[1] for row in self.cursor.execute("PRAGMA table_info(fine_records)")}
        if "status" not in columns:
            self.cursor.execute(
                "ALTER TABLE fine_records ADD COLUMN status TEXT DEFAULT 'Pending'")

        # Speed up the lookups the UI does constantly
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_fine_roll   ON fine_records(roll_no)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_fine_name   ON fine_records(student_name)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_fine_status ON fine_records(status)")
        self.conn.commit()
        self._create_student_master_table()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS character_certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cert_no TEXT UNIQUE NOT NULL,
                student_name TEXT NOT NULL,
                father_name TEXT NOT NULL,
                roll_no TEXT,
                class_name TEXT NOT NULL,
                program TEXT NOT NULL,
                session TEXT NOT NULL,
                date_of_admission TEXT,
                date_of_leaving TEXT,
                conduct TEXT NOT NULL,
                behavior TEXT NOT NULL,
                character_remarks TEXT,
                pdf_path TEXT,
                date_issued TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_cert_no ON character_certificates(cert_no)")
        self.conn.commit()

    def _create_student_master_table(self) -> None:
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_master (
                roll_no TEXT PRIMARY KEY,
                student_name TEXT NOT NULL,
                father_name TEXT,
                class TEXT,
                program TEXT,
                session TEXT,
                contact TEXT,
                address TEXT,
                admission_date TEXT,
                status TEXT DEFAULT 'Active'
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_master_session ON student_master(session)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_master_class ON student_master(class)")
        self.conn.commit()

    def upsert_student(self, p: dict) -> None:
        """Insert or update a student profile by Roll No."""
        self.cursor.execute("""
            INSERT INTO student_master (roll_no, student_name, father_name, class, program, session, contact, address, admission_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(roll_no) DO UPDATE SET
                student_name=excluded.student_name,
                father_name=excluded.father_name,
                class=excluded.class,
                program=excluded.program,
                session=excluded.session,
                contact=excluded.contact,
                address=excluded.address
        """, (
            p.get("roll_no"), p.get("student_name"), p.get("father_name"),
            p.get("class"), p.get("program"), p.get("session"),
            p.get("contact", ""), p.get("address", ""), p.get("admission_date", ""), "Active"
        ))
        self.conn.commit()

    def get_filtered_students_dataframe(self, session: str = None, class_name: str = None) -> pd.DataFrame:
        """Export students filtered by session, class, or both with full descriptions."""
        query = """
            SELECT roll_no AS 'Roll No',
                   student_name AS 'Student Name',
                   father_name AS 'Father Name',
                   class AS 'Class',
                   program AS 'Program',
                   session AS 'Session',
                   contact AS 'Contact No',
                   address AS 'Address',
                   admission_date AS 'Admission Date',
                   status AS 'Status'
            FROM student_master
            WHERE 1=1
        """
        params = []
        if session and session != "All Sessions":
            query += " AND session = ?"
            params.append(session)
        if class_name and class_name != "All Classes":
            query += " AND class = ?"
            params.append(class_name)
            
        query += " ORDER BY roll_no ASC"
        return pd.read_sql_query(query, self.conn, params=params)

    def fetch_all_master_students(self):
        self.cursor.execute("SELECT roll_no, student_name, father_name, class, program, session, contact FROM student_master ORDER BY roll_no ASC")
        return self.cursor.fetchall()

    # ───────────────────────── writes ─────────────────────────
    def insert_record(self, payload: dict) -> int:
        self.cursor.execute("""
            INSERT INTO fine_records
                (student_name, father_name, class, roll_no, program, session,
                 fine_type, reason, amount, date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload["name"], payload["father_name"], payload["class"],
            payload["roll_no"], payload["program"], payload["session"],
            payload["fine_type"], payload["reason"], payload["amount"],
            payload["date"], STATUS_PENDING,
        ))
        self.conn.commit()
        return self.cursor.lastrowid

    def update_record(self, challan_no: int, payload: dict) -> None:
        self.cursor.execute("""
            UPDATE fine_records
               SET student_name = ?, father_name = ?, class = ?, roll_no = ?,
                   program = ?, session = ?, fine_type = ?, reason = ?, amount = ?
             WHERE challan_no = ?
        """, (
            payload["name"], payload["father_name"], payload["class"],
            payload["roll_no"], payload["program"], payload["session"],
            payload["fine_type"], payload["reason"], payload["amount"], challan_no,
        ))
        self.conn.commit()

    def update_status(self, challan_no: int, status: str) -> None:
        self.update_status_bulk([challan_no], status)

    def update_status_bulk(self, challan_nos: Iterable[int], status: str) -> int:
        """Set the payment status of many challans in one transaction."""
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status!r}")
        ids = [(status, int(n)) for n in challan_nos]
        if not ids:
            return 0
        self.cursor.executemany(
            "UPDATE fine_records SET status = ? WHERE challan_no = ?", ids)
        self.conn.commit()
        return len(ids)

    def delete_record(self, challan_no: int) -> None:
        self.cursor.execute("DELETE FROM fine_records WHERE challan_no = ?", (challan_no,))
        self.conn.commit()

    # ───────────────────────── reads ─────────────────────────
    def get_record(self, challan_no: int) -> Optional[dict]:
        """Return one full record as a dict (column name -> value) or None."""
        cur = self.conn.execute(
            "SELECT * FROM fine_records WHERE challan_no = ?", (challan_no,))
        row = cur.fetchone()
        if row is None:
            return None
        return {desc[0]: value for desc, value in zip(cur.description, row)}

    def fetch_all_records(self):
        self.cursor.execute("""
            SELECT challan_no, student_name, class, fine_type, reason, amount, date, status
              FROM fine_records
             ORDER BY challan_no DESC
        """)
        return self.cursor.fetchall()

    def get_student_by_roll(self, roll_no: str):
        """Look up the most recent record for a Roll No (used for auto-fill)."""
        if not roll_no or roll_no.strip().upper() == "N/A":
            return None
        self.cursor.execute("""
            SELECT student_name, father_name, class, program, session
              FROM fine_records
             WHERE roll_no = ?
             ORDER BY challan_no DESC
             LIMIT 1
        """, (roll_no,))
        return self.cursor.fetchone()

    def get_summary_stats(self):
        """(total_amount, total_count, [(fine_type, count, amount), ...])"""
        self.cursor.execute("SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM fine_records")
        total_amt, total_cnt = self.cursor.fetchone()

        self.cursor.execute("""
            SELECT fine_type, COUNT(*), COALESCE(SUM(amount), 0)
              FROM fine_records
             GROUP BY fine_type
             ORDER BY SUM(amount) DESC
        """)
        return float(total_amt), int(total_cnt), self.cursor.fetchall()

    def get_status_stats(self) -> dict:
        """Paid vs. pending totals, e.g. for the status bar."""
        stats = {
            "paid_amt": 0.0, "paid_cnt": 0,
            "pending_amt": 0.0, "pending_cnt": 0,
        }
        self.cursor.execute("""
            SELECT COALESCE(status, 'Pending'), COUNT(*), COALESCE(SUM(amount), 0)
              FROM fine_records
             GROUP BY COALESCE(status, 'Pending')
        """)
        for status, cnt, amt in self.cursor.fetchall():
            key = "paid" if status == STATUS_PAID else "pending"
            stats[f"{key}_cnt"] += int(cnt)
            stats[f"{key}_amt"] += float(amt)
        return stats

    def search_clearance(self, query_text: str):
        """Search by student name, roll number, father name or challan number (F-0012 / 12)."""
        text = (query_text or "").strip()
        like = f"%{text}%"
        match = re.fullmatch(r"(?:F-?)?0*(\d+)", text, flags=re.IGNORECASE)
        challan = int(match.group(1)) if match else -1

        self.cursor.execute("""
            SELECT challan_no, student_name, father_name, class, roll_no,
                   fine_type, reason, amount, date, status
              FROM fine_records
             WHERE student_name LIKE ? OR roll_no LIKE ? OR father_name LIKE ?
                   OR challan_no = ?
             ORDER BY challan_no DESC
        """, (like, like, like, challan))
        return self.cursor.fetchall()

    # ───────────────────────── exports ─────────────────────────
    def get_range_dataframe(self, from_num: int, to_num: int) -> pd.DataFrame:
        query = _EXPORT_SELECT + " WHERE challan_no BETWEEN ? AND ? ORDER BY challan_no ASC"
        return pd.read_sql_query(query, self.conn, params=(from_num, to_num))

    def get_all_dataframe(self) -> pd.DataFrame:
        return pd.read_sql_query(_EXPORT_SELECT + " ORDER BY challan_no ASC", self.conn)

    # ───────────────────────── lifecycle ─────────────────────────
    def close(self) -> None:
        try:
            self.conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

 
