# 🚀 Deployment Guide: Neon PostgreSQL + Render Web Service

This guide explains how to deploy the **Pawnshop Management System** using **Neon Serverless PostgreSQL** for persistent storage and **Render** for application hosting.

---

## 📋 Architecture & Status

- **Database**: [Neon.tech](https://neon.tech) PostgreSQL
  - **Status**: ✅ Connected & All 60+ Migrations Successfully Applied!
  - **Host**: `ep-withered-forest-b4p3ff03-pooler.c-6.us-east-2.aws.neon.tech`
  - **Initial Admin**: `admin` / `admin123@Password`
- **Web Application**: [Render.com](https://render.com) (Python 3.11 Web Service running Gunicorn & WhiteNoise)

---

## 🛠️ Deployment Steps

### ✅ Step 1: Neon Database Setup & Migrations (COMPLETED)
- Neon database is active and fully migrated.
- Default Organization (*First Money Gold Pawnshop*), Main Branch, Superuser (*admin*), and Gold Scheme (*Standard Gold Loan Scheme*) are already initialized.

---

### 📍 Step 2: Push Latest Code to GitHub
Run the following commands in your local terminal:

```bash
git add .
git commit -m "Configure Neon PostgreSQL and Render deployment"
git push origin main
```

---

### 📍 Step 3: Create & Deploy Web Service on Render
1. Log in to [https://dashboard.render.com](https://dashboard.render.com).
2. Click **New +** (top right) &rarr; Select **Web Service**.
3. Select your GitHub repository: `sambathkumar0212/pawnshop_v2` (or click *Connect account* if not connected).
4. Fill in the service configuration:
   - **Name**: `pawnshop-app` (or any name you like)
   - **Region**: `Ohio (US East)` (closest to your Neon database in `us-east-2`)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `./build.sh`
   - **Start Command**: `./start.sh`
   - **Instance Type**: `Free`

5. Scroll down to **Environment Variables** and add:

| Key | Value |
|---|---|
| `PYTHON_VERSION` | `3.11.11` |
| `RENDER` | `true` |
| `DJANGO_SETTINGS_MODULE` | `pawnshop_management.settings` |
| `DJANGO_ENV` | `production` |
| `DEBUG` | `False` |
| `SECRET_KEY` | *(Click "Generate" or enter random string)* |
| `DATABASE_URL` | `postgresql://neondb_owner:npg_2q4MUFjyfkzt@ep-withered-forest-b4p3ff03-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require` |
| `DJANGO_SUPERUSER_USERNAME` | `admin` |
| `DJANGO_SUPERUSER_EMAIL` | `admin@firstmoneygold.com` |
| `DJANGO_SUPERUSER_PASSWORD` | `admin123@Password` |

6. Click **Deploy Web Service**.

---

### 📍 Step 4: Access Your Live Application
1. Render will build and deploy your service (usually takes ~2-3 minutes).
2. When the build finishes and displays **`Live`**, click the URL (e.g. `https://pawnshop-app.onrender.com`).
3. Log in with:
   - **Username**: `admin`
   - **Password**: `admin123@Password`
4. Once logged in, you can update your password under `/profile/`.
