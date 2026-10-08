"""
package_for_cpanel.py
Automates bundling of Pawnshop Management ERP for cPanel File Manager upload.
Excludes unnecessary development files, virtual environments, caches, and large local databases.
"""
import os
import sys
import zipfile
import subprocess

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_ZIP = os.path.join(PROJECT_DIR, "pawnshop_v2_cpanel.zip")

EXCLUDE_DIRS = {
    ".git",
    ".github",
    ".vscode",
    ".agents",
    ".whatsapp_user_data",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    "scratch",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
}

# Large local development databases - exclude to avoid upload size limits
EXCLUDE_FILES = {
    "pawnshop_v2_cpanel.zip",
    "db.sqlite3",
    "db_kurunchi_shop.sqlite3",
    "PyWhatKit_DB.txt",
}

def collect_static_files():
    print("--> 1. Running 'python manage.py collectstatic --noinput'...")
    try:
        subprocess.run([sys.executable, "manage.py", "collectstatic", "--noinput"], cwd=PROJECT_DIR, check=True)
        print("    [OK] Static files collected successfully.")
    except Exception as e:
        print(f"    [WARNING] Could not collect static files locally ({e}). You can run this on cPanel.")

def create_zip():
    print(f"--> 2. Creating deployment package: {os.path.basename(OUTPUT_ZIP)}...")
    total_files = 0

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(PROJECT_DIR):
            # Prune excluded directories in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith("__pycache__")]

            for file in files:
                if file in EXCLUDE_FILES:
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in EXCLUDE_EXTENSIONS:
                    continue

                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, PROJECT_DIR)

                zip_file.write(abs_path, rel_path)
                total_files += 1

    size_mb = os.path.getsize(OUTPUT_ZIP) / (1024 * 1024)
    print(f"    [OK] Packed {total_files} files into {os.path.basename(OUTPUT_ZIP)} ({size_mb:.2f} MB).")
    print("\n=======================================================")
    print("PACKAGE READY FOR CPANEL UPLOAD!")
    print(f"File location: {OUTPUT_ZIP}")
    print("Steps:")
    print("  1. Log in to cPanel -> File Manager")
    print("  2. Open your application folder (e.g. /home/user/pawnshop_v2)")
    print("  3. Upload 'pawnshop_v2_cpanel.zip' and click Extract")
    print("=======================================================")

if __name__ == "__main__":
    collect_static_files()
    create_zip()
