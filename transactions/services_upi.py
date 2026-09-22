"""
Free Indian UPI Payment QR Code Generator & Processing Service
Generates standard NPCI compliant upi://pay URI strings and encodes them into Base64 PNG QR matrices.
"""

import io
import base64
import urllib.parse
import logging
from decimal import Decimal
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_UPI_VPA = getattr(settings, 'DEFAULT_UPI_VPA', 'firstmoneygold@icici')
DEFAULT_MERCHANT_NAME = getattr(settings, 'DEFAULT_UPI_MERCHANT_NAME', 'First Money Gold')


def build_upi_uri(
    vpa: str, 
    merchant_name: str, 
    amount: Decimal | float | int | str, 
    loan_number: str = "", 
    note: str = ""
) -> str:
    """
    Constructs a standard NPCI compliant Indian UPI payment URI link.
    Example: upi://pay?pa=shop@icici&pn=First+Money+Gold&am=2500.00&cu=INR&tn=Loan_FMG101
    """
    clean_vpa = (vpa or DEFAULT_UPI_VPA).strip()
    clean_merchant = (merchant_name or DEFAULT_MERCHANT_NAME).strip()
    
    try:
        amt_dec = Decimal(str(amount))
        amt_str = f"{amt_dec:.2f}"
    except Exception:
        amt_str = "0.00"
        
    transaction_note = (note or f"Loan Repayment {loan_number}").strip()
    
    params = {
        'pa': clean_vpa,
        'pn': clean_merchant,
        'am': amt_str,
        'cu': 'INR',
        'tn': transaction_note[:50]
    }
    
    query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"upi://pay?{query_string}"


def generate_upi_qr_base64(upi_uri: str, box_size: int = 6, border: int = 2) -> str:
    """
    Generates a high-clarity QR matrix image for the given UPI URI
    and returns a base64 Data URI string (e.g. data:image/png;base64,...).
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border
    )
    qr.add_data(upi_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    
    b64_encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{b64_encoded}"


def get_loan_upi_payment_payload(loan, requested_amount=None) -> dict:
    """
    Resolves branch VPA, merchant name, calculates due balance, and generates
    the dynamic UPI link and Base64 QR code for a given loan instance.
    """
    branch = getattr(loan, 'branch', None)
    
    # Priority: Branch VPA -> Settings VPA -> Default Fallback
    vpa = ""
    merchant_name = ""
    
    if branch:
        vpa = getattr(branch, 'upi_vpa', '') or ''
        merchant_name = getattr(branch, 'upi_merchant_name', '') or ''
        
    if not vpa:
        vpa = getattr(settings, 'UPI_DEFAULT_VPA', DEFAULT_UPI_VPA)
    if not merchant_name:
        merchant_name = getattr(branch, 'name', '') or DEFAULT_MERCHANT_NAME

    # Determine amount
    if requested_amount is not None:
        amount = Decimal(str(requested_amount))
    else:
        # Fall back to current loan balance or total interest due
        amount = getattr(loan, 'total_outstanding_amount', None) or getattr(loan, 'amount', Decimal('1000.00'))
        
    loan_number = getattr(loan, 'loan_number', str(loan.id))
    transaction_note = f"Loan {loan_number}"
    
    upi_uri = build_upi_uri(
        vpa=vpa,
        merchant_name=merchant_name,
        amount=amount,
        loan_number=loan_number,
        note=transaction_note
    )
    
    qr_base64 = generate_upi_qr_base64(upi_uri)
    
    return {
        'vpa': vpa,
        'merchant_name': merchant_name,
        'amount': amount,
        'loan_number': loan_number,
        'upi_uri': upi_uri,
        'qr_base64': qr_base64,
        'customer_name': loan.customer.full_name if hasattr(loan, 'customer') and loan.customer else ''
    }
