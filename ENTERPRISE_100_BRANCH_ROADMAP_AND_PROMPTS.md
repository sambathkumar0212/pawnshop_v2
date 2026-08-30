# Enterprise 100+ Branch Gold Loan Transformation Roadmap & Task Prompts
*Modeled after industry standards of Muthoot Finance & Manappuram Finance*

---

## 📌 Executive Summary

To operate a network of **100+ branches** with institutional compliance (RBI NBFC norms & Income Tax Act), the system requires enterprise-grade controls across:
1. **Physical Asset & Vault Custody** (Tamper-proof pouch tracking, dual keyholder custody, real-time safe explorer).
2. **Regulatory & Financial Controls** (Strict 75% LTV ceiling, central HO daily rate engine, Sec 269SS/269T cash limits).
3. **Branch Governance & Cash Accounting** (Multi-tier hierarchy, tiered maker-checker approvals, daily cash till/scroll reconciliation).
4. **Lifecycle Operations** (Automated EOD interest accrual, IRAC NPA tagging, partial ornament release, renewals/top-ups, 3-stage statutory auction notices).
5. **Digital Ecosystem & Infrastructure** (Customer repayment portal, WhatsApp/SMS gateway, digital KYC, Celery/Redis high-concurrency scaling).

---

## 🗺️ Master Implementation Roadmap

```
PHASE 1: Security, Compliance & Core Financials
├── Task 1.1: Tamper-Proof Vault Pouch & Barcode Tracking System
├── Task 1.2: Central Daily Gold Rate & Strict RBI 75% LTV Cap Engine
├── Task 1.3: Income Tax Sec 269SS/269T Disbursal Rules & Bank Payout Integration
├── Task 1.4: Branch Cash Drawer, Cash Till & Daily Cash Scroll (EOD Reconciliation)
└── Task 1.5: Core Double-Entry General Ledger & Day Book Accounting

PHASE 2: Hierarchy, Approvals & Lifecycle Operations
├── Task 2.1: Multi-Tier Hierarchy (HO ➔ Zone ➔ Region ➔ Branch) & Tiered Maker-Checker Approvals
├── Task 2.2: Automated EOD Engine (Daily Interest Accrual & RBI IRAC NPA Tagging)
├── Task 2.3: Partial Payment & Partial Ornament Release Workflow
├── Task 2.4: Instant Loan Top-Up & Same-Gold Renewal (Rollover) Engine
└── Task 2.5: Statutory Auction & 3-Stage Legal Notice Management Engine

PHASE 3: Digital Channels & Scalable Infrastructure
├── Task 3.1: Customer Portal & Online Repayment Gateway (UPI / NetBanking)
├── Task 3.2: Automated WhatsApp & SMS Notification Gateway
├── Task 3.3: Digital KYC Verification (Aadhaar OTP / PAN NSDL Verification)
└── Task 3.4: Production Hardening for 100+ Branches (Celery, Redis & PostgreSQL)
```

---

# 🚀 Phase 1: Security, Compliance & Core Financials

---

### Task 1.1: Tamper-Proof Vault Pouch & Barcode Tracking System

#### 📋 Execution Prompt
```text
Implement a complete Vault Asset Custody and Tamper-Proof Pouch Tracking System for our gold loan application:

1. Models & Database:
   - Create a `VaultPouch` model in the `inventory` app with fields:
     * `pouch_number` (Unique alphanumeric string / barcode)
     * `loan` (OneToOne/ForeignKey to Loan)
     * `branch` (ForeignKey to Branch)
     * `safe_locker_number` (CharField, e.g. "Safe-1 / Locker-A3")
     * `shelf_rack_number` (CharField)
     * `seal_barcode` (CharField, unique security seal number)
     * `status` (Choices: 'vaulted', 'in_transit', 'released', 'auctioned')
     * `custodian_maker` (ForeignKey to User - Staff who packed)
     * `custodian_checker` (ForeignKey to User - Branch Manager / Joint Keyholder who verified & locked)
     * `sealed_at`, `released_at`, `notes`
   - Add a `VaultAuditLog` model to track physical verification history and packet movements.

2. Workflows & UI:
   - On loan creation/approval, mandate entry of `pouch_number`, `safe_locker_number`, and `seal_barcode`.
   - Implement a "Vault Inward" dual-custody verification screen requiring two staff credentials.
   - Generate printable pouch labels with QR codes / Barcodes containing Loan ID, Customer Name, Net Weight, and Pouch No.
   - Build a "Vault Inventory Explorer" UI showing all pouches grouped by Safe Locker and Shelf Rack with instant search by Barcode / Pouch No.

3. Validation Rules:
   - Prevent loan finalization if pouch details are missing.
   - Pouch cannot be marked 'released' unless the associated loan status is 'repaid' or approved for partial release.
```

