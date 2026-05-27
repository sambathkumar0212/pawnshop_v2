#!/usr/bin/env python
"""Test if Tamil font can be loaded"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from django.conf import settings
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

tamil_font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'NotoSansTamil-Regular.ttf')
print(f'Font path: {tamil_font_path}')
print(f'Exists: {os.path.exists(tamil_font_path)}')

if os.path.exists(tamil_font_path):
    print(f'File size: {os.path.getsize(tamil_font_path)} bytes')
    
    try:
        pdfmetrics.registerFont(TTFont('NamilTamil', tamil_font_path))
        print('✓ Font registered successfully')
        
        # Test Tamil text rendering
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph
        from reportlab.lib.styles import ParagraphStyle
        from io import BytesIO
        
        # Create test PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        style = ParagraphStyle(
            'TamilTest',
            fontName='NamilTamil',
            fontSize=12
        )
        
        tamil_text = "கடன் எண்: 12345"
        para = Paragraph(tamil_text, style)
        
        doc.build([para])
        print(f'✓ Test PDF created successfully ({buffer.tell()} bytes)')
        
    except Exception as e:
        print(f'✗ Error: {e}')
        import traceback
        traceback.print_exc()
else:
    print('✗ Font file not found')
