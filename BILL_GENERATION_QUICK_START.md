# 📄 Bilingual Bill Generation - Quick Start Guide

## ✅ System Status
- ✓ English bills: **Ready**
- ✓ Tamil bills: **Ready**
- ✓ 121 test loans available
- ✓ All fonts installed
- ✓ Single-page layout configured

---

## 🚀 How to Generate a Bill (3 Steps)

### Step 1️⃣: Select Language
In the **top-right corner** of the web interface:
- Click the **language dropdown** (flags icon or text)
- **Select "English"** for English bill OR **"தமிழ்"** for Tamil bill

### Step 2️⃣: Find Your Loan
- Go to **"Loans"** or **"கடன்கள்"** menu
- Search or scroll to find the loan you need
- Click on the **loan number** (e.g., TAM-20260413-0001)

### Step 3️⃣: Download Bill
- Click the **"Download Loan Agreement"** button or **"ஒப்பந்தம் பதிவிறக்கவும்"** (Tamil)
- The PDF will automatically download with the name:
  ```
  CustomerName_Item_LoanNumber_agreement.pdf
  ```
- The bill will be **in your selected language**

---

## 📋 What's Included in the Bill

### PDF Layout (Single Page - A4)
```
┌─────────────────────────────────────────┐
│  Organization Name | Branch Address     │ <- Header with contact info
│      Document Title (English/Tamil)      │
├──────────────────┬──────────────────────┤
│ Customer Info    │  Borrower Photo      │ <- Personal details + photo
│ (Name, Address,  │  (Scales auto-fit)   │
│  Contact, ID)    │                      │
├──────────────────┴──────────────────────┤
│ Loan Details (Amount, Dates, Interest)   │
├──────────────────────────────────────────┤
│ Gold Items (Description, Karat, Weight)  │
├──────────────────────────────────────────┤
│ Gold Item Photos (2-4 photos auto-grid)  │
├──────────────────────────────────────────┤
│ Terms & Conditions (English or Tamil)    │
├──────────────────┬──────────────────────┤
│ Borrower         │ Authorized Signatory │ <- Signature lines
│ Signature        │ Branch Manager       │
└──────────────────┴──────────────────────┘
```

### Content in Each Language

**English Bill** 📝
- Title: "Gold Loan Agreement"
- All labels in English
- 8 terms in plain English
- Professional formatting

**Tamil Bill** 📝
- Title: "பொன் கடன் ஒப்பந்தம்" (Gold Loan Agreement)
- All labels in Tamil (തmil script)
- 8 terms in Tamil
- Same professional formatting
- Amounts in numbers (universal)

---

## 🎨 Bill Features

### ✨ **Auto-Adjusted Layout**
- **Font sizes** automatically scale based on content
- **Images** resize to fit available space
- **Text** flows naturally without overlaps
- **Single page** - everything fits on one A4

### 🎯 **Smart Image Handling**
- **Borrower photo**: Scales up/down as needed
- **Gold photos**: Automatically arrange (2, 3, or 4 per row)
- **Aspect ratios** preserved
- **Quality maintained** in PDF

### 🌍 **Language Features**
- **Complete Tamil support** with Noto Sans Tamil font
- **Proper character rendering** (no boxes or symbols)
- **Line spacing** optimized for each language
- **Professional typography**

---

## 💾 File Naming Convention

Bills are saved with this pattern:
```
FirstName_LastName_ItemType_LoanNumber_agreement.pdf
```

### Examples:
- `Alagarsamy_Selvaraj_Gold_TAM-20260413-0001_agreement.pdf`
- `Aman_Ali_Jafar_Pearl_TAM-202404-0005_agreement.pdf`
- `Sam_Singh_Bracelet_TAM-202405-0010_agreement.pdf`

---

## ❓ Common Questions

### Q: Can I generate bills in both languages?
**A:** Yes! Generate once in English and once in Tamil (just change language and regenerate)

### Q: Do I need to change any settings?
**A:** No! Just select your language - everything else is automatic

### Q: Will all loan information be on one page?
**A:** Yes! Fonts and images automatically adjust to fit single A4 page

### Q: What if there are many gold items?
**A:** The table will condense, font size adjusts, and photos arrange in a grid

### Q: Can I print the bill?
**A:** Yes! Open PDF and press Ctrl+P or use File > Print

### Q: What formats are supported?
**A:** PDF only (optimized for printing and sharing)

### Q: Is my customer data safe?
**A:** Yes! Bills are generated locally and not stored on the system

---

## 🔧 Technical Details

