"""
PDF Generator Module - HTML Challan Mode (Enhanced Visual Design)
- Generates a modern HTML Challan (Colorful & Attractive) + Signature Embedded + Bank Logo for all classes/students.
"""

import os
import logging
import base64
from pathlib import Path
from datetime import datetime
from io import BytesIO

import qrcode

logger = logging.getLogger(__name__)

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CONFIG


class NumberToWords:
    def __init__(self):
        self.ones = ["", "One", "Two", "Three", "Four", "Five", "Six", 
                    "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
                    "Thirteen", "Fourteen", "Fifteen", "Sixteen",
                    "Seventeen", "Eighteen", "Nineteen"]
        self.tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty",
                    "Sixty", "Seventy", "Eighty", "Ninety"]

    def convert(self, number):
        try:
            n = int(number)
        except ValueError:
            return "Invalid Amount"
        if n == 0: return "Zero"
        if n < 0: return "Minus " + self.convert(-n)
        result = ""
        if n >= 10000000:
            result += self._convert_less_than_hundred(n // 10000000) + " Crore "
            n %= 10000000
        if n >= 100000:
            result += self._convert_less_than_hundred(n // 100000) + " Lakh "
            n %= 100000
        if n >= 1000:
            result += self._convert_less_than_hundred(n // 1000) + " Thousand "
            n %= 1000
        if n >= 100:
            result += self.ones[n // 100] + " Hundred "
            n %= 100
        if n > 0:
            result += self._convert_less_than_hundred(n)
        return result.strip()

    def _convert_less_than_hundred(self, n):
        if n < 20: return self.ones[n]
        tens_part = self.tens[n // 10]
        ones_part = self.ones[n % 10]
        if ones_part: return f"{tens_part}-{ones_part}"
        return tens_part


class ChallanGenerator:
    def __init__(self):
        self.bank = {
            'account_no': CONFIG.BANK_ACCOUNT,
            'branch_name': CONFIG.BANK_BRANCH,
            'branch_code': CONFIG.BRANCH_CODE
        }
        self.converter = NumberToWords()

        try:
            self.folder = str(CONFIG.OUTPUT_DIR / "Generated")
            Path(self.folder).mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            self.folder = str(Path.home() / "Documents" / "CollegeChallan" / "Generated")
            try:
                Path(self.folder).mkdir(parents=True, exist_ok=True)
            except Exception:
                import tempfile
                self.folder = tempfile.gettempdir()

        current_dir = Path(__file__).parent
        assets_dir = current_dir / "assets"
        if not assets_dir.exists():
            assets_dir = current_dir.parent / "assets"

        self.college_logo_path = str(assets_dir / "college_logo.png")
        self.bank_logo_path = str(assets_dir / "bok_logo.png")
        self.signature_path = str(assets_dir / "signature.png") 
        self.logo_url = "https://z-cdn-media.chatglm.cn/files/b23855e6-6c50-425a-b7ea-b18a4230684c.png"

    def generate_pdf(self, student, challan_no, amount):
        return self._generate_html_challan(student, challan_no, amount)

    def _clean_value(self, val):
        if not val or str(val).strip().lower() in ["n/a", "none", "nan", ""]:
            return ""
        return str(val).strip()

    def _get_logo_base64(self):
        if os.path.exists(self.college_logo_path):
            try:
                with open(self.college_logo_path, "rb") as f:
                    return base64.b64encode(f.read()).decode('utf-8')
            except Exception: pass
        return None

    def _get_bank_logo_base64(self):
        if os.path.exists(self.bank_logo_path):
            try:
                with open(self.bank_logo_path, "rb") as f:
                    return base64.b64encode(f.read()).decode('utf-8')
            except Exception: pass
        return None

    def _get_signature_base64(self):
        if os.path.exists(self.signature_path):
            try:
                with open(self.signature_path, "rb") as f:
                    return base64.b64encode(f.read()).decode('utf-8')
            except Exception: pass
        return None

    def _generate_qr_base64(self, data):
        try:
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=5, border=1)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Exception:
            return ""

    def _generate_html_challan(self, student, challan_no, amount):
        try:
            amount_float = float(amount)
            amount_int = int(amount_float)
            date_str = datetime.now().strftime("%d-%m-%Y")

            s_name = self._clean_value(student.get('name'))
            s_fname = self._clean_value(student.get('father_name'))
            s_class = self._clean_value(student.get('class'))
            s_roll = self._clean_value(student.get('roll_no'))
            s_program = self._clean_value(student.get('program')).lower()
            s_session = self._clean_value(student.get('session'))
            s_purpose = student.get('purpose', 'Student Admission Fee')
            s_description = self._clean_value(student.get('description'))

            if s_purpose == 'Other':
                path = os.path.join(self.folder, "Miscellaneous")
            else:
                path = os.path.join(self.folder, f"Session_{s_session}", s_class)
            Path(path).mkdir(parents=True, exist_ok=True)

            safe_name = s_name.replace(' ', '_').replace('/', '_') if s_name else "Misc"
            file_path = os.path.join(path, f"Challan_{safe_name}_{challan_no}.html")

            logo_b64 = self._get_logo_base64()
            logo_src = f"data:image/png;base64,{logo_b64}" if logo_b64 else self.logo_url
            qr_data = f"Challan: {challan_no}\nStudent: {s_name}\nAmount: Rs. {amount_int}\nDate: {date_str}"
            qr_b64 = self._generate_qr_base64(qr_data)
            qr_src = f"data:image/png;base64,{qr_b64}"

            sig_b64 = self._get_signature_base64()
            sig_html_block = f'<div class="signature-img-wrapper"><img src="data:image/png;base64,{sig_b64}" class="signature-img" alt="Sig"></div>' if sig_b64 else ""

            bank_logo_b64 = self._get_bank_logo_base64()
            bank_logo_html = f'<div class="bank-logo-area"><img src="data:image/png;base64,{bank_logo_b64}" class="bank-logo-img" alt="BOK"></div>' if bank_logo_b64 else ''

            # Clean single-row or category-based fee printing for Admission/Promotion/Semester fees
            fee_title = s_purpose if s_purpose else "Institutional Fee"
            fee_rows = f"""
                <tr>
                    <td>1</td>
                    <td>{fee_title} ({s_class})</td>
                    <td style='text-align:right'>{amount_int}/-</td>
                </tr>
                <tr class='total-row'>
                    <td colspan='2' style='text-align:right'>TOTAL</td>
                    <td style='text-align:right'><strong>{amount_int}/-</strong></td>
                </tr>
            """

            footer_html = f"""
                <div class="footer-area">
                    <div class="signature-box">{sig_html_block}<div class="sign-line"></div><div class="sign-label">Depositor Signature</div></div>
                    <div class="bank-use-box"><div class="bank-use-title">For Bank Use Only</div></div>
                </div>"""

            bank_details_block = f"""<div class="bank-details-box">{bank_logo_html}<div class="bank-text"><div class="bank-details-title">Bank Details:</div><div><strong>Bank of Khyber</strong>, {self.bank.get('branch_name','')}</div><div>Branch Code: <strong>{self.bank.get('branch_code','')}</strong></div><div>A/c No: <strong>{self.bank.get('account_no','')}</strong></div></div><div class="qr-code-area"><img src="{qr_src}" alt="QR"><div class="scan-text">Scan for Info</div></div></div>"""

            single_copy_html = f"""
            <div class="copy-section">
                <div class="watermark">Govt Girls Degree College KHADO KHEL</div>
                <div class="copy-badge {{badge_class}}">{{copy_title}}</div>
                <div class="header">
                    <div class="logo-area">
                        <img src="{logo_src}" alt="Logo" class="college-logo">
                        <div class="header-text">
                            <h2>Govt Girls Degree College Khado Khel Buner</h2>
                            <h3>Fee Deposit Challan</h3>
                        </div>
                    </div>
                </div>
                <div class="challan-info">
                    <div><strong>Challan No:</strong> {challan_no}</div>
                    <div style="text-align:right"><strong>Date:</strong> {date_str}</div>
                </div>
                <div class="main-content">
                    <div class="info-group"><span class="info-label">Student Name</span><div class="info-value">{s_name}</div></div>
                    <div class="info-group"><span class="info-label">Father Name</span><div class="info-value">{s_fname}</div></div>
                    <div class="info-group"><span class="info-label">Class</span><div class="info-value">{s_class}</div></div>
                    <div class="info-group"><span class="info-label">Roll No</span><div class="info-value">{s_roll}</div></div>
                    <div class="info-group"><span class="info-label">Program</span><div class="info-value">{student.get('program','')}</div></div>
                    <div class="info-group"><span class="info-label">Session</span><div class="info-value">{s_session}</div></div>
                </div>
                <table class="fee-table">
                    <thead><tr><th>Sr#</th><th>Description</th><th style="text-align:right">Amount (Rs.)</th></tr></thead>
                    <tbody>{fee_rows}</tbody>
                </table>
                {bank_details_block}
                {footer_html}
            </div>"""

            bank_copy = single_copy_html.replace("{badge_class}", "bg-bank").replace("{copy_title}", "Bank Copy")
            student_copy = single_copy_html.replace("{badge_class}", "bg-student").replace("{copy_title}", "Student Copy")
            college_copy = single_copy_html.replace("{badge_class}", "bg-college").replace("{copy_title}", "College Record")

            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Challan {challan_no}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:6px;-webkit-print-color-adjust:exact;font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif}}
.challan-wrapper{{max-width:297mm;margin:0 auto;background:rgba(255,255,255,0.95);border-radius:10px;box-shadow:0 25px 50px -12px rgba(0,0,0,0.25);padding:4px;backdrop-filter:blur(10px)}}
.challan-container{{width:100%;background:white;border-radius:12px;overflow:hidden;display:flex;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1)}}
.copy-section{{flex:1;padding:10px 12px;border-right:3px dashed #e2e8f0;position:relative;background:linear-gradient(180deg,#ffffff 0%,#f8fafc 100%)}}
.copy-section:last-child{{border-right:none}}
.copy-section::before{{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,#3b82f6,#8b5cf6,#ec4899);opacity:0.8}}
.header{{text-align:center;padding-bottom:6px;margin-bottom:8px;position:relative}}
.logo-area{{display:flex;align-items:center;justify-content:center;margin-bottom:4px;gap:8px}}
.college-logo{{width:48px;height:auto;filter:drop-shadow(0 4px 6px rgba(0,0,0,0.1));border-radius:6px}}
.header-text h2{{background:linear-gradient(135deg,#1e40af 0%,#3b82f6 50%,#1e40af 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;font-size:12px;text-transform:uppercase;margin-bottom:2px;font-weight:800;letter-spacing:0.5px}}
.header-text h3{{color:#64748b;font-size:11px;font-weight:600;letter-spacing:1px}}
.copy-badge{{position:absolute;top:0;right:0;padding:4px 12px;font-size:9px;font-weight:800;text-transform:uppercase;border-bottom-left-radius:10px;color:white;letter-spacing:1px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);z-index:10}}
.bg-bank{{background:linear-gradient(135deg,#3b82f6 0%,#1d4ed8 100%)}}
.bg-student{{background:linear-gradient(135deg,#10b981 0%,#059669 100%)}}
.bg-college{{background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%)}}
.challan-info{{display:flex;justify-content:space-between;margin-bottom:8px;font-size:11px;background:linear-gradient(135deg,#f1f5f9 0%,#e2e8f0 100%);padding:5px 10px;border-radius:7px;border:1px solid #cbd5e1}}
.challan-info strong{{color:#1e40af;font-weight:700}}
.main-content{{display:grid;grid-template-columns:1fr 1fr;gap:5px 10px;margin-bottom:8px;background:#ffffff;padding:8px;border-radius:7px;border:1px solid #e2e8f0;box-shadow:0 1px 3px rgba(0,0,0,0.05)}}
.info-group{{position:relative}}
.info-label{{display:block;font-size:8px;color:#64748b;text-transform:uppercase;margin-bottom:1px;font-weight:600;letter-spacing:0.5px}}
.info-value{{font-size:11px;font-weight:700;color:#1e293b;border-bottom:2px solid #e2e8f0;padding-bottom:2px;min-height:16px}}
.fee-table{{width:100%;border-collapse:separate;border-spacing:0;margin-top:0;font-size:10px;border-radius:7px;overflow:hidden;box-shadow:0 2px 4px -1px rgba(0,0,0,0.05)}}
.fee-table th{{text-align:left;padding:5px 8px;background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);color:white;font-weight:700;text-transform:uppercase;font-size:8px;letter-spacing:0.5px}}
.fee-table th:first-child{{border-radius:7px 0 0 0}}.fee-table th:last-child{{border-radius:0 7px 0 0}}
.fee-table td{{padding:4px 8px;border-bottom:1px solid #e2e8f0;background:white}}
.fee-table tr:nth-child(even) td{{background:#f8fafc}}
.total-row td{{font-weight:800;font-size:11px;border-top:2px solid #3b82f6;background:linear-gradient(135deg,#dbeafe 0%,#bfdbfe 100%)!important;color:#1e40af}}
.bank-details-box{{background:linear-gradient(135deg,#ecfdf5 0%,#d1fae5 100%);padding:7px 10px;border-radius:8px;margin-top:7px;border:1.5px solid #10b981;box-shadow:0 2px 4px -1px rgba(16,185,129,0.1);display:flex;justify-content:space-between;align-items:center;gap:8px}}
.bank-logo-area{{flex-shrink:0;text-align:center;background:white;padding:4px;border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,0.05)}}
.bank-logo-img{{width:52px;height:52px;border:1.5px solid #10b981;border-radius:6px;background:white;object-fit:contain;display:block}}
.bank-text{{flex:1;min-width:0}}
.bank-details-title{{font-weight:800;background:linear-gradient(135deg,#059669 0%,#10b981 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:3px;font-size:9px;text-transform:uppercase;letter-spacing:0.5px}}
.bank-details-box div{{color:#065f46;font-size:9px;line-height:1.4}}
.bank-details-box strong{{color:#047857;font-weight:700}}
.qr-code-area{{flex-shrink:0;text-align:center;background:white;padding:4px;border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,0.05)}}
.qr-code-area img{{width:52px;height:52px;border:1.5px solid #10b981;border-radius:6px;background:white}}
.scan-text{{font-size:8px;color:#059669;margin-top:4px;font-weight:600}}
.footer-area{{margin-top:8px;border-top:1.5px solid #e2e8f0;padding-top:7px;display:flex;justify-content:space-between;align-items:stretch;min-height:133px}}
.signature-box{{text-align:center;width:38.5%;background:linear-gradient(180deg,#f8fafc 0%,#f1f5f9 100%);padding:8px 10px;border-radius:7px;border:1px solid #e2e8f0;min-height:133px;display:flex;flex-direction:column;justify-content:flex-end;align-items:center}}
.signature-img-wrapper{{width:100%;display:flex;align-items:center;justify-content:center;margin-bottom:2px;margin-top:auto;min-height:55px}}
.signature-img{{max-width:120px;max-height:55px;height:auto;width:auto;object-fit:contain;filter:contrast(1.05) brightness(1.02);opacity:0.92}}
.sign-line{{border-top:1.5px solid #475569;width:100%;margin-bottom:4px;border-radius:2px}}
.sign-label{{font-size:9px;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:0.5px}}
.bank-use-box{{border:1.5px dashed #94a3b8;width:59%;min-height:133px;height:auto;padding:8px;position:relative;background:linear-gradient(135deg,#f8fafc 0%,#f1f5f9 100%);border-radius:7px}}
.bank-use-title{{position:absolute;top:7px;left:8px;font-size:9px;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;background:#f1f5f9;padding:1px 6px;border-radius:3px}}
.watermark{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%) rotate(-30deg);font-size:60px;font-weight:800;color:rgba(59,130,246,0.03);pointer-events:none;z-index:0;text-transform:uppercase;letter-spacing:10px}}
@media print{{html,body{{background:white!important;padding:0!important;margin:0!important;height:auto!important;overflow:hidden!important}}
.challan-wrapper{{box-shadow:none!important;border-radius:0!important;padding:0!important;margin:0!important;background:white!important;max-width:100%!important}}
.challan-container{{box-shadow:none!important;width:100%!important;border-radius:0!important;page-break-inside:avoid!important;break-inside:avoid!important}}
.copy-section{{background:white!important;page-break-inside:avoid!important;break-inside:avoid!important}}
@page{{size:A4 landscape;margin:5mm}}}}
</style>
</head>
<body>
<div class="challan-wrapper">
    <div class="challan-container">
        {bank_copy}
        {student_copy}
        {college_copy}
    </div>
</div>
</body>
</html>"""

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            return file_path
        except Exception as e:
            logger.error(f"HTML generation error: {e}")
            raise


PDFGenerator = ChallanGenerator