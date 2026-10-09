#!/usr/bin/env python3
"""
requirements.py — Dependency Checker, Installer & Verifier for Pawnshop ERP
===========================================================================
This utility inspects all project dependencies, identifies missing packages in
local or production (cPanel, Render, VPS, PythonAnywhere), and can automatically
install or verify them.

Usage:
  python requirements.py               # Check all dependencies and display report
  python requirements.py --check       # Detailed audit of installed vs required
  python requirements.py --install     # Automatically install all missing packages
  python requirements.py --minimal     # Install only essential lightweight packages
  python requirements.py --verify      # Verify that all project modules can be imported
  python requirements.py --export      # Export clean requirements.txt and requirements-minimal.txt
"""

import sys
import os
import re
import subprocess
import importlib
import importlib.metadata
import argparse

# -----------------------------------------------------------------------------
# Dependency Definitions with Metadata and Purpose
# -----------------------------------------------------------------------------

# Category 1: Core Framework & API
CORE_REQUIREMENTS = {
    'Django': {
        'spec': 'django>=5.2.0,<6.0',
        'import_name': 'django',
        'desc': 'Core Django web framework (v5.2)',
        'required': True,
    },
    'djangorestframework': {
        'spec': 'djangorestframework>=3.16.0',
        'import_name': 'rest_framework',
        'desc': 'REST API framework for mobile & external endpoints',
        'required': True,
    },
    'djangorestframework-simplejwt': {
        'spec': 'djangorestframework-simplejwt>=5.3.0',
        'import_name': 'rest_framework_simplejwt',
        'desc': 'JWT authentication tokens for customer portal & API',
        'required': True,
    },
    'djoser': {
        'spec': 'djoser>=2.2.2',
        'import_name': 'djoser',
        'desc': 'REST auth endpoints (login, register, password reset)',
        'required': True,
    },
    'django-cors-headers': {
        'spec': 'django-cors-headers>=4.0.0',
        'import_name': 'corsheaders',
        'desc': 'Cross-Origin Resource Sharing for API requests',
        'required': True,
    },
    'django-crispy-forms': {
        'spec': 'django-crispy-forms>=2.0',
        'import_name': 'crispy_forms',
        'desc': 'Bootstrap form rendering & crispy tag helpers',
        'required': True,
    },
    'crispy-bootstrap5': {
        'spec': 'crispy-bootstrap5>=2023.10',
        'import_name': 'crispy_bootstrap5',
        'desc': 'Bootstrap 5 template pack for crispy forms',
        'required': True,
    },
    'django-filter': {
        'spec': 'django-filter>=25.0',
        'import_name': 'django_filters',
        'desc': 'Dynamic query filtering for loans, inventory & customers',
        'required': True,
    },
    'python-dotenv': {
        'spec': 'python-dotenv>=1.0.0',
        'import_name': 'dotenv',
        'desc': 'Loads configuration from .env files',
        'required': True,
    },
    'django-environ': {
        'spec': 'django-environ>=0.11.0',
        'import_name': 'environ',
        'desc': 'Environment variable parsing helper',
        'required': True,
    },
    'whitenoise': {
        'spec': 'whitenoise>=6.6.0',
        'import_name': 'whitenoise',
        'desc': 'Production static file serving with gzip compression',
        'required': True,
    },
    'gunicorn': {
        'spec': 'gunicorn>=20.1.0',
        'import_name': 'gunicorn',
        'desc': 'WSGI HTTP Server for production Linux / Render / VPS',
        'required': False,
    },
}

