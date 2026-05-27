#!/usr/bin/env python
"""
Fix Tamil text encoding in loan PDF generation.
Converts HTML entity-encoded Tamil text to proper Unicode.
"""

tamil_fixes = {
    # Document Labels
    'Tamil document title': 'பொன் கடன் ஒப்பந்தம்',
    'Tamil borrower name': 'கடனாளியின் பெயர்',
    'Tamil loan number': 'கடன் எண்',
    'Tamil email': 'மின்னஞ்சல்',
    'Tamil phone': 'தொலைபேசி எண்',
    'Tamil address': 'முகவரி',
    'Tamil id details': 'அடையாள விவரங்கள்',
    'Tamil not provided': 'வழங்கப்படவில்லை',
    'Tamil borrower photo': 'கடனாளியின் படம்',
    
    # Financial Terms
    'Tamil principal amount': 'முதன்மை தொகை',
    'Tamil processing fee': 'நடப்பு சேவை கட்டணம்',
    'Tamil distribution amount': 'விநியோக தொகை',
    'Tamil monthly interest': 'மாத வட்டி',
    'Tamil issue date': 'வழங்கிய தேதி',
    'Tamil due date': 'வட்டி செலுத்த வேண்டிய தேதி',
    
    # Gold Related
    'Tamil gold items details': 'தங்க ஆபரணங்கள் விவரங்கள்',
    'Tamil item description': 'பொருள் விவரம்',
    'Tamil gold karat': 'தங்கம் சுத்தம்',
    'Tamil gross weight': 'மொத்த எடை (கி)',
    'Tamil net weight': 'நிகர எடை (கி)',
    'Tamil total items': 'மொத்த பொருட்கள்',
    'Tamil pledged gold item photos': 'அடமான பொருள் புகைப்படங்கள்',
    'Tamil item': 'பொருள்',
    'Tamil no photos': 'இந்த கடனுக்கு புகைப்படங்கள் இல்லை.',
    
    # Signatures
    'Tamil borrower signature': 'கடனாளியின் கையொப்பம்',
    'Tamil authorized signatory': 'அங்கீகரிக்கப்பட்ட கையொப்பம்',
    'Tamil branch manager': 'கிளை மேலாளர்',
    'Tamil phone label': 'தொலைபேசி',
    'Tamil email label': 'மின்னஞ்சல்',
    
    # Document Info
    'Tamil document generated on': 'ஆவணம் உருவாக்கப்பட்ட தேதி',
    'Tamil terms and conditions': 'விதிமுறைகள் மற்றும் நிபந்தனைகள்',
    
    # Terms Titles (from terms_list)
    'Tamil loan scheme details': 'கடன் திட்ட விவரங்கள்',
    'Tamil purpose of loan': 'கடனின் நோக்கம்',
    'Tamil gold recovery timing': 'தங்கம் மீட்டெடுப்பு நேரம்',
    'Tamil kyc compliance': 'KYC இணக்கத்தன்மை',
    'Tamil fair practices code': 'நியாய நடைமுறைகள் குறியீடு',
    'Tamil repayment and recovery': 'முறையீடு மற்றும் திருப்பிச்செலுத்தல்',
    'Tamil receipt requirement': 'ரசீது தேவை',
    'Tamil declaration': 'அறிக்கை',
}

if __name__ == '__main__':
    print("Tamil Text Fixes Summary:")
    print("=" * 60)
    for key, value in tamil_fixes.items():
        print(f"{key}: {value}")