#### ✅ Validation & Acceptance Checklist
- [x] **Creation Test:** Create a new loan. Verify UI blocks submission without valid Pouch No and Seal Barcode.
- [x] **Barcode Label Test:** Click "Print Pouch Label" — verify generated PDF/print preview contains the correct barcode and details.
- [x] **Dual-Custody Test:** Log in as staff and attempt vault inwarding; verify second keyholder approval is enforced.
- [x] **Locker Search Test:** In Vault Explorer, search by `pouch_number` or `safe_locker_number` and verify instant filtering.
- [x] **Security Release Test:** Attempt to release a pouch on an active overdue loan; verify the system throws a validation error.

---

### Task 1.2: Central Daily Gold Rate & Strict RBI 75% LTV Cap Engine

#### 📋 Execution Prompt
```text
Implement a Centralized Gold Rate Management and Strict RBI Regulatory 75% LTV (Loan-To-Value) Cap Engine:

1. Models & Setup:
   - Create a `DailyGoldRate` model in the `schemes` app with fields:
     * `date` (DateField, unique per organization/region)
     * `rate_24k_per_gram`, `rate_22k_per_gram`, `rate_18k_per_gram` (DecimalField)
     * `maximum_ltv_percentage` (DecimalField, default=75.00, hard maximum 90.00 as per RBI norms)
     * `updated_by` (ForeignKey to User)
     * `is_active` (BooleanField)
   - Store historical rate logs to prevent retroactive tampering.

2. Loan Valuation Engine:
   - In `Loan` and `LoanItem` creation logic, dynamically fetch today's active rate for the item's purity.
   - Calculate:
     * `Market Value = Net Weight (grams) × Daily Rate per gram for purity`
     * `Max Eligible Loan Amount = Market Value × (Scheme LTV % or 75%, whichever is lower)`
   - Strictly prevent saving loans where `principal_amount > Max Eligible Loan Amount`.
   - Add Head Office (HO) rate update dashboard allowing Super Admin to broadcast daily rates across all 100+ branches.

3. Live Warnings & Visuals:
   - In the loan creation form, show a real-time LTV Gauge (Green < 75%, Yellow 75-90%, Red > 90% - BLOCKED).
```

#### ✅ Validation & Acceptance Checklist
- [x] **Daily Rate Broadcast Test:** Update today's 22K gold rate from HO panel. Open loan creation form in any branch and verify new rate is loaded.
- [x] **LTV Math Verification:** Add a 10.00g 22K gold ornament at ₹6,000/g (Market Value = ₹60,000). Verify maximum eligible loan cannot exceed ₹54,000 (90%).
- [x] **Hard Block Test:** Attempt to input principal of ₹55,000. Verify the system shows an error and refuses to save.
- [x] **Purity Calculation Test:** Verify calculations adjust for 22K (91.6%), 20K (83.3%), 18K (75.0%) purity ratios.

---

### Task 1.3: Income Tax Sec 269SS/269T Disbursal Rules & Bank Payout Integration

