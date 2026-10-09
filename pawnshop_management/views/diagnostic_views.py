"""
pawnshop_management/views/diagnostic_views.py
Diagnostic console for server health, PDF engine verification, package installation, and log inspection.
"""

import os
import sys
import io
import re
import traceback
import subprocess
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.csrf import csrf_exempt

def is_staff_or_valid_token(request):
    """Check if request is from a staff/superuser or has valid secret key token."""
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return True
    token = request.GET.get('token') or request.POST.get('token')
    if token and token == getattr(settings, 'SECRET_KEY', ''):
        return True
    return False

def get_pdf_diagnostics():
    """Probe all PDF engines, font files, and environment status."""
    diag = {
        'python_version': sys.version,
        'python_executable': sys.executable,
        'base_dir': str(settings.BASE_DIR),
        'packages': {},
        'fonts': {},
        'browser': {},
        'pdf_test': {},
    }

    # 1. Check Python packages
    for pkg in ['reportlab', 'xhtml2pdf', 'playwright', 'PIL', 'whitenoise', 'dotenv']:
        try:
            mod = __import__(pkg)
            version = getattr(mod, '__version__', 'Installed (version unknown)')
            diag['packages'][pkg] = {'status': 'OK', 'version': str(version)}
        except ImportError as e:
            diag['packages'][pkg] = {'status': 'MISSING', 'error': str(e)}
        except Exception as e:
            diag['packages'][pkg] = {'status': 'ERROR', 'error': str(e)}

    # 2. Check Tamil font
    try:
        from pawnshop_management.fonts import get_tamil_font_path, get_tamil_font_base64
        font_path = get_tamil_font_path()
        diag['fonts']['noto_sans_tamil'] = {
            'found': bool(font_path and os.path.exists(font_path)),
            'path': font_path or 'Not Found',
            'size_bytes': os.path.getsize(font_path) if (font_path and os.path.exists(font_path)) else 0,
        }
    except Exception as e:
        diag['fonts']['noto_sans_tamil'] = {'found': False, 'error': str(e)}

    # 3. Check Headless Browser
    try:
        from pawnshop_management.fonts import find_browser_executable
        browser_exe = find_browser_executable()
        diag['browser'] = {
            'found': bool(browser_exe),
            'path': browser_exe or 'None found (Falling back to pure Python xhtml2pdf)',
        }
    except Exception as e:
        diag['browser'] = {'found': False, 'error': str(e)}

    # 4. Run live PDF rendering test
    test_html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: 'Helvetica', 'Arial', sans-serif; font-size: 14px; color: #1e3a8a; }
  h1 { color: #002f6c; }
  .box { border: 2px solid #002f6c; padding: 15px; border-radius: 8px; }
  .tamil { font-family: 'NotoSansTamil', serif; }
</style>
</head>
<body>
<div class="box">
  <h1>First Money Gold - Diagnostic Test PDF</h1>
  <p>Status: All engines operational.</p>
  <p class="tamil">தமிழ் எழுத்துரு சோதனை: முதல் பணம் தங்கம் அடகு மேலாண்மை அமைப்பு.</p>
  <p>Timestamp: Automated PDF Generator Test</p>
</div>
</body>
</html>"""

    try:
        from pawnshop_management.fonts import render_html_to_pdf_bytes
        # Clear cache for honest probe
        pdf_bytes = render_html_to_pdf_bytes(test_html)
        if pdf_bytes and len(pdf_bytes) > 500:
            diag['pdf_test'] = {
                'success': True,
                'pdf_size_bytes': len(pdf_bytes),
                'message': f'PDF generation successful ({len(pdf_bytes):,} bytes generated).'
            }
        else:
            diag['pdf_test'] = {
                'success': False,
                'pdf_size_bytes': len(pdf_bytes) if pdf_bytes else 0,
                'message': 'PDF generator returned empty or null output.'
            }
    except Exception as e:
        diag['pdf_test'] = {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'message': f'PDF generation failed with exception: {e}'
        }

    return diag


def get_recent_logs(max_lines=80):
    """Read recent lines from django.log."""
    log_file = getattr(settings, 'LOGS_DIR', settings.BASE_DIR / 'logs') / 'django.log'
    if not os.path.exists(log_file):
        return f"Log file not found at: {log_file}"
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            return ''.join(lines[-max_lines:])
    except Exception as e:
        return f"Error reading log file: {e}"


@csrf_exempt
def pdf_status_view(request):
    """
    Public / Staff diagnostic endpoint for PDF status.
    URL: /pdf-status/ or /system-diagnostics/
    """
    # Permission check for sensitive actions or full view
    is_authorized = is_staff_or_valid_token(request)

    # Action: Run Pip Install for PDF dependencies
    pip_output = None
    if request.method == 'POST' and request.POST.get('action') == 'install_pdf_packages':
        if not is_authorized:
            return JsonResponse({'error': 'Unauthorized. Staff login or secret token required.'}, status=403)
        try:
            cmd = [sys.executable, "-m", "pip", "install", "xhtml2pdf>=0.2.13", "reportlab>=4.0.0"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            pip_output = {
                'returncode': res.returncode,
                'stdout': res.stdout,
                'stderr': res.stderr,
                'success': res.returncode == 0
            }
        except Exception as e:
            pip_output = {'success': False, 'error': str(e)}

    # Action: Download test PDF
    if request.GET.get('action') == 'download_test_pdf':
        try:
            from pawnshop_management.fonts import render_html_to_pdf_bytes
            test_html = "<h1>First Money Gold - Diagnostic Test PDF</h1><p>Rendering is working correctly.</p>"
            pdf = render_html_to_pdf_bytes(test_html)
            if pdf:
                resp = HttpResponse(pdf, content_type='application/pdf')
                resp['Content-Disposition'] = 'attachment; filename="fmg_test_diagnostic.pdf"'
                return resp
            return HttpResponse("PDF generation returned null bytes.", status=500)
        except Exception as e:
            return HttpResponse(f"Error generating test PDF: {e}<pre>{traceback.format_exc()}</pre>", status=500)

    diag = get_pdf_diagnostics()

    if request.GET.get('format') == 'json':
        return JsonResponse(diag, safe=False)

    recent_logs = get_recent_logs(80) if is_authorized else "Log inspection requires staff authentication."

    # Build sleek HTML status dashboard
    status_badge = '<span style="background:#16a34a;color:#fff;padding:4px 12px;border-radius:9999px;font-weight:bold;">OPERATIONAL</span>' if diag['pdf_test'].get('success') else '<span style="background:#dc2626;color:#fff;padding:4px 12px;border-radius:9999px;font-weight:bold;">ACTION REQUIRED</span>'

    pkg_rows = ""
    for pkg, info in diag['packages'].items():
        is_ok = info.get('status') == 'OK'
        badge = '<span style="color:#16a34a;font-weight:bold;">&#10004; Installed</span>' if is_ok else '<span style="color:#dc2626;font-weight:bold;">&#10008; Missing</span>'
        detail = info.get('version', info.get('error', ''))
        pkg_rows += f"<tr><td style='padding:8px;border-bottom:1px solid #e2e8f0;'><strong>{pkg}</strong></td><td style='padding:8px;border-bottom:1px solid #e2e8f0;'>{badge}</td><td style='padding:8px;border-bottom:1px solid #e2e8f0;font-family:monospace;font-size:12px;'>{detail}</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FMG ERP - PDF & System Diagnostics</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background:#f8fafc; color:#1e293b; margin:0; padding:24px; }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  .card {{ background:#ffffff; border-radius:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.1); padding:24px; margin-bottom:24px; border:1px solid #e2e8f0; }}
  h1, h2, h3 {{ color:#0f172a; margin-top:0; }}
  .header {{ display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #e2e8f0; padding-bottom:16px; margin-bottom:20px; }}
  table {{ width:100%; border-collapse:collapse; text-align:left; }}
  th {{ background:#f1f5f9; padding:10px 8px; font-weight:600; font-size:13px; text-transform:uppercase; letter-spacing:0.5px; border-bottom:2px solid #cbd5e1; }}
  .btn {{ display:inline-block; padding:8px 16px; border-radius:6px; font-weight:600; text-decoration:none; cursor:pointer; border:none; }}
  .btn-primary {{ background:#2563eb; color:#fff; }}
  .btn-success {{ background:#16a34a; color:#fff; }}
  .btn-danger {{ background:#dc2626; color:#fff; }}
  pre {{ background:#0f172a; color:#38bdf8; padding:16px; border-radius:8px; overflow-x:auto; font-size:12px; line-height:1.4; }}
  .alert {{ padding:12px 16px; border-radius:8px; margin-bottom:16px; }}
  .alert-success {{ background:#dcfce7; border:1px solid #86efac; color:#166534; }}
  .alert-danger {{ background:#fee2e2; border:1px solid #fca5a5; color:#991b1b; }}
</style>
</head>
<body>
<div class="container">
  <div class="card">
    <div class="header">
      <div>
        <h1>FMG ERP System Diagnostics</h1>
        <p style="margin:0;color:#64748b;">PDF Generation, Environment & Server Health Console</p>
      </div>
      <div>{status_badge}</div>
    </div>

    {f'<div class="alert alert-success"><strong>Pip Install Output:</strong><pre>{pip_output["stdout"] or pip_output.get("error")}</pre></div>' if pip_output and pip_output.get('success') else ''}
    {f'<div class="alert alert-danger"><strong>Pip Install Error:</strong><pre>{pip_output.get("stderr") or pip_output.get("error")}</pre></div>' if pip_output and not pip_output.get('success') else ''}

    <h2>1. Live PDF Generation Test</h2>
    <div style="padding:16px;border-radius:8px;background:{'#f0fdf4;border:1px solid #bbf7d0;' if diag['pdf_test'].get('success') else '#fef2f2;border:1px solid #fecaca;'}margin-bottom:16px;">
      <p style="margin:0 0 8px 0;font-weight:600;color:{'#166534' if diag['pdf_test'].get('success') else '#991b1b'};">
        {diag['pdf_test'].get('message')}
      </p>
      {f'<pre style="color:#f87171;">{diag["pdf_test"].get("traceback") or diag["pdf_test"].get("error")}</pre>' if not diag['pdf_test'].get('success') and diag['pdf_test'].get('error') else ''}
      <div style="margin-top:12px;">
        <a href="?action=download_test_pdf" class="btn btn-primary" target="_blank">&#8595; Download Sample Test PDF</a>
      </div>
    </div>

    <h2>2. PDF Engine & Python Dependencies</h2>
    <table>
      <thead>
        <tr><th>Package</th><th>Status</th><th>Version / Path</th></tr>
      </thead>
      <tbody>
        {pkg_rows}
        <tr>
          <td style='padding:8px;border-bottom:1px solid #e2e8f0;'><strong>Tamil Font (NotoSansTamil)</strong></td>
          <td style='padding:8px;border-bottom:1px solid #e2e8f0;'>{'<span style="color:#16a34a;font-weight:bold;">&#10004; Found</span>' if diag['fonts']['noto_sans_tamil']['found'] else '<span style="color:#dc2626;font-weight:bold;">&#10008; Missing</span>'}</td>
          <td style='padding:8px;border-bottom:1px solid #e2e8f0;font-family:monospace;font-size:12px;'>{diag['fonts']['noto_sans_tamil'].get('path')} ({diag['fonts']['noto_sans_tamil'].get('size_bytes', 0):,} bytes)</td>
        </tr>
        <tr>
          <td style='padding:8px;border-bottom:1px solid #e2e8f0;'><strong>Headless Chromium</strong></td>
          <td style='padding:8px;border-bottom:1px solid #e2e8f0;'>{'<span style="color:#16a34a;font-weight:bold;">&#10004; Found</span>' if diag['browser']['found'] else '<span style="color:#eab308;font-weight:bold;">&#9888; Not in Shared Host</span>'}</td>
          <td style='padding:8px;border-bottom:1px solid #e2e8f0;font-family:monospace;font-size:12px;'>{diag['browser'].get('path')}</td>
        </tr>
      </tbody>
    </table>

    <div style="margin-top:20px;padding:16px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;">
      <h3 style="margin-bottom:8px;">Fix / Install Missing PDF Libraries on cPanel:</h3>
      <p style="font-size:13px;color:#475569;margin-bottom:12px;">
        If <code>xhtml2pdf</code> or <code>reportlab</code> is missing, click below to install directly or run in cPanel terminal:
      </p>
      <form method="POST" style="display:inline-block;">
        <input type="hidden" name="action" value="install_pdf_packages">
        <button type="submit" class="btn btn-success">&#9881; Run Pip Install (xhtml2pdf & reportlab)</button>
      </form>
    </div>
  </div>

  <div class="card">
    <h2>3. System Environment Info</h2>
    <p><strong>Python Executable:</strong> <code>{diag['python_executable']}</code></p>
    <p><strong>Base Directory:</strong> <code>{diag['base_dir']}</code></p>
    <p><strong>Python Version:</strong> <code>{diag['python_version']}</code></p>
  </div>

  <div class="card">
    <h2>4. Recent Server Logs (django.log)</h2>
    <pre>{recent_logs}</pre>
  </div>
</div>
</body>
</html>"""
    return HttpResponse(html, content_type='text/html')
