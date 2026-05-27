#!/bin/bash

echo "Deploying to Google App Engine..."

# Collect static files
python manage.py collectstatic --noinput

# Deploy to App Engine
gcloud app deploy app.yaml --project=YOUR_PROJECT_ID

echo "Deployment complete!"
