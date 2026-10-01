import os
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR_DIR = os.path.join(BASE_DIR, 'static', 'vendor')

FILES_TO_DOWNLOAD = [
    # Bootstrap
    (
        'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
        os.path.join(VENDOR_DIR, 'bootstrap', 'css', 'bootstrap.min.css')
    ),
    (
        'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
        os.path.join(VENDOR_DIR, 'bootstrap', 'js', 'bootstrap.bundle.min.js')
    ),
    # Font Awesome CSS
    (
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
        os.path.join(VENDOR_DIR, 'fontawesome', 'css', 'all.min.css')
    ),
    # Font Awesome Webfonts
    (
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.woff2',
        os.path.join(VENDOR_DIR, 'fontawesome', 'webfonts', 'fa-solid-900.woff2')
    ),
    (
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.ttf',
        os.path.join(VENDOR_DIR, 'fontawesome', 'webfonts', 'fa-solid-900.ttf')
    ),
    (
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-regular-400.woff2',
        os.path.join(VENDOR_DIR, 'fontawesome', 'webfonts', 'fa-regular-400.woff2')
    ),
    (
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-regular-400.ttf',
        os.path.join(VENDOR_DIR, 'fontawesome', 'webfonts', 'fa-regular-400.ttf')
    ),
    (
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-brands-400.woff2',
        os.path.join(VENDOR_DIR, 'fontawesome', 'webfonts', 'fa-brands-400.woff2')
    ),
    (
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-brands-400.ttf',
        os.path.join(VENDOR_DIR, 'fontawesome', 'webfonts', 'fa-brands-400.ttf')
    ),
    (
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-v4compatibility.woff2',
        os.path.join(VENDOR_DIR, 'fontawesome', 'webfonts', 'fa-v4compatibility.woff2')
    ),
    (
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-v4compatibility.ttf',
        os.path.join(VENDOR_DIR, 'fontawesome', 'webfonts', 'fa-v4compatibility.ttf')
    ),
    # jQuery
    (
        'https://code.jquery.com/jquery-3.6.0.min.js',
        os.path.join(VENDOR_DIR, 'jquery', 'jquery.min.js')
    ),
    # Chart.js
    (
        'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js',
        os.path.join(VENDOR_DIR, 'chartjs', 'chart.min.js')
    ),
    # JSZip
    (
        'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js',
        os.path.join(VENDOR_DIR, 'jszip', 'jszip.min.js')
    ),
    # FileSaver
    (
        'https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/2.0.5/FileSaver.min.js',
        os.path.join(VENDOR_DIR, 'filesaver', 'FileSaver.min.js')
    ),
    # JsBarcode
    (
        'https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js',
        os.path.join(VENDOR_DIR, 'jsbarcode', 'JsBarcode.all.min.js')
    ),
    # QRCode.js
    (
        'https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js',
        os.path.join(VENDOR_DIR, 'qrcodejs', 'qrcode.min.js')
    ),
]

def download_vendors():
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')]
    urllib.request.install_opener(opener)

    print("Starting download of vendor libraries...")
    for url, target_path in FILES_TO_DOWNLOAD:
        dir_name = os.path.dirname(target_path)
        os.makedirs(dir_name, exist_ok=True)
        try:
            print(f"Downloading {url} -> {target_path}...")
            urllib.request.urlretrieve(url, target_path)
            size_kb = os.path.getsize(target_path) / 1024
            print(f"  [OK] Saved ({size_kb:.1f} KB)")
        except Exception as e:
            print(f"  [FAILED] {url}: {e}")

    print("\nAll downloads complete!")

if __name__ == '__main__':
    download_vendors()
