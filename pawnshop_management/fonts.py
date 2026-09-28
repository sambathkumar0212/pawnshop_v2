"""
Font and PDF Generation Service for Pawnshop Management System.

Provides:
1. Base64 font embedding (for NotoSansTamil) ensuring 100% offline & container font availability.
2. Cross-platform Chromium browser discovery (Playwright Chromium, Linux Google Chrome/Chromium, macOS, Windows).
3. Primary PDF Generation via Playwright CDP (Pixel-perfect OpenType HarfBuzz Tamil script shaping).
4. Secondary PDF Generation via Headless Chromium CLI Subprocess.
5. Tertiary PDF Fallback via xhtml2pdf / ReportLab with registered TTF fonts.
"""
import os
import sys
import base64
import shutil
import glob
import tempfile
import subprocess
from pathlib import Path
from django.conf import settings

_TAMIL_FONT_BASE64_CACHE = None

def get_tamil_font_path():
    """Return the absolute path to NotoSansTamil-Regular.ttf if present."""
    base_dir = Path(settings.BASE_DIR)
    candidates = [
        base_dir / 'static' / 'fonts' / 'NotoSansTamil-Regular.ttf',
        Path(settings.STATIC_ROOT or '') / 'fonts' / 'NotoSansTamil-Regular.ttf',
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None

def get_tamil_font_base64():
    """Return cached base64 string of NotoSansTamil-Regular.ttf."""
    global _TAMIL_FONT_BASE64_CACHE
    if _TAMIL_FONT_BASE64_CACHE is not None:
        return _TAMIL_FONT_BASE64_CACHE

    font_path = get_tamil_font_path()
    if font_path and os.path.exists(font_path):
        try:
            with open(font_path, 'rb') as f:
                _TAMIL_FONT_BASE64_CACHE = base64.b64encode(f.read()).decode('utf-8')
                return _TAMIL_FONT_BASE64_CACHE
        except Exception as e:
            print(f"[Fonts] Warning reading Tamil font: {e}")
    _TAMIL_FONT_BASE64_CACHE = ""
    return _TAMIL_FONT_BASE64_CACHE

def get_tamil_font_uri():
    """Return file:/// URI for the font."""
    font_path = get_tamil_font_path()
    if font_path:
        return f"file:///{font_path.replace(os.sep, '/')}"
    return ""

def find_browser_executable():
    """
    Find an installed Chromium-based browser executable across:
    - CHROME_BIN / CHROMIUM_PATH environment variables
    - Linux Docker / Render paths (/usr/bin/chromium, /usr/bin/google-chrome, etc.)
    - Playwright Chromium binaries (Linux / Render / Docker / Windows / macOS)
    - System Google Chrome / Chromium / Edge binaries in PATH
    - Standard Windows & macOS paths
    """
    # 0. Check explicit environment variables (e.g. In Docker/Render)
    for env_var in ['CHROME_BIN', 'CHROMIUM_PATH', 'GOOGLE_CHROME_BIN', 'CHROME_PATH']:
        val = os.environ.get(env_var)
        if val and os.path.exists(val):
            return val

    # 1. Standard Linux container paths (Docker, Ubuntu, Debian, Render)
    linux_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/local/bin/chromium",
        "/usr/local/bin/google-chrome",
        "/snap/bin/chromium",
    ]
    for p in linux_paths:
        if os.path.exists(p):
            return p

    # 2. System PATH search
    system_names = [
        'chromium',
        'chromium-browser',
        'google-chrome',
        'google-chrome-stable',
        'chrome',
        'msedge',
        'microsoft-edge',
    ]
    for name in system_names:
        p = shutil.which(name)
        if p and os.path.exists(p):
            return p

    # 3. Direct Playwright sync_api executable path
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            pw_path = p.chromium.executable_path
            if pw_path and os.path.exists(pw_path):
                return pw_path
    except Exception:
        pass

    # 4. Direct check for Playwright cached browser directories on Linux / Render / Docker / Windows
    home_dir = os.path.expanduser("~")
    possible_playwright_patterns = [
        os.path.join(home_dir, ".cache", "ms-playwright", "chromium-*", "chrome-linux", "chrome"),
        os.path.join(home_dir, ".cache", "ms-playwright", "chromium_headless_shell-*", "chrome-linux", "headless_shell"),
        "/opt/render/project/src/.venv/lib/python*/site-packages/playwright/driver/package/.local-browsers/chromium-*/chrome-linux/chrome",
        "/opt/render/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
        "/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
        os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright\chromium-*\chrome-win\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright\chromium-*\chrome-win64\chrome.exe"),
    ]
    for pattern in possible_playwright_patterns:
        matches = glob.glob(pattern)
        if matches:
            for match in matches:
                if os.path.exists(match):
                    return match

    # 5. Standard Windows paths
    win_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in win_paths:
        if os.path.exists(p):
            return p

    # 6. Standard macOS paths
    mac_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for p in mac_paths:
        if os.path.exists(p):
            return p

    return None