# Category 2: Database Drivers
DATABASE_REQUIREMENTS = {
    'dj-database-url': {
        'spec': 'dj-database-url>=2.1.0',
        'import_name': 'dj_database_url',
        'desc': 'DATABASE_URL configuration parsing (Postgres/Neon/MySQL)',
        'required': True,
    },
    'psycopg2-binary': {
        'spec': 'psycopg2-binary>=2.9.0',
        'import_name': 'psycopg2',
        'desc': 'PostgreSQL driver for Neon / RDS / Cloud Postgres',
        'required': False,
    },
    'mysql-connector-python': {
        'spec': 'mysql-connector-python>=8.0.0',
        'import_name': 'mysql.connector',
        'desc': 'MySQL driver for cPanel MySQL / MariaDB',
        'required': False,
    },
    'pymysql': {
        'spec': 'pymysql>=1.1.0',
        'import_name': 'pymysql',
        'desc': 'Pure Python MySQL driver alternative for cPanel',
        'required': False,
    },
    'cryptography': {
        'spec': 'cryptography>=42.0.0',
        'import_name': 'cryptography',
        'desc': 'SSL/TLS encryption & JWT security support',
        'required': True,
    },
}

# Category 3: Document, Image, PDF & Excel Processing
DOCUMENT_REQUIREMENTS = {
    'Pillow': {
        'spec': 'Pillow>=11.0.0',
        'import_name': 'PIL',
        'desc': 'Image processing for customer photos, item KYC & receipts',
        'required': True,
    },
    'reportlab': {
        'spec': 'reportlab>=4.0.0',
        'import_name': 'reportlab',
        'desc': 'High-performance PDF generation engine & canvas drawing',
        'required': True,
    },
    'xhtml2pdf': {
        'spec': 'xhtml2pdf>=0.2.13',
        'import_name': 'xhtml2pdf',
        'desc': 'HTML to PDF bill, pawn receipt & loan document generation',
        'required': True,
    },
    'num2words': {
        'spec': 'num2words>=0.5.12',
        'import_name': 'num2words',
        'desc': 'Converts numbers to words (e.g. Rupees in English/Tamil)',
        'required': True,
    },
    'openpyxl': {
        'spec': 'openpyxl>=3.1.0',
        'import_name': 'openpyxl',
        'desc': 'Excel read/write for bulk imports and loan statements',
        'required': True,
    },
    'xlsxwriter': {
        'spec': 'xlsxwriter>=3.2.0',
        'import_name': 'xlsxwriter',
        'desc': 'High-speed Excel generation for GST GSTR-1 / GSTR-3B reports',
        'required': True,
    },
}

# Category 4: Multi-Language & Translation
LANGUAGE_REQUIREMENTS = {
    'polib': {
        'spec': 'polib>=1.1.0',
        'import_name': 'polib',
        'desc': 'Compiles .po translation files into .mo binary catalogs (Tamil)',
        'required': True,
    },
    'indic-transliteration': {
        'spec': 'indic-transliteration>=2.3.79',
        'import_name': 'indic_transliteration',
        'desc': 'English-to-Tamil phonetic transliteration for names/search',
        'required': True,
    },
}

# Category 5: External Integrations & Automations
INTEGRATION_REQUIREMENTS = {
    'requests': {
        'spec': 'requests>=2.28.0',
        'import_name': 'requests',
        'desc': 'HTTP client for Brevo Email API, Gemini AI & Gold Rates',
        'required': True,
    },
    'beautifulsoup4': {
        'spec': 'beautifulsoup4>=4.12.0',
        'import_name': 'bs4',
        'desc': 'Scrapes live Chennai retail gold prices from market feeds',
        'required': True,
    },
    'qrcode': {
        'spec': 'qrcode>=8.0',
        'import_name': 'qrcode',
        'desc': 'Generates dynamic UPI QR codes on loan bills & receipts',
        'required': True,
    },
    'pywhatkit': {
        'spec': 'pywhatkit>=5.4',
        'import_name': 'pywhatkit',
        'desc': 'WhatsApp notifications & marketing message dispatch',
        'required': False,
    },
    'playwright': {
        'spec': 'playwright>=1.40.0',
        'import_name': 'playwright',
        'desc': 'Headless browser automation for marketing & PDF fallback',
        'required': False,
    },
}

ALL_GROUPS = [
    ("Core Framework & Web API", CORE_REQUIREMENTS),
    ("Database Drivers & Security", DATABASE_REQUIREMENTS),
    ("Document, PDF, Image & Excel Processing", DOCUMENT_REQUIREMENTS),
    ("Multi-Language & Transliteration (Tamil/English)", LANGUAGE_REQUIREMENTS),
    ("Integrations, Live Gold Rates & WhatsApp", INTEGRATION_REQUIREMENTS),
]


