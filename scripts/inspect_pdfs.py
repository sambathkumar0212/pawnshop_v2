"""Extract text from PDFs and print key snippets for visual inspection.

This uses PyPDF2 (if available) or falls back to reading raw bytes and looking for UTF-8/UTF-16 sequences.
"""
from pathlib import Path
import sys

PDFS = [Path('artifacts/sample_payment_receipt.pdf'), Path('artifacts/sample_sale_receipt.pdf')]

try:
    import PyPDF2
except Exception:
    PyPDF2 = None


def extract_with_pypdf2(path):
    texts = []
    try:
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for p in reader.pages:
                try:
                    texts.append(p.extract_text() or '')
                except Exception:
                    texts.append('')
    except Exception as e:
        return None, str(e)
    return '\n'.join(texts), None


def extract_fallback(path):
    # crude fallback: search for UTF-8/UTF-16 text runs in the PDF bytes
    data = path.read_bytes()
    try:
        s = data.decode('utf-8')
    except Exception:
        try:
            s = data.decode('utf-16')
        except Exception:
            # fallback: return first 2000 bytes as latin-1
            s = data[:2000].decode('latin-1', errors='replace')
    return s, None


def inspect_pdf(path):
    print('\n===', path, '===')
    if not path.exists():
        print('MISSING:', path)
        return
    if PyPDF2:
        text, err = extract_with_pypdf2(path)
        if err:
            print('PyPDF2 extraction error:', err)
            text, _ = extract_fallback(path)
    else:
        print('PyPDF2 not installed; using fallback extraction')
        text, _ = extract_fallback(path)

    # Print first 1200 chars and highlight presence of Tamil words
    snippet = text[:1200]
    print('\n--- Extracted text snippet (first 1200 chars) ---\n')
    print(snippet)

    # Check for expected bilingual markers
    checks = [
        ('Payment Receipt', 'English label'),
        ('கட்டண ரசீது', 'Tamil label'),
        ('Amount in words', 'English amount-in-words label'),
        ('எண்ணில் தொகை', 'Tamil amount-in-words label'),
        ('Sale Invoice', 'English sale invoice label'),
        ('விற்பனை ரசீது', 'Tamil sale invoice label'),
    ]
    print('\n--- Presence checks ---')
    for token, desc in checks:
        print(f"{desc:30}:", 'YES' if token in text else 'NO')


if __name__ == '__main__':
    for p in PDFS:
        inspect_pdf(p)
