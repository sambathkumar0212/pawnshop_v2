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
import re
import base64
import shutil
import glob
import tempfile
import subprocess
import logging
from pathlib import Path
from django.conf import settings

logger = logging.getLogger('pawnshop_management.fonts')
_TAMIL_FONT_BASE64_CACHE = None
_BROWSER_EXE_CACHE = None
_BROWSER_EXE_CHECKED = False

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
            logger.warning(f"Warning reading Tamil font: {e}")
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
    global _BROWSER_EXE_CACHE, _BROWSER_EXE_CHECKED
    if _BROWSER_EXE_CHECKED:
        return _BROWSER_EXE_CACHE

    def _resolve():
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
            os.path.join(home_dir, ".cache", "ms-playwright", "chromium-*", "chrome-linux64", "chrome"),
            os.path.join(home_dir, ".cache", "ms-playwright", "chromium_headless_shell-*", "chrome-linux", "headless_shell"),
            os.path.join(home_dir, ".cache", "ms-playwright", "chromium_headless_shell-*", "chrome-linux64", "headless_shell"),
            "/opt/render/project/src/.venv/lib/python*/site-packages/playwright/driver/package/.local-browsers/chromium-*/chrome-linux/chrome",
            "/opt/render/project/src/.venv/lib/python*/site-packages/playwright/driver/package/.local-browsers/chromium-*/chrome-linux64/chrome",
            "/opt/render/project/src/.venv/lib/python*/site-packages/playwright/driver/package/.local-browsers/chromium_headless_shell-*/chrome-linux/headless_shell",
            "/opt/render/project/src/.venv/lib/python*/site-packages/playwright/driver/package/.local-browsers/chromium_headless_shell-*/chrome-linux64/headless_shell",
            "/opt/render/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
            "/opt/render/.cache/ms-playwright/chromium-*/chrome-linux64/chrome",
            "/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
            "/root/.cache/ms-playwright/chromium-*/chrome-linux64/chrome",
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

    _BROWSER_EXE_CACHE = _resolve()
    _BROWSER_EXE_CHECKED = True
    return _BROWSER_EXE_CACHE