def render_html_to_pdf_bytes(html_content, page_size='A4', margins=None):
    """
    Render HTML content to PDF bytes using:
    1. Playwright CDP API (highest quality, HarfBuzz OpenType script shaping)
    2. Headless Chromium CLI Subprocess
    3. xhtml2pdf Fallback
    """
    if margins is None:
        margins = {'top': '0.5cm', 'right': '0.5cm', 'bottom': '0.5cm', 'left': '0.5cm'}

    browser_exe = find_browser_executable()

    # 1. Primary Method: Playwright Python API
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            launch_kwargs = {
                'headless': True,
                'args': [
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--disable-setuid-sandbox',
                    '--allow-file-access-from-files',
                    '--disable-web-security',
                ]
            }
            if browser_exe and os.path.exists(browser_exe):
                launch_kwargs['executable_path'] = browser_exe

            browser = p.chromium.launch(**launch_kwargs)
            page = browser.new_page()
            page.set_content(html_content, wait_until='load')
            pdf_bytes = page.pdf(
                format=page_size,
                margin=margins,
                print_background=True,
                prefer_css_page_size=True,
            )
            browser.close()
            if pdf_bytes and len(pdf_bytes) > 500:
                return pdf_bytes
    except Exception as pw_err:
        print(f"[PDF Engine] Playwright API generation info: {pw_err}")

    # 2. Secondary Method: Headless Browser Subprocess
    if browser_exe:
        tmp_dir = tempfile.mkdtemp(prefix='render_pdf_')
        html_path = os.path.join(tmp_dir, 'document.html')
        pdf_path = os.path.join(tmp_dir, 'document.pdf')
        profile_dir = os.path.join(tmp_dir, 'profile')
        os.makedirs(profile_dir, exist_ok=True)
        try:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            cmd = [
                browser_exe,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                f"--user-data-dir={profile_dir}",
                "--allow-file-access-from-files",
                "--disable-web-security",
                "--print-to-pdf-no-header",
                f"--print-to-pdf={pdf_path}",
                f"file:///{html_path.replace(os.sep, '/')}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
            if result.returncode == 0 and os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    pdf_bytes = f.read()
                if pdf_bytes and len(pdf_bytes) > 500:
                    return pdf_bytes
        except Exception as sub_err:
            print(f"[PDF Engine] Subprocess browser PDF error: {sub_err}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # 3. Tertiary Fallback: xhtml2pdf (ReportLab)
    try:
        from xhtml2pdf import pisa
        import io
        register_fonts()
        out_stream = io.BytesIO()

        def link_callback(uri, rel):
            if uri.startswith(settings.MEDIA_URL):
                return os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ''))
            elif uri.startswith(settings.STATIC_URL):
                return os.path.join(settings.STATIC_ROOT or (Path(settings.BASE_DIR) / 'static'), uri.replace(settings.STATIC_URL, ''))
            return uri

        # Strip large base64 @font-face blocks because xhtml2pdf uses fonts registered via pdfmetrics
        clean_html = re.sub(r'@font-face\s*\{[^}]*\}', '', html_content, flags=re.DOTALL)
        pisa_status = pisa.CreatePDF(clean_html, dest=out_stream, link_callback=link_callback)
        pdf_bytes = out_stream.getvalue()
        if pdf_bytes and len(pdf_bytes) > 500:
            return pdf_bytes
    except Exception as xh_err:
        print(f"[PDF Engine] xhtml2pdf fallback error: {xh_err}")

    return None

def register_fonts():
    """Register fonts with ReportLab if they exist on disk."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from xhtml2pdf.default import DEFAULT_FONT
    except ImportError:
        return

    font_path = get_tamil_font_path()
    if font_path and os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('NotoSansTamil', font_path))
            DEFAULT_FONT['notosanstamil'] = 'NotoSansTamil'
            DEFAULT_FONT['notosans-tamil'] = 'NotoSansTamil'
            DEFAULT_FONT['tamil'] = 'NotoSansTamil'
        except Exception as e:
            print(f"Warning: could not register Tamil font: {e}")

# Register on module import
register_fonts()
