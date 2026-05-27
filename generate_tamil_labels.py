#!/usr/bin/env python
"""Generate corrected build_loan_pdf_language_context function with proper Tamil Unicode"""

tamil_labels = """
    labels = {
        'document_title': 'பொன் கடன் ஒப்பந்தம்' if use_tamil else 'Gold Loan Agreement',
        'borrower_name': 'கடனாளியின் பெயர்' if use_tamil else 'Borrower Name',
        'loan_number': 'கடன் எண்' if use_tamil else 'Loan Number',
        'email': 'மின்னஞ்சல்' if use_tamil else 'Email',
        'phone': 'தொலைபேசி எண்' if use_tamil else 'Phone Number',
        'address': 'முகவரி' if use_tamil else 'Address',
        'id_details': 'அடையாள விவரங்கள்' if use_tamil else 'ID Details',
        'not_provided': 'வழங்கப்படவில்லை' if use_tamil else 'Not provided',
        'borrower_photo': 'கடனாளியின் படம்' if use_tamil else 'Borrower Photo',
        'principal_amount': 'முதன்மை தொகை' if use_tamil else 'Principal Amount',
        'processing_fee': 'நடப்பு சேவை கட்டணம்' if use_tamil else 'Processing Fee',
        'distribution_amount': 'விநியோக தொகை' if use_tamil else 'Distribution Amount',
        'monthly_interest': 'மாத வட்டி' if use_tamil else 'Monthly Interest',
        'issue_date': 'வழங்கிய தேதி' if use_tamil else 'Issue Date',
        'due_date': 'வட்டி செலுத்த வேண்டிய தேதி' if use_tamil else 'Due Date',
        'gold_items_details': 'தங்க ஆபரணங்கள் விவரங்கள்' if use_tamil else 'Gold Items Details',
        'item_description': 'பொருள் விவரம்' if use_tamil else 'Item Description',
        'gold_karat': 'தங்கம் சுத்தம்' if use_tamil else 'Gold Karat',
        'gross_weight': 'மொத்த எடை (கி)' if use_tamil else 'Gross Weight (g)',
        'net_weight': 'நிகர எடை (கி)' if use_tamil else 'Net Weight (g)',
        'total_items': 'மொத்த பொருட்கள்' if use_tamil else 'Total Items',
        'pledged_gold_item_photos': 'அடமான பொருள் புகைப்படங்கள்' if use_tamil else 'Pledged Gold Item Photos',
        'item': 'பொருள்' if use_tamil else 'Item',
        'no_photos': 'இந்த கடனுக்கு புகைப்படங்கள் இல்லை.' if use_tamil else 'No photos available for this loan.',
        'borrower_signature': 'கடனாளியின் கையொப்பம்' if use_tamil else 'Borrower Signature',
        'authorized_signatory': 'அங்கீகரிக்கப்பட்ட கையொப்பம்' if use_tamil else 'Authorized Signatory',
        'branch_manager': 'கிளை மேலாளர்' if use_tamil else 'Branch Manager',
        'phone_label': 'தொலைபேசி' if use_tamil else 'Phone',
        'email_label': 'மின்னஞ்சல்' if use_tamil else 'Email',
        'document_generated_on': 'ஆவணம் உருவாக்கப்பட்ட தேதி' if use_tamil else 'Document generated on',
        'terms_and_conditions': 'விதிமுறைகள் மற்றும் நிபந்தனைகள்' if use_tamil else 'TERMS AND CONDITIONS',
    }
"""

print("Corrected Tamil labels dictionary:")
print(tamil_labels)
