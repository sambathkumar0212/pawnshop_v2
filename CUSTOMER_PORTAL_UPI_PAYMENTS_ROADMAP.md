# Customer Portal & Dynamic UPI Payment Integration Roadmap

## Project Overview
This feature adds an integrated Self-Service Customer Portal, Dynamic UPI QR Payment generation (with 12-digit UTR verification), Automated Customer User Credential Generation with WhatsApp deep-linking, and strict RBAC governance (Super-Admin reset exclusivity, Manager read-only).

---

## 1. Feature Specifications

### 1.1 Free UPI QR Payment Integration
- **Mechanism:** Dynamically generate a standard Indian UPI payment string link (`upi://pay?pa=...`) inside Django views.
- **Rendering:** Encode URI into a scannable QR code matrix image using `qrcode` and `BytesIO`, rendered inline as a Base64 data URI image in HTML.
- **Verification:** Text sub-form underneath the QR code where customers manually enter their 12-digit UPI reference / transaction UTR number to serve as confirmation with a pending status.
- **Staff Approval:** Branch Managers/Cashiers can verify the UTR against bank statements and approve/reject with one click.

### 1.2 Automated Account & Credential Creation
- **Triggers:** Automatically generate a unique customer username (e.g., `fm_` + last 10 digits of mobile number) and randomized secure 8-character temporary PIN directly upon customer creation.
- **Delivery:** Automatically compile these credentials into a structured bilingual (English + Tamil) WhatsApp message template with deep-links (`https://wa.me/91<phone>?text=...`).
- **Action Button:** A dedicated green "Send via WhatsApp" button on the Customer Detail page and creation success screen.

### 1.3 Strict Permission Rules & Governance
- **Branch Manager Constraints:** Restricted to view-only access for existing portal credentials once initially generated. Managers cannot edit passwords, usernames, or modify security parameters directly.
- **Admin-Only Controls:** Explicit administrative rights reserved solely for the System Super-Admin profile, who holds the exclusive power to force-reset and regenerate fresh login credentials for an existing customer profile.

### 1.4 Self-Service Customer Portal Experience
- **Dedicated Route:** `/portal/` (Login, Dashboard, Payment).
- **Main Dashboard Layout:**
  1. Customer profile context & summary header.
  2. Active Loans table (outstanding balances, next due dates, quick pay triggers).
  3. Closed Loans history table.
  4. Chronological Repayment History Logs table with processing & verification statuses (Pending / Verified).

---

## 2. Implementation Modules Breakdown

### Module 1: Automated Customer User Creation & WhatsApp Deep-Link
1. Link `Customer` model to `CustomUser` via `OneToOneField(CustomUser, null=True, blank=True, on_delete=models.SET_NULL, related_name='customer_profile')`.
2. Add helper fields: `temp_password_plain` (temporary field cleared or securely referenced), `portal_active` (boolean).
3. On customer creation in `accounts/views.py` or post-save signal:
   - Extract last 10 digits of phone, form `fm_<phone>`.
   - Generate 8-character random PIN (`secrets`).
   - Create or link `CustomUser` with `role_type='customer'`.
4. Create `accounts/services_portal.py` for compiling the bilingual WhatsApp message & generating `https://wa.me/` links.
5. Add the green "Send Credentials via WhatsApp" banner to `accounts/templates/accounts/customer_detail.html`.

### Module 2: Permission Governance & Super-Admin Force-Reset
1. Restrict Branch Manager and Staff views from editing customer authentication details.
2. Create `AdminResetCustomerCredentialsView` accessible only by `is_superuser` or IT Admins.
3. On admin reset, generate a new 8-character PIN, update user password, update audit log timestamp, and generate a new WhatsApp share URL.

### Module 3: Dynamic UPI QR Code & 12-Digit UTR Form
1. Create `transactions/services_upi.py` using `qrcode` library to generate Base64 PNG data URI.
2. In `transactions/models.py`, ensure `Payment` supports:
   - `utr_number = models.CharField(max_length=12, blank=True, null=True, db_index=True)`
   - `verification_status = models.CharField(max_length=20, choices=[('pending', 'Pending Verification'), ('verified', 'Verified'), ('rejected', 'Rejected')], default='verified')`
3. Create UPI QR payment view & modal for customer portal.
4. Add staff verification dashboard table in transactions app for confirming incoming pending UTR payments.

### Module 4: Self-Service Customer Portal Dashboard
1. Create `portal/` app or routing in `accounts/views_portal.py` and `accounts/urls_portal.py`.
2. Build custom login/logout views ensuring customer role redirection.
3. Build `portal_dashboard.html`:
   - Profile card & total outstanding balance.
   - Active Loans table with interest due and "Pay via UPI" trigger modal.
   - Closed Loans table with settlement history.
   - Repayment history table with UTR status badges.
4. Test mobile responsiveness and security tokens (CSRF & auth guards).
