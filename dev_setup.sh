#!/bin/bash

echo "Setting up development environment..."

# Create and activate virtual environment
python -m venv pawnshop_env
source pawnshop_env/bin/activate

# Install requirements
pip install -r requirements.txt

# Set development environment
export DJANGO_ENV=development

# Run migrations
python manage.py migrate

# Create superuser if it doesn't exist
echo "Creating superuser..."
python manage.py createsuperuser --noinput \
    --username=admin \
    --email=admin@example.com \
    || echo "Superuser already exists"

# Create required directories
mkdir -p transactions/templatetags

# Run development server
echo "Starting development server..."
python manage.py runserver
