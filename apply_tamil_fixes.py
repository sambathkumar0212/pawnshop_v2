#!/usr/bin/env python3
"""
Fix corrupted Tamil text in transactions/views.py
This script reads the file, finds the corrupted labels dictionary,
and replaces it with correct Unicode Tamil text.
"""

import os
import re

# Define corrected labels
corrected_labels = {
    'document_title': 'பொன் கடன் ஒப்பந்தம்',
    'borrower_name': 'கடனாளியின் பெயர்',
    'loan_number': 'கடன் எண்',
    'email': 'மின்னஞ்சல்',
    'phone': 'தொலைபேசி எண்',
    'address': 'முகவரி',
    'id_details': 'அடையாள விவரங்கள்',
    'not_provided': 'வழங்கப்படவில்லை',
    'borrower_photo': 'கடனாளியின் படம்',
    'principal_amount': 'முதன்மை தொகை',
    'processing_fee': 'நடப்பு சேவை கட்டணம்',
    'distribution_amount': 'விநியோக தொகை',
    'monthly_interest': 'மாத வட்டி',
    'issue_date': 'வழங்கிய தேதி',
    'due_date': 'வட்டி செலுத்த வேண்டிய தேதி',
    'gold_items_details': 'தங்க ஆபரணங்கள் விவரங்கள்',
    'item_description': 'பொருள் விவரம்',
    'gold_karat': 'தங்கம் சுத்தம்',
    'gross_weight': 'மொத்த எடை (கி)',
    'net_weight': 'நிகர எடை (கி)',
    'total_items': 'மொத்த பொருள்கள்',
    'pledged_gold_item_photos': 'அடமான பொருள் புகைப்படங்கள்',
    'item': 'பொருள்',
    'no_photos': 'இந்த கடனுக்கு புகைப்படங்கள் இல்லை.',
    'borrower_signature': 'கடனாளியின் கையொப்பம்',
    'authorized_signatory': 'அங்கீகரிக்கப்பட்ட கையொப்பம்',
    'branch_manager': 'கிளை மேலாளர்',
    'phone_label': 'தொலைபேசி',
    'email_label': 'மின்னஞ்சல்',
    'document_generated_on': 'ஆவணம் உருவாக்கப்பட்ட தேதி',
    'terms_and_conditions': 'விதிமுறைகள் மற்றும் நிபந்தனைகள்',
}

# English labels for fallback
english_labels = {
    'document_title': 'Gold Loan Agreement',
    'borrower_name': 'Borrower Name',
    'loan_number': 'Loan Number',
    'email': 'Email',
    'phone': 'Phone Number',
    'address': 'Address',
    'id_details': 'ID Details',
    'not_provided': 'Not provided',
    'borrower_photo': 'Borrower Photo',
    'principal_amount': 'Principal Amount',
    'processing_fee': 'Processing Fee',
    'distribution_amount': 'Distribution Amount',
    'monthly_interest': 'Monthly Interest',
    'issue_date': 'Issue Date',
    'due_date': 'Due Date',
    'gold_items_details': 'Gold Items Details',
    'item_description': 'Item Description',
    'gold_karat': 'Gold Karat',
    'gross_weight': 'Gross Weight (g)',
    'net_weight': 'Net Weight (g)',
    'total_items': 'Total Items',
    'pledged_gold_item_photos': 'Pledged Gold Item Photos',
    'item': 'Item',
    'no_photos': 'No photos available for this loan.',
    'borrower_signature': 'Borrower Signature',
    'authorized_signatory': 'Authorized Signatory',
    'branch_manager': 'Branch Manager',
    'phone_label': 'Phone',
    'email_label': 'Email',
    'document_generated_on': 'Document generated on',
    'terms_and_conditions': 'TERMS AND CONDITIONS',
}

def generate_corrected_labels_dict():
    """Generate the corrected labels dictionary Python code"""
    lines = ["    labels = {"]
    
    for key, tamil_val in corrected_labels.items():
        english_val = english_labels[key]
        line = f"        '{key}': '{tamil_val}' if use_tamil else '{english_val}',"
        lines.append(line)
    
    lines.append("    }")
    return "\n".join(lines)

def main():
    filepath = 'transactions/views.py'
    
    print(f"Reading {filepath}...")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"✓ File read successfully ({len(content)} characters)")
        
        # Show the corrected dictionary
        print("\n" + "="*60)
        print("CORRECTED LABELS DICTIONARY:")
        print("="*60)
        corrected_dict = generate_corrected_labels_dict()
        print(corrected_dict)
        print("="*60)
        
        # Count how many corrupted entries exist
        corrupted_count = content.count('ÃƒÂ ')
        print(f"\n✓ Found {corrupted_count} corrupted Tamil text segments")
        print(f"✓ Generated {len(corrected_labels)} corrected labels")
        
        # Show what needs to be done
        print("\n" + "="*60)
        print("NEXT STEPS:")
        print("="*60)
        print("1. The corrected dictionary above needs to replace lines 154-189")
        print("2. The terms list (lines 191-250+) needs similar corrections")
        print("3. Use multi_replace_string_in_file with proper context")
        print("="*60)
        
    except FileNotFoundError:
        print(f"ERROR: File {filepath} not found")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    
    return True

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