#### 📋 Execution Prompt
```text
Implement Income Tax Act Compliance (Section 269SS / 269T) for Loan Disbursals and Repayments:

1. Disbursal Limit Enforcer:
   - Add a rule in loan disbursement:
     * If `distribution_amount <= 19999`: Allow payment mode choices `['CASH', 'BANK_TRANSFER', 'UPI', 'CHEQUE']`.
     * If `distribution_amount >= 20000`: FORBID 'CASH'. Mandate payment mode `['BANK_TRANSFER', 'NEFT', 'IMPS', 'RTGS', 'UPI']`.
   - Mandate customer bank account details (`account_number`, `ifsc_code`, `bank_name`, `beneficiary_name`) for non-cash disbursals.

2. Customer Repayment Cash Limits:
   - Implement a daily cash repayment ceiling of ₹1,99,999 per customer across all branches to comply with Section 269ST.
   - If cumulative daily cash repayment >= ₹2,00,000, force digital mode (NetBanking / UPI / Cheque / DD).

3. Bank Payout Records:
   - Create a `DisbursementTransaction` model storing `utr_number`, `transaction_reference`, `payment_mode`, `bank_status`, and `disbursed_at`.
   - Add a printable Bank Transfer Advice / NEFT Mandate slip for branch records.
```

#### ✅ Validation & Acceptance Checklist
- [ ] **Cash Block Test:** Create a loan of ₹25,000 and select payment mode "CASH". Verify form validation blocks submission with Sec 269SS statutory message.
- [ ] **Bank Info Validation:** Enter ₹50,000 disbursal; verify IFSC code format and Account Number are required fields.
- [ ] **Cash Repayment Cap Test:** Submit multiple cash payments for a single customer on the same date totaling ₹2,05,000. Verify payment exceeding ₹1,99,999 is blocked from cash entry.

---

### Task 1.4: Branch Cash Drawer, Cash Till & Daily Cash Scroll (EOD Reconciliation)

#### 📋 Execution Prompt
```text
Build a comprehensive Cash Counter & Till Management System (Cash Scroll) for Branch Operations:

1. Models & Database:
   - Create `CashTill` in the `branches` app:
     * `branch` (ForeignKey)
     * `cashier` (ForeignKey to User)
     * `date` (DateField)
     * `opening_balance` (DecimalField, carry-forward from previous day's close)
     * `cash_inwards` (Total cash collected from repayments, fees, etc.)
     * `cash_outwards` (Total cash disbursed for loans <= 19,999, petty expenses)
     * `cash_to_bank` (Cash transferred to CIT/Bank during the day)
     * `closing_balance_system` (Computed balance)
     * `closing_balance_physical` (Actual counted currency notes)
     * `denomination_breakdown` (JSONField: count of 500, 200, 100, 50, 20, 10 notes)
     * `status` (Choices: 'open', 'reconciled', 'closed', 'mismatched')
     * `verified_by_manager` (ForeignKey to User)

2. Daily Workflow & UI:
   - Beginning of Day (BOD): Cashier logs in, enters opening cash count or accepts carryover.
   - Live Cash Scroll: Cashier dashboard showing real-time debit/credit stream of all cash transactions.
   - End of Day (EOD): Cashier inputs note denominations. System calculates physical vs system variance.
   - If variance == 0, allow Branch Manager sign-off and close the day. If variance != 0, require discrepancy explanation.
```

#### ✅ Validation & Acceptance Checklist
- [ ] **Opening Till Test:** Open a branch register with ₹50,000.
- [ ] **Live Scroll Test:** Process cash loan disbursal of ₹15,000 and cash repayment of ₹5,000. Verify till balance updates to ₹40,000 in real time.
- [ ] **Denomination Calculator Test:** In closing screen, enter 80 notes of ₹500 (= ₹40,000). Verify physical balance equals system balance.
- [ ] **Mismatch Warning Test:** Intentionally enter ₹39,000 in physical cash; verify manager approval and discrepancy note are required before closing.

---

### Task 1.5: Core Double-Entry General Ledger & Day Book Accounting

