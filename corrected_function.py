def build_loan_pdf_language_context(loan, use_tamil=False):
    """Build bilingual context dictionary for loan PDF generation"""
    
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
        'total_items': 'மொத்த பொருள்கள்' if use_tamil else 'Total Items',
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

    scheme_name = loan.scheme.name if loan.scheme else 'Standard Gold Loan'
    scheme_name_ta = translate_text_for_pdf(scheme_name, 'ta') if use_tamil and scheme_name else scheme_name
    scheme_interest = loan.scheme.interest_rate if loan.scheme else loan.interest_rate
    scheme_duration = loan.scheme.loan_duration if loan.scheme and loan.scheme.loan_duration else 0
    terms = [
        {
            'title': f'1. {"கடன் திட்ட விவரங்கள்" if use_tamil else "Loan Scheme Details"}:',
            'content': (
                f'இக்கடன் திட்டத்தில் "{scheme_name_ta}" என்ற திட்டத்தின் கீழ் வழங்கப்படுகிறது. வட்டி விகிதம்: {scheme_interest}% சதவீதம் மற்றும் கடன் கால அவधि {scheme_duration} நாட்களாக உள்ளது.'
                if use_tamil else
                f'This loan is issued under the "{scheme_name}" scheme. Interest rate: {scheme_interest}% per annum for {scheme_duration} days duration.'
            ),
        },
        {
            'title': f'2. {"கடனின் நோக்கம்" if use_tamil else "Purpose of Loan"}:',
            'content': (
                'கடன் பொற்கடமான உள்ளது. கடனாளி தாங்கள் அட்டவணை செய்ததை உறுதிசெய்கின்றார். பொற்பதார்த்தங்கள் சொந்தம் என்ற உறுதிசெய்தல் மற்றும் கடனுக்கு பதிலீடு செய்ய முடிந்தது என்பதை அறிவிக்கிறார்.'
                if use_tamil else
                'The loan is granted solely on the security of gold ornaments/items deposited as collateral with the lender. The borrower affirms that the pledged article is their own property and is not stolen or encumbered.'
            ),
        },
        {
            'title': f'3. {"தங்கம் மீட்டெடுப்பு நேரம்" if use_tamil else "Gold Recovery Timing"}:',
            'content': (
                'தங்கம் மீட்டெடுப்பு முதன்மைத் தொகை மற்றும் வட்டி முழுமையாக செலுத்திய பிறகு மற்றும் அனைத்து பொறுப்புகளை நிறைவேற்றியபின் நடைபெறும்.'
                if use_tamil else
                'Gold items shall be returned only after complete payment of principal amount and accrued interest along with any other charges/fees.'
            ),
        },
        {
            'title': f'4. {"KYC இணக்கத்தன்மை" if use_tamil else "KYC Compliance"}:',
            'content': (
                'கடনாளியின் அடையாள விவரங்கள் சரிபார்க்கப்பட்டுள்ளது என்பதை உறுதிசெய்கிறது. அனைத்து விபரங்களும் உண்மையாகவும் நிখிலமாகவும் வழங்கப்பட்டுள்ளது.'
                if use_tamil else
                'Know Your Customer (KYC) compliance has been verified. All information provided is true and complete.'
            ),
        },
        {
            'title': f'5. {"நியாய நடைமுறைகள் குறியீடு" if use_tamil else "Fair Practices Code"}:',
            'content': (
                'நியாய நடைமுறைகள் குறியீடு நிறுவனம் எல்லா கடன்களுக்கும் செய்ய வேண்டிய கடமைகளை வரையறுக்கிறது. கடனாளிக்கு சரியான மற்றும் நேர்மையான சேவை வழங்குவது உறுதிசெய்யப்படும்.'
                if use_tamil else
                'The Fair Practices Code ensures that the lender follows ethical and fair practices in all transactions.'
            ),
        },
        {
            'title': f'6. {"முறையீடு மற்றும் திருப்பிச்செலுத்தல்" if use_tamil else "Repayment and Recovery"}:',
            'content': (
                'முறையீடு முதன்மைத் தொகை மற்றும் வட்டியுடன் செய்யப்பட வேண்டும். எந்தவித தாமதம் இருந்தால் கூடுதல் கட்டணங்கள் விதிக்கப்படும்.'
                if use_tamil else
                'Repayment of the loan should be made on or before the due date along with accrued interest. Late payments may attract additional charges.'
            ),
        },
        {
            'title': f'7. {"ரசீது தேவை" if use_tamil else "Receipt Requirement"}:',
            'content': (
                'ஒவ்வொரு பணம் செலுத்தல்க்கும் ரசீது வழங்கப்பட வேண்டும். ரசீதை பாதுகாப்பாக வைக்க வேண்டும்.'
                if use_tamil else
                'Receipt shall be provided for every payment made towards the loan. The receipt should be safely retained.'
            ),
        },
        {
            'title': f'8. {"அறிக்கை" if use_tamil else "Declaration"}:',
            'content': (
                'கடனாளி மேலోட்டமாக கூறிய விபரங்கள் உண்மையாக உள்ளது என்பதை ஒப்புக்கொள்ளுகின்றார். எந்தவித தொகை சம்பந்தப்பட்ட விவாதங்களுக்கு நம்மை சம்பந்தப்பட்ட அதிகாரிகளிடம் முறையிட்டு தீர்வாக தேடுகிறார்.'
                if use_tamil else
                'The borrower hereby declares that all information provided above is true and correct. Any disputes regarding the loan amount shall be settled as per the RBI guidelines.'
            ),
        },
    ]

    return {
        'labels': labels,
        'terms': terms,
        'loan': loan,
        'use_tamil': use_tamil,
    }
