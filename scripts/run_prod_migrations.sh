#!/bin/bash
# Script to run all migrations in production environment
# Run this as a one-off job in Render.com

set -e  # Exit on error

echo "========================================"
echo "PRODUCTION MIGRATION SCRIPT"
echo "========================================"
echo "Starting at $(date)"

# Set environment variables
export DJANGO_SETTINGS_MODULE=pawnshop_management.settings
export RENDER=true

# Remove any minimal startup flags
unset SKIP_DB_CHECKS
unset MINIMAL_STARTUP

# Print environment info
echo "Python version: $(python --version)"
echo "Current directory: $(pwd)"
echo "Django settings module: $DJANGO_SETTINGS_MODULE"

# Run the migration script
echo "Running migrations..."
python scripts/run_migrations.py

# Check exit code
if [ $? -eq 0 ]; then
    echo "✅ Migrations completed successfully!"
else
    echo "❌ Migrations failed!"
fi

echo "========================================"
echo "Migration script finished at $(date)"
echo "========================================"