def normalize_pkg_name(name):
    """Normalize package name to lowercase alphanumeric format."""
    return re.split(r'[<>=!~]', name)[0].strip().lower().replace('_', '-')


def get_installed_packages():
    """Returns a dict of {normalized_pkg_name: installed_version}."""
    installed = {}
    for dist in importlib.metadata.distributions():
        try:
            norm_name = normalize_pkg_name(dist.metadata['Name'])
            installed[norm_name] = dist.version
        except Exception:
            continue
    return installed


def check_dependencies():
    """Audits all dependencies and prints an informative table."""
    installed = get_installed_packages()
    missing_required = []
    missing_optional = []
    installed_count = 0
    total_count = 0

    print("=" * 80)
    print(" PAWNSHOP ERP — PRODUCTION & LOCAL DEPENDENCY STATUS AUDIT")
    print("=" * 80)
    print(f"Python Version: {sys.version.split()[0]} ({sys.executable})")
    print(f"Platform:       {sys.platform}")
    print("-" * 80)

    for group_name, group_dict in ALL_GROUPS:
        print(f"\n[{group_name}]")
        print(f"{'Package':<28} {'Status':<12} {'Installed':<15} {'Description'}")
        print("-" * 80)
        for pkg_name, info in group_dict.items():
            total_count += 1
            norm_name = normalize_pkg_name(pkg_name)
            ver = installed.get(norm_name)
            is_installed = ver is not None

            # Secondary check: try importing module directly
            if not is_installed:
                try:
                    importlib.import_module(info['import_name'].split('.')[0])
                    is_installed = True
                    ver = "available"
                except Exception:
                    pass

            if is_installed:
                installed_count += 1
                status = " OK"
                ver_display = ver[:14]
            else:
                if info['required']:
                    status = "! MISSING"
                    missing_required.append((pkg_name, info))
                else:
                    status = "- OPTIONAL"
                    missing_optional.append((pkg_name, info))
                ver_display = "Not Installed"

            print(f"{pkg_name:<28} {status:<12} {ver_display:<15} {info['desc']}")

    print("\n" + "=" * 80)
    print(f"SUMMARY: {installed_count}/{total_count} packages available.")
    if missing_required:
        print(f"\n[!] {len(missing_required)} REQUIRED packages are MISSING in this environment:")
        for pkg_name, info in missing_required:
            print(f"    - {pkg_name} ({info['spec']}) -> {info['desc']}")
        print("\nTo install all missing packages automatically, run:")
        print(f"    {sys.executable} requirements.py --install")
    else:
        print("\n[SUCCESS] All required packages are installed and ready!")

    if missing_optional:
        print(f"\n[*] {len(missing_optional)} Optional packages not installed (can install if needed):")
        for pkg_name, info in missing_optional:
            print(f"    - {pkg_name} ({info['spec']}) -> {info['desc']}")
    print("=" * 80)

    return len(missing_required) == 0


def install_missing(only_minimal=False):
    """Installs missing packages using pip."""
    installed = get_installed_packages()
    to_install = []

    for group_name, group_dict in ALL_GROUPS:
        for pkg_name, info in group_dict.items():
            if only_minimal and not info['required']:
                continue
            norm_name = normalize_pkg_name(pkg_name)
            if norm_name not in installed:
                # Check import fallback
                try:
                    importlib.import_module(info['import_name'].split('.')[0])
                    continue
                except Exception:
                    pass
                to_install.append(info['spec'])

    if not to_install:
        print("\n[OK] No missing packages to install. All dependencies are already satisfied!")
        return True

    print(f"\n--> Installing {len(to_install)} missing packages via pip...")
    for pkg in to_install:
        print(f"    + Installing {pkg}...")
        cmd = [sys.executable, "-m", "pip", "install", pkg]
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"    [WARNING] Failed to install {pkg}. Continuing with others...")

    print("\n--> Installation complete. Re-checking dependencies...")
    return check_dependencies()


