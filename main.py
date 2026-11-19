"""
GGDC Khado Khel - Enterprise Fine & Special Fine Management System (PySide6 Edition)
"""
import os
import sqlite3
import sys
import urllib.parse
from datetime import datetime

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QColor, QDesktopServices, QFont, QKeySequence, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QMainWindow, QMenu, QMessageBox, QProgressDialog, QPushButton,
    QTableWidgetItem, QVBoxLayout,
)

from database import DatabaseManager, STATUS_PAID, STATUS_PENDING
from fee_database import FeeDatabaseManager
from fee_engine import resolve_fee_category
from pdf_generator import PDFGenerator
from cc_dialog import CCDialog
from ui.components import (
    ACCENT_2, BG_RAISED, BORDER_HI, STYLESHEET, TEXT, TEXT_DIM, ApplicationUI,
    CLASSES, PROGRAMS, SESSIONS, FINE_TYPES, _combo, _line_edit, _amount_edit
)

TYPE_COLORS = {
    "Special Fine": "#f59e0b",
    "Regular Fine": "#60a5fa",
    "Library Fine": "#a78bfa",
    "Discipline Fine": "#f43f5e",
    "Sports Fine": "#34d399",
    "Damage Fine": "#fb923c",
}
AMOUNT_COLOR = "#fbbf24"
CHALLAN_COLOR = "#22d3ee"
SUCCESS_COLOR = "#10b981"
PENDING_COLOR = "#fbbf24"
DEFAULT_CELL_COLOR = "#e8eefc"

STATUS_BG = {STATUS_PAID: "#0e2b24", STATUS_PENDING: "#2e2610"}
DB_CANDIDATES = ("fines.db", "database.db", "college_fines.db")

EXTRA_QSS = f"""
QMenu {{
    background-color: {BG_RAISED}; color: {TEXT};
    border: 1.5px solid {ACCENT_2}; border-radius: 10px; padding: 6px;
}}
QMenu::item {{ padding: 9px 28px 9px 14px; border-radius: 6px; margin: 1px 0; }}
QMenu::item:selected {{ background-color: #6366f1; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {BORDER_HI}; margin: 6px 8px; }}
QStatusBar {{ background-color: #0a1020; color: {TEXT_DIM}; border-top: 1px solid {BORDER_HI}; }}
QStatusBar::item {{ border: none; }}
QToolTip {{ background-color: {BG_RAISED}; color: {TEXT}; border: 1px solid {ACCENT_2}; border-radius: 6px; padding: 6px 8px; }}
QMessageBox {{ background-color: {BG_RAISED}; }}
QMessageBox QLabel {{ color: {TEXT}; font-size: 13px; }}
QMessageBox QPushButton {{ min-width: 84px; min-height: 30px; }}
QFrame#dialogHeader {{ background-color: #111b36; border: 1px solid {BORDER_HI}; border-radius: 12px; }}
"""


def _split_items(text):
    return [p.strip() for p in text.replace("\n", ",").split(",") if p.strip()]


class EditRecordDialog(QDialog):
    def __init__(self, rec_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Fine Record & Correct Challan")
        self.setModal(True)
        self.resize(520, 640)
        self.record_id = rec_dict["id"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header = QFrame()
        header.setObjectName("dialogHeader")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 12, 16, 12)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("✏️  Edit Fine Record")
        title.setStyleSheet(f"color:{TEXT}; font-size:16px; font-weight:800; background:transparent;")
        sub = QLabel("Corrections will regenerate the challan PDF")
        sub.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; background:transparent;")
        title_box.addWidget(title)
        title_box.addWidget(sub)

        badge = QLabel(f"GGDC-{self.record_id:04d}")
        badge.setStyleSheet(
            f"color:{CHALLAN_COLOR}; font-size:15px; font-weight:800; background:#0d1528;"
            f"border:1.5px solid {CHALLAN_COLOR}; border-radius:8px; padding:6px 14px;")
        h_lay.addLayout(title_box, 1)
        h_lay.addWidget(badge)
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.name_edit = _line_edit("Student Name", str(rec_dict.get("name", "")))
        self.fname_edit = _line_edit("Father Name", str(rec_dict.get("father_name", "")))
        self.class_combo = _combo(CLASSES)
        self.class_combo.setCurrentText(str(rec_dict.get("class", CLASSES[0])))
        self.roll_edit = _line_edit("Roll No", str(rec_dict.get("roll_no", "")))
        self.program_combo = _combo(PROGRAMS)
        self.program_combo.setCurrentText(str(rec_dict.get("program", PROGRAMS[0])))
        self.session_combo = _combo(SESSIONS)
        self.session_combo.setCurrentText(str(rec_dict.get("session", SESSIONS[0])))
        self.type_combo = _combo(FINE_TYPES)
        self.type_combo.setCurrentText(str(rec_dict.get("fine_type", FINE_TYPES[0])))
        self.reason_edit = _line_edit("Reason", str(rec_dict.get("reason", "")))
        self.amount_edit = _amount_edit("Amount")
        self.amount_edit.setText(str(rec_dict.get("amount", "")))

        form.addRow("Student Name *", self.name_edit)
        form.addRow("Father Name", self.fname_edit)
        form.addRow("Class", self.class_combo)
        form.addRow("Roll No", self.roll_edit)
        form.addRow("Program", self.program_combo)
        form.addRow("Session", self.session_combo)
        form.addRow("Fine Type", self.type_combo)
        form.addRow("Reason *", self.reason_edit)
        form.addRow("Amount (Rs.) *", self.amount_edit)
        layout.addLayout(form)
        layout.addStretch(1)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color:#f43f5e; font-weight:600; background:transparent;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(44)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("💾  Save Changes && Regenerate Challan PDF")
        save_btn.setProperty("variant", "success")
        save_btn.setMinimumHeight(44)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)

        btn_row.addWidget(cancel_btn, 1)
        btn_row.addWidget(save_btn, 3)
        layout.addLayout(btn_row)
        self.name_edit.setFocus()

    def _on_save(self):
        data = self.get_updated_payload()
        if not data["name"] or not data["reason"] or data["amount"] <= 0:
            self.error_label.setText("⚠ Please fill in all required fields correctly.")
            self.error_label.show()
            return
        self.accept()

    def get_updated_payload(self):
        try:
            amount = float(self.amount_edit.text().replace(",", "").replace("Rs.", "").strip())
        except ValueError:
            amount = 0.0
        return {
            "name": self.name_edit.text().strip(),
            "father_name": self.fname_edit.text().strip(),
            "class": self.class_combo.currentText(),
            "roll_no": self.roll_edit.text().strip() or "N/A",
            "program": self.program_combo.currentText(),
            "session": self.session_combo.currentText(),
            "fine_type": self.type_combo.currentText(),
            "reason": self.reason_edit.text().strip(),
            "amount": amount,
        }


