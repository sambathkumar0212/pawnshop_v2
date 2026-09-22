#!/usr/bin/env bash
set -e

echo "==> Starting build process for Render.com deployment..."

# Set environment variables
export PYTHONPATH="$(pwd):$PYTHONPATH"
export DJANGO_SETTINGS_MODULE=pawnshop_management.settings
export RENDER=true

# Install dependencies from requirements.txt
echo "==> Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

# Install Playwright browser binaries for WhatsApp Web engine
echo "==> Installing Playwright Chromium browser binaries..."
export PLAYWRIGHT_BROWSERS_PATH=0
playwright install --with-deps chromium || playwright install chromium || true

# Run migrations
echo "==> Applying database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "==> Collecting static assets..."
python manage.py collectstatic --noinput

echo "==> ✅ Build completed successfully!"