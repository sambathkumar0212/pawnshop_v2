# Complete Guide: Deploying Pawnshop ERP on cPanel

This guide provides a comprehensive walkthrough for deploying the **Pawnshop ERP (Django 5)** to a cPanel shared or cloud hosting account using **cPanel's "Setup Python App"** (powered by Phusion Passenger).

---

## 📋 Overview of Files Included for cPanel

We have added all necessary files to the repository:
1. `passenger_wsgi.py` - WSGI bridge connecting cPanel's Passenger server to Django.
2. `.htaccess` - Configured for static asset delivery, caching, and security (blocks direct downloads of `.env` or database files).
3. `.cpanel.yml` - Automated deployment file for cPanel Git Version Control.
4. `package_for_cpanel.bat` & `package_for_cpanel.py` - One-click script to create a clean `pawnshop_v2_cpanel.zip` file ready to upload.

---

## 🔍 Pre-Deployment Check: Does Your cPanel Support Python?

1. Log into your **cPanel**.
2. Search for **"Setup Python App"** (under the **Software** section).
   - If visible: Your hosting plan supports running Django directly.
   - If missing: Your hosting plan only supports PHP/Static files. Contact your hosting support to enable CloudLinux Python selector, or use [PythonAnywhere](file:///d:/Hari_files/FirstMoneyGold/software_apps/pawnshop_v2/PYTHONANYWHERE_DEPLOYMENT_GUIDE.md) / Render.

---

## 🚀 Step-by-Step Deployment Instructions

### Step 1: Create the Python App in cPanel
1. In cPanel, click **Setup Python App**.
2. Click **Create Application**.
3. Fill in the following settings:
   - **Python version**: Select `3.10` or `3.11`.
   - **Application root**: `pawnshop_v2` *(This is the folder where your files will live in `/home/username/`)*.
   - **Application URL**: Select your domain or subdomain (e.g. `erp.yourdomain.com` or `yourdomain.com`).
   - **Application startup file**: `passenger_wsgi.py`
   - **Application Entry point**: `application`
4. Click **Create** at the top right.
5. Once created, notice the command displayed at the top:
   ```bash
   source /home/username/virtualenv/pawnshop_v2/3.11/bin/activate && cd /home/username/pawnshop_v2
   ```
   *(Keep this command handy; you will need it in Step 4).*

---

### Step 2: Package and Upload the Project Files

#### Option A: Quick Upload via ZIP (Recommended)
1. On your local Windows computer, open the project folder and double-click:
   ```cmd
   package_for_cpanel.bat
   ```
   *This automatically runs `collectstatic` and packages the project into `pawnshop_v2_cpanel.zip` while excluding cache, `.git`, and test files.*
2. In cPanel, go to **File Manager**.
3. Navigate to `/home/username/pawnshop_v2/`.
4. Click **Upload** $\rightarrow$ select `pawnshop_v2_cpanel.zip`.
5. Once uploaded, right-click the zip file $\rightarrow$ click **Extract**.
6. Delete the uploaded `.zip` file to save disk space.

#### Option B: Deploy via cPanel Git Version Control
1. In cPanel, open **Git™ Version Control**.
2. Click **Create** $\rightarrow$ Clone URL: `https://github.com/sambathkumar0212/pawnshop_v2.git`.
3. Set Repository Path: `/home/username/pawnshop_v2`.
4. Because `.cpanel.yml` is present in the repository, clicking **Deploy HEAD Commit** will automatically deploy all files.

---

### Step 3: Configure Environment Variables (`.env`)

In cPanel **File Manager**:
1. Check the box to "Show Hidden Files" in File Manager settings.
2. Inside `/home/username/pawnshop_v2/`, create or edit `.env`.
3. Set your production values:

```env
DJANGO_ENV=production
DEBUG=False
SECRET_KEY=generate-a-strong-random-key-here-12345
ALLOWED_HOSTS=127.0.0.1,localhost,yourdomain.com,erp.yourdomain.com

# Timezone & Currency
TIME_ZONE=Asia/Kolkata

# Database: SQLite is default and simplest. For MySQL, see Database section below.
DATABASE_ENGINE=django.db.backends.sqlite3
DATABASE_NAME=db.sqlite3
```

---

### Step 4: Install Dependencies & Run Database Migrations

1. In cPanel, open **Terminal** (under the **Advanced** section).
2. Paste the virtual environment command you copied in Step 1 and press **Enter**:
   ```bash
   source /home/username/virtualenv/pawnshop_v2/3.11/bin/activate && cd /home/username/pawnshop_v2
   ```
3. Upgrade pip and install the project requirements:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. Run database migrations:
   ```bash
   python manage.py migrate
   ```
5. Create an initial Superuser / Admin account:
   ```bash
   python manage.py createsuperuser
   ```
6. Pre-collect static assets (CSS, JS, images):
   ```bash
   python manage.py collectstatic --noinput
   ```

---

### Step 5: Restart the Application

1. Go back to **cPanel** $\rightarrow$ **Setup Python App**.
2. Locate `pawnshop_v2` in the applications list.
3. Click the **Restart** (🔄) button.

Visit your domain (e.g., `https://erp.yourdomain.com`) in your web browser. Your Pawnshop ERP is now live!

---

## 🗄️ Optional: Connecting to cPanel MySQL Database

If you prefer MySQL over SQLite:
1. In cPanel, go to **MySQL® Databases**.
2. Create a new database (e.g., `username_pawnshop`) and database user with full privileges.
3. Install `mysqlclient` or `pymysql` in your cPanel Terminal:
   ```bash
   pip install pymysql
   ```
4. Update your `/home/username/pawnshop_v2/.env` file:
   ```env
   DATABASE_ENGINE=django.db.backends.mysql
   DATABASE_NAME=username_pawnshop
   DATABASE_USER=username_pawnuser
   DATABASE_PASSWORD=your_secure_password
   DATABASE_HOST=localhost
   DATABASE_PORT=3306
   ```
5. Run migrations: `python manage.py migrate`.

---

## 🛠️ Troubleshooting Common cPanel Issues

### 1. "500 Internal Server Error"
- **Cause**: Python syntax error, missing package, or unhandled exception.
- **Fix**: Check Passenger error log:
  1. In File Manager, look for `stderr.log` inside `/home/username/pawnshop_v2/`.
  2. Or check `passenger.log` in `/home/username/logs/`.
  3. Ensure `ALLOWED_HOSTS` in `.env` includes your exact domain.

### 2. Static CSS / JavaScript not loading
- **Cause**: Static files not collected or `.htaccess` missing.
- **Fix**:
  1. Run `python manage.py collectstatic --noinput` in cPanel Terminal.
  2. Ensure the `.htaccess` file is present in your domain's document root (e.g., `public_html/` or subdomain directory).
  3. The included `settings.py` already includes **WhiteNoise**, which automatically serves static files even if Apache rewrite rules are bypassed.

### 3. Restarting the App After Code Changes
Whenever you update files in cPanel, trigger a reload by running:
```bash
touch /home/username/pawnshop_v2/tmp/restart.txt
```
Or click the **Restart** button in cPanel's **Setup Python App** interface.