class EditFeeRecordDialog(QDialog):
    def __init__(self, rec_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Institutional Fee Record & Correct Challan")
        self.setModal(True)
        self.resize(520, 640)
        self.record_id = rec_dict["id"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header = QFrame()
        header.setObjectName("dialogHeader")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 12, 16, 12)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("✏️  Edit Institutional Fee Record")
        title.setStyleSheet(f"color:{TEXT}; font-size:16px; font-weight:800; background:transparent;")
        sub = QLabel("Corrections will update database and regenerate the challan PDF")
        sub.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; background:transparent;")
        title_box.addWidget(title)
        title_box.addWidget(sub)

        badge = QLabel(f"FEE-{self.record_id:04d}")
        badge.setStyleSheet(
            f"color:{CHALLAN_COLOR}; font-size:15px; font-weight:800; background:#0d1528;"
            f"border:1.5px solid {CHALLAN_COLOR}; border-radius:8px; padding:6px 14px;")
        h_lay.addLayout(title_box, 1)
        h_lay.addWidget(badge)
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.name_edit = _line_edit("Student Name", str(rec_dict.get("name", "")))
        self.fname_edit = _line_edit("Father Name", str(rec_dict.get("father_name", "")))
        self.roll_edit = _line_edit("Roll No (Optional)", str(rec_dict.get("roll_no", "")))

        self.program_combo = _combo(["Pre-Medical", "Pre-Engineering", "Computer Sci (Inter)", "Humanities/Arts", "ADA", "ADS"])
        self.program_combo.setCurrentText(str(rec_dict.get("program_type", "Pre-Medical")))

        self.class_combo = _combo(["1st Year", "2nd Year", "1st Semester", "2nd Semester", "3rd Semester", "4th Semester"])
        self.class_combo.setCurrentText(str(rec_dict.get("current_class", "1st Year")))

        self.session_combo = _combo(SESSIONS)
        self.session_combo.setCurrentText(str(rec_dict.get("session", SESSIONS[0])))

        self.fee_type_combo = _combo(["Admission Fee", "Promotion Fee", "Semester Fee", "Institutional Fee"])
        self.fee_type_combo.setCurrentText(str(rec_dict.get("fee_type", "Admission Fee")))

        self.amount_edit = _amount_edit("Amount")
        self.amount_edit.setText(str(rec_dict.get("amount", "")))

        form.addRow("Student Name *", self.name_edit)
        form.addRow("Father Name", self.fname_edit)
        form.addRow("Roll No", self.roll_edit)
        form.addRow("Program Type", self.program_combo)
        form.addRow("Class / Semester", self.class_combo)
        form.addRow("Session", self.session_combo)
        form.addRow("Fee Type", self.fee_type_combo)
        form.addRow("Amount (Rs.) *", self.amount_edit)
        layout.addLayout(form)
        layout.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(44)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("💾  Save Changes && Regenerate Challan PDF")
        save_btn.setProperty("variant", "success")
        save_btn.setMinimumHeight(44)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn, 1)
        btn_row.addWidget(save_btn, 3)
        layout.addLayout(btn_row)

    def get_updated_payload(self):
        try:
            amount = float(self.amount_edit.text().replace(",", "").replace("Rs.", "").strip())
        except ValueError:
            amount = 0.0
        return {
            "name": self.name_edit.text().strip(),
            "father_name": self.fname_edit.text().strip(),
            "roll_no": self.roll_edit.text().strip(),
            "program_type": self.program_combo.currentText(),
            "current_class": self.class_combo.currentText(),
            "session": self.session_combo.currentText(),
            "fee_type": self.fee_type_combo.currentText(),
            "academic_period": self.class_combo.currentText(),
            "amount": amount,
            "contact": ""
        }


class EnterpriseFineCollectionApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            "GGDC Khado Khel — Enterprise Fine & Special Fine Management System (PySide6 Edition)")
        self.resize(1360, 840)
        self.setMinimumSize(1100, 700)

        self.db = DatabaseManager()
        self.pdf_gen = PDFGenerator()
        self.fee_db = FeeDatabaseManager()

        self.ui = ApplicationUI(self)
        self.setCentralWidget(self.ui)

        self._build_status_bar()
        self._wire_tables()
        self._wire_autofill()
        # Wire the institutional fee excel export button
        if hasattr(self.ui, "export_fee_excel_btn"):
            self.ui.export_fee_excel_btn.clicked.connect(self.export_institutional_fees_excel)
        # Wire up the Character Certificate button if present in UI
        if hasattr(self.ui, "cc_btn"):
            self.ui.cc_btn.clicked.connect(self.open_character_certificate_dialog)
            
        self.setup_shortcuts()

        self._refresh_all(quiet=True)
        self.load_fee_records()
        self.entries["name_entry"].setFocus()
        
    def import_students_from_excel(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Students Excel", "", "Excel Files (*.xlsx *.xls)")
        if not file_path:
            return

        try:
            import pandas as pd
            df = pd.read_excel(file_path)
            
            count = 0
            for _, row in df.iterrows():
                payload = {
                    "roll_no": str(row.get("Roll No", "")).strip(),
                    "student_name": str(row.get("Student Name", "")).strip(),
                    "father_name": str(row.get("Father Name", "N/A")).strip(),
                    "class": str(row.get("Class", CLASSES[0])).strip(),
                    "program": str(row.get("Program", PROGRAMS[0])).strip(),
                    "session": str(row.get("Session", SESSIONS[0])).strip(),
                    "contact": str(row.get("Contact", "")).strip(),
                }
                if payload["roll_no"] and payload["roll_no"].lower() != "nan":
                    self.db.upsert_student(payload)
                    count += 1
                    
            self.load_master_students_table()
            QMessageBox.information(self, "Success", f"Successfully imported/updated {count} student records from Excel!")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to read Excel file:\n{e}")

    def export_student_directory_report(self):
        selected_session = self.ui.dir_session_combo.currentText()
        selected_class = self.ui.dir_class_combo.currentText()
        
        df = self.db.get_filtered_students_dataframe(selected_session, selected_class)
        if df.empty:
            QMessageBox.information(self, "No Records", "No student records found for the selected filters.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Student Report", f"Students_{selected_session}_{selected_class}.xlsx".replace(" ", "_"), "Excel Files (*.xlsx)")
        if not file_path:
            return

        try:
            with_ext = file_path if file_path.lower().endswith(".xlsx") else file_path + ".xlsx"
            self._styled_excel(df, with_ext)
            self._toast(f"✅ Report exported successfully → {with_ext}")
            self._open_path(with_ext)
        except Exception as err:
            QMessageBox.critical(self, "Export Failed", f"Could not write the Excel file:\n{err}")

    def load_master_students_table(self):
        if not hasattr(self.ui, "master_tree"):
            return
        records = self.db.fetch_all_master_students()
        table = self.ui.master_tree
        cols = ["Roll No", "Student Name", "Father Name", "Class", "Program", "Session", "Contact"]
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setRowCount(len(records))
        for row_idx, row in enumerate(records):
            for col_idx, val in enumerate(row):
                table.setItem(row_idx, col_idx, QTableWidgetItem(str(val if val else "")))

    def setup_shortcuts(self):
        for seq, idx in (("Ctrl+G", 0), ("Ctrl+D", 1), ("Ctrl+L", 2), ("Ctrl+B", 3)):
            QShortcut(QKeySequence(seq), self,
                      activated=lambda i=idx: self.ui.setCurrentIndex(i))
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.backup_database)
        
        # 💡 Add the Character Certificate shortcut here:
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.open_character_certificate_dialog)

    def _build_status_bar(self):
        bar = self.statusBar()
        bar.setSizeGripEnabled(True)

        def chip(color):
            lbl = QLabel("")
            lbl.setStyleSheet(
                f"color:{color}; font-weight:700; padding:2px 12px; margin:2px 3px;"
                f"background:#0d1528; border:1px solid {BORDER_HI}; border-radius:10px;")
            bar.addPermanentWidget(lbl)
            return lbl

        self.lbl_status_records = chip(ACCENT_2)
        self.lbl_status_total = chip(AMOUNT_COLOR)
        self.lbl_status_paid = chip(SUCCESS_COLOR)
        self.lbl_status_pending = chip(PENDING_COLOR)
        self.lbl_status_records.setText("🧾 Records: 0")
        self.lbl_status_total.setText("💰 Total: Rs. 0")
        self.lbl_status_paid.setText("✅ Paid: Rs. 0")
        self.lbl_status_pending.setText("⏳ Pending: Rs. 0")

        hint = QLabel("Ctrl+Shift+S Backup  •  Right-click rows for actions (multi-select supported)")
        hint.setStyleSheet(f"color:{TEXT_DIM}; padding:0 12px; background:transparent;")
        bar.addPermanentWidget(hint)

    def _wire_tables(self):
        for table in (self.tree, self.sum_tree, self.res_tree):
            table.setContextMenuPolicy(Qt.CustomContextMenu)
            table.customContextMenuRequested.connect(
                lambda pos, t=table: self._table_menu(t, pos))
        self.tree.cellDoubleClicked.connect(self._use_row_for_range)
        self.res_tree.cellDoubleClicked.connect(self._use_row_for_range_from_results)

        # Wire context menu for institutional fee records table
        if hasattr(self.ui, "fee_tree"):
            self.ui.fee_tree.setContextMenuPolicy(Qt.CustomContextMenu)
            self.ui.fee_tree.customContextMenuRequested.connect(
                lambda pos: self._fee_table_menu(self.ui.fee_tree, pos)
            )

    def open_character_certificate_dialog(self):
        dialog = CCDialog(self.db, self)
        dialog.exec()

    def export_institutional_fees_excel(self):
        records = self.fee_db.fetch_all_fees()
        if not records:
            QMessageBox.information(self, "Info", "No institutional fee records found to export.")
            return

        import pandas as pd
        data = []
        for row in records:
            # (challan_no, roll_no, student_name, current_class, fee_type, amount, date, status)
            data.append({
                "Challan No": f"FEE-{row[0]:04d}",
                "Roll No": row[1] or "N/A",
                "Student Name": row[2],
                "Class / Semester": row[3],
                "Fee Type": row[4],
                "Amount (Rs.)": float(row[5]) if row[5] else 0.0,
                "Collection Date": row[6],
                "Payment Status": row[7] or "Pending"
            })
        
        df = pd.DataFrame(data)
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Institutional Fee Report", "Institutional_Fee_Report.xlsx", "Excel Files (*.xlsx)")
        if not file_path:
            return

        try:
            with_ext = file_path if file_path.lower().endswith(".xlsx") else file_path + ".xlsx"
            self._styled_excel(df, with_ext) # Reuses your existing professional styling engine!
            self._toast(f"✅ Exported successfully → {with_ext}")
            self._open_path(with_ext)
        except Exception as err:
            QMessageBox.critical(self, "Export Failed", f"Could not write the Excel file:\n{err}")

    def _wire_autofill(self):
        if "roll_entry" in self.entries:
            self.entries["roll_entry"].editingFinished.connect(self._check_student_autofill)

    def _check_student_autofill(self):
        roll_no = self.entries["roll_entry"].text().strip()
        if not roll_no or roll_no.upper() == "N/A":
            return
        student = self.db.get_student_by_roll(roll_no)
        if not student:
            return
        name, fname, cls, prog, sess = student
        if name and not self.entries["name_entry"].text().strip():
            self.entries["name_entry"].setText(name)
        if fname and fname not in ("N/A", "Batch Import") and not self.entries["fname_entry"].text().strip():
            self.entries["fname_entry"].setText(fname)
        if cls:
            self.entries["class_combo"].setCurrentText(cls)
        if prog:
            self.entries["program_combo"].setCurrentText(prog)
        if sess:
            self.entries["session_combo"].setCurrentText(sess)
        self._toast(f"✨ Auto-filled details for Roll No: {roll_no}", 3000)

    def _refresh_all(self, quiet=False):
        self.load_records(quiet=quiet)
        self.load_summary_stats()
        self.load_fee_records()

    def _toast(self, text, ms=5000):
        self.statusBar().showMessage(text, ms)
        
    @staticmethod
    def _styled_excel(df, path):
        """Polished workbook: banded rows, status colours, currency format, totals row."""
        try:
            from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            df.to_excel(path, index=False)
            return
        import pandas as pd

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Report")
            ws = writer.sheets["Report"]

            header_fill = PatternFill("solid", fgColor="26337A")
            band_fill = PatternFill("solid", fgColor="F3F6FE")
            paid_fill = PatternFill("solid", fgColor="D1FAE5")
            pend_fill = PatternFill("solid", fgColor="FEF3C7")
            thin = Side(style="thin", color="D5DCF0")
            border = Border(left=thin, right=thin, top=thin, bottom=thin)

            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF", size=11)
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = border
            ws.row_dimensions[1].height = 26

            cols = list(df.columns)
            amount_idx = next((i for i, c in enumerate(cols, 1)
                               if "amount" in str(c).lower()), None)
            status_idx = next((i for i, c in enumerate(cols, 1)
                               if "status" in str(c).lower()), None)

            for r in range(2, ws.max_row + 1):
                for c in range(1, ws.max_column + 1):
                    cell = ws.cell(row=r, column=c)
                    cell.border = border
                    cell.alignment = Alignment(vertical="center")
                    if r % 2 == 1:
                        cell.fill = band_fill
                if amount_idx:
                    cell = ws.cell(row=r, column=amount_idx)
                    if isinstance(cell.value, (int, float)):
                        cell.number_format = '#,##0'
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        cell.font = Font(bold=True)
                if status_idx:
                    cell = ws.cell(row=r, column=status_idx)
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.font = Font(bold=True)
                    if str(cell.value) == STATUS_PAID:
                        cell.fill = paid_fill
                    elif str(cell.value) == STATUS_PENDING:
                        cell.fill = pend_fill

            if amount_idx and ws.max_row >= 2:
                total_row = ws.max_row + 1
                letter = get_column_letter(amount_idx)
                label = ws.cell(row=total_row, column=max(amount_idx - 1, 1), value="TOTAL")
                label.font = Font(bold=True, color="FFFFFF")
                label.fill = header_fill
                label.alignment = Alignment(horizontal="right")
                total = ws.cell(row=total_row, column=amount_idx,
                                value=f"=SUM({letter}2:{letter}{total_row - 1})")
                total.font = Font(bold=True, color="FFFFFF")
                total.fill = header_fill
                total.number_format = '#,##0'
                total.alignment = Alignment(horizontal="right")

            ws.freeze_panes = "A2"
            ws.auto_filter.ref = f"A1:{get_column_letter(ws.max_column)}{ws.max_row - (1 if amount_idx else 0)}"
            for idx, column in enumerate(cols, start=1):
                longest = max([len(str(column))] + [len(str(v)) for v in df[column].head(500)])
                ws.column_dimensions[get_column_letter(idx)].width = min(max(longest + 3, 11), 48)

    @staticmethod
    def _open_path(path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @staticmethod
    def _cell(text, align=Qt.AlignVCenter | Qt.AlignLeft, color=None, bold=False, bg=None):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(align)
        item.setToolTip(str(text))
        if color:
            item.setForeground(QColor(color))
        if bg:
            item.setBackground(QColor(bg))
        if bold:
            font = QFont()
            font.setBold(True)
            item.setFont(font)
        return item

    def _fill_row(self, table, row_idx, values, type_col=None, amount_col=None,
                  status_col=None, challan_col=0):
        for col_idx, val in enumerate(values):
            if col_idx == challan_col:
                item = self._cell(val, Qt.AlignCenter, CHALLAN_COLOR, bold=True)
            elif col_idx == amount_col:
                item = self._cell(val, Qt.AlignVCenter | Qt.AlignRight, AMOUNT_COLOR, bold=True)
            elif col_idx == type_col:
                item = self._cell(val, Qt.AlignCenter,
                                  TYPE_COLORS.get(str(val), DEFAULT_CELL_COLOR), bold=True)
            elif col_idx == status_col:
                paid = str(val) == STATUS_PAID
                item = self._cell(val, Qt.AlignCenter,
                                  SUCCESS_COLOR if paid else PENDING_COLOR, bold=True,
                                  bg=STATUS_BG[STATUS_PAID if paid else STATUS_PENDING])
            else:
                item = self._cell(val)
            table.setItem(row_idx, col_idx, item)

    @staticmethod
    def _parse_amount(text):
        try:
            value = float(str(text).replace(",", "").replace("Rs.", "").strip())
            return value if value > 0 else None
        except ValueError:
            return None

    @staticmethod
    def _challan_to_int(text, prefix="GGDC-"):
        try:
            return int(text.strip().upper().replace(prefix, ""))
        except (ValueError, AttributeError):
            return None

    def _get_record_dict_by_id(self, raw_id):
        try:
            rec = self.db.get_record(raw_id)
        except Exception:
            return None
        if not rec:
            return None
        return {
            "id": raw_id,
            "name": rec.get("student_name", ""),
            "father_name": rec.get("father_name", "") or "",
            "class": rec.get("class", CLASSES[0]),
            "roll_no": rec.get("roll_no", "N/A"),
            "program": rec.get("program", PROGRAMS[0]),
            "session": rec.get("session", SESSIONS[0]),
            "fine_type": rec.get("fine_type", FINE_TYPES[0]),
            "reason": rec.get("reason", ""),
            "amount": self._parse_amount(rec.get("amount", 0.0)) or 0.0,
        }

    def _selected_ids(self, table, clicked_row, prefix="GGDC-"):
        rows = {i.row() for i in table.selectedIndexes()}
        if clicked_row not in rows:
            rows = {clicked_row}
        ids = []
        for r in sorted(rows):
            item = table.item(r, 0)
            num = self._challan_to_int(item.text(), prefix=prefix) if item else None
            if num is not None:
                ids.append(num)
        return ids

    def _fee_table_menu(self, table, pos):
        index = table.indexAt(pos)
        if not index.isValid():
            return
        row, col = index.row(), index.column()
        ids = self._selected_ids(table, row, prefix="FEE-")
        many = len(ids) > 1

        menu = QMenu(table)
        act_edit = act_regen = act_paid = act_pending = None

        if not many and ids:
            act_edit = menu.addAction("✏️  Edit Fee Record & Correct Challan...")
            act_regen = menu.addAction("🔄  Regenerate Fee Challan PDF")
            menu.addSeparator()

        suffix = f"  ({len(ids)} selected)" if many else ""
        act_paid = menu.addAction(f"✅  Mark as Paid{suffix}")
        act_pending = menu.addAction(f"⏳  Mark as Pending{suffix}")
        menu.addSeparator()

        act_cell = menu.addAction("📋  Copy cell")
        act_row = menu.addAction("📄  Copy row")
        act_challan = menu.addAction("🧾  Copy challan no")

        chosen = menu.exec(table.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        challan_item = table.item(row, 0)
        raw_challan_text = challan_item.text() if challan_item else ""
        raw_id = self._challan_to_int(raw_challan_text, prefix="FEE-")
        clip = QApplication.clipboard()

        if chosen is act_edit and raw_id is not None:
            self._edit_fee_record_dialog(raw_id)
        elif chosen is act_regen and raw_id is not None:
            self._regenerate_fee_pdf(raw_id)
        elif chosen is act_paid and ids:
            self._set_fee_status(ids, "Paid")
        elif chosen is act_pending and ids:
            self._set_fee_status(ids, "Pending")
        elif chosen is act_cell:
            item = table.item(row, col)
            clip.setText(item.text() if item else "")
            self._toast("📋 Cell copied to clipboard", 2500)
        elif chosen is act_row:
            cells = [(table.item(row, c).text() if table.item(row, c) else "")
                     for c in range(table.columnCount())]
            clip.setText("\t".join(cells))
            self._toast("📄 Row copied to clipboard", 2500)
        elif chosen is act_challan and challan_item:
            clip.setText(raw_challan_text)
            self._toast("🧾 Challan number copied", 2500)

    def _set_fee_status(self, ids, status):
        try:
            self.fee_db.update_fee_status_bulk(ids, status)
        except Exception as ex:
            QMessageBox.critical(self, "Database Error", f"Could not update fee status: {ex}")
            return
        self.load_fee_records()
        icon = "✅" if status == "Paid" else "⏳"
        what = f"Challan #FEE-{ids[0]:04d}" if len(ids) == 1 else f"{len(ids)} challans"
        self._toast(f"{icon} {what} marked as {status}")

    def _edit_fee_record_dialog(self, challan_id):
        rec = self.fee_db.get_fee_record(challan_id)
        if not rec:
            QMessageBox.warning(self, "Error", f"Could not find fee record for ID {challan_id}")
            return

        dialog = EditFeeRecordDialog(rec, self)
        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_updated_payload()
        if not payload["name"] or payload["amount"] <= 0:
            QMessageBox.warning(self, "Invalid Data", "Please fill in Student Name and a valid Amount greater than 0.")
            return

        try:
            self.fee_db.update_fee_record(challan_id, payload)
        except Exception as ex:
            QMessageBox.critical(self, "Database Error", f"Failed to update fee record: {ex}")
            return

        self.load_fee_records()
        self._regenerate_fee_pdf(challan_id)
        self._toast(f"✅ Fee Record FEE-{challan_id:04d} updated successfully!")

    def _regenerate_fee_pdf(self, challan_id):
        rec = self.fee_db.get_fee_record(challan_id)
        if not rec:
            QMessageBox.warning(self, "Error", f"Could not find fee record for ID {challan_id}")
            return

        challan_no = f"FEE-{challan_id:04d}"
        student_payload = {
            "name": rec.get("name", ""),
            "father_name": rec.get("father_name", ""),
            "class": rec.get("current_class", ""),
            "roll_no": rec.get("roll_no", ""),
            "program": rec.get("program_type", ""),
            "session": rec.get("session", ""),
            "purpose": rec.get("fee_type", "Institutional Fee"),
            "description": f"[{rec.get('fee_type', '')}] Academic Fee for {rec.get('current_class', '')}"
        }
        amt_val = rec.get("amount", 0.0)

        try:
            pdf_file_path = self.pdf_gen.generate_pdf(student_payload, challan_no, amt_val)
        except Exception as e:
            QMessageBox.critical(self, "PDF Error", f"Failed to generate fee challan PDF: {e}")
            return

        self._toast(f"✅ Regenerated Fee Challan #{challan_no}")
        QMessageBox.information(
            self, "Challan Regenerated",
            f"Fee Challan #{challan_no} successfully updated & generated at:\n{pdf_file_path}")
        self._open_path(pdf_file_path)

    def _table_menu(self, table, pos):
        index = table.indexAt(pos)
        if not index.isValid():
            return
        row, col = index.row(), index.column()
        menu = QMenu(table)

        act_edit = act_regen = act_whatsapp = act_folder = act_paid = act_pending = None
        ids = self._selected_ids(table, row, prefix="GGDC-")
        many = len(ids) > 1

        if table is not self.sum_tree:
            if not many:
                act_edit = menu.addAction("✏️  Edit Record & Correct Challan...")
                act_regen = menu.addAction("🔄  Regenerate Challan PDF")
                act_whatsapp = menu.addAction("💬  Share Challan Details via WhatsApp")
            act_folder = menu.addAction("📂  Open PDF Output Folder")
            menu.addSeparator()
            suffix = f"  ({len(ids)} selected)" if many else ""
            act_paid = menu.addAction(f"✅  Mark as Paid{suffix}")
            act_pending = menu.addAction(f"⏳  Mark as Pending{suffix}")
            menu.addSeparator()

        act_cell = menu.addAction("📋  Copy cell")
        act_row = menu.addAction("📄  Copy row")
        act_challan = None
        if table is not self.sum_tree:
            act_challan = menu.addAction("🧾  Copy challan no")

        chosen = menu.exec(table.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        challan_item = table.item(row, 0)
        raw_challan_text = challan_item.text() if challan_item else ""
        raw_id = self._challan_to_int(raw_challan_text, prefix="GGDC-")
        clip = QApplication.clipboard()

        if chosen is act_edit and raw_id is not None:
            self._edit_record_dialog(raw_id)
        elif chosen is act_regen and raw_id is not None:
            self._regenerate_challan_pdf(raw_id)
        elif chosen is act_whatsapp and raw_id is not None:
            self._share_whatsapp(raw_id)
        elif chosen is act_folder:
            self._open_pdf_folder()
        elif chosen is act_paid and ids:
            self._set_status(ids, STATUS_PAID)
        elif chosen is act_pending and ids:
            self._set_status(ids, STATUS_PENDING)
        elif chosen is act_cell:
            item = table.item(row, col)
            clip.setText(item.text() if item else "")
            self._toast("📋 Cell copied to clipboard", 2500)
        elif chosen is act_row:
            cells = [(table.item(row, c).text() if table.item(row, c) else "")
                     for c in range(table.columnCount())]
            clip.setText("\t".join(cells))
            self._toast("📄 Row copied to clipboard", 2500)
        elif chosen is act_challan and challan_item:
            clip.setText(raw_challan_text)
            self._toast("🧾 Challan number copied", 2500)

    def _set_status(self, ids, status):
        try:
            self.db.update_status_bulk(ids, status)
        except Exception as ex:
            QMessageBox.critical(self, "Database Error", f"Could not update status: {ex}")
            return
        self._refresh_all(quiet=True)
        icon = "✅" if status == STATUS_PAID else "⏳"
        what = f"Challan #{ids[0]:04d}" if len(ids) == 1 else f"{len(ids)} challans"
        self._toast(f"{icon} {what} marked as {status}")

    def _share_whatsapp(self, raw_id):
        rec = self._get_record_dict_by_id(raw_id)
        if not rec:
            QMessageBox.warning(self, "Error", f"Could not find record for ID {raw_id}")
            return
        challan_no = f"GGDC-{raw_id:04d}"
        msg = (
            f"🎓 *Government Girls Degree College Khado Khel*\n"
            f"Official Fine Notice / Challan Reminder\n\n"
            f"*Challan No:* {challan_no}\n"
            f"*Student Name:* {rec.get('name', 'Student')}\n"
            f"*Class:* {rec.get('class', '')}\n"
            f"*Reason:* {rec.get('reason', 'Fine')}\n"
            f"*Amount:* Rs. {rec.get('amount', 0):,.0f}\n\n"
            f"Please deposit this amount at Bank of Khyber, Totalai Branch, and submit the office copy."
        )
        QDesktopServices.openUrl(QUrl(f"https://wa.me/?text={urllib.parse.quote(msg)}"))
        self._toast(f"💬 Opened WhatsApp share window for Challan #{challan_no}")

    def _open_pdf_folder(self):
        pdf_dir = getattr(self.pdf_gen, "output_dir", "challans")
        os.makedirs(pdf_dir, exist_ok=True)
        self._open_path(os.path.abspath(str(pdf_dir)))

    def _edit_record_dialog(self, raw_id):
        rec = self._get_record_dict_by_id(raw_id)
        if not rec:
            QMessageBox.warning(self, "Error", f"Could not find record for ID {raw_id}")
            return
        dialog = EditRecordDialog(rec, self)
        if dialog.exec() != QDialog.Accepted:
            return
        payload = dialog.get_updated_payload()
        try:
            self.db.update_record(raw_id, payload)
        except Exception as ex:
            QMessageBox.critical(self, "Database Error", f"Failed to update record: {ex}")
            return
        self._refresh_all(quiet=True)
        self._regenerate_challan_pdf(raw_id)
        self._toast(f"✅ Record GGDC-{raw_id:04d} updated successfully!")

    def _regenerate_challan_pdf(self, raw_id):
        rec = self._get_record_dict_by_id(raw_id)
        if not rec:
            QMessageBox.warning(self, "Error", f"Could not find record for ID {raw_id}")
            return
        challan_no = f"GGDC-{raw_id:04d}"
        student_payload = {
            "name": rec.get("name", ""),
            "father_name": rec.get("father_name", ""),
            "class": rec.get("class", ""),
            "roll_no": rec.get("roll_no", "N/A"),
            "program": rec.get("program", PROGRAMS[0]),
            "session": rec.get("session", SESSIONS[0]),
            "purpose": "Other",
            "description": f"[{rec.get('fine_type', 'Fine')}] {rec.get('reason', '')}",
        }
        amt_val = self._parse_amount(rec.get("amount", 0.0)) or 0.0
        try:
            pdf_file_path = self.pdf_gen.generate_pdf(student_payload, challan_no, amt_val)
        except Exception as e:
            QMessageBox.critical(self, "PDF Error", f"Failed to generate challan PDF: {e}")
            return
        self._toast(f"✅ Regenerated Challan #{challan_no}")
        QMessageBox.information(
            self, "Challan Regenerated",
            f"Challan #{challan_no} successfully updated & generated at:\n{pdf_file_path}")
        self._open_path(pdf_file_path)

    def _use_row_for_range(self, row, _col):
        item = self.tree.item(row, 0)
        num = self._challan_to_int(item.text(), prefix="GGDC-") if item else None
        if num is not None:
            self.from_entry.setText(str(num))
            self.to_entry.setText(str(num))
            self._toast(f"📤 Export range set to challan #{num}", 3000)

    def _use_row_for_range_from_results(self, row, _col):
        item = self.res_tree.item(row, 0)
        num = self._challan_to_int(item.text(), prefix="GGDC-") if item else None
        if num is not None:
            self.from_entry.setText(str(num))
            self.to_entry.setText(str(num))
            self._toast(f"📤 Export range set to challan #{num}", 3000)

    def backup_database(self):
        try:
            db_file = getattr(self.db, "db_file", None)
            db_file = str(db_file) if db_file and os.path.exists(db_file) else \
                next((c for c in DB_CANDIDATES if os.path.exists(c)), None)
            if not db_file:
                QMessageBox.warning(self, "Notice", "Database file location could not be detected.")
                return
            suggested = f"Backup_GDC_Fines_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Database Backup", suggested, "Database Files (*.db)")
            if not file_path:
                return
            if not file_path.lower().endswith(".db"):
                file_path += ".db"
            src = sqlite3.connect(db_file)
            dst = sqlite3.connect(file_path)
            try:
                with dst:
                    src.backup(dst)
            finally:
                dst.close()
                src.close()
            self._toast("💾 Database backup completed", 4000)
            QMessageBox.information(self, "Backup Success", f"Database successfully backed up to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Backup Error", f"Could not create backup: {e}")

    def generate_fine_challan(self):
        name = self.entries["name_entry"].text().strip()
        reason = self.entries["reason_entry"].text().strip()
        amount_str = self.entries["amount_entry"].text().strip()
        if not name or not reason or not amount_str:
            QMessageBox.warning(self, "Missing Information", "Please enter Student Name, Reason, and Amount.")
            return
        amount = self._parse_amount(amount_str)
        if amount is None:
            QMessageBox.warning(self, "Invalid Amount", "Please enter a valid numeric amount greater than 0.")
            return
        payload = {
            "name": name,
            "father_name": self.entries["fname_entry"].text().strip(),
            "class": self.entries["class_combo"].currentText(),
            "roll_no": self.entries["roll_entry"].text().strip() or "N/A",
            "program": self.entries["program_combo"].currentText(),
            "session": self.entries["session_combo"].currentText(),
            "fine_type": self.entries["type_combo"].currentText(),
            "reason": reason,
            "amount": amount,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        raw_id = self.db.insert_record(payload)
        challan_no = f"GGDC-{raw_id:04d}"
        student_payload = {
            "name": payload["name"], "father_name": payload["father_name"],
            "class": payload["class"], "roll_no": payload["roll_no"],
            "program": payload["program"], "session": payload["session"],
            "purpose": "Other", "description": f"[{payload['fine_type']}] {payload['reason']}",
        }
        self._refresh_all(quiet=True)
        pdf_file_path = self.pdf_gen.generate_pdf(student_payload, challan_no, amount)
        self._open_path(pdf_file_path)
        QMessageBox.information(self, "Success", f"Challan #{challan_no} generated successfully!\n\nSaved at:\n{pdf_file_path}")
        self.clear_form()

    def load_records(self, quiet=False):
        records = self.db.fetch_all_records()
        table = self.tree
        columns = ["Challan#", "Student Name", "Class", "Type", "Reason / Description", "Amount", "Date", "Status"]
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setRowCount(len(records))
        for row_idx, row in enumerate(records):
            values = [f"GGDC-{row[0]:04d}", row[1], row[2], row[3], row[4], f"Rs. {row[5]:,.0f}", row[6], row[7] or STATUS_PENDING]
            self._fill_row(table, row_idx, values, type_col=3, amount_col=5, status_col=7)
        self.lbl_status_records.setText(f"🧾 Records: {len(records)}")

    def filter_records_table(self, query):
        query = query.lower().strip()
        table = self.tree
        for row in range(table.rowCount()):
            match = not query or any((item := table.item(row, col)) and query in item.text().lower() for col in range(table.columnCount()))
            table.setRowHidden(row, not match)

    def load_summary_stats(self):
        # 1. Get Fine stats from database.py
        fine_total_amt, fine_total_cnt, fine_breakdown = self.db.get_summary_stats()
        fine_status = self.db.get_status_stats()

        # 2. Get Institutional Fee stats from fee_database.py
        fee_records = self.fee_db.fetch_all_fees()
        fee_total_amt = sum(row[5] for row in fee_records if row[5]) # row[5] is amount
        fee_total_cnt = len(fee_records)
        
        fee_paid_amt = sum(row[5] for row in fee_records if row[7] == "Paid" and row[5])
        fee_paid_cnt = sum(1 for row in fee_records if row[7] == "Paid")
        
        fee_pending_amt = sum(row[5] for row in fee_records if row[7] != "Paid" and row[5])
        fee_pending_cnt = sum(1 for row in fee_records if row[7] != "Paid")

        # 3. Combine totals for the dashboard
        grand_total_amt = fine_total_amt + fee_total_amt
        grand_total_cnt = fine_total_cnt + fee_total_cnt
        
        total_paid_amt = fine_status['paid_amt'] + fee_paid_amt
        total_paid_cnt = fine_status['paid_cnt'] + fee_paid_cnt
        
        total_pending_amt = fine_status['pending_amt'] + fee_pending_amt
        total_pending_cnt = fine_status['pending_cnt'] + fee_pending_cnt

        # ── Update Main Collection & Challan Cards ──
        self.lbl_total_collection.setText(f"💰  Total Collection (Fines + Fees): Rs. {grand_total_amt:,.0f}")
        self.lbl_total_challans.setText(f"🧾  Total Challans Issued: {grand_total_cnt}")
        
        # ── 💡 FIX: Update Dashboard Paid & Pending Cards Instantly! ──
        self.lbl_paid_amount.setText(f"✅  Paid: Rs. {total_paid_amt:,.0f} ({total_paid_cnt})")
        self.lbl_pending_amount.setText(f"⏳  Pending: Rs. {total_pending_amt:,.0f} ({total_pending_cnt})")

        # ── Update Bottom Status Bar Chips ──
        self.lbl_status_total.setText(f"💰 Total: Rs. {grand_total_amt:,.0f}")
        self.lbl_status_paid.setText(f"✅ Paid: Rs. {total_paid_amt:,.0f} ({total_paid_cnt})")
        self.lbl_status_pending.setText(f"⏳ Pending: Rs. {total_pending_amt:,.0f} ({total_pending_cnt})")

        breakdown = list(fine_breakdown)
        if fee_total_cnt > 0:
            breakdown.append(("Institutional Fees", fee_total_cnt, fee_total_amt))

        table = self.sum_tree
        table.setRowCount(len(breakdown))
        for row_idx, (cat, cnt, amt) in enumerate(breakdown):
            cat_color = TYPE_COLORS.get(str(cat), "#34d399")
            table.setItem(row_idx, 0, self._cell(cat, color=cat_color, bold=True))
            table.setItem(row_idx, 1, self._cell(cnt, Qt.AlignCenter))
            table.setItem(row_idx, 2, self._cell(
                f"Rs. {amt:,.0f}", Qt.AlignVCenter | Qt.AlignRight, AMOUNT_COLOR, bold=True))

    def search_student_clearance(self):
        query_text = self.search_entry.text().strip()
        if not query_text:
            QMessageBox.warning(self, "Search Required",
                                "Please enter a student name, roll number or challan number.")
            self.search_entry.setFocus()
            return

        # Search Fines Database
        fine_results = self.db.search_clearance(query_text)
        
        # Search Institutional Fee Database
        fee_raw = self.fee_db.fetch_all_fees()
        fee_results = []
        for row in fee_raw:
            if query_text.lower() in str(row[1]).lower() or query_text.lower() in str(row[2]).lower() or query_text in str(row[0]):
                fee_results.append((
                    row[0],          # challan id
                    row[2],          # student name
                    "N/A",           # father name placeholder
                    row[3],          # class
                    row[1] or "N/A", # roll no
                    row[4],          # fee type
                    f"[{row[4]}] Institutional Fee", # reason
                    row[5],          # amount
                    row[6],          # date
                    row[7]           # status
                ))

        results = list(fine_results) + list(fee_results)

        if not results:
            self.res_tree.setRowCount(0)
            self._toast(f"No records found for '{query_text}'", 4000)
            QMessageBox.information(self, "Not Found", f"No records found for '{query_text}'.")
            return

        table = self.res_tree
        res_cols = ["Challan#", "Student Name", "Father Name", "Class", "Roll No",
                    "Fine/Fee Type", "Reason", "Amount", "Date", "Status"]
        table.setColumnCount(len(res_cols))
        table.setHorizontalHeaderLabels(res_cols)

        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(len(results))
            for row_idx, row in enumerate(results):
                prefix = "FEE-" if row[5] in ["Admission Fee", "Promotion Fee", "Semester Fee", "Institutional Fee"] else "GGDC-"
                challan_display = f"{prefix}{row[0]:04d}"
                
                values = [challan_display, row[1], row[2], row[3], row[4], row[5], row[6],
                          f"Rs. {row[7]:,.0f}", row[8], row[9] or STATUS_PENDING]
                self._fill_row(table, row_idx, values, type_col=5, amount_col=7, status_col=9)
        finally:
            table.setUpdatesEnabled(True)

        pending = sum(1 for r in results if (r[9] or STATUS_PENDING) != STATUS_PAID)
        self._toast(f"🔍 Found {len(results)} total record(s)  •  {pending} pending")

    def process_bulk_fines(self):
        names_text = self.bulk_names_text.toPlainText().strip()
        rolls_text = self.bulk_rolls_text.toPlainText().strip()
        reason = self.bulk_reason_entry.text().strip()
        amount_str = self.bulk_amount_entry.text().strip()

        if not names_text or not amount_str:
            QMessageBox.warning(self, "Missing Information", "Please enter student names and a fine amount.")
            return

        amount = self._parse_amount(amount_str)
        if amount is None or amount <= 0:
            QMessageBox.warning(self, "Invalid Amount", "Please enter a valid numeric amount greater than 0.")
            return

        names_list = _split_items(names_text)
        rolls_list = _split_items(rolls_text) if rolls_text else []

        if not names_list:
            QMessageBox.warning(self, "Empty List", "No valid student names found.")
            return

        cls = self.bulk_class_combo.currentText()
        program = self.bulk_program_combo.currentText()
        session = self.bulk_session_combo.currentText()
        fine_type = self.bulk_type_combo.currentText()
        date_str = datetime.now().strftime("%Y-%m-%d")

        success_count = 0
        last_file_path = None

        for idx, name in enumerate(names_list):
            roll_no = rolls_list[idx] if idx < len(rolls_list) else "N/A"
            
            payload = {
                "name": name,
                "father_name": "Batch Import",
                "class": cls,
                "roll_no": roll_no,
                "program": program,
                "session": session,
                "fine_type": fine_type,
                "reason": reason or "Class Fine",
                "amount": amount,
                "date": date_str,
            }

            try:
                raw_id = self.db.insert_record(payload)
                challan_no = f"GGDC-{raw_id:04d}"
                student_payload = {
                    "name": name,
                    "father_name": "Batch Import",
                    "class": cls,
                    "roll_no": roll_no,
                    "program": program,
                    "session": session,
                    "purpose": "Other",
                    "description": f"[{fine_type}] {reason or 'Class Fine'}",
                }
                last_file_path = self.pdf_gen.generate_pdf(student_payload, challan_no, amount)
                success_count += 1
            except Exception as e:
                print(f"Failed to generate for {name}: {e}")

        self._refresh_all(quiet=True)
        
        QMessageBox.information(
            self, "Batch Generation Complete",
            f"Successfully generated {success_count} challan(s)!\n\nSaved inside your output directory."
        )
        
        if last_file_path and os.path.exists(last_file_path):
            self._open_path(os.path.dirname(last_file_path))
            
        self.clear_bulk_form()

    def clear_bulk_form(self):
        self.bulk_names_text.clear()
        self.bulk_rolls_text.clear()
        self.bulk_reason_entry.setText("College General Fine")
        self.bulk_amount_entry.clear()
        for combo in (self.bulk_class_combo, self.bulk_program_combo, self.bulk_type_combo):
            combo.setCurrentIndex(0)
        self.bulk_session_combo.setCurrentIndex(min(2, self.bulk_session_combo.count() - 1))
        self.bulk_names_text.setFocus()

    def export_range_excel(self):
        pass

    def export_dashboard_excel(self):
        pass

    def export_clearance_excel(self):
        pass

    def clear_form(self):
        e = self.entries
        e["name_entry"].clear()
        e["fname_entry"].clear()
        e["roll_entry"].clear()
        e["reason_entry"].setText("Late Fee Fine")
        e["amount_entry"].clear()
        e["name_entry"].setFocus()

    def closeEvent(self, event):
        try:
            self.db.close()
            self.fee_db.close()
        finally:
            super().closeEvent(event)

    # ───────────────────────── Institutional Fee Handlers ─────────────────────────
    def generate_institutional_fee(self):
        ui = self.ui
        name = ui.fee_name_edit.text().strip()
        roll = ui.fee_roll_edit.text().strip()  # Optional: blank is totally fine!
        program = ui.fee_program_combo.currentText()
        curr_class = ui.fee_class_combo.currentText()
        session = ui.fee_session_combo.currentText()
        amount_str = ui.fee_amount_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Missing Information", "Please enter Student Name.")
            ui.fee_name_edit.setFocus()
            return

        auto_fee_type, default_amt = resolve_fee_category(program, curr_class)
        try:
            amount = float(amount_str) if amount_str else default_amt
        except ValueError:
            amount = default_amt

        date_str = datetime.now().strftime("%Y-%m-%d")
        payload = {
            "roll_no": roll,
            "name": name,
            "father_name": ui.fee_fname_edit.text().strip() or "N/A",
            "program_type": program,
            "current_class": curr_class,
            "session": session,
            "contact": "",
            "fee_type": auto_fee_type,
            "academic_period": curr_class,
            "amount": amount,
            "date": date_str
        }

        try:
            challan_id = self.fee_db.insert_fee_record(payload)
            challan_no = f"FEE-{challan_id:04d}"
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not save fee record: {e}")
            return

        student_payload = {
            "name": name,
            "father_name": payload["father_name"],
            "class": curr_class,
            "roll_no": roll if roll else "N/A",
            "program": program,
            "session": session,
            "purpose": auto_fee_type,
            "description": f"[{auto_fee_type}] Academic Fee for {curr_class}"
        }

        try:
            pdf_path = self.pdf_gen.generate_pdf(student_payload, challan_no, amount)
            self._open_path(pdf_path)
            QMessageBox.information(self, "Success", f"Generated {auto_fee_type} Challan #{challan_no} successfully!")
            self.load_fee_records()
            self.load_summary_stats()
        except Exception as ex:
            QMessageBox.warning(self, "PDF Warning", f"Fee saved to database, but PDF generation failed: {ex}")

    def load_fee_records(self):
        if not hasattr(self.ui, "fee_tree"):
            return
        records = self.fee_db.fetch_all_fees()
        table = self.ui.fee_tree
        
        # Ensure column count matches your UI setup (8 columns)
        fee_columns = ["Challan#", "Roll No", "Student Name", "Class/Sem", "Fee Type", "Amount", "Date", "Status"]
        table.setColumnCount(len(fee_columns))
        table.setHorizontalHeaderLabels(fee_columns)
        
        table.setRowCount(len(records))
        for row_idx, row in enumerate(records):
            status_val = row[7] or "Pending"
            paid = status_val == "Paid"
            
            # row format from fetch_all_fees:
            # (challan_no, roll_no, student_name, current_class, fee_type, amount, date, status)
            values = [
                f"FEE-{row[0]:04d}", 
                row[1] if row[1] else "N/A", 
                row[2], 
                row[3], 
                row[4], 
                f"Rs. {row[5]:,.0f}", 
                row[6], 
                status_val
            ]
            
            for col_idx, val in enumerate(values):
                if col_idx == 7:  # Status Column styling
                    item = self._cell(val, Qt.AlignCenter, SUCCESS_COLOR if paid else PENDING_COLOR, bold=True,
                                      bg=STATUS_BG[STATUS_PAID if paid else STATUS_PENDING])
                else:
                    item = QTableWidgetItem(str(val))
                table.setItem(row_idx, col_idx, item)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET + EXTRA_QSS)
    window = EnterpriseFineCollectionApp()
    window.show()
    sys.exit(app.exec())