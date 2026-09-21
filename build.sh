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

# Run migrations
echo "==> Applying database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "==> Collecting static assets..."
python manage.py collectstatic --noinput

echo "==> ✅ Build completed successfully!"