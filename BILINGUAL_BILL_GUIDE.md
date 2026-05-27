# 🌐 Bilingual Loan Bill Generation Guide

## Overview
The pawnshop management system now supports generating loan bills in **both English and Tamil** with automatic layout adjustment on a single page.

---

## How to Generate Bills

### Method 1: Web Interface (Recommended)

**Step 1: Select Language**
- Look at the top-right corner of the page
- Click on the **language selector dropdown**
- Choose:
  - **English** - for English bills (English text display)
  - **தமிழ்** - for Tamil bills (Tamil text display)

**Step 2: Navigate to Loans**
- Go to **Loans** section
- Find or search for the loan you want to bill

**Step 3: Generate PDF**
- Click on the **loan number** to open loan details
- Click **"Download Loan Agreement"** button
- The bill will automatically generate in your selected language

**Step 4: Save Bill**
- The PDF will download automatically with filename:
  - English: `CustomerName_Item_LoanNumber_agreement.pdf`
  - Tamil: `CustomerName_Item_LoanNumber_agreement.pdf` (same name, content in Tamil)

---

## Bill Features

### ✅ Single Page Layout
- Fits all information on **one A4 page**
- Professional compact design
- No page breaks

### ✅ Automatic Text Adjustment
- **Font sizes scale** based on content length
- **Line spacing optimizes** for readability
- **Tamil Unicode** properly rendered with Noto Sans Tamil font

### ✅ Auto-Adjusted Images
- **Borrower photo** scales to fit available space
- **Gold item photos** automatically resize (2-4 items per row)
- **Maintains aspect ratio** for all images

### ✅ Bilingual Support
- **English Bill**: All text in English
- **Tamil Bill**: All text in Tamil (தமிழ்)
  - Labels in Tamil
  - Term & conditions in Tamil
  - Amounts and numbers in English (standard)

---

## Bill Contents

### Header Section
- **Organization Name** (தமிழ் R கோல்ட் லோன்ஸ் / Tamil R Gold Loans)
- **Branch Address** with phone and email
- **Document Title** (பொன் கடன் ஒப்பந்தம் / Gold Loan Agreement)

### Customer Information (Left Column)
- Borrower Name (தமிழ் / English)
- Loan Number
- Email address
- Phone number
- Address
- ID Details

### Borrower Photo (Right Column)
- Large customer photo
- Auto-scaled to fit available space

### Loan Details (Two Columns)
- **Principal Amount**: Rs
- **Processing Fee**: Rs
- **Distribution Amount**: Rs (green highlight)
- **Monthly Interest**: Rs (blue highlight)
- **Issue Date**: DD/MM/YYYY (red highlight)
- **Due Date**: DD/MM/YYYY (red highlight)

### Gold Items Table
- Item Description (with Tamil support)
- Gold Karat (K)
- Gross Weight (grams)
- Net Weight (grams)

### Pledged Gold Photos
- 2-4 photos per row (auto-adjusted)
- Item photos with proper sizing

### Terms and Conditions
- 8 numbered terms in selected language:
  1. Loan Scheme Details
  2. Purpose of Loan
  3. Gold Recovery Timing
  4. KYC Compliance
  5. Fair Practices Code
  6. Repayment and Recovery
  7. Receipt Requirement
  8. Declaration

### Signatures Section (Bottom)
- Borrower Signature line
- Authorized Signatory name
- Branch Manager line

---

## Language-Specific Features

### English Bill (Tamil_R_Gold_Loans.pdf)
```
Title: Gold Loan Agreement
Borrower Name: Aman Ali Jafar
Amount: Rs 20000
Terms: In English with proper formatting
```

### Tamil Bill (Tamil_R_Gold_Loans_Sam.pdf)
```
Title: பொன் கடன் ஒப்பந்தம் (Gold Loan Agreement)
Borrower Name: கடனாளியின் பெயர் (Borrower Name in Tamil)
Amount: Rs 20000
Terms: தமிழ் உரையில் (In Tamil with proper formatting)
```

---

## Font & Display Settings

### Fonts Used
- **English**: Helvetica, Arial (system fonts)
- **Tamil**: 
  - Primary: Noto Sans Tamil (Google Fonts)
  - Fallback 1: Nirmala UI (Windows)
  - Fallback 2: Latha (Windows)

