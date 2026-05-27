from pathlib import Path
import sys

PDFS = [Path('artifacts/sample_payment_receipt.pdf'), Path('artifacts/sample_sale_receipt.pdf')]

try:
    from pypdf import PdfReader
except Exception as e:
    print('pypdf not available:', e)
    sys.exit(1)


def extract_with_pypdf(path):
    try:
        reader = PdfReader(str(path))
        texts = []
        for p in reader.pages:
            texts.append(p.extract_text() or '')
        return '\n'.join(texts)
    except Exception as e:
        return None


def inspect_pdf(path):
    print('\n===', path, '===')
    if not path.exists():
        print('MISSING:', path)
        return
    text = extract_with_pypdf(path)
    if text is None:
        print('Extraction failed')
        return
    snippet = text[:1500]
    print('\n--- Extracted text snippet (first 1500 chars) ---\n')
    print(snippet)

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
