# GGDC Khado Khel — Enterprise Fine & Special Fine Management System

A professional desktop application built for institutional administration to manage student fine collections, admission/institutional fees, official character certificates, generate standardized bank challans, track daily cash books, and process bulk class fine impositions with high-speed keyboard navigation.

---

## 🚀 Key Features

* **Uniform 3-Section Challan Layout:** Automatically renders a clean, standardized HTML challan containing Bank Copy, Student Copy, and College Record with embedded signatures, college logos, and Bank of Khyber details[cite: 5].
* **Character Certificate Management:** Fully integrated native tab to issue official parchment-style character certificates with QR code verification, automated serial numbering, conduct assessments, and print-ready A4 PDF generation[cite: 1].
* **Admission & Institutional Fees:** Dedicated tracking and challan generation for institutional fees (Admission, Promotion, and Semester fees) with automated Excel reporting[cite: 5].
* **Financial Summary & Cash Book:** Real-time tracking of total collections, total issued challans, and category-wise breakdowns across fines and fees[cite: 5].
* **Bulk Class Fines:** Instantly impose uniform fines across an entire class using comma-separated student names and roll numbers, paired with automated Excel report generation[cite: 5].
* **Student Clearance Lookup:** Quickly search student fine and fee histories to calculate total dues[cite: 5].
* **Advanced Office Workflow & Shortcuts:**
  * **Up / Down / Enter:** Smooth form navigation without touching the mouse[cite: 5].
  * **`Ctrl + Enter`:** Instantly generate a challan or submit forms[cite: 5].
  * **`Ctrl + 1 to 7`**: Quickly switch between navigation tabs.
  * **`Ctrl + F` / `Ctrl + K`**: Quick filter and search shortcuts[cite: 5].
  * **`Ctrl + Shift + S`**: Create an instant database backup[cite: 5].
* **Data Security & Exporting:** Full Excel export capabilities for range reports, daily cash books, institutional fees, and student directories[cite: 5].

---

## 🛠️ Project Structure

```text
GGDC Khado Khel software/
│
├── main.py               # Main application window & controller logic
├── cc_dialog.py          # Character certificate models, repository, and PDF renderer
├── database.py           # Main SQLite database manager & fine queries
├── fee_database.py       # Institutional fee SQLite database manager
├── fee_engine.py         # Fee category resolution engine
├── pdf_generator.py      # HTML challan template renderer
├── requirements.txt      # Python dependencies list
│
├── ui/
│   └── components.py     # UI layouts, tabs (including Character Certificate), and event filters
│
└── assets/
    ├── college_logo.png  # Institutional logo
    ├── bok_logo.png      # Bank logo
    └── signature.png     # Official authorized signature