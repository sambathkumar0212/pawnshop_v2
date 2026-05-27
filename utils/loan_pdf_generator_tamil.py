"""
Tamil-optimized PDF generator for loan documents.
Uses ReportLab with proper Tamil font support and rendering.
UTF-8 encoding support for Tamil characters.
"""

import os
import sys
from io import BytesIO
from datetime import datetime
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Ensure UTF-8 encoding
if sys.version_info[0] < 3:
    reload(sys)
    sys.setdefaultencoding('utf-8')

# Register Tamil font - Try multiple font sources
TAMIL_FONT_AVAILABLE = False
TAMIL_FONT_NAME = 'NamilTamil'

try:
    # First try: Noto Sans Tamil
    tamil_font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'NotoSansTamil-Regular.ttf')
    if os.path.exists(tamil_font_path):
        pdfmetrics.registerFont(TTFont(TAMIL_FONT_NAME, tamil_font_path))
        TAMIL_FONT_AVAILABLE = True
        print(f"[SUCCESS] Tamil font (Noto Sans Tamil) loaded from {tamil_font_path}")
    else:
        print(f"[WARNING] Noto Sans Tamil not found at {tamil_font_path}")
        # Try alternative path
        tamil_font_path = os.path.join(settings.BASE_DIR, 'pawnshop_management', 'fonts', 'NotoSansTamil-Regular.ttf')
        if os.path.exists(tamil_font_path):
            pdfmetrics.registerFont(TTFont(TAMIL_FONT_NAME, tamil_font_path))
            TAMIL_FONT_AVAILABLE = True
            print(f"[SUCCESS] Tamil font loaded from alternative path: {tamil_font_path}")
except Exception as e:
    print(f"[ERROR] Failed to register Tamil font: {e}")
    TAMIL_FONT_AVAILABLE = False


