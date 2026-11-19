"""
cc_dialog.py — GGDC Khado Khel College Accounting System
Character Certificate — Issue, preview, and manage certificates.

Design language: "Institutional Heritage" — deep navy + gold seal aesthetic.
Matches the system-wide "Institutional Premium" look with extra gravitas
befitting an official government college document.

Certificate PDF:
  • Ornate double border with corner medallions
  • College logo centred at top with gold rule
  • GGDC Khado Khel watermark diagonally across centre
  • Georgian serif typography throughout
  • Soft parchment background (#fdfbf5)
  • Gold decorative dividers
  • QR code + dual signature blocks
  • Print-ready A4 portrait
"""

import sys
import logging
import traceback
import base64
import os
from pathlib import Path
from datetime import datetime
from io import BytesIO

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit, QFrame,
    QHeaderView, QAbstractItemView, QGraphicsDropShadowEffect,
    QTextEdit, QScrollArea, QWidget, QFormLayout, QSizePolicy,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  MODELS & REPOSITORIES (Embedded for zero-dependency imports)
# ═══════════════════════════════════════════════════════════════════════════════

class CharacterCertificate:
    def __init__(self, cert_no, student_name, father_name, roll_no, 
                 class_name, program, session, date_of_admission, 
                 date_of_leaving, conduct, behavior, character_remarks, 
                 pdf_path=None, id=None, date_issued=None):
        self.id = id
        self.cert_no = cert_no
        self.student_name = student_name
        self.father_name = father_name
        self.roll_no = roll_no
        self.class_name = class_name
        self.program = program
        self.session = session
        self.date_of_admission = date_of_admission
        self.date_of_leaving = date_of_leaving
        self.conduct = conduct
        self.behavior = behavior
        self.character_remarks = character_remarks
        self.pdf_path = pdf_path
        self.date_issued = date_issued


class CharacterCertificateRepository:
    def __init__(self, db_manager):
        self.db = db_manager

    def get_next_cert_no(self) -> str:
        cursor = self.db.cursor
        cursor.execute("SELECT MAX(id) FROM character_certificates")
        row = cursor.fetchone()
        next_id = (row[0] or 0) + 1
        return f"CC-{next_id:04d}"

    def save(self, cc: CharacterCertificate):
        cursor = self.db.cursor
        cursor.execute("""
            INSERT INTO character_certificates 
            (cert_no, student_name, father_name, roll_no, class_name, program, 
             session, date_of_admission, date_of_leaving, conduct, behavior, 
             character_remarks, pdf_path, date_issued)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cc.cert_no, cc.student_name, cc.father_name, cc.roll_no,
            cc.class_name, cc.program, cc.session, cc.date_of_admission,
            cc.date_of_leaving, cc.conduct, cc.behavior,
            cc.character_remarks, cc.pdf_path, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        self.db.conn.commit()
        cc.id = cursor.lastrowid
        return cc

    def get_all(self):
        cursor = self.db.cursor
        cursor.execute("SELECT * FROM character_certificates ORDER BY id DESC")
        rows = cursor.fetchall()
        results = []
        for r in rows:
            cc = CharacterCertificate(
                id=r[0], cert_no=r[1], student_name=r[2], father_name=r[3],
                roll_no=r[4], class_name=r[5], program=r[6], session=r[7],
                date_of_admission=r[8], date_of_leaving=r[9], conduct=r[10],
                behavior=r[11], character_remarks=r[12], pdf_path=r[13], date_issued=r[14]
            )
            results.append(cc)
        return results


class StudentRepository:
    def __init__(self, db_manager):
        self.db = db_manager

    def get_all(self):
        cursor = self.db.cursor
        cursor.execute("SELECT roll_no, student_name, father_name, class, program, session FROM student_master ORDER BY roll_no ASC")
        rows = cursor.fetchall()
        
        class StudentRecord:
            def __init__(self, id, roll_no, name, father_name, class_name, program, session):
                self.id = id
                self.roll_no = roll_no
                self.name = name
                self.father_name = father_name
                self.class_name = class_name
                self.program = program
                self.session = session
                self.admission_date = ""

        return [StudentRecord(i, r[0], r[1], r[2], r[3], r[4], r[5]) for i, r in enumerate(rows)]

    def get_by_id(self, student_id):
        students = self.get_all()
        if 0 <= student_id < len(students):
            return students[student_id]
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  DESIGN TOKENS
# ═══════════════════════════════════════════════════════════════════════════════
NAV_BG      = "#0d1b2a"
PRIMARY     = "#1e3c72"
ACCENT_GOLD = "#c8a84b"
ACCENT_BLUE = "#3b82f6"
PAGE_BG     = "#f0f4f8"
CARD_BG     = "#ffffff"
BORDER      = "#dde3ef"
TEXT_MAIN   = "#1a2540"
TEXT_MUTED  = "#64748b"
SUCCESS     = "#059669"
DANGER      = "#dc2626"
WARNING     = "#d97706"
BODY        = "Calibri"
HEAD        = "Georgia"

FIELD_SS = f"""
    QLineEdit, QComboBox, QTextEdit {{
        border: 1.5px solid {BORDER};
        border-radius: 8px;
        padding: 7px 11px;
        background: #f8faff;
        color: {TEXT_MAIN};
        font-size: 13px;
        font-family: {BODY};
    }}
    QLineEdit:hover, QComboBox:hover, QTextEdit:hover {{
        border-color: #93b4dc; background: #f0f6ff;
    }}
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
        border: 2px solid {PRIMARY}; background: #ffffff;
    }}
    QLineEdit:read-only {{ background: #eef0f5; color: {TEXT_MUTED}; }}
    QComboBox::drop-down {{ border: none; padding-right: 8px; }}
    QComboBox QAbstractItemView {{
        border: 1.5px solid {BORDER}; border-radius: 8px;
        background: white; selection-background-color: #dbeafe;
    }}
"""

TABLE_SS = f"""
    QTableWidget {{
        background: {CARD_BG}; alternate-background-color: #f8fafc;
        border: none; gridline-color: #eef2f7;
        font-size: 12px; font-family: {BODY}; color: {TEXT_MAIN};
        selection-background-color: #dbeafe;
    }}
    QHeaderView::section {{
        background: #f1f5fb; padding: 9px 8px;
        border: none; border-bottom: 2px solid {BORDER};
        font-weight: bold; font-size: 10px;
        font-family: {BODY}; color: {TEXT_MUTED};
        letter-spacing: 0.5px;
    }}
    QScrollBar:vertical {{
        border: none; background: #f8fafc; width: 8px;
    }}
    QScrollBar::handle:vertical {{
        background: #cbd5e1; border-radius: 4px; min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  SHARED HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _shadow(blur=20, dy=4, alpha=50) -> QGraphicsDropShadowEffect:
    s = QGraphicsDropShadowEffect()
    s.setBlurRadius(blur)
    s.setXOffset(0)
    s.setYOffset(dy)
    s.setColor(QColor(0, 0, 0, alpha))
    return s


def _divider() -> QFrame:
    d = QFrame()
    d.setFixedHeight(1)
    d.setStyleSheet(
        "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
        "stop:0 transparent,stop:0.2 #dde3ef,stop:0.8 #dde3ef,stop:1 transparent);"
    )
    return d


def _section_title(icon: str, text: str) -> QWidget:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    accent = QFrame()
    accent.setFixedSize(4, 18)
    accent.setStyleSheet(f"background: {ACCENT_GOLD}; border-radius: 2px;")
    row.addWidget(accent)
    lbl = QLabel(f"{icon}  {text}")
    lbl.setFont(QFont(HEAD, 11, QFont.Bold))
    lbl.setStyleSheet(f"color: {PRIMARY}; background: transparent;")
    row.addWidget(lbl)
    row.addStretch()
    return w


def _label(text: str, tooltip: str = "") -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"color: {TEXT_MUTED}; font-size: 12px; "
        f"font-family: {BODY}; font-weight: 600;"
    )
    if tooltip:
        l.setToolTip(tooltip)
    return l


def _action_btn(text: str, bg: str, hover: str,
                height: int = 36, tooltip: str = "") -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFixedHeight(height)
    if tooltip:
        btn.setToolTip(tooltip)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {bg}; color: white; border: none;
            border-radius: 8px; padding: 0 20px;
            font-size: 13px; font-family: {BODY}; font-weight: bold;
            letter-spacing: 0.3px;
        }}
        QPushButton:hover   {{ background: {hover}; }}
        QPushButton:pressed {{ background: {hover}; }}
        QPushButton:disabled {{ background: #b0bec5; color: rgba(255,255,255,0.6); }}
    """)
    return btn


def _ghost_btn(text: str, height: int = 36, tooltip: str = "") -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFixedHeight(height)
    if tooltip:
        btn.setToolTip(tooltip)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent; color: {TEXT_MUTED};
            border: 1.5px solid {BORDER}; border-radius: 8px; padding: 0 18px;
            font-size: 12px; font-family: {BODY};
        }}
        QPushButton:hover   {{ background: #f1f5fb; border-color: #aab8d0; color: {TEXT_MAIN}; }}
        QPushButton:pressed {{ background: #e8eef8; }}
    """)
    return btn


# ═══════════════════════════════════════════════════════════════════════════════
#  INLINE BADGE
# ═══════════════════════════════════════════════════════════════════════════════
class _Badge(QLabel):
    _T = {
        "error":   (DANGER,  "#fee2e2", "#fecaca"),
        "success": (SUCCESS, "#d1fae5", "#a7f3d0"),
        "warning": (WARNING, "#fef3c7", "#fcd34d"),
        "info":    (PRIMARY, "#eff6ff", "#bfdbfe"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.hide()
        self.setStyleSheet(
            f"font-size: 12px; font-family: {BODY}; border-radius: 7px; padding: 7px 12px;"
        )

    def show_as(self, kind: str, text: str):
        fg, bg, bd = self._T.get(kind, self._T["info"])
        self.setStyleSheet(
            f"font-size: 12px; font-family: {BODY}; border-radius: 7px; "
            f"padding: 7px 12px; color: {fg}; background: {bg}; border: 1px solid {bd};"
        )
        self.setText(text)
        self.show()

    def clear_badge(self):
        self.hide()
        self.clear()


# ═══════════════════════════════════════════════════════════════════════════════
#  CERTIFICATE PDF GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

def _logo_b64(project_root: Path) -> str | None:
    for p in [
        project_root / "assets" / "college_logo.png",
        project_root / "ui" / "assets" / "college_logo.png",
        Path("assets") / "college_logo.png",
    ]:
        if p.exists():
            try:
                with open(p, "rb") as f:
                    return base64.b64encode(f.read()).decode()
            except Exception:
                pass
    return None


def generate_character_certificate_pdf(cc: CharacterCertificate,
                                        project_root: Path) -> str:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader, simpleSplit
    import qrcode

    folder = project_root / "Generated" / "Certificates" / "Character"
    folder.mkdir(parents=True, exist_ok=True)
    safe = cc.student_name.replace(" ", "_").replace("/", "_")
    fp   = folder / f"CC_{safe}_{cc.cert_no}.pdf"

    c = canvas.Canvas(str(fp), pagesize=A4)
    W, H = A4
    M    = 36

    c.setFillColor(colors.HexColor("#fdfbf5"))
    c.rect(0, 0, W, H, fill=True, stroke=False)

    c.setStrokeColor(colors.HexColor("#1e3c72"))
    c.setLineWidth(2.5)
    c.rect(M, M, W - 2*M, H - 2*M, fill=False, stroke=True)

    GAP = 7
    c.setStrokeColor(colors.HexColor("#c8a84b"))
    c.setLineWidth(1.0)
    c.rect(M + GAP, M + GAP, W - 2*(M+GAP), H - 2*(M+GAP), fill=False, stroke=True)

    corners = [
        (M + 2, M + 2),
        (W - M - 2, M + 2),
        (M + 2, H - M - 2),
        (W - M - 2, H - M - 2),
    ]
    c.setFillColor(colors.HexColor("#c8a84b"))
    c.setFont("Helvetica-Bold", 14)
    for cx, cy in corners:
        c.drawCentredString(cx, cy - 5, "✦")

    c.saveState()
    c.setFillColor(colors.HexColor("#1e3c72"))
    c.setFont("Helvetica-Bold", 52)
    c.setFillAlpha(0.035)
    c.translate(W / 2, H / 2)
    c.rotate(42)
    c.drawCentredString(0, 30,  "GGDC Khado Khel")
    c.drawCentredString(0, -30, "BUNER")
    c.restoreState()

    logo_data = _logo_b64(project_root)
    logo_y    = H - M - GAP - 72
    if logo_data:
        try:
            img_buf = BytesIO(base64.b64decode(logo_data))
            c.drawImage(
                ImageReader(img_buf),
                W / 2 - 28, logo_y,
                width=56, height=56,
                preserveAspectRatio=True, mask="auto"
            )
        except Exception:
            logo_data = None

    if not logo_data:
        c.setFillColor(colors.HexColor("#1e3c72"))
        c.circle(W / 2, logo_y + 28, 28, fill=True, stroke=False)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(W / 2, logo_y + 23, "GDC")

    rule_y = logo_y + 28
    c.setStrokeColor(colors.HexColor("#c8a84b"))
    c.setLineWidth(1.2)
    c.line(M + GAP + 10, rule_y, W / 2 - 38, rule_y)
    c.line(W / 2 + 38,   rule_y, W - M - GAP - 10, rule_y)

    y = logo_y - 22
    c.setFillColor(colors.HexColor("#1e3c72"))
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(W / 2, y, "GOVERNMENT GIRLS DEGREE COLLEGE KHADO KHEL")
    y -= 16
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#374151"))
    c.drawCentredString(W / 2, y, "DISTRICT BUNER, KHYBER PAKHTUNKHWA")
    y -= 10
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#6b7280"))
    c.drawCentredString(W / 2, y, "Affiliated with BISE Swat · Established 2024")

    y -= 14
    c.setStrokeColor(colors.HexColor("#1e3c72"))
    c.setLineWidth(2)
    c.line(M + GAP + 10, y, W - M - GAP - 10, y)
    c.setStrokeColor(colors.HexColor("#c8a84b"))
    c.setLineWidth(1)
    c.line(M + GAP + 10, y - 3, W - M - GAP - 10, y - 3)

    y -= 24
    c.setFillColor(colors.HexColor("#1e3c72"))
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(W / 2, y, "CHARACTER  CERTIFICATE")
    y -= 6
    c.setStrokeColor(colors.HexColor("#c8a84b"))
    c.setLineWidth(0.8)
    c.line(W / 2 - 80, y, W / 2 + 80, y)

    y -= 18
    strip_h = 18
    c.setFillColor(colors.HexColor("#eef2fb"))
    c.roundRect(M + GAP + 10, y - strip_h + 4, W - 2*(M+GAP) - 20, strip_h, 3,
                fill=True, stroke=False)
    c.setFillColor(colors.HexColor("#1e3c72"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(M + GAP + 18, y - 8, f"Certificate No:  {cc.cert_no}")
    c.drawRightString(W - M - GAP - 18, y - 8, f"Date of Issue:  {cc.date_issued}")

    y -= 30
    TW = W - 2*(M + GAP) - 40
    TX = M + GAP + 20

    def prose(text: str, font: str = "Helvetica", size: int = 11,
              color: str = "#1f2937", indent: int = 0, line_gap: int = 16):
        nonlocal y
        c.setFillColor(colors.HexColor(color))
        c.setFont(font, size)
        for ln in simpleSplit(text, font, size, TW - indent):
            c.drawString(TX + indent, y, ln)
            y -= line_gap

    prose(
        f"This is to certify that  {cc.student_name}  son of  "
        f"{cc.father_name},  bearing Roll No.  {cc.roll_no or '—'},  "
        f"was a bonafide student of this institution.",
        "Helvetica", 11, "#1f2937", line_gap=17
    )
    y -= 6

    prose(
        f"He was enrolled in Class  {cc.class_name}  under the program  "
        f"{cc.program}  during the academic session  {cc.session}.",
        "Helvetica", 11, "#1f2937", line_gap=17
    )
    y -= 6

    if cc.date_of_admission or cc.date_of_leaving:
        adm  = cc.date_of_admission  or "—"
        left = cc.date_of_leaving    or "—"
        prose(
            f"He remained a student of this college from  {adm}  to  {left}.",
            "Helvetica", 11, "#1f2937", line_gap=17
        )
        y -= 6

    y -= 4
    c.setFillColor(colors.HexColor("#f0f6ff"))
    c.roundRect(TX - 4, y - 54, TW + 8, 62, 5, fill=True, stroke=False)
    c.setStrokeColor(colors.HexColor("#c8a84b"))
    c.setLineWidth(0.8)
    c.roundRect(TX - 4, y - 54, TW + 8, 62, 5, fill=False, stroke=True)

    c.setFillColor(colors.HexColor("#1e3c72"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(TX + 4, y - 2, "ACADEMIC & CHARACTER ASSESSMENT")

    row_y = y - 18
    for label, value, color in [
        ("Conduct",  cc.conduct,  "#059669"),
        ("Behavior", cc.behavior, "#1e3c72"),
    ]:
        c.setFillColor(colors.HexColor("#374151"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(TX + 8,  row_y, f"{label}:")
        c.setFillColor(colors.HexColor(color))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(TX + 80, row_y, value)
        row_y -= 16

    y -= 62

    if cc.character_remarks and cc.character_remarks.strip():
        y -= 8
        c.setFillColor(colors.HexColor("#1e3c72"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(TX, y, "Remarks:")
        y -= 14
        c.setFillColor(colors.HexColor("#374151"))
        c.setFont("Helvetica-Oblique", 10)
        for ln in simpleSplit(cc.character_remarks, "Helvetica-Oblique", 10, TW - 10)[:4]:
            c.drawString(TX + 12, y, ln)
            y -= 13

    y -= 16
    c.setStrokeColor(colors.HexColor("#c8a84b"))
    c.setLineWidth(0.6)
    c.line(TX, y + 6, TX + TW, y + 6)
    y -= 6
    prose(
        "During his stay at this institution, his conduct and character "
        "were found to be  good.  We wish him all the best in future endeavours.",
        "Helvetica", 10, "#374151", line_gap=14
    )
    y -= 8
    c.setFillColor(colors.HexColor("#6b7280"))
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(W / 2, y,
        "This certificate is issued on the request of the student and bears no financial liability.")
    y -= 6
    c.setStrokeColor(colors.HexColor("#dde3ef"))
    c.setLineWidth(0.5)
    c.line(TX, y, TX + TW, y)

    sig_y     = M + GAP + 62
    sig_w     = 130
    left_x    = TX + 10
    right_x   = TX + TW - sig_w - 10

    for sx, role, dept in [
        (left_x,  "Clerk Incharge",   "Office"),
        (right_x, "Principal",        "GGDC Khado Khel, Buner"),
    ]:
        c.setStrokeColor(colors.HexColor("#1e3c72"))
        c.setLineWidth(1)
        c.line(sx, sig_y, sx + sig_w, sig_y)

        c.setStrokeColor(colors.HexColor("#c8a84b"))
        c.setLineWidth(0.5)
        c.line(sx, sig_y - 2, sx + sig_w, sig_y - 2)

        c.setFillColor(colors.HexColor("#1e3c72"))
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(sx + sig_w / 2, sig_y - 14, role)
        c.setFillColor(colors.HexColor("#6b7280"))
        c.setFont("Helvetica", 8)
        c.drawCentredString(sx + sig_w / 2, sig_y - 24, dept)

    stamp_x = W / 2
    stamp_y = sig_y - 10
    c.setStrokeColor(colors.HexColor("#c8a84b"))
    c.setLineWidth(1.2)
    c.circle(stamp_x, stamp_y, 26, fill=False, stroke=True)
    c.setStrokeColor(colors.HexColor("#1e3c72"))
    c.setLineWidth(0.6)
    c.circle(stamp_x, stamp_y, 22, fill=False, stroke=True)
    c.setFillColor(colors.HexColor("#1e3c72"))
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(stamp_x, stamp_y + 6,  "OFFICIAL")
    c.drawCentredString(stamp_x, stamp_y - 2,  "STAMP")
    c.setFont("Helvetica", 6)
    c.drawCentredString(stamp_x, stamp_y - 10, "GGDC Khado Khel")

    try:
        qr = qrcode.QRCode(
            version=2,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=3, border=1
        )
        qr.add_data(
            f"CERT:{cc.cert_no}|{cc.student_name}|{cc.roll_no}|"
            f"{cc.class_name}|{cc.session}|{cc.date_issued}"
        )
        qr.make(fit=True)
        buf = BytesIO()
        qr.make_image(fill_color="#1e3c72", back_color="#fdfbf5").save(buf, "PNG")
        buf.seek(0)
        qr_size = 52
        c.drawImage(
            ImageReader(buf),
            W - M - GAP - qr_size - 6,
            M + GAP + 6,
            width=qr_size, height=qr_size
        )
        c.setFillColor(colors.HexColor("#6b7280"))
        c.setFont("Helvetica", 7)
        c.drawCentredString(
            W - M - GAP - qr_size / 2 - 6,
            M + GAP + 2,
            "Scan to verify"
        )
    except Exception as exc:
        logger.warning(f"QR error: {exc}")

    c.setFillColor(colors.HexColor("#1e3c72"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(M + GAP + 10, M + GAP + 8,
                 f"GGDC Khado Khel | Cert No: {cc.cert_no} | Issued: {cc.date_issued}")

    c.save()
    return str(fp)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN DIALOG
# ═══════════════════════════════════════════════════════════════════════════════

class CCDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db       = db
        self.cc_repo  = CharacterCertificateRepository(db)
        self.stu_repo = StudentRepository(db)

        self.setWindowTitle("Character Certificate")
        self.setMinimumSize(780, 780)
        self.setStyleSheet(f"QDialog {{ background: {PAGE_BG}; }}")

        self._build_ui()
        self._fade_in()
        QTimer.singleShot(80, self._refresh_cert_no)

    def _fade_in(self):
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(280)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def _make_header(self) -> QFrame:
        banner = QFrame()
        banner.setFixedHeight(70)
        banner.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {NAV_BG}, stop:1 {PRIMARY});
                border-radius: 12px;
            }}
        """)
        row = QHBoxLayout(banner)
        row.setContentsMargins(20, 0, 20, 0)
        row.setSpacing(14)

        icon = QLabel("📜")
        icon.setStyleSheet("font-size: 30px; background: transparent;")
        row.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(2)
        h = QLabel("Character Certificate")
        h.setFont(QFont(HEAD, 15, QFont.Bold))
        h.setStyleSheet("color: white; background: transparent; letter-spacing: 0.5px;")
        sub = QLabel("Issue official character certificates for students of GGDC Khado Khel, Buner")
        sub.setStyleSheet(
            f"color: rgba(255,255,255,0.60); font-size: 11px; "
            f"background: transparent; font-family: {BODY};"
        )
        col.addWidget(h)
        col.addWidget(sub)
        row.addLayout(col)
        row.addStretch()

        badge = QLabel(f" GGDC Khado Khel ")
        badge.setStyleSheet(f"""
            QLabel {{
                background: {ACCENT_GOLD}; color: #3d2800;
                border-radius: 5px; padding: 3px 10px;
                font-size: 10px; font-weight: bold; font-family: {BODY};
            }}
        """)
        row.addWidget(badge)
        return banner

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(self._make_header())

        cert_strip = QFrame()
        cert_strip.setStyleSheet(f"""
            QFrame {{
                background: {CARD_BG};
                border-radius: 8px;
                border: 1px solid {BORDER};
            }}
        """)
        cs_lay = QHBoxLayout(cert_strip)
        cs_lay.setContentsMargins(14, 8, 14, 8)
        cs_lay.setSpacing(10)

        cert_icon = QLabel("🔖")
        cert_icon.setStyleSheet("font-size: 16px; background: transparent;")
        cs_lay.addWidget(cert_icon)

        lbl_cn = QLabel("Certificate No:")
        lbl_cn.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 600; "
            f"font-family: {BODY}; background: transparent;"
        )
        cs_lay.addWidget(lbl_cn)

        self.cert_e = QLineEdit()
        self.cert_e.setReadOnly(True)
        self.cert_e.setFixedWidth(130)
        self.cert_e.setFixedHeight(32)
        self.cert_e.setStyleSheet(FIELD_SS)
        cs_lay.addWidget(self.cert_e)

        cs_lay.addSpacing(20)

        lbl_date = QLabel(f"📅  Today:  {datetime.now().strftime('%d %B %Y')}")
        lbl_date.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; font-family: {BODY}; background: transparent;"
        )
        cs_lay.addWidget(lbl_date)
        cs_lay.addStretch()

        root.addWidget(cert_strip)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        body = QWidget()
        body.setStyleSheet(f"background: {PAGE_BG};")
        b_lay = QVBoxLayout(body)
        b_lay.setContentsMargins(0, 0, 4, 0)
        b_lay.setSpacing(12)

        b_lay.addWidget(self._build_student_card())
        b_lay.addWidget(self._build_info_card())
        b_lay.addWidget(self._build_cert_card())

        self._badge = _Badge()
        b_lay.addWidget(self._badge)

        b_lay.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        root.addWidget(_divider())

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_hist = _action_btn(
            "📋  History", ACCENT_BLUE, "#2563eb", 40,
            tooltip="View all previously issued character certificates."
        )
        btn_hist.clicked.connect(self._show_history)
        btn_row.addWidget(btn_hist)

        btn_row.addStretch()

        btn_clear = _ghost_btn("🔄  Clear Form", 40, tooltip="Reset all fields.")
        btn_clear.clicked.connect(self._clear)
        btn_row.addWidget(btn_clear)

        self.btn_generate = _action_btn(
            "📜  Generate Certificate", SUCCESS, "#047857", 40,
            tooltip="Generate and save official certificate PDF."
        )
        self.btn_generate.setDefault(True)
        self.btn_generate.clicked.connect(self._generate)
        btn_row.addWidget(self.btn_generate)

        btn_close = _ghost_btn("Close", 40)
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)

        root.addLayout(btn_row)

    def _build_student_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background: {CARD_BG}; border-radius: 10px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(10)
        lay.addWidget(_section_title("🎓", "Select Student"))

        row = QHBoxLayout()
        row.setSpacing(10)

        self.stu_combo = QComboBox()
        self.stu_combo.setFixedHeight(36)
        self.stu_combo.setStyleSheet(FIELD_SS)
        self.stu_combo.addItem("— Select a student —", None)

        students = self.stu_repo.get_all()
        for s in students:
            label = f"{s.roll_no or '—'}  ·  {s.name}  ·  {s.class_name} ({s.program})"
            self.stu_combo.addItem(label, s.id)

        self.stu_combo.currentIndexChanged.connect(self._on_student_selected)
        row.addWidget(self.stu_combo, 1)

        lbl_count = QLabel(f"{len(students)} students in database")
        lbl_count.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-family: {BODY}; background: transparent;")
        row.addWidget(lbl_count)
        lay.addLayout(row)
        return card

    def _build_info_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background: {CARD_BG}; border-radius: 10px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(10)
        lay.addWidget(_section_title("👤", "Student Details"))

        pf = QFormLayout()
        pf.setLabelAlignment(Qt.AlignRight)
        pf.setSpacing(10)

        def _row(lbl_text, widget, tip=""):
            widget.setFixedHeight(36)
            widget.setStyleSheet(FIELD_SS)
            if tip:
                widget.setToolTip(tip)
            pf.addRow(_label(lbl_text, tip), widget)

        self.name_e  = QLineEdit()
        _row("Student Name *", self.name_e)
        self.fname_e = QLineEdit()
        _row("Father's Name *", self.fname_e)
        self.roll_e  = QLineEdit()
        _row("Roll Number", self.roll_e)
        self.class_e = QLineEdit()
        _row("Class *", self.class_e)
        self.prog_e  = QLineEdit()
        _row("Program *", self.prog_e)
        self.sess_e  = QLineEdit()
        _row("Session *", self.sess_e)

        lay.addLayout(pf)
        return card

    def _build_cert_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background: {CARD_BG}; border-radius: 10px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(10)
        lay.addWidget(_section_title("📝", "Certificate Details"))

        pf = QFormLayout()
        pf.setLabelAlignment(Qt.AlignRight)
        pf.setSpacing(10)

        self.adm_e = QLineEdit()
        self.adm_e.setFixedHeight(36)
        self.adm_e.setStyleSheet(FIELD_SS)
        pf.addRow(_label("Date of Admission"), self.adm_e)

        self.leave_e = QLineEdit()
        self.leave_e.setFixedHeight(36)
        self.leave_e.setStyleSheet(FIELD_SS)
        pf.addRow(_label("Date of Leaving"), self.leave_e)

        self.conduct_combo = QComboBox()
        self.conduct_combo.addItems(["Good", "Very Good", "Excellent", "Satisfactory", "Poor"])
        self.conduct_combo.setFixedHeight(36)
        self.conduct_combo.setStyleSheet(FIELD_SS)
        pf.addRow(_label("Conduct *"), self.conduct_combo)

        self.behav_combo = QComboBox()
        self.behav_combo.addItems(["Disciplined", "Well-Behaved", "Respectful", "Average", "Needs Improvement"])
        self.behav_combo.setFixedHeight(36)
        self.behav_combo.setStyleSheet(FIELD_SS)
        pf.addRow(_label("Behavior *"), self.behav_combo)

        lay.addLayout(pf)

        lay.addSpacing(4)
        lay.addWidget(_label("Additional Remarks:"))
        self.remarks_e = QTextEdit()
        self.remarks_e.setFixedHeight(70)
        self.remarks_e.setStyleSheet(f"""
            QTextEdit {{
                border: 1.5px solid {BORDER}; border-radius: 8px;
                padding: 7px 11px; background: #f8faff;
                color: {TEXT_MAIN}; font-size: 13px; font-family: {BODY};
            }}
            QTextEdit:focus {{ border: 2px solid {PRIMARY}; background: white; }}
        """)
        lay.addWidget(self.remarks_e)
        return card

    def _refresh_cert_no(self):
        try:
            self.cert_e.setText(self.cc_repo.get_next_cert_no())
        except Exception:
            self.cert_e.setText("CC-0001")

    def _on_student_selected(self, idx: int):
        if idx <= 0:
            return
        sid = self.stu_combo.currentData()
        if sid is None:
            return
        try:
            s = self.stu_repo.get_by_id(sid)
            if s:
                self.name_e.setText(s.name or "")
                self.fname_e.setText(s.father_name or "")
                self.roll_e.setText(s.roll_no or "")
                self.class_e.setText(s.class_name or "")
                self.prog_e.setText(s.program or "")
                self.sess_e.setText(s.session or "")
                self._badge.show_as("info", f"ℹ️  Loaded details for {s.name}")
        except Exception as exc:
            self._badge.show_as("warning", f"⚠️  Error: {exc}")

    def _validate(self) -> str:
        if not self.name_e.text().strip(): return "Student name is required."
        if not self.fname_e.text().strip(): return "Father's name is required."
        if not self.class_e.text().strip(): return "Class is required."
        if not self.prog_e.text().strip(): return "Program is required."
        if not self.sess_e.text().strip(): return "Session is required."
        return ""

    def _generate(self):
        self._badge.clear_badge()
        err = self._validate()
        if err:
            self._badge.show_as("error", f"⚠️  {err}")
            return

        name = self.name_e.text().strip()
        try:
            # 💡 Pass date_issued here so it is never None!
            today_str = datetime.now().strftime('%d-%m-%Y')

            cc = CharacterCertificate(
                cert_no           = self.cert_e.text(),
                student_name      = name,
                father_name       = self.fname_e.text().strip(),
                roll_no           = self.roll_e.text().strip(),
                class_name        = self.class_e.text().strip(),
                program           = self.prog_e.text().strip(),
                session           = self.sess_e.text().strip(),
                date_of_admission = self.adm_e.text().strip(),
                date_of_leaving   = self.leave_e.text().strip(),
                conduct           = self.conduct_combo.currentText(),
                behavior          = self.behav_combo.currentText(),
                character_remarks = self.remarks_e.toPlainText().strip(),
                date_issued       = today_str,  # <--- Added this line
            )

            project_root = Path(__file__).parent
            pdf_path = generate_character_certificate_pdf(cc, project_root)
            cc.pdf_path = pdf_path
            self.cc_repo.save(cc)

            self._badge.show_as("success", f"✅  Certificate {cc.cert_no} generated successfully!")
            self._refresh_cert_no()
            self._clear(keep_badge=True)
            self._open_pdf(pdf_path)
        except Exception as exc:
            traceback.print_exc()
            self._badge.show_as("error", f"❌  Generation failed: {exc}")

    def _open_pdf(self, path: str):
        import platform, subprocess
        try:
            if platform.system() == "Windows": os.startfile(path)
            elif platform.system() == "Darwin": subprocess.call(["open", path])
            else: subprocess.call(["xdg-open", path])
        except Exception:
            pass

    def _show_history(self):
        items = self.cc_repo.get_all()
        dlg = QDialog(self)
        dlg.setWindowTitle("Certificate History")
        dlg.setMinimumSize(820, 420)
        dlg.setStyleSheet(f"QDialog {{ background: {PAGE_BG}; }}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 14)

        t = QTableWidget()
        t.setColumnCount(7)
        t.setHorizontalHeaderLabels(["Cert No", "Student", "Father", "Class", "Conduct", "Behavior", "Date Issued"])
        t.verticalHeader().setVisible(False)
        t.setStyleSheet(TABLE_SS)
        t.setRowCount(len(items))

        for i, cc in enumerate(items):
            for col, val in enumerate([
                cc.cert_no, cc.student_name, cc.father_name,
                f"{cc.class_name} ({cc.program})", cc.conduct, cc.behavior, cc.date_issued,
            ]):
                t.setItem(i, col, QTableWidgetItem(val or "—"))

        lay.addWidget(t)
        dlg.exec()

    def _clear(self, keep_badge: bool = False):
        self.stu_combo.setCurrentIndex(0)
        for w in (self.name_e, self.fname_e, self.roll_e, self.class_e, self.prog_e, self.sess_e, self.adm_e, self.leave_e):
            w.clear()
        self.conduct_combo.setCurrentText("Good")
        self.behav_combo.setCurrentText("Disciplined")
        self.remarks_e.clear()
        if not keep_badge:
            self._badge.clear_badge()