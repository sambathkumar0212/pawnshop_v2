# First Money Gold - Pawnshop Management System (V2)

A enterprise-grade Django management ecosystem tailored for gold pawnshops, jewelers, and multi-branch NBFC operations with biometric authentication, dynamic UPI QR integration, maker-checker governance, automated WhatsApp engine, and real-time RBI IRAC compliance.

[![Python Version](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Django Version](https://img.shields.io/badge/Django-5.2+-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20%2F%20SQLite-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![WhatsApp Engine](https://img.shields.io/badge/WhatsApp-Playwright_Automator-25D366?logo=whatsapp&logoColor=white)](https://web.whatsapp.com/)
[![Run Project (Windows)](https://img.shields.io/badge/Run_Project-Windows_BAT-0078D4?logo=windows&logoColor=white)](./run_project.bat)

---

## 🌐 System URLs & Quick Access Links

| Application Console / Portal | URL Route | Description |
| :--- | :--- | :--- |
| 🌐 **Customer Self-Service Portal** | [http://127.0.0.1:8000/portal/login/](http://127.0.0.1:8000/portal/login/) | Customer self-service login (username `fm_<phone>` + 8-digit temporary PIN). |
| 📊 **Customer Dashboard** | [http://127.0.0.1:8000/portal/dashboard/](http://127.0.0.1:8000/portal/dashboard/) | Customer dashboard with Active Loans, Interest Due, Repayment Logs, and "Pay via UPI QR" modal. |
| 📲 **Staff UPI Verification Queue** | [http://127.0.0.1:8000/transactions/payments/pending-upi/](http://127.0.0.1:8000/transactions/payments/pending-upi/) | Live queue for staff to review incoming customer 12-digit UTRs and approve/reject with 1 click. |
| 👥 **Customer Directory & Credentials** | [http://127.0.0.1:8000/accounts/customers/](http://127.0.0.1:8000/accounts/customers/) | Staff management view with green "Send Login via WhatsApp" button & Super-Admin Force-Reset controls. |
| 🏢 **Main Staff Dashboard** | [http://127.0.0.1:8000/](http://127.0.0.1:8000/) | Pawnshop management home console for loan operations, billing, and appraisal. |
| 🛡️ **Maker-Checker Loan Approvals** | [http://127.0.0.1:8000/transactions/approvals/](http://127.0.0.1:8000/transactions/approvals/) | 3-Tier loan approval queue with OTP verification and appraisal reviews. |
| 🤖 **24/7 Autopilot Control Console** | [http://127.0.0.1:8000/transactions/autopilot/](http://127.0.0.1:8000/transactions/autopilot/) | Background daemon for automated reminders, collections, and marketing. |
| 🌙 **EOD Operations & IRAC NPA Hub** | [http://127.0.0.1:8000/transactions/eod-console/](http://127.0.0.1:8000/transactions/eod-console/) | End-of-Day batch execution, daily interest accrual, and RBI NPA tagging. |
| 💵 **Cash Till & Scroll Management** | [http://127.0.0.1:8000/accounting/cash-till/](http://127.0.0.1:8000/accounting/cash-till/) | Physical drawer count auditing, denomination logging, and real-time cash balances. |
| 🏛️ **Vault Pouch Custody Explorer** | [http://127.0.0.1:8000/inventory/vault-explorer/](http://127.0.0.1:8000/inventory/vault-explorer/) | Barcode-based sealed pouch tracking across safe lockers and branch vaults. |
| ⚙️ **Django Admin Portal** | [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/) | System administrative backend. |

---

## 🌟 Core Features & Capabilities

### 💳 1. Self-Service Customer Portal & Free UPI QR Payments
* **Dynamic UPI QR Code Generator**: Free NPCI-compliant `upi://pay?pa=...` generator rendered as Base64 inline PNG matrix images without payment gateway transaction fees.
* **12-Digit UTR Sub-Form & Verification Queue**: Customers submit their 12-digit transaction UTR; staff can review against bank credits and approve or reject with 1 click.
* **Automated Customer Credentials & WhatsApp Dispatch**: Auto-generation of unique usernames (`fm_<phone>`) and randomized 8-character temporary PINs, deliverable via green WhatsApp deep-link buttons.
* **Strict Super-Admin RBAC Governance**: Branch Managers are restricted to view-only credential access; Super-Admin holds exclusive power to force-reset credentials or toggle portal access.
* **Self-Service Customer Dashboard**: Mobile-first responsive dashboard under `/portal/` displaying active loans, interest due, quick payment triggers, repayment history logs, and closed loan history.

### 🛡️ 2. Risk Management & Maker-Checker Governance
* **Tiered Maker-Checker Approvals**: 3-level approval governance:
  * **Tier 1**: Principal &le; ₹2,00,000 (Branch Manager approval).
  * **Tier 2**: Principal ₹2,00,001 &ndash; ₹10,00,000 (Branch Manager + Regional Manager approval).
  * **Tier 3**: Principal > ₹10,00,000 (Branch Manager + Regional Manager + Head Office Credit Committee).
* **Customer OTP Verification**: Mandatory 6-digit cryptographic OTP verification via WhatsApp on loan creation before manager approval can be granted.
* **Controlled Disbursals (IT Sec 269SS/269T)**: Money disbursement locked until manager approval; strict statutory cash limit enforcement (< ₹20,000 in Cash; mandatory Bank Transfer/UPI/Cheque for &ge; ₹20,000).
* **Section 269ST Repayment Cap**: Prevents cash repayments of ₹2,00,000 or more per customer across all branches within a single day.
* **RBI IRAC NPA Tagging & EOD Console**: Automated asset classification (`Standard`, `SMA-0`, `SMA-1`, `SMA-2`, `NPA Substandard`, `Doubtful`, `Loss`) with daily interest accrual and provisioning calculations.

### 🤖 3. 24/7 Autopilot Automation & WhatsApp Broadcast Hub
* **24/7 Autopilot Background Engine**: Automatic background daemon running scheduled cycles for overdue collections, payment reminders, and retention alerts.
* **Headless In-Modal WhatsApp QR Streaming**: Pair WhatsApp Web seamlessly with real-time base64 QR stream directly inside the modal with zero popup windows.
* **Automated Customer Welcome Wishes**: Instant bilingual WhatsApp welcome message sent upon customer registration with live delivery diagnostics.
* **Special Occasion Celebration Engine**: Proactive automated Birthday (🎂) & Wedding Anniversary (💍) WhatsApp wishes dispatch with duplicate suppression.
* **Digital Marketing Auto-Blaster**: Headless bulk broadcasts with smart tags (`{customer_name}`, `{gold_rate}`, `{branch_name}`), invalid/dummy number auto-skipping, and pause/resume/stop campaign controls.

### 💎 4. Gold Loan Operations & Collateral Management
* **Partial Ornament Release**: Item-level collateral release workflow with real-time valuation recalculation and bilingual PDF release vouchers.
* **Spot Gold Purchasing (Old Gold Buyback)**: Spot cash gold purchasing with karat testing valuation, biometric KYC, and instant receipts.
* **Bilingual Bills (Tamil / English)**: Dynamic bilingual PDF bill generation for pawn agreements, receipts, and closure certificates with translation caching.
* **Branch Cash Till & Double-Entry Accounting**: Real-time cash till tracking, daily drawer reconciliation, physical cash count auditing, and automated GL entries.
* **Vault Custody & Sealed Pouch Tracking**: Safe locker assignment, tamper-evident barcode seal tracking, and multi-tier vault audits.
* **Biometric Face Identification**: High-accuracy face enrollment and real-time verification matching customers to their active loan records.

---

## 🛠️ Technology Stack

* **Backend**: Python 3.9+, Django 5.2 (LTS), Django REST Framework
* **Frontend**: HTML5, Vanilla JavaScript, Bootstrap 5.3, FontAwesome 6, Google Fonts (Plus Jakarta Sans)
* **Database**: PostgreSQL (Production / Neon / Cloud SQL) / SQLite3 (Development)
* **Automation & Messaging**: Playwright (Headless Chromium), `qrcode` (Base64 matrix rendering), PyWhatKit
* **Document Generation**: ReportLab, xhtml2pdf, openpyxl, xlsxwriter
* **Authentication**: Django RBAC, Session Auth, JWT, Biometric Encoded Embeddings

---

## 🚀 Quick Start & Installation

### 1. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/sambathkumar0212/pawnshop.git
cd pawnshop_v2

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env.development` or `.env`:
```bash
cp .env.example .env.development
```

### 4. Run Database Migrations
```bash
python manage.py migrate
```

### 5. Create Superuser (Admin)
```bash
python manage.py createsuperuser
```

### 6. Run Development Server
```bash
# Windows Quick Launcher:
.\run_project.bat

# Standard Command:
python manage.py runserver
```
Access the application at [http://127.0.0.1:8000/](http://127.0.0.1:8000/) and the Customer Portal at [http://127.0.0.1:8000/portal/login/](http://127.0.0.1:8000/portal/login/).

---

## 👥 Role-Based Access Control (RBAC)

| Role | Permissions & Scope |
| :--- | :--- |
| **System Super-Admin / IT Admin** | Full system configuration, multi-tenant organization control, exclusive customer portal force-reset and access toggle, system audits. |
| **Regional Manager** | Multi-branch surveillance, Tier 2 loan approvals (up to ₹10 Lakhs), regional asset classification and audit monitoring. |
| **Branch Manager** | Daily branch operations, staff oversight, Tier 1 loan approvals (up to ₹2 Lakhs), cash drawer opening/closing, view-only customer credentials. |
| **Loan Officer / Appraiser** | Customer onboarding, gold karat valuation, weighing, loan origination, OTP trigger, pledge receipt printing. |
| **Cashier / Teller** | Cash scroll management, cash/bank disbursals, interest payment collection, UPI payment verification queue. |
| **Customer (Self-Service)** | Read-only access to active/closed loan details, real-time interest accrued, repayment logs, and dynamic UPI QR code generator. |

---

## 🧪 Verification & Testing Suite

Run the automated verification suite for the Customer Portal, UPI QR generation, and loan approval flows:
```bash
python scratch/verify_portal_features.py
```

Run Django project health checks:
```bash
python manage.py check
```

---

## 📄 License & Intellectual Property

First Money Gold &copy; 2026. All rights reserved. Proprietary software developed for pawnshop and financial lending operations.