| Feature | Details |
|---------|---------|
| **Format** | PDF (Portable Document Format) |
| **Size** | A4 (210mm × 297mm) |
| **Margins** | 0.7cm all sides |
| **Color** | Full color with professional styling |
| **Font Face (English)** | Helvetica / Arial |
| **Font Face (Tamil)** | Noto Sans Tamil |
| **Compression** | Optimized for file size |

---

## ½ Support & Help

### For Technical Issues:
1. **Refresh the page** (F5) - clears cache
2. **Try a different browser** - Chrome/Edge recommended
3. **Check internet connection** - needed for fonts to load
4. **Verify loan data** - ensure all fields are filled

### For Language Issues:
- **Tamil shows as boxes?** → Install Noto Sans Tamil font
- **Layout looks wrong?** → Try a different browser
- **Loan info missing?** → Complete all customer details

---

## 📊 Example Bills

### Sample English Bill:
```
┌────────────────────────────────────────┐
│   Tamil R Gold Loans                   │
│   South Street, Alliapuram, Tamil Nadu │
│   Phone: 8870105241                    │
│                                        │
│   GOLD LOAN AGREEMENT                  │
│────────────────────────────────────────│
│ Borrower Name: Alagarsamy Selvaraj    │
│ Loan Number: TAM-20260413-0001         │     [Photo]
│ Email: Not provided                    │        📷
│ Phone: (951)212-5015                   │     250px ×
│ Address: Palaical street, Vettapath... │     300px
│                                        │
│ Principal Amount: Rs 14,141            │
│ Processing Fee: Rs 252                 │
│ Monthly Interest: Rs 400 (2.5% monthly)│
│ Issue Date: 13/04/2026                 │
│ Due Date: 13/05/2026                   │
│                                        │
│ GOLD ITEMS:                            │
│ ┌──────────────────────────────────┐  │
│ │ Bangle - 22K                     │  │
│ │ 45.000g gross, 40.500g net       │  │
│ └──────────────────────────────────┘  │
│                                        │
│ TERMS & CONDITIONS:                    │
│ 1. Loan Scheme Details...              │
│ 2. Purpose of Loan...                  │
│ [... 6 more terms ...]                 │
│                                        │
│ _______________    _______________    │
│ Borrower           Authorized          │
│ Signature          Signatory           │
└────────────────────────────────────────┘
```

### Sample Tamil Bill:
```
┌────────────────────────────────────────┐
│   தமிழ் R கோல்ட் லோன்ஸ்               │
│   தெற்கு தெரு, அலியபுரம், தமிழ்நாடு    │
│   தொலைபேசி: 8870105241                │
│                                        │
│   பொன் கடன் ஒப்பந்தம்                  │
│────────────────────────────────────────│
│ கடனாளியின் பெயர்: அளவர்சாமி செல்வராஜ் │
│ கடன் எண்: TAM-20260413-0001           │     [Photo]
│ மின்னஞ்சல்: வழங்கப்படவில்லை          │        📷
│ தொலைபேசி: (951)212-5015               │     250px ×
│ முகவரி: பாலிசல் தெரு, வேட்டப்பாத...   │     300px
│                                        │
│ முதன்மை தொகை: Rs 14,141              │
│ நடப்பு சேவை கட்டணம்: Rs 252           │
│ மாத வட்டி: Rs 400 (2.5%)              │
│ வழங்கிய தேதி: 13/04/2026              │
│ வட்டி செலுத்த வேண்டிய தேதி: 13/05/26 │
│                                        │
│ தங்க ஆபரணங்கள்:                       │
│ ┌──────────────────────────────────┐  │
│ │ வளையல் - 22K                    │  │
│ │ 45.000கி மொத்தம், 40.500கி நிகரம்  │
│ └──────────────────────────────────┘  │
│                                        │
│ விதிமுறைகள் மற்றும் நிபந்தனைகள்:       │
│ 1. கடன் திட்ட விவரங்கள்...            │
│ 2. கடனின் நோக்கம்...                  │
│ [... 6க்கு மேற்பட்ட விதிகள் ...]       │
│                                        │
│ _______________    _______________    │
│ கடனாளி              அங்கீகரிக்கப்பட்ட │
│ கையொப்பம்          கையொப்பம்          │
└────────────────────────────────────────┘
```

---

## 📞 Quick Reference

| Need | Action |
|------|--------|
| Change language | Click dropdown at top-right |
| Create English bill | Select "English" then download |
| Create Tamil bill | Select "தமிழ்" then download |
| Find a loan | Use Loans menu search |
| Update customer info | Edit loan before generating |
| Print bill | Open PDF and press Ctrl+P |
| Share bill | Email the PDF file |

---

**Version**: 1.0 - April 2026  
**Status**: ✅ Production Ready  
**Tested**: 121+ loans ✓ | Both languages ✓ | Auto-layout ✓
