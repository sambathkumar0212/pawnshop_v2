# FirstMoney Gold — Mobile Application (Flutter)

A cross-platform native mobile application for **FirstMoney Gold Pawnshop Management**, built with Flutter & Dart, connecting seamlessly to the Django REST Backend.

---

## 📱 Features

1. **Owner & Manager Live Dashboard**:
   - Real-time KPIs (Today's collections, loans disbursed, net cash in drawer, gold in locker custody).
   - Portfolio overview with overdue alerts.
2. **Fast Pledge Creation (New Loan Wizard)**:
   - Customer onboarding / search.
   - Pledged gold item weights (Gross & Net weight, Karats).
   - Direct camera photo capture for gold ornaments and KYC.
   - Statutory Section 269SS compliance checks.
3. **Repayment & Interest Collection**:
   - Search by loan number, customer name, or phone.
   - Cash / UPI / Bank transfer recording with real-time balance calculations.
   - Section 269ST cash ceiling alert (< ₹2,00,000/day).
4. **JWT Authentication & Token Auto-Refresh**:
   - Secure token storage with `flutter_secure_storage`.
   - Multi-tenant and role-based permissions (Branch Manager, Appraiser, Cashier, Owner).

---

## 🛠️ How to Run Locally

### 1. Prerequisites
- Install **Flutter SDK** (Version >= 3.0): https://docs.flutter.dev/get-started/install
- Install **Android Studio** (for Android build) or **Xcode** (for iOS build)
- Ensure Django backend server is running: `python manage.py runserver 0.0.0.0:8000`

### 2. Configure Backend Server IP
Open [lib/config/api_constants.dart](file:///d:/Hari_files/FirstMoneyGold/software_apps/pawnshop_v2/mobile_app/lib/config/api_constants.dart):
- **Android Emulator**: `http://10.0.2.2:8000` (already default)
- **Physical Phone over Wi-Fi**: `http://<YOUR_PC_IP>:8000` (e.g. `http://192.168.1.10:8000`)
- **Production Server**: `https://your-domain.com`

### 3. Run the App
```bash
# Navigate to mobile app directory
cd mobile_app

# Install dependencies
flutter pub get

# Run on connected device or emulator
flutter run
```

### 4. Build Release APK (Android)
```bash
flutter build apk --release
```
The compiled APK will be located at:
`mobile_app/build/app/outputs/flutter-apk/app-release.apk`