def verify_project_imports():
    """Imports all Django apps and views to guarantee zero missing modules."""
    print("\n--> Verifying full project module integrity...")
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
    try:
        import django
        django.setup()
        print("    [OK] Django initialized successfully.")
    except Exception as e:
        print(f"    [ERROR] Django initialization failed: {e}")
        return False

    project_root = os.path.dirname(os.path.abspath(__file__))
    successful = 0
    failed = []

    for dirpath, _, filenames in os.walk(project_root):
        if any(p in dirpath for p in ['.git', '.vscode', '__pycache__', 'staticfiles', 'node_modules', '.agents', '.whatsapp_user_data', 'scratch']):
            continue
        for f in filenames:
            if f.endswith('.py') and not f.startswith('00'):
                rel_path = os.path.relpath(os.path.join(dirpath, f), project_root)
                mod_name = rel_path.replace(os.path.sep, '.')[:-3]
                try:
                    importlib.import_module(mod_name)
                    successful += 1
                except Exception as exc:
                    failed.append((mod_name, str(exc)))

    print(f"    [OK] {successful} modules imported without errors.")
    if failed:
        print(f"\n[!] {len(failed)} import errors encountered:")
        for mod, err in failed:
            print(f"    - {mod}: {err}")
        return False
    else:
        print("[SUCCESS] All project modules imported cleanly with ZERO errors!")
        return True


def export_requirements_files():
    """Exports updated requirements.txt and requirements-minimal.txt."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    req_file = os.path.join(project_root, "requirements.txt")
    min_file = os.path.join(project_root, "requirements-minimal.txt")

    # Full requirements.txt
    lines = [
        "# =============================================================================",
        "# PAWNSHOP ERP — COMPLETE PRODUCTION REQUIREMENTS (Django 5.2)",
        "# Generated & validated for local development and cloud/cPanel hosting",
        "# =============================================================================",
        "",
    ]
    for group_name, group_dict in ALL_GROUPS:
        lines.append(f"# --- {group_name} ---")
        for pkg_name, info in group_dict.items():
            if info['required']:
                lines.append(f"{info['spec']:<35} # {info['desc']}")
            else:
                lines.append(f"{info['spec']:<35} # (Optional) {info['desc']}")
        lines.append("")

    with open(req_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines).strip() + "\n")
    print(f"    [OK] Updated: {req_file}")

    # Minimal requirements-minimal.txt (all essential required packages for memory-light deploys)
    min_lines = [
        "# =============================================================================",
        "# PAWNSHOP ERP — ESSENTIAL LIGHTWEIGHT REQUIREMENTS",
        "# Includes all mandatory core modules required for zero-error runtime execution",
        "# =============================================================================",
        "",
    ]
    for group_name, group_dict in ALL_GROUPS:
        req_items = [info for info in group_dict.values() if info['required']]
        if req_items:
            min_lines.append(f"# --- {group_name} ---")
            for info in req_items:
                min_lines.append(f"{info['spec']:<35} # {info['desc']}")
            min_lines.append("")

    with open(min_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(min_lines).strip() + "\n")
    print(f"    [OK] Updated: {min_file}")


def main():
    parser = argparse.ArgumentParser(description="Pawnshop ERP Dependency Checker & Manager")
    parser.add_argument('--check', action='store_true', help="Check dependency status (default)")
    parser.add_argument('--install', action='store_true', help="Install all missing required & optional packages")
    parser.add_argument('--minimal', action='store_true', help="Install only essential required packages")
    parser.add_argument('--verify', action='store_true', help="Verify that all Django modules can be imported")
    parser.add_argument('--export', action='store_true', help="Regenerate requirements.txt and requirements-minimal.txt")

    args = parser.parse_args()

    if args.export:
        export_requirements_files()
    elif args.install:
        install_missing(only_minimal=False)
    elif args.minimal:
        install_missing(only_minimal=True)
    elif args.verify:
        verify_project_imports()
    else:
        check_dependencies()


if __name__ == '__main__':
    main()
