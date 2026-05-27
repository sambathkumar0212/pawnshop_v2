"""
Custom PDF generator for loan documents with Tamil script support.
Uses ReportLab directly for better control over font rendering.
"""

import os
from io import BytesIO
from datetime import datetime
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# Register Tamil font
try:
    tamil_font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'NotoSansTamil-Regular.ttf')
    pdfmetrics.registerFont(TTFont('NamilTamil', tamil_font_path))
    TAMIL_FONT_AVAILABLE = True
except Exception as e:
    print(f"Warning: Tamil font not available: {e}")
    TAMIL_FONT_AVAILABLE = False


def generate_loan_agreement_pdf(loan, request=None):
    """
    Generate a loan agreement PDF with bilingual (English + Tamil) content.
    
    Args:
        loan: Loan model instance
        request: Django request object (optional)
        
    Returns:
        BytesIO: PDF file as bytes
    """
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2d3748'),
        spaceAfter=12,
        alignment=0,  # Left align
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#2d3748'),
        spaceAfter=6,
        spaceBefore=6,
    )
    
    tamil_style = ParagraphStyle(
        'TamilText',
        parent=styles['Normal'],
        fontName='NamilTamil' if TAMIL_FONT_AVAILABLE else 'Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#666666'),
        spaceAfter=3,
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=9,
        spaceAfter=6,
        alignment=4,  # Justified
    )
    
    # Build document content
    elements = []
    
    # Header
    elements.append(Paragraph("GOLD LOAN AGREEMENT", title_style))
    if TAMIL_FONT_AVAILABLE:
        elements.append(Paragraph("பொன் கடன் ஒப்பந்தம்", tamil_style))
    else:
        elements.append(Paragraph("(Pohn Kataan Opbandham)", tamil_style))
    elements.append(Spacer(1, 12))
    
    # Loan Details
    loan_details = [
        ['Loan Number:', loan.loan_number],
        ['Customer Name:', loan.customer.full_name],
        ['Loan Date:', str(loan.created_at.date())],
        ['Principal Amount:', f'₹{loan.principal_amount:,.2f}'],
        ['Interest Rate:', f'{loan.scheme.interest_rate}% per annum'],
        ['Loan Duration:', f'{loan.scheme.loan_duration} days'],
    ]
    
    if TAMIL_FONT_AVAILABLE:
        loan_details_tamil = [
            ['கடன் எண்:', loan.loan_number],
            ['வாடிக்கையாளர் பெயர்:', loan.customer.full_name],
            ['கடன் தேதி:', str(loan.created_at.date())],
            ['முதன்மை தொகை:', f'₹{loan.principal_amount:,.2f}'],
            ['வட்டி விகிதம்:', f'{loan.scheme.interest_rate}% ஆண்டுக்கு'],
            ['கடன் கால அளவு:', f'{loan.scheme.loan_duration} நாட்கள்'],
        ]
    else:
        loan_details_tamil = [
            ['Kataan Enru:', loan.loan_number],
            ['Vaadikayalalar Peyar:', loan.customer.full_name],
            ['Kataan Thedum:', str(loan.created_at.date())],
            ['Muthana Thogai:', f'₹{loan.principal_amount:,.2f}'],
            ['Vadi Vikadam:', f'{loan.scheme.interest_rate}% Aandukku'],
            ['Kataan Kaal Alavai:', f'{loan.scheme.loan_duration} Nateghal'],
        ]
    
    # Create two-column table for English and Tamil
    loan_table_data = [['English', 'Tamil']]
    
    for eng_row, tamil_row in zip(loan_details, loan_details_tamil):
        eng_text = f"<b>{eng_row[0]}</b> {eng_row[1]}"
        tamil_text = f"<b>{tamil_row[0]}</b> {tamil_row[1]}"
        
        loan_table_data.append([
            Paragraph(eng_text, normal_style),
            Paragraph(tamil_text, tamil_style if TAMIL_FONT_AVAILABLE else normal_style)
        ])
    
    loan_table = Table(loan_table_data, colWidths=[3.5*inch, 3.5*inch])
    loan_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    elements.append(loan_table)
    elements.append(Spacer(1, 12))
    
    # Terms and Conditions Section
    elements.append(Paragraph("TERMS AND CONDITIONS", heading_style))
    if TAMIL_FONT_AVAILABLE:
        elements.append(Paragraph("விதிமுறைகள் மற்றும் நிபந்தனைகள்", tamil_style))
    else:
        elements.append(Paragraph("(Vidhimurikal Matrum Niphandhanaigal)", tamil_style))
    
    elements.append(Spacer(1, 6))
    
    # Terms data
    terms = [
        {
            'en_title': '1. Loan Scheme Details:',
            'ta_title': '1. கடன் திட்ட விவரங்கள்:',
            'en_content': f'This loan is issued under the "{loan.scheme.name}" scheme. Interest rate: {loan.scheme.interest_rate}% per annum for {loan.scheme.loan_duration} days duration.',
            'ta_content': f'இந்த கடன் "{loan.scheme.name}" திட்டத்தின் கீழ் வழங்கப்படுகிறது. வட்டி விகிதம்: ஆண்டுக்கு {loan.scheme.interest_rate}% {loan.scheme.loan_duration} நாட்கள் கால அளவுக்கு।',
        },
        {
            'en_title': '2. Purpose of Loan:',
            'ta_title': '2. கடனின் நோக்கம்:',
            'en_content': 'The loan is granted solely on the security of gold ornaments/items deposited as collateral with the lender. The Borrower affirms that the pledged article is their own property and is not stolen or encumbered.',
            'ta_content': 'கடன் கடனாளியிடம் வைப்புத் தொகையாக வைப்பிடப்பட்ட தங்கப் பொருட்களின் பாதுகாப்பின் அடிப்படையில் மட்டுமே வழங்கப்படுகிறது। கடன் வாங்குபவர் பத்திரத் தொகை தங்களுடைய சொத்து என்றும் அது திருடப்பட்ட அல்ல என்றும் உறுதி அளிக்கிறார்।',
        },
        {
            'en_title': '3. Gold Recovery Timing:',
            'ta_title': '3. தங்கம் மீட்டெடுப்பு நேரம்:',
            'en_content': 'For gold recovery, payment must be made before 11:00 AM and gold collection will be available after 4:00 PM on the same day. This allows sufficient time for verification and processing of the loan closure.',
            'ta_content': 'தங்கம் மீட்டெடுப்புக்கு, பணம் 11:00 AM க்கு முன்பு செலுத்தப்பட வேண்டும் மற்றும் தங்கம் சேகரிப்பு அதே நாளின் 4:00 PM க்குப் பிறகு கிடைக்கும்।',
        },
        {
            'en_title': '4. KYC Compliance:',
            'ta_title': '4. KYC இணக்கத்தன்மை:',
            'en_content': 'The borrower has provided necessary KYC documents as required under RBI guidelines, including proof of identity and address.',
            'ta_content': 'கடன் வாங்குபவர் RBI வழிகாட்டுதல்களின் கீழ் தேவைப்படும் தேவையான KYC ஆவணங்களை வழங்கியுள்ளார்।',
        },
        {
            'en_title': '5. Fair Practices Code:',
            'ta_title': '5. நியாய நடைமுறைகள் குறியீடு:',
            'en_content': 'Loss or damage to the pledged article due to natural calamities, theft, or circumstances beyond the Lender\'s control will not be the responsibility of the Lender, as prescribed by RBI.',
            'ta_content': 'RBI ஆல் குறிப்பிட்டுள்ளபடி, இயற்கைப் பேரிடர், திருட்டு, அல்லது கடனாளியின் நியந்திரணத்திற்கு அப்பாற்பட்ட சூழ்நிலைகளால் ஏற்படும் பத்திரத் தொகையின் இழப்பு அல்லது சேதம் கடனாளியின் பொறுப்பு அல்ல।',
        },
        {
            'en_title': '6. Grievance Redressal:',
            'ta_title': '6. முறைப்பாடு தீர்வு:',
            'en_content': 'The loan is repayable after 3 months or before the due date. If not repaid, the Lender may sell the pledged article as per the provisions of the Indian Contract Act, 1872 and the Pawn Brokers Act, 1943.',
            'ta_content': 'கடன் 3 மாதங்களுக்குப் பிறகு அல்லது நிறுவப்பட்ட தேதிக்கு முன்பு திருப்பிக்கொடுக்கப்படும்। திருப்பிக்கொடுக்கப்படாவிட்டால், கடனாளி இந்திய ஒப்பந்த சட்டம் 1872 மற்றும் பணய சட்டம் 1943 ஆகியவற்றின் விதிகளின்படி பத்திரத் தொகையை விற்கலாம்।',
        },
        {
            'en_title': '7. Receipt Requirement:',
            'ta_title': '7. ரசீது தேவை:',
            'en_content': 'No release of pledged gold items will be processed without verification of this original loan document and ID proof submitted.',
            'ta_content': 'பத்திரத் தொகுப்பப்பட்ட தங்கப் பொருட்களை இந்த அசல் கடன் ஆவணம் மற்றும் சமர்ப்பிக்கப்பட்ட ஐடி சான்று சரிபார்ப்பு இல்லாமல் விடுவிக்க முடியாது.',
        },
        {
            'en_title': '8. Declaration:',
            'ta_title': '8. அறிக்கை:',
            'en_content': 'The borrower declares all information provided is true. Borrower has read and understood all the terms & conditions mentioned herein.',
            'ta_content': 'கடன் வாங்குபவர் வழங்கப்பட்ட அனைத்து தகவலும் உண்மை என்று அறிவிக்கிறார். கடன் வாங்குபவர் இங்குக் குறிப்பிடப்பட்ட அனைத்து விதிமுறைகள் மற்றும் நிபந்தனைகளைப் படித்து புரிந்துகொண்டுள்ளார்.',
        },
    ]
    
    # Add each term
    for term in terms:
        # English title and content
        elements.append(Paragraph(term['en_title'], heading_style))
        elements.append(Paragraph(term['en_content'], normal_style))
        
        # Tamil title and content
        if TAMIL_FONT_AVAILABLE:
            elements.append(Paragraph(term['ta_title'], heading_style))
            elements.append(Paragraph(term['ta_content'], tamil_style))
        else:
            # Fallback to transliteration if font not available
            ta_title_transliterated = term['ta_title'].replace('கடன்', 'Kataan').replace('திட்ட', 'Thittan')
            elements.append(Paragraph(f"<i>{ta_title_transliterated}</i>", heading_style))
        
        elements.append(Spacer(1, 6))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
