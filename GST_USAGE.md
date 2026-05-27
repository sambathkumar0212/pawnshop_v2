# GST Service User Guide for Pawnshop Management System

## Overview

The GST (Goods and Services Tax) module in this pawnshop management system provides comprehensive tax management features including:

- GST rate management with HSN codes
- Transaction tracking with automatic GST calculations
- Company GST details management
- GST report generation (GSTR-1, GSTR-3B, B2B, B2C, HSN)
- Support for both interstate (IGST) and intrastate (CGST+SGST) transactions

## Accessing the GST Module

The GST module can be accessed through the main navigation menu or directly via these URLs:

- GST Dashboard: `/gst/dashboard/`
- GST Rates: `/gst/rates/`
- GST Transactions: `/gst/transactions/`
- GST Reports: `/gst/reports/`
- Company GST Details: `/gst/company/0/`

## Step-by-Step Setup Guide

### 1. Setting Up Company GST Details

Before using GST features, you must set up your company's GST registration details:

1. Navigate to the GST Dashboard (`/gst/dashboard/`)
2. Click on "Configure Company GST Details" or go directly to `/gst/company/0/`
3. Fill in your company's:
   - Legal Name (as registered with GST)
   - GSTIN (15-character GST Identification Number)
   - State Code (2-digit code as per GST rules)
   - Registered Business Address
   - Email and Phone (for GST correspondence)
4. Save the details

### 2. Setting Up GST Rates

Configure the GST rates applicable to your business:

1. Go to GST Rates section (`/gst/rates/`)
2. Click "Add New GST Rate"
3. For each rate, provide:
   - Name (e.g., "Standard", "Luxury Items", "Gold")
   - HSN Code (Harmonized System of Nomenclature)
   - CGST Rate (Central GST percentage)
   - SGST Rate (State GST percentage)
   - IGST Rate (Integrated GST percentage for interstate)
   - Description (optional)
4. The system will automatically ensure IGST = CGST + SGST
5. Toggle rates active/inactive as needed

### 3. Recording GST Transactions

To record transactions with GST:

1. Go to GST Transactions (`/gst/transactions/`)
2. Click "Add New Transaction"
3. Fill in:
   - Transaction Date
   - Transaction Type (Sale, Purchase, Loan, Extension, Return, Other)
   - Invoice Number
   - Select appropriate GST Rate
   - Party Name (customer/vendor)
   - Party GSTIN (if registered)
   - Mark if the party is a registered dealer
   - Place of Supply (state)
   - Mark if Interstate transaction
   - Taxable Value (amount before tax)
4. The system will automatically calculate:
   - CGST Amount (for intrastate)
   - SGST Amount (for intrastate)
   - IGST Amount (for interstate)
   - Total Tax
   - Total Amount (including tax)

### 4. Generating GST Reports

For GST compliance and filing, you can generate various reports:

1. Go to GST Reports (`/gst/reports/`)
2. Select:
   - Start Date and End Date
   - Report Type:
     - GSTR-1 (Outward supplies)
     - GSTR-3B (Summary return)
     - B2B Invoices (Business to Business)
     - B2C Invoices (Business to Consumer)
     - HSN Summary (Item-wise)
   - Export Format (CSV, Excel, JSON)
3. Click "Generate Report"
4. Download the report for filing or reference

## Permissions Setup

To access the GST module, users need appropriate permissions:

1. Admin users can manage permissions at `/admin/`
2. The following permissions are required:
   - `gst.view_gstrate`, `gst.add_gstrate`, `gst.change_gstrate` - For GST rate management
   - `gst.view_gsttransaction`, `gst.add_gsttransaction`, `gst.change_gsttransaction` - For transaction management
   - `gst.view_companygstdetails`, `gst.change_companygstdetails` - For company details
   - `gst.delete_gsttransaction` - For deleting transactions (if needed)

## Integrating GST with Sales and Loans

### Sales Integration

When creating a sale transaction, the system can automatically:
1. Calculate the taxable value
2. Apply the appropriate GST rate
3. Create a GST transaction record linked to the sale

Example process:
```
1. Create a sale record
2. Select the applicable GST rate
3. Mark if interstate or intrastate
4. The system calculates GST and adds to invoice
5. GST transaction is linked to the sale for reporting
```

### Loans Integration

For loan transactions involving GST (on service charges, processing fees):
1. Determine if GST applies to the loan
2. Calculate the taxable component
3. Create a GST transaction record linked to the loan

## GST Dashboard Features

The GST Dashboard (`/gst/dashboard/`) provides:

1. Summary of GST collected for the current month
2. Financial year GST statistics
3. Recent GST transactions
4. Quick links to common GST functions
5. Company GST registration details

## Troubleshooting

If you encounter issues with the GST module:

1. **Permission Issues**: Ensure your user has the required permissions
2. **Missing Navigation**: If GST is not in the menu, check with administrator
3. **Calculation Errors**: Verify GST rates are set up correctly
4. **Report Generation Issues**: Check date ranges and data consistency
5. **Integration Problems**: Ensure proper linkage between transactions and GST records

## GST Compliance Tips

1. **Regular Filing**: Use the GST reports to prepare monthly/quarterly GST returns
2. **Proper HSN Codes**: Ensure correct HSN codes for your products/services
3. **Invoice Requirements**: GST invoices must include specific details:
   - GSTIN of supplier
   - GSTIN of recipient (for B2B)
   - HSN codes
   - Taxable value and tax amounts separated by CGST, SGST, IGST
4. **Record Keeping**: Maintain all invoices and transaction records for 5+ years
5. **Regular Reconciliation**: Compare GST records with financial books
6. **Stay Updated**: Keep GST rates current with government regulations

## Technical Information

The GST module consists of these main models:
- `CompanyGSTDetails`: Stores company's GST registration information
- `GSTRate`: Manages different GST rates with HSN codes
- `GSTTransaction`: Records all GST transactions for reporting
- `GSTReportLog`: Tracks generated GST reports

For developers extending this module, the Generic Foreign Key in `GSTTransaction` allows linking GST transactions to any model (Sales, Purchases, Loans) in the system.