def generate_tamil_loan_pdf(loan, request=None):
    """
    Generate a loan agreement PDF with proper Tamil script rendering using ReportLab.
    
    Args:
        loan: Loan model instance
        request: Django request object (optional)
        
    Returns:
        BytesIO: PDF file as bytes
    """
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch
    )
    
    styles = getSampleStyleSheet()
    
    # Define custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#000000'),
        spaceAfter=6,
        alignment=1,  # Center
        fontName='Helvetica-Bold'
    )
    
    tamil_title_style = ParagraphStyle(
        'TamilTitle',
        parent=styles['Heading1'],
        fontName=TAMIL_FONT_NAME if TAMIL_FONT_AVAILABLE else 'Helvetica',
        fontSize=12,
        textColor=colors.HexColor('#000000'),
        spaceAfter=12,
        alignment=1,  # Center
    )
    
    english_heading_style = ParagraphStyle(
        'EnglishHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        textColor=colors.HexColor('#2d3748'),
        spaceAfter=6,
        spaceBefore=6,
    )
    
    tamil_paragraph_style = ParagraphStyle(
        'TamilParagraph',
        parent=styles['Normal'],
        fontName=TAMIL_FONT_NAME if TAMIL_FONT_AVAILABLE else 'Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#333333'),
        spaceAfter=8,
        alignment=4,  # Justified
        leading=14,
        encoding='utf-8',
    )
    
    english_paragraph_style = ParagraphStyle(
        'EnglishParagraph',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#333333'),
        spaceAfter=6,
        alignment=0,  # Left align
    )
    
    # Build document content
    elements = []
    
    # Title
    elements.append(Paragraph("GOLD LOAN AGREEMENT", title_style))
    if TAMIL_FONT_AVAILABLE:
        elements.append(Paragraph("பொன் கடன் ஒப்பந்தம்", tamil_title_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Loan Details Header
    elements.append(Paragraph("Loan Details", english_heading_style))
    
    # Loan details table
    loan_details_data = [
        ['Loan Number:', loan.loan_number, 'Loan Date:', loan.created_at.strftime('%d/%m/%Y')],
        ['Customer Name:', loan.customer.full_name if loan.customer else 'N/A', 'Loan Duration:', f'{loan.scheme.loan_duration} days'],
        ['Principal Amount:', f'₹{loan.principal_amount:,.2f}', 'Interest Rate:', f'{loan.scheme.interest_rate}% p.a.'],
        ['Monthly Interest:', f'₹{getattr(loan.monthly_interest, "amount", loan.monthly_interest.rate if hasattr(loan.monthly_interest, "rate") else "N/A"):,.2f}' if hasattr(loan, 'monthly_interest') else 'N/A', 'Due Date:', loan.due_date.strftime('%d/%m/%Y')],
    ]
    
    loan_details_table = Table(loan_details_data, colWidths=[2*cm, 3.5*cm, 2.5*cm, 3.5*cm])
    loan_details_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    elements.append(loan_details_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Terms and Conditions Section
    elements.append(Paragraph("TERMS AND CONDITIONS", english_heading_style))
    
    # Tamil Terms and Conditions as a complete paragraph
    tamil_terms = """விதிமுறைகள் மற்றும் நிபந்தனைகள்: 1. கடன் திட்ட விவரங்கள்: இந்தக் கடன் "3 பைசா | 6 மாதத் திட்டம் | எந்த தங்கமும்" திட்டத்தின் கீழ் வழங்கப்படுகிறது. வட்டி விகிதம்: ஆண்டுக்கு 36.00% 180 நாட்களுக்கு. கடன் தொகை வரம்பு: ரூ. 1000 முதல் ரூ. 1000000 வரை. 2. கடனின் நோக்கம்: கடன் வழங்குபவரிடம் பிணையமாக டெபாசிட் செய்யப்பட்ட தங்க ஆபரணங்கள்/பொருட்களின் பாதுகாப்பின் பேரில் மட்டுமே கடன் வழங்கப்படுகிறது. கடன் வாங்குபவர் அடமானம் வைக்கப்பட்ட பொருள் தனக்குச் சொந்தமான சொத்து என்றும் அது திருடப்படவில்லை அல்லது சுமையாக இல்லை என்றும் உறுதிப்படுத்துகிறார். 3. தங்கம் மீட்பு நேரம்: தங்கம் மீட்புக்கு, காலை 11:00 மணிக்கு முன் பணம் செலுத்தப்பட வேண்டும். அதே நாளில் மாலை 4:00 மணிக்குப் பிறகு தங்க சேகரிப்பு கிடைக்கும். இது கடன் முடிவின் சரிபார்ப்பு மற்றும் செயல்முறைக்கு போதுமான நேரம் அளிக்கிறது. 4. KYC இணக்கம்: கடன் வாங்குபவர் RBI வழிகாட்டுதல்களின் கீழ் தேவைப்படும் தேவையான KYC ஆவணங்களை வழங்கியுள்ளார், இதில் அடையாளம் மற்றும் முகவரிச் சான்று உட்பட உள்ளது. 5. நியாயமான நடைமுறைகள் குறியீடு: இயற்கை பேரழிவுகள், திருட்டு அல்லது கடன் வழங்குபவரின் கட்டுப்பாட்டிற்கு அப்பாற்பட்ட சூழ்நிலைகள் காரணமாக அடமானம் வைக்கப்பட்ட பொருளுக்கு ஏற்படும் இழப்பு அல்லது சேதத்திற்கு RBI பரிந்துரையின்படி கடன் வழங்குபவர் பொறுப்பேற்க மாட்டார். 6. குறை தீர்க்கும் தீர்வு: கடனை 3 மாதங்களுக்குப் பிறகு அல்லது காலக்கெடுவுக்கு முன் திருப்பிச் செலுத்த வேண்டும். திருப்பிச் செலுத்தப்படாவிட்டால், Indian Contract Act 1872 மற்றும் Pawn Brokers Act 1943 ன் விதிகளின்படி கடன் வழங்குபவர் அடமானம் வைக்கப்பட்ட பொருளை விற்கலாம். 7. ரசீது தேவை: இந்த அசல் கடன் ஆவணம் மற்றும் சமர்ப்பிக்கப்பட்ட அடையாளச் சான்று சரிபார்ப்பு இல்லாமல் அடமானம் வைக்கப்பட்ட தங்கப் பொருட்களின் வெளியீடு செயல்படுத்தப்படாது. 8. பிரகடனம்: வழங்கப்பட்ட அனைத்து தகவல்களும் உண்மை என்று கடன் வாங்குபவர் பிரகடனம் செய்கிறார். கடன் வாங்குபவர் இங்கு குறிப்பிடப்பட்டுள்ள அனைத்து விதிமுறைகளையும் நிபந்தனைகளையும் படித்து புரிந்துகொண்டுள்ளார்."""
    
    elements.append(Paragraph(tamil_terms, tamil_paragraph_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Signature Section
    elements.append(Spacer(1, 0.3*inch))
    
    sig_data = [
        ['Borrower Signature', '', 'Authorized Signatory'],
        ['________________________', '', '________________________'],
        [loan.customer.full_name if loan.customer else '', '', loan.branch.name if loan.branch else 'Branch Manager'],
        ['Date: ________________', '', 'Date: ________________'],
    ]
    
    sig_table = Table(sig_data, colWidths=[2.5*inch, 1*inch, 2.5*inch])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    elements.append(sig_table)
    
    # Footer
    elements.append(Spacer(1, 0.2*inch))
    footer_text = f"Document generated on: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    elements.append(Paragraph(footer_text, english_paragraph_style))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer
