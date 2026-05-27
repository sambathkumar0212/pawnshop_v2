"""Generate sample bilingual receipts (HTML -> PDF) for manual verification.

This script will:
- Setup Django environment
- Render `transactions/payment_receipt_pdf.html` and `transactions/sale_receipt_pdf.html`
  with small, realistic dummy context objects
- Attempt to convert rendered HTML to PDF using xhtml2pdf (pisa)
- Save outputs under `artifacts/`

Run:
    python scripts\generate_sample_receipts.py

If xhtml2pdf is not installed, the script will write the rendered HTML to `artifacts/` for manual inspection.
"""
import os
import sys
import django
from pathlib import Path
from types import SimpleNamespace

# Ensure project root is on sys.path so Django can import project modules
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Initialize Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

# Register fonts explicitly for xhtml2pdf (ensure ToUnicode mapping)
try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from django.conf import settings
    tamil_font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'NotoSansTamil-Regular.ttf')
    if os.path.exists(tamil_font_path):
        pdfmetrics.registerFont(TTFont('NotoSansTamil', tamil_font_path))
        # Also try registering without suffix for fallback
        try:
            pdfmetrics.registerFont(TTFont('NotoSansTamil-Regular', tamil_font_path))
        except Exception:
            pass
except Exception as e:
    print(f"Warning: Could not register fonts: {e}")

from django.template import loader
from django.utils import timezone

ARTIFACTS_DIR = Path('artifacts')
ARTIFACTS_DIR.mkdir(exist_ok=True)

# Minimal helper to create objects used by the template
class Dummy:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getattr__(self, item):
        raise AttributeError(item)


def render_template_to_html(template_name, context):
    tpl = loader.get_template(template_name)
    return tpl.render(context)


def html_to_pdf(html_content, out_path):
    try:
        from xhtml2pdf import pisa
    except Exception as e:
        print('xhtml2pdf not available:', e)
        return False
    with open(out_path, 'wb') as f:
        pisa_status = pisa.CreatePDF(html_content, dest=f)
    return not pisa_status.err


def make_payment_context():
    from pathlib import Path
    customer = Dummy(full_name='Ramesh Kumar')
    received_by = Dummy(get_full_name='Branch Manager')
    branch = Dummy(name='Central Branch', address='123 Main St', city='Chennai', state='TN', zip_code='600001', phone='044-123456', email='branch@example.com')
    loan = Dummy(loan_number='LN1001', customer=customer, principal_amount=15000.00, status='active')
    payment = Dummy(id=101, payment_date=timezone.now(), amount=1250.00, get_payment_method_display='Cash', reference_number='REF123', notes='Paid in full for the month', received_by=received_by)

    # Get the BASE_DIR from django settings
    from django.conf import settings
    base_dir = settings.BASE_DIR
    tamil_font_path = str((base_dir / 'static' / 'fonts' / 'NotoSansTamil-Regular.ttf')).replace(os.sep, '/')
    
    ctx = {
        'payment': payment,
        'loan': loan,
        'branch': branch,
        'payment_type': 'partial',
        'interest_amount': 250.00,
        'total_paid': 5000.00,
        'remaining_balance': 10000.00,
        'amount_in_words': 'One Thousand Two Hundred Fifty Rupees Only',
        'amount_in_words_tamil': 'ஓர் தனி இணைவு',
        'date_today': timezone.now(),
        'tamil_font_file_uri': f'file:///{tamil_font_path}',
    }
    return ctx


def make_sale_context():
    customer = Dummy(full_name='Lakshmi Devi')
    branch = Dummy(name='Central Branch', address='123 Main St', city='Chennai', state='TN', zip_code='600001', phone='044-123456', email='branch@example.com')
    sale = Dummy(id=201, invoice_number='SINV-201', total_amount=3200.50, total_amount_in_words='Three Thousand Two Hundred Rupees and Fifty Paise Only', total_amount_in_words_tamil='மூன்று ஆயிரத்து இருநூறு ரூபாய் 50 பைசா', customer=customer)

    ctx = {
        'sale': sale,
        'branch': branch,
        'now': timezone.now(),
    }
    return ctx


def main():
    # Payment receipt
    payment_ctx = make_payment_context()
    html = render_template_to_html('transactions/payment_receipt_pdf.html', payment_ctx)
    html_path = ARTIFACTS_DIR / 'sample_payment_receipt.html'
    html_path.write_text(html, encoding='utf-8')
    print('Wrote HTML to', html_path)

    pdf_path = ARTIFACTS_DIR / 'sample_payment_receipt.pdf'
    if html_to_pdf(html, str(pdf_path)):
        print('Wrote PDF to', pdf_path)
    else:
        print('PDF conversion failed; HTML saved for inspection at', html_path)

    # Sale receipt (if template exists)
    try:
        sale_ctx = make_sale_context()
        html2 = render_template_to_html('transactions/sale_receipt_pdf.html', sale_ctx)
        html2_path = ARTIFACTS_DIR / 'sample_sale_receipt.html'
        html2_path.write_text(html2, encoding='utf-8')
        print('Wrote HTML to', html2_path)

        pdf2_path = ARTIFACTS_DIR / 'sample_sale_receipt.pdf'
        if html_to_pdf(html2, str(pdf2_path)):
            print('Wrote PDF to', pdf2_path)
        else:
            print('PDF conversion failed; HTML saved for inspection at', html2_path)
    except Exception as e:
        print('Skipping sale receipt render; error:', e)


if __name__ == '__main__':
    main()
