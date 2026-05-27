#!/bin/bash

echo "�� Starting Pawnshop Management System - Development Mode"

echo "=================================================="

# Change to project directory
cd /Users/sku316/Documents/Final_projects/pawnshop

# Activate virtual environment
echo "📦 Activating virtual environment..."
source pawnshop_env/bin/activate

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment activated: $VIRTUAL_ENV"
else
    echo "❌ Failed to activate virtual environment"
    exit 1
fi

# Set Django settings
export DJANGO_SETTINGS_MODULE=pawnshop_management.settings
export PYTHONPATH="$PYTHONPATH:$(pwd)"

# Check database and run migrations if needed
echo "🔧 Checking database..."
python manage.py migrate --check || {
    echo "📊 Running database migrations..."
    python manage.py migrate
}

# Collect static files for development
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Start development server
echo "🌐 Starting Django development server..."
echo "📍 Server will be available at: http://localhost:8001"
echo "�� Press Ctrl+C to stop the server"
echo "=================================================="

python manage.py runserver 0.0.0.0:8000