def render_html_to_pdf_bytes(html_content, page_size='A4', margins=None):
    """
    Render HTML content to PDF bytes using:
    1. Memory Cache (Instant 0.001s return for pre-rendered / repeated PDFs)
    2. Playwright CDP API (highest quality, HarfBuzz OpenType script shaping) — if browser exists
    3. Headless Chromium CLI Subprocess (quick 6s timeout) — if browser exists
    4. xhtml2pdf Fallback (pure Python ReportLab TTF renderer) — always works without external binaries
    """
    if margins is None:
        margins = {'top': '0.5cm', 'right': '0.5cm', 'bottom': '0.5cm', 'left': '0.5cm'}

    # 0. Check in-memory pre-rendered cache
    cache_key = None
    try:
        from utils.async_tasks import compute_html_hash, get_cached_pdf_bytes, set_cached_pdf_bytes
        cache_key = compute_html_hash(html_content, extra_key=page_size)
        cached_pdf = get_cached_pdf_bytes(cache_key)
        if cached_pdf:
            return cached_pdf
    except Exception:
        pass

    browser_exe = find_browser_executable()

    # 1. Primary Method: Playwright Python API (Only if a valid browser binary exists)
    if browser_exe:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                launch_kwargs = {
                    'headless': True,
                    'executable_path': browser_exe,
                    'args': [
                        '--no-sandbox',
                        '--disable-gpu',
                        '--disable-dev-shm-usage',
                        '--disable-setuid-sandbox',
                        '--single-process',
                        '--no-zygote',
                        '--disable-software-rasterizer',
                        '--allow-file-access-from-files',
                        '--disable-web-security',
                    ]
                }
                browser = p.chromium.launch(**launch_kwargs)
                page = browser.new_page()
                page.set_content(html_content, wait_until='domcontentloaded', timeout=10000)
                pdf_bytes = page.pdf(
                    format=page_size,
                    margin=margins,
                    print_background=True,
                    prefer_css_page_size=True,
                )
                browser.close()
                if pdf_bytes and len(pdf_bytes) > 500:
                    if cache_key:
                        try:
                            set_cached_pdf_bytes(cache_key, pdf_bytes)
                        except Exception:
                            pass
                    return pdf_bytes
        except Exception as pw_err:
            safe_err = str(pw_err).encode('ascii', 'replace').decode('ascii')
            logger.info(f"Playwright API generation info: {safe_err}")

        # 2. Secondary Method: Headless Browser Subprocess (with short 6s timeout)
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
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--single-process",
                "--no-zygote",
                "--disable-software-rasterizer",
                "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=2000",
                f"--user-data-dir={profile_dir}",
                "--allow-file-access-from-files",
                "--disable-web-security",
                "--print-to-pdf-no-header",
                f"--print-to-pdf={pdf_path}",
                f"file:///{html_path.replace(os.sep, '/')}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
            if result.returncode == 0 and os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    pdf_bytes = f.read()
                if pdf_bytes and len(pdf_bytes) > 500:
                    if cache_key:
                        try:
                            set_cached_pdf_bytes(cache_key, pdf_bytes)
                        except Exception:
                            pass
                    return pdf_bytes
        except Exception as sub_err:
            safe_sub = str(sub_err).encode('ascii', 'replace').decode('ascii')
            logger.info(f"Subprocess browser PDF error: {safe_sub}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # 3. Tertiary Fallback: xhtml2pdf (ReportLab) — pure Python, requires no browser executable
    try:
        from xhtml2pdf import pisa
        import io
        register_fonts()
        out_stream = io.BytesIO()

        def link_callback(uri, rel):
            try:
                if not uri:
                    return uri
                if uri.startswith('data:'):
                    return uri
                if uri.startswith('file://'):
                    import urllib.parse
                    parsed_path = urllib.parse.urlparse(uri).path
                    if os.name == 'nt' and parsed_path.startswith('/'):
                        clean_path = parsed_path.lstrip('/')
                    else:
                        clean_path = parsed_path
                    if os.path.exists(clean_path):
                        return clean_path
                    # Fallback checks
                    alt = uri.replace('file:///', '').replace('file://', '')
                    if os.path.exists(alt):
                        return alt
                    if not alt.startswith('/') and os.path.exists('/' + alt):
                        return '/' + alt
                if hasattr(settings, 'MEDIA_URL') and settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
                    path = os.path.join(settings.MEDIA_ROOT, uri[len(settings.MEDIA_URL):])
                    if os.path.exists(path):
                        return path
                if hasattr(settings, 'STATIC_URL') and settings.STATIC_URL and uri.startswith(settings.STATIC_URL):
                    rel_path = uri[len(settings.STATIC_URL):]
                    if settings.STATIC_ROOT and os.path.exists(os.path.join(settings.STATIC_ROOT, rel_path)):
                        return os.path.join(settings.STATIC_ROOT, rel_path)
                    static_base = Path(settings.BASE_DIR) / 'static'
                    if (static_base / rel_path).exists():
                        return str(static_base / rel_path)
                if uri.startswith('/static/') or uri.startswith('static/'):
                    clean_rel = uri.lstrip('/')
                    if clean_rel.startswith('static/'):
                        clean_rel = clean_rel[7:]
                    static_base = Path(settings.BASE_DIR) / 'static'
                    if (static_base / clean_rel).exists():
                        return str(static_base / clean_rel)
            except Exception as e:
                logger.warning(f"link_callback error for uri '{uri}': {e}")
            return uri

        # Strip large base64 @font-face blocks and troublesome CSS properties that crash ReportLab
        clean_html = re.sub(r'@font-face\s*\{[^}]*\}', '', html_content, flags=re.DOTALL)
        clean_html = re.sub(r'height\s*:\s*100%\s*;?', '', clean_html, flags=re.IGNORECASE)
        clean_html = re.sub(r'min-height\s*:\s*100%\s*;?', '', clean_html, flags=re.IGNORECASE)
        clean_html = re.sub(r'page-break-inside\s*:\s*avoid\s*;?', '', clean_html, flags=re.IGNORECASE)

        patch_reportlab()
        pisa_status = pisa.CreatePDF(clean_html, dest=out_stream, link_callback=link_callback)
        pdf_bytes = out_stream.getvalue()
        if pdf_bytes and len(pdf_bytes) > 200:
            if cache_key:
                try:
                    set_cached_pdf_bytes(cache_key, pdf_bytes)
                except Exception:
                    pass
            return pdf_bytes
        else:
            err_count = getattr(pisa_status, 'err', 0)
            logger.error(
                f"[PDF] xhtml2pdf returned invalid or empty output: err_count={err_count}, "
                f"bytes={len(pdf_bytes) if pdf_bytes else 0}. HTML length={len(html_content)}"
            )
    except Exception as xh_err:
        safe_xh = str(xh_err).encode('ascii', 'replace').decode('ascii')
        logger.error(f"[PDF] xhtml2pdf fallback error: {safe_xh}", exc_info=True)

    return None

def patch_reportlab():
    """Fix ReportLab KeepTogether AttributeError where draw() method is missing when nested in tables."""
    try:
        from reportlab.platypus import KeepTogether
        if not hasattr(KeepTogether, 'draw'):
            def _keep_together_draw(self):
                for f in getattr(self, '_content', []):
                    if hasattr(f, 'drawOn'):
                        f.drawOn(self.canv, 0, 0)
                    elif hasattr(f, 'draw'):
                        f.draw()
            KeepTogether.draw = _keep_together_draw
    except Exception:
        pass

def register_fonts():
    """Register fonts with ReportLab if they exist on disk."""
    patch_reportlab()
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from xhtml2pdf.default import DEFAULT_FONT
    except ImportError:
        return

    font_path = get_tamil_font_path()
    if font_path and os.path.exists(font_path):
        try:
            if 'NotoSansTamil' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('NotoSansTamil', font_path))
            DEFAULT_FONT['notosanstamil'] = 'NotoSansTamil'
            DEFAULT_FONT['notosans-tamil'] = 'NotoSansTamil'
            DEFAULT_FONT['tamil'] = 'NotoSansTamil'
        except Exception as e:
            logger.warning(f"Could not register Tamil font: {e}")

# Register and patch on module import
patch_reportlab()
register_fonts()

