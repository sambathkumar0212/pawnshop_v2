"""Register fonts with ReportLab for PDF generation.

This module registers custom fonts (especially Tamil-capable ones) with ReportLab
so xhtml2pdf can embed them in generated PDFs.
"""
import os
from django.conf import settings

def register_fonts():
    """Register fonts with ReportLab if they exist on disk."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        return
    
    # Register Noto Sans Tamil
    tamil_font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'NotoSansTamil-Regular.ttf')
    if os.path.exists(tamil_font_path):
        try:
            pdfmetrics.registerFont(TTFont('NotoSansTamil', tamil_font_path))
        except Exception as e:
            print(f"Warning: could not register Tamil font: {e}")
    else:
        print(f"Note: Tamil font not found at {tamil_font_path}; PDF output will use fallback fonts.")


# Register on module import
register_fonts()
