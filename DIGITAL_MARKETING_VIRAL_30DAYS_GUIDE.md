# 🚀 30-Day Viral Digital Marketing & Hyper-Local Ad Automation Engine

> **Pawnshop & Gold Loan Growth Architecture**  
> *Target: 10x Inquiries, Hyper-Local 10km Precision, and Viral Organic Referrals within 30 Days.*

---

## 📑 Table of Contents
1. [Overview & Growth Flywheel](#1-overview--growth-flywheel)
2. [Zero-Error 10km Hyper-Local Ad Targeting (Meta & Google)](#2-zero-error-10km-hyper-local-ad-targeting-meta--google)
3. [The 6 Core Automated Marketing Pillars](#3-the-6-core-automated-marketing-pillars)
4. [Architecture & Decoupled Standalone App Design](#4-architecture--decoupled-standalone-app-design)
5. [30-Day Step-by-Step Viral Launch Calendar](#5-30-day-step-by-step-viral-launch-calendar)
6. [Step 1 Implementation Plan](#6-step-1-implementation-plan)

---

## 1. Overview & Growth Flywheel

Gold loan and pawnshop customers have unique psychological and geographic behaviors:
* **Urgency & Proximity**: Over 90% of borrowers choose a branch within **3 to 10 km** of their home or workplace.
* **Privacy Preference**: Over 80% prefer WhatsApp chat or instant calculators over long form submissions.
* **Trust & Transparency**: Live gold rates, clear valuation formulas, and instant Google Map directions convert 4x better than generic promotions.

```
                         ┌────────────────────────────────────────────────────────┐
                         │  HYPER-LOCAL ADS (META & GOOGLE ADS: STRICT 10KM)      │
                         └──────────────────────────┬─────────────────────────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           STANDALONE MARKETING PORTAL / LANDING PAGE                            │
│  • Live 22K/24K Gold Price Ticker                                                               │
│  • Interactive Gold Loan Eligibility Calculator (Weight in Grams -> Instant Estimated Cash)     │
│  • Geo-Fenced Branch Detector ("Your nearest branch is 1.8km away in T. Nagar")                 │
│  • 1-Click WhatsApp Lead Connect / Tap-to-Call                                                  │
└───────────────────────────────────────────┬─────────────────────────────────────────────────────┘
                                            │ Lead Captured (Phone / WhatsApp)
                                            ▼
                         ┌────────────────────────────────────────────────────────┐
                         │  INSTANT AUTOMATION:                                   │
                         │  1. WhatsApp Bot sends instant Gold Loan Estimation    │
                         │  2. Branch Manager receives instant SMS/Push alert     │
                         │  3. Pixel & Server-side CAPI registers "Lead"          │
                         └──────────────────────────┬─────────────────────────────┘
                                                    │ Customer visits branch & disburses loan
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                VIRAL REFERRAL & SOCIAL MULTIPLIER                               │
│  • Automated WhatsApp "Give ₹500, Get ₹500" unique invite link generated for customer           │
│  • Google 5-Star Review Booster (+ ₹100 Cashback / Interest discount on verification)           │
│  • Server-to-Server Meta CAPI & Google Offline Conversion optimizes algorithm for high-value    │
│    borrowers                                                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Zero-Error 10km Hyper-Local Ad Targeting (Meta & Google)

### The #1 Budget Waste Trap
Most ad campaigns waste 40% to 50% of budget by showing ads to commuters, highway travelers, or people residing outside the branch's service radius.

```
                              ┌───────────────────────────────────┐
                              │      BRANCH LOCATION (GPS PIN)    │
                              │      Lat: 13.0418, Long: 80.2341  │
                              └─────────────────┬─────────────────┘
                                                │
                                                ▼
         ┌─────────────────────────────────────────────────────────────────────────────┐
         │                          10 KM EXACT SERVICE RADIUS                         │
         │  ✅ Target: "People LIVING in this location"                                │
         │  ✅ Pincodes: Explicitly include branch service postal codes                │
         │  ❌ Exclude: "People living in or recently in this location" (Default trap) │
         │  ❌ Exclude: Outside districts / adjacent cities > 15 km                    │
         └─────────────────────────────────────────────────────────────────────────────┘
```

### 1. Meta Ads Manager (Facebook & Instagram) Strict Configuration
1. **Audience Location Setting**:
   * Change from default `People living in or recently in this location` ➡️ **`People living in this location`**.
2. **Pin Drop + Radius**:
   * Drop the pin directly on the branch's coordinates.
   * Set radius to **5 km – 10 km**.
3. **Pincode Backup**:
   * In the same Ad Set, add all 6-digit postal pincodes covering that branch's catchment zone.
4. **Demographics & Language**:
   * Age: `23 – 58`
   * Language: **Tamil** + **English** (or local regional language).
5. **Creative Format**:
   * Video / Carousel showing: (1) Live Gold Rate per gram, (2) 3-minute cash disbursement, (3) Safe locker guarantee, (4) Branch Google Maps landmark.

### 2. Google Ads (Search, Maps & PMax) Strict Configuration
1. **Location Target Option**:
   * Open `Location options` (advanced).
   * Change from `Presence or interest` ➡️ **`Presence: People in or regularly in your targeted locations`**.
2. **Radius Targeting**:
   * Select **Radius** -> Enter branch address -> Set `10 km`.
3. **Negative Locations**:
   * Add surrounding non-service towns/districts under **Excluded Locations**.
4. **Google Business Profile Asset**:
   * Link the branch's verified Google Business Profile to display the **Location Extension** on Google Maps searches.
5. **High-Intent Keywords (Exact / Phrase Match)**:
   * `"gold loan near me"`, `"pawn shop near me"`, `"instant cash for gold [area name]"`, `"lowest gold loan interest rate"`.

---

## 3. The 6 Core Automated Marketing Pillars

### Pillar 1: Interactive Gold Valuation Lead Magnet (Landing Page & Widget)
* Real-time calculation: `Estimated Loan = Grams × Purity Rate (22K) × LTV% (75%)`.
* User enters grams and selects karat -> instantly sees loan eligibility range.
* One-click "Get Official Valuation on WhatsApp" locks in the lead with phone number.

### Pillar 2: 1-Click Viral WhatsApp Referral Engine
* Every customer receives a unique referral code: `https://offers.yourshop.com/ref/HARI500`.
* Automated message: *"Need instant cash? Get highest gold rate + ₹500 cash reward with my invite link."*
* **Fraud-Proof Rule**: Reward is only unlocked when the referred friend's loan status moves to **`Disbursed`** with verified KYC in the backend.

### Pillar 3: Meta Conversions API (CAPI) & Google Server-Side Tracking
* Bypasses iOS 14+ ad blockers and browser restrictions.
* When cashier disburses cash in the ERP, the backend dispatches a secure hashed event (`Purchase`, value = loan amount) to Meta/Google.
* The ad algorithm automatically learns and shows ads to people most likely to take loans.

### Pillar 4: Automated WhatsApp Broadcast Triggers
* **Gold Surge Alert**: Automated notification when market gold price increases > ₹100/g.
* **Win-Back Campaign**: Pre-approved renewal offer sent 45 days after loan redemption.
* **Google 5-Star Review Booster**: Automated review request sent after smooth loan settlement offering ₹100 fee waiver on their next transaction.

### Pillar 5: Hyper-Local Branch Locator & Dynamic Geo-Detection
* Landing page detects visitor coordinates and displays:
  * Closest branch name, address, and distance.
  * Direct Google Maps "Directions" navigation button.
  * Direct WhatsApp chat button to the branch manager.

### Pillar 6: Built-in AI Ad & Social Content Generator
* Generates high-converting Meta ad copy, Google Search headlines, and festive WhatsApp promo templates in English and Tamil in one click.

---

## 4. Architecture & Decoupled Standalone App Design

To ensure high performance, zero interference with the main ERP system, and independent scalability:

```
┌──────────────────────────────────────────────┐        ┌──────────────────────────────────────────────┐
│          MAIN ERP (pawnshop_v2)              │        │      MARKETING APP (pawnshop_marketing)      │
│  • Loans, Inventory, Cash Till, KYC, GST     │        │  • Public Landing Page & Gold Calculator     │
│  • Internal Staff & Cashier Workflow         │        │  • Lead Capture & WhatsApp Integration       │
│  • Port: 8000 (Internal ERP Domain)          │        │  • Geo-Fenced 10km Branch Locator            │
│                                              │        │  • Meta CAPI & Google Ads Tracking           │
│                                              │        │  • Port: 8001 / https://offers.yourshop.com  │
└──────────────────────┬───────────────────────┘        └──────────────────────┬───────────────────────┘
                       │                                                       │
                       └───────────────────────────┬───────────────────────────┘
                                                   │
                                                   ▼
                                ┌────────────────────────────────────┐
                                │      SHARED DATABASE / REST API    │
                                │  • Branch Geolocation & Contacts   │
                                │  • Live Gold Market Rates          │
                                │  • Leads & Referral Logs           │
                                └────────────────────────────────────┘
```

---

## 5. 30-Day Step-by-Step Viral Launch Calendar

| Week | Focus | Action Items | Target Metric |
| :--- | :--- | :--- | :--- |
| **Week 1 (Days 1–7)** | **Foundation & Setup** | • Deploy Standalone Marketing Portal on Port 8001.<br>• Configure Meta Pixel, Meta CAPI, and Google Ads Tag.<br>• Populate branch GPS, 10km service pincodes, and WhatsApp numbers.<br>• Embed Interactive Gold Loan Calculator. | 100% Tracking Accuracy, Zero Lead Leaks |
| **Week 2 (Days 8–14)** | **Hyper-Local Ad Launch** | • Launch Meta Video/Image Ads (Strict 10km radius + Pincodes).<br>• Launch Google Search Ads on "gold loan near me".<br>• Activate Click-to-WhatsApp direct ads. | ₹15–₹30 per qualified lead |
| **Week 3 (Days 15–21)** | **Viral Referral & Review Boost** | • Launch "Give ₹500, Get ₹500" WhatsApp referral engine.<br>• Trigger automated 5-Star Google Review requests.<br>• Enable Gold Surge automated WhatsApp broadcasts. | 30%+ organic referral increase, 50+ 5-star Google Reviews |
| **Week 4 (Days 22–30)** | **Scaling & CAPI Optimization** | • Sync offline loan disbursements to Meta CAPI.<br>• Double down on highest ROAS pincodes.<br>• Launch Festival / Flash interest rate promotion. | 3x to 5x increase in monthly loan disbursements |

---

## 6. Step 1 Implementation Plan

1. **In `pawnshop_v2` (Main ERP)**:
   * Update [branches/models.py](file:///d:/Hari_files/FirstMoneyGold/software_apps/pawnshop_v2/branches/models.py) to support GPS `latitude`, `longitude`, `service_radius_km`, `service_pincodes`, `whatsapp_business_number`, `google_maps_review_url`, and `google_place_id`.
   * Add marketing tracking keys to [pawnshop_management/settings.py](file:///d:/Hari_files/FirstMoneyGold/software_apps/pawnshop_v2/pawnshop_management/settings.py) and [.env](file:///d:/Hari_files/FirstMoneyGold/software_apps/pawnshop_v2/.env).

2. **In `marketing_portal` (New Standalone App)**:
   * Initialize a high-performance standalone project with:
     * Interactive Gold Valuation Calculator (Live 18K/22K/24K rates)
     * 10km Geo-Fenced Nearest Branch Locator with Google Maps Directions
     * WhatsApp 1-Click Lead Capturing
     * Meta Pixel & Google Ads tracking tags
     * Referral Link Generator (`/ref/CODE`)