#### 📋 Execution Prompt
```text
Implement a Double-Entry Core Financial Accounting Engine with Chart of Accounts and Day Book:

1. Models & Database:
   - Create accounting models in a new or extended `accounting` app:
     * `AccountHead` (Code, Name, Category: Asset/Liability/Income/Expense/Equity, Parent Account, Branch).
     * `JournalEntry` (Entry No, Date, Branch, Reference Type: Loan Disbursal/Repayment/Interest/Fee/Expense, Narrative, Created By).
     * `JournalItem` (JournalEntry, AccountHead, Debit Amount, Credit Amount).

2. Automated Journal Posting:
   - Hook automatic postings on core events:
     * On Loan Disbursal: Debit `Loan Assets (Principal)`, Credit `Cash in Hand / Bank Account`, Credit `Processing Fee Income`.
     * On Loan Repayment: Debit `Cash / Bank`, Credit `Interest Income`, Credit `Loan Assets (Principal)`.
     * On Expense: Debit `Expense Head`, Credit `Cash in Hand`.

3. Financial Reports:
   - Generate automated Branch Day Book, Cash Book, Trial Balance, Profit & Loss Statement, and Balance Sheet with branch filtering and consolidation across all 100+ branches.
```

#### ✅ Validation & Acceptance Checklist
- [ ] **Double-Entry Equilibrium:** Disburse a loan and accept repayment; verify Total Debits == Total Credits across all generated journal items.
- [ ] **Day Book Accuracy:** Run Day Book for today's date; verify every transaction matches the cashier's physical log.
- [ ] **Multi-Branch Consolidation:** Run consolidated Trial Balance for all branches; verify balance sums accurately without cross-branch duplicate rows.

---

# 🏢 Phase 2: Hierarchy, Approvals & Lifecycle Operations

---

### Task 2.1: Multi-Tier Hierarchy (HO ➔ Zone ➔ Region ➔ Branch) & Tiered Maker-Checker Approvals

#### 📋 Execution Prompt
```text
Implement an Enterprise Multi-Tier Organizational Hierarchy and Tiered Maker-Checker Loan Approval Workflow:

1. Organization Hierarchy Models:
   - Update `accounts` and `branches` apps:
     * `Zone` (e.g. South Zone, North Zone) -> `RegionalOffice` (e.g. Chennai Region, Coimbatore Region) -> `BranchCluster` -> `Branch`.
     * Assign users to specific levels (Branch Staff, Branch Manager, Area Manager, Regional Manager, Zonal Head, Super Admin).

2. Tiered Approval Engine:
   - Configure tiered approval thresholds in `BranchSettings` / `Organization`:
     * Tier 1 (Loan <= ₹2,00,000): Maker (Appraiser) -> Checker (Branch Manager) approval.
     * Tier 2 (Loan ₹2,00,001 to ₹10,00,000): Requires Regional Manager (RO) digital sign-off.
     * Tier 3 (Loan > ₹10,00,000): Requires Head Office (HO) Credit Committee sign-off.

3. Approval Dashboard:
   - Build a real-time "Loan Approval Queue" for Branch Managers and Regional Managers.
   - Include comparison of appraised gross/net weight vs purity test results, KYC photo, and risk score.
   - Actions: 'Approve', 'Reject with Reason', 'Request Re-appraisal'.
```

#### ✅ Validation & Acceptance Checklist
- [ ] **Hierarchy Navigation Test:** Log in as Regional Manager; verify dashboard aggregates metrics exclusively for branches within that region.
- [ ] **Tier 1 Workflow:** Create a ₹1,00,000 loan as clerk. Verify loan state is `pending_approval` until Branch Manager approves it.
- [ ] **Tier 2 Escalation:** Create a ₹5,00,000 loan. Verify it automatically appears in Regional Manager's Approval Queue.
- [ ] **Disbursal Prevention:** Verify clerk cannot trigger disbursal until the required higher tier approves the loan.

---

### Task 2.2: Automated EOD Engine (Daily Interest Accrual & RBI IRAC NPA Tagging)

#### 📋 Execution Prompt
```text
Build an automated End-of-Day (EOD) batch processing engine for Daily Interest Accrual and RBI IRAC Asset Classification (NPA Tagging):

1. Daily Interest Accrual Engine:
   - Create an `InterestAccrualLog` model (`loan`, `date`, `principal_outstanding`, `daily_interest_accrued`, `cumulative_interest`).
   - Implement an automated job that runs daily at 23:59:
     * Compute exact daily interest per loan: `(Outstanding Principal × Annual Interest Rate) / (365 × 100)`.
     * Handle rebate schemes: Calculate base interest rate and conditional rebate interest.

2. RBI IRAC Asset Classification (NPA Tagging):
   - At each EOD run, calculate overdue days for every active loan:
     * `Standard Asset`: 0 overdue days.
     * `SMA-0 (Special Mention Account)`: Overdue by 1 to 30 days.
     * `SMA-1`: Overdue by 31 to 60 days.
     * `SMA-2`: Overdue by 61 to 90 days.
     * `NPA (Sub-standard)`: Overdue by 91+ days.
   - Update `asset_classification` on `Loan` and log historical status transitions.
   - Create a Management NPA Dashboard showing branch-wise SMA-0, SMA-1, SMA-2, and NPA portfolio at risk.
```

#### ✅ Validation & Acceptance Checklist
- [ ] **Batch Execution Test:** Run `python manage.py run_daily_eod_accrual --date 2026-08-28`. Verify accrual logs are generated for all active loans.
- [ ] **Math Verification:** For a ₹1,00,000 loan at 12% p.a., verify daily interest logged is exactly ₹32.88.
- [ ] **NPA Tagging Test:** Seed test loans with due dates 15 days ago, 45 days ago, 75 days ago, and 95 days ago. Run EOD and verify classifications (SMA-0, SMA-1, SMA-2, NPA).

---

### Task 2.3: Partial Payment & Partial Ornament Release Workflow

#### 📋 Execution Prompt
```text
Implement a Partial Ornament Release and Part-Payment Engine:

1. Workflow Logic:
   - When a customer with multiple pledged items wants to retrieve specific items (e.g. releasing 2 gold rings out of 5 pledged items):
     * Customer pays required principal reduction + accrued interest.
     * System checks remaining items' market value at current gold rate.
     * Recalculates: `New Outstanding Principal / Remaining Gold Market Value = New LTV %`.
     * If `New LTV > 75%`, calculate the exact additional principal amount required before release can be permitted.
     * ensure same ltv should follow for new ltv also.
     user just wants to release some ornaments and but system only need to find calculation and mention how much amount need to release that ornament to balance ltv.
2. Data & Documents:
   - Create a `PartialReleaseRecord` model tracking released items, photos, released date, customer acknowledgment signature, and receiving staff.
   - Update `LoanItem` status to 'released' with timestamp.
   - Generate a "Partial Ornament Release Voucher" PDF containing the list of released vs retained items and updated loan balance.
```

#### ✅ Validation & Acceptance Checklist
- [ ] **Multi-Item Setup:** Create loan with 3 items (Item A: ₹50,000, Item B: ₹50,000, Item C: ₹50,000; Loan: ₹1,00,000).
- [ ] **LTV Safety Check:** Attempt to release Item A & B while ₹90,000 loan is outstanding. Verify system blocks release (remaining LTV = 180% > 75%).
- [ ] **Successful Part-Release:** Repay required principal reduction so remaining LTV. Verify release succeeds.
- [ ] **Voucher Generation:** Verify the generated Partial Release Voucher accurately lists released vs retained items.

---

### Task 2.4: Instant Loan Top-Up & Same-Gold Renewal (Rollover) Engine

#### 📋 Execution Prompt
```text
Implement a Digital Loan Renewal (Rollover) and Top-Up Engine without physical gold release:

1. Instant Top-Up Engine:
   - If current gold rates have increased since the loan issue date:
     * Compute `Current Market Value = Pledged Net Weight × Today's Rate`.
     * `Max Eligible Amount = Current Market Value × 75%`.
     * `Top-Up Available = Max Eligible Amount - (Current Principal + Accrued Interest)`.
   - If Top-Up Available > 0, allow disbursing the differential amount directly to the customer's bank account with an addendum agreement.

2. Loan Renewal / Rollover Engine:
   - At maturity (e.g. 6/12 months), allow the customer to settle existing interest dues.
   - Automatically close the old loan as 'renewed_rollover' and generate a new loan ID linked to the existing `VaultPouch`.
   - Re-evaluate the gold at today's active rate and issue a fresh loan pledge card without opening the physical safe.
```

#### ✅ Validation & Acceptance Checklist
- [ ] **Top-Up Eligibility Test:** Seed loan created at ₹5,000/g gold rate. Update current rate to ₹6,500/g. Verify "Eligible Top-Up" button displays correct amount.
- [ ] **Renewal Balance Validation:** Attempt to renew a loan with unpaid interest. Verify system requires clearing interest first.
- [ ] **Vault Pouch Continuity:** Complete renewal and verify existing `VaultPouch` transfers to new loan ID without repacking.

---

### Task 2.5: Statutory Auction & 3-Stage Legal Notice Management Engine

#### 📋 Execution Prompt
```text
Build an RBI-Compliant Statutory Auction and Legal Notice Management Engine:

1. Notice Generation & Tracking:
   - Create an `AuctionNotice` model:
     * Stage 1: **Overdue Reminder Notice** (30 days post-due).
     * Stage 2: **Final Demand Notice** (60 days post-due, 14-day statutory cure period).
     * Stage 3: **Public Auction Intimation Notice** (with Registered Post tracking number and date of delivery).
   - Generate bilingual (English/Tamil) legal notice PDFs with customer address, item description, weight, and total dues.

2. Public Auction Catalog & Bidding:
   - Build an Auction Batch Creator: Group NPA loans approved for auction into an `AuctionEvent`.
   - Record auctioneer details, auction date, venue, newspaper publication date, and earnest money deposit (EMD).
   - Capture winning bidder, winning bid amount, and GST invoice on auction sale.

3. Surplus / Deficit Ledger:
   - If `Bid Amount > Total Dues (Principal + Interest + Auction Expenses)`: Calculate surplus and credit to `CustomerSurplusRefund` ledger.
   - If `Bid Amount < Total Dues`: Tag shortfall to recovery ledger.
```

#### ✅ Validation & Acceptance Checklist
- [ ] **Notice Sequence Test:** Move test loan to overdue. Verify Stage 1, Stage 2, and Stage 3 notices generate in sequence with correct legal templates.
- [ ] **Registered Post Logging:** Enter a postal consignment number and delivery date; verify notice status moves to "Served".
- [ ] **Surplus Math Test:** Auction a lot with ₹50,000 total dues for ₹65,000 winning bid. Verify system creates ₹15,000 Surplus Refund record payable to customer.

---

# 📱 Phase 3: Digital Channels & Scalable Infrastructure

---

### Task 3.1: Customer Portal & Online Repayment Gateway (UPI / NetBanking)

#### 📋 Execution Prompt
```text
Build a Customer Self-Service Portal and Online Payment Gateway Integration:

1. Customer Authentication & Dashboard:
   - Mobile OTP login for registered customers (`Customer` mobile number).
   - Secure customer dashboard showing:
     * Active Loans with live accrued interest and due dates.
     * Pledged ornament photos and weight details.
     * Repayment history and downloadable tax receipts / statements.

2. Payment Integration:
   - Integrate Razorpay / Cashfree / PayU payment gateway for online repayments:
     * Support full settlement, monthly interest payment, and part-principal payments.
     * Support UPI Intent, QR Code, NetBanking, and Debit Cards.
   - Webhook handler: Automatically post successful transactions to `Payment` model and update loan outstanding balance instantly in a database transaction.
   - Issue automated WhatsApp / SMS receipt upon successful payment.
```

#### ✅ Validation & Acceptance Checklist
- [ ] **OTP Login Test:** Test customer login with mobile number and verify OTP verification.
- [ ] **Payment Simulation:** In test mode, pay ₹1,200 interest via mock UPI. Verify payment is captured, interest marked paid, and receipt PDF downloadable.
- [ ] **Webhook Idempotency:** Send duplicate webhook callbacks; verify system processes payment exactly once without duplicate deductions.

---

### Task 3.2: Automated WhatsApp & SMS Notification Gateway

#### 📋 Execution Prompt
```text
Implement an automated multi-channel messaging service (WhatsApp Business API & SMS Gateway):