### Responsive Sizing
- **Heading**: 20px (organization name)
- **Sub-heading**: 16px (document title)
- **Body Text**: 12px
- **Labels**: 11px
- **Tamil Text**: 12px (optimized for Tamil script)
- **Tables**: 11px
- **Smaller text**: 8-10px

### Automatic Adjustments
```
Content Range          Font Size
Standard 1 item        12px (normal)
2-3 items              11px (compact)
4+ items               10px (condensed)
Large text             Auto-scale down
```

---

## Troubleshooting

### Issue: Bill appears to have no text (blank)
**Solution**: 
- Ensure language is selected in top-right dropdown
- Refresh the page (F5)
- Try the other rendering method (browser PDF or xhtml2pdf)

### Issue: Tamil text shows as boxes (□□□)
**Solution**:
- Install Noto Sans Tamil font on your system
- Update your browser (recommended: Chrome, Edge)
- Use a different browser with better font support

### Issue: Layout is broken or text overlaps
**Solution**:
- Clear browser cache (Ctrl+Shift+Delete)
- Try a different browser
- Check that loan has valid customer data

### Issue: PDF generation takes too long
**Solution**:
- Close other applications (to free memory)
- Refresh the page and try again
- Use the simpler xhtml2pdf fallback

---

## Advanced Settings (Admin Only)

### PDF Rendering Methods
1. **Browser (Default)**: Uses Chromium headless for best Tamil support
2. **xhtml2pdf**: Fallback method, faster but less features

### Font Configuration
Edit `transactions/templates/transactions/loan_document_pdf.html`:
```css
@font-face {
    font-family: 'NotoSansTamil';
    src: url('file:///path/to/NotoSansTamil-Regular.ttf') format('truetype');
}
```

### Page Size Options
Current: **A4 (210mm × 297mm)**
Margins: **0.7cm** all sides

To change in template:
```css
@page {size: A4; margin: 0.7cm;}
```

---

## File Storage

### Where PDF is Generated
- **Temporary**: System temp folder (auto-deleted)
- **Downloaded to**: Your Downloads folder
- **Naming**: `CustomerName_Item_LoanNumber_agreement.pdf`

### How to Organize
```
Downloads/
├── Aman_Ali_Jafar_Gold_TAM-202404-0005_agreement.pdf  (English)
├── Aman_Ali_Jafar_Gold_TAM-202404-0005_agreement.pdf  (Tamil - same name, different content)
└── Sam_Singh_Pearl_TAM-202405-0010_agreement.pdf
```

---

## Sample Output

### English Bill
- Header: "Tamil R Gold Loans" | Address, Phone, Email
- Title: "Gold Loan Agreement"
- All labels and terms in English
- Professional blue and green color scheme

### Tamil Bill  
- Header: "தமிழ் R கோல்ட் லோன்ஸ்" | முகவரி, தொலைபேசி, மின்னஞ்சல்
- Title: "பொன் கடன் ஒப்பந்தம்"
- All labels and terms in Tamil
- Same professional color scheme

---

## Tips for Best Results

1. **Use Latest Browser**: Chrome, Edge, or Firefox (updated)
2. **Ensure Good Internet**: Required for Google Fonts loading
3. **Check Customer Data**: Complete all customer fields
4. **Add Photos**: Include borrower and item photos for completeness
5. **Verify Loan Details**: Ensure all financial data is correct before printing
6. **Test Print**: Do a test print before distributing to customers

---

## Technical Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Backend | Django | 5.x |
| Language Support | Django i18n | Built-in |
| HTML to PDF | Chromium headless | Latest |
| Fallback | xhtml2pdf | Latest |
| Tamil Font | Noto Sans Tamil | v1.0+ |
| Template Engine | Django Templates | Built-in |

---

## Contact Support

For issues with bill generation:
1. Check the troubleshooting section above
2. Verify your Django i18n configuration
3. Ensure locale files are compiled: `python manage.py compilemessages`
4. Check browser console (F12) for errors
5. Contact system administrator

---

**Last Updated**: April 13, 2026  
**Tested With**: 121 loans in database ✓  
**Status**: ✅ Both language bills generating successfully
