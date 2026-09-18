# How to Host Pawnshop ERP on PythonAnywhere Free Account

This guide provides a comprehensive, step-by-step walkthrough to deploy and host the **Pawnshop ERP** on a free [PythonAnywhere](https://www.pythonanywhere.com/) account (`<username>.pythonanywhere.com`).

---

## 📋 PythonAnywhere Free Tier Specifications
- **Free Domain/URL**: `https://<username>.pythonanywhere.com`
- **Storage Limit**: 512 MB
- **Database Support**: SQLite (`db.sqlite3`) and free MySQL
- **Certificate**: Free automatic HTTPS (SSL)
- **Maintenance**: Must click **"Run until 3 months from today"** once every 3 months in the Web tab.

---

## 🔗 Project GitHub Repository
* **Repository URL**: `https://github.com/sambathkumar0212/pawnshop_v2.git`
* **Default Branch**: `main`

---

## Step 1: Sync & Push Latest Code to GitHub
In your local computer terminal (VS Code / Antigravity Terminal), sync all latest commits and guides to GitHub:

```bash
git add .
git commit -m "docs: add PythonAnywhere deployment guide and latest updates"
git push origin main
```

---

## Step 2: Open Bash Console on PythonAnywhere & Clone Repo
1. Log in to [PythonAnywhere](https://www.pythonanywhere.com/).
2. Navigate to the **Consoles** tab.
3. Click on **Bash** to launch a new terminal session.
4. Clone this exact repository into your PythonAnywhere account:

```bash
git clone https://github.com/sambathkumar0212/pawnshop_v2.git
cd pawnshop_v2
```

---

## Step 3: Create and Activate Virtual Environment
Inside the PythonAnywhere Bash console, create a Python 3.11 virtual environment:

```bash
# 1. Create a dedicated virtual environment
python3.11 -m venv ~/.virtualenvs/pawnshop-env

# 2. Activate the virtual environment
source ~/.virtualenvs/pawnshop-env/bin/activate
```

---

## Step 4: Install Dependencies
With the virtual environment active, install the required packages:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 5: Configure Environment Variables (`.env`)
Create a production `.env` file in the project root:

```bash
nano .env
```

Paste the following configuration (replace `<username>` with your actual PythonAnywhere username):

```env
DJANGO_ENV=production
DEBUG=False
SECRET_KEY=generate-a-strong-random-key-here-12345
ALLOWED_HOSTS=127.0.0.1,localhost,<username>.pythonanywhere.com
DATABASE_ENGINE=django.db.backends.sqlite3
DATABASE_NAME=db.sqlite3
TIME_ZONE=Asia/Kolkata
```

Save and exit:
- Press `Ctrl + O`, then `Enter` to write the file.
- Press `Ctrl + X` to exit `nano`.

---

## Step 6: Run Migrations and Collect Static Files
Run the standard Django setup commands inside the console:

```bash
# 1. Apply database migrations
python manage.py migrate

# 2. Collect all static assets (CSS, JS, Fonts, Icons)
python manage.py collectstatic --noinput

# 3. Create Super Admin User (if starting with fresh database)
python manage.py createsuperuser
```

---

## Step 7: Configure PythonAnywhere Web Tab

1. Go to the **Web** tab in the top navigation bar of PythonAnywhere.
2. Click the **"Add a new web app"** button.
3. Choose **Manual configuration** (do **NOT** select the Django wizard).
4. Select **Python 3.11**.

### A. Set Code Paths
In the **Code** section:
- **Source code**: `/home/<username>/pawnshop_v2`
- **Working directory**: `/home/<username>/pawnshop_v2`
- **WSGI configuration file**: Click the link `/var/www/<username>_pythonanywhere_com_wsgi.py` to edit it.

### B. Configure WSGI File
Delete all existing contents in `/var/www/<username>_pythonanywhere_com_wsgi.py` and replace with:

```python
import os
import sys

# 1. Add project directory to python sys.path
path = '/home/<username>/pawnshop_v2'
if path not in sys.path:
    sys.path.insert(0, path)

# 2. Load environment variables (.env)
from env_loader import load_env
load_env()

# 3. Set Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'pawnshop_management.settings'

# 4. Expose WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```
*(Replace `<username>` with your PythonAnywhere username).*
Click the green **Save** button in the top right corner.

### C. Set Virtual Environment Path
In the **Virtualenv** section:
- Enter: `/home/<username>/.virtualenvs/pawnshop-env`

### D. Set Static & Media File Mappings
In the **Static files** section, add the following two URL mappings:

| URL | Directory |
| :--- | :--- |
| `/static/` | `/home/<username>/pawnshop_v2/staticfiles` |
| `/media/` | `/home/<username>/pawnshop_v2/media` |

---

## Step 8: Reload and Launch
1. Scroll to the top of the **Web** tab.
2. Click the green **"Reload <username>.pythonanywhere.com"** button.
3. Visit your live site in the browser:
   ```
   https://<username>.pythonanywhere.com/
   ```

---

## 🛠 Troubleshooting & Useful Commands

### Check Error Logs
If you encounter a "500 Internal Server Error" or "Something went wrong", inspect the logs on the **Web** tab:
- **Error log**: `/var/log/<username>.pythonanywhere.com.error.log`
- **Server log**: `/var/log/<username>.pythonanywhere.com.server.log`

### Pulling Updates After Git Push
Whenever you push changes to GitHub, update your live site by running:

```bash
cd ~/pawnshop_v2
git pull origin main
source ~/.virtualenvs/pawnshop-env/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
```
Then click **Reload** in the **Web** tab.