1. Service Integration:
   - Create a unified `NotificationService` in `integrations` app supporting WhatsApp (Interakt / Gupshup / Twilio) and SMS (Fast2SMS / Textlocal).
   - Create message templates:
     * Loan Sanction & Disbursal Alert (with pledge summary & PDF link).
     * Payment Received Acknowledgment (with receipt download link).
     * Upcoming Due Date Reminder (T-7 days and T-2 days).
     * Overdue & Demand Alerts.

2. Message Queue & Audit Log:
   - Create `NotificationLog` model storing `recipient`, `channel` (SMS/WhatsApp), `template_name`, `status` (sent/delivered/failed), and `response_payload`.
   - Run notifications asynchronously using Celery / background worker to prevent slowing down web requests.
```

#### ✅ Validation & Acceptance Checklist
- [ ] **Trigger on Disbursal:** Disburse a loan; verify notification record is queued and logged in `NotificationLog`.
- [ ] **Template Rendering:** Verify all template variables (`{{customer_name}}`, `{{loan_number}}`, `{{amount}}`) format with correct currency and values.
- [ ] **Async Non-blocking:** Disburse a loan during simulated API downtime; verify web request completes smoothly without hanging.

---

### Task 3.3: Digital KYC Verification (Aadhaar OTP / PAN NSDL Verification)

#### 📋 Execution Prompt
```text
Implement automated Digital KYC verification for Customer onboarding:

1. Verification APIs:
   - Integrate PAN Verification (NSDL / Protean / Karza / Setu API):
     * Input PAN number -> Fetch registered name -> Match against customer entered name (fuzzy matching >= 85%).
   - Integrate Aadhaar OKYC / DigiLocker verification:
     * Aadhaar number -> Generate OTP -> Validate OTP -> Fetch verified photo, name, DOB, and address.
     * Auto-populate customer profile from verified Aadhaar response.

2. KYC Compliance & Storage:
   - Store masked Aadhaar number (first 8 digits masked: `XXXX-XXXX-1234`) as per UIDAI regulatory compliance.
   - Add a `KYCVerificationLog` model recording verification timestamp, provider reference ID, and match confidence score.
```

#### ✅ Validation & Acceptance Checklist
- [ ] **PAN Test:** Input test PAN number; verify API returns holder status and name match score.
- [ ] **Masking Compliance:** Check database table `accounts_customer`; verify raw 12-digit Aadhaar is NEVER stored in plaintext and only masked format `XXXX-XXXX-1234` is stored.
- [ ] **Fuzzy Match Threshold:** Test with a name mismatch; verify system flags registration for manual compliance review.

---

### Task 3.4: Production Hardening for 100+ Branches (Celery, Redis & PostgreSQL)

#### 📋 Execution Prompt
```text
Upgrade backend infrastructure and database configuration for high-concurrency 100+ branch scale:

1. Asynchronous Task Queue:
   - Configure Celery with Redis broker in `pawnshop_management`.
   - Move heavy operations to background Celery tasks:
     * PDF bill generation and digital signing.
     * EOD interest accrual batch jobs.
     * SMS, WhatsApp, and Email notifications.
     * Nightly database backups and analytics aggregations.

2. PostgreSQL Optimization & Connection Pooling:
   - Optimize database settings for PostgreSQL:
     * Add database indexes on frequently queried combinations: `('branch', 'status', 'due_date')`, `('customer', 'status')`.
     * Set up PgBouncer connection pooling configuration.
     * Implement database query optimizations (`select_related`, `prefetch_related`) across all branch list and dashboard views.

3. Health Check & Security:
   - Add `/health/` monitoring endpoint checking DB latency, Redis connectivity, and disk storage.
   - Implement rate limiting on login and payment endpoints.
```

#### ✅ Validation & Acceptance Checklist
- [ ] **Celery Worker Test:** Trigger bulk report generation; verify Celery worker processes job in background and web UI responds instantly.
- [ ] **Query Count Validation:** Verify loan list view executes in under 5 SQL queries (no N+1 query problem).
- [ ] **Health Endpoint:** Send `GET /health/` request; verify it returns `HTTP 200 OK` with status of Database and Redis.
