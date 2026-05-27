# Deploying to Google Cloud Platform

This document provides instructions for deploying the Pawnshop Management System to Google Cloud Platform (GCP).

## Prerequisites

1. A Google Cloud Platform account
2. Google Cloud SDK installed and configured
3. A GCP project created and billing enabled

## Deployment Options

### Option 1: Google App Engine Flexible Environment (Recommended)

#### Step 1: Prepare your GCP environment

1. Create a Google Cloud Project:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable billing for the project

2. Install and initialize the Google Cloud SDK:
   ```bash
   # Download and install the Google Cloud SDK
   # Follow instructions at: https://cloud.google.com/sdk/docs/install
   
   # Initialize the SDK
   gcloud init
   ```

#### Step 2: Configure the application

The `app.yaml` file has already been created with the necessary configuration for App Engine.

#### Step 3: Deploy the application

1. Update the `deploy_gcp.sh` script with your actual project ID:
   ```bash
   # Edit deploy_gcp.sh and replace YOUR_PROJECT_ID with your actual GCP project ID
   ```

2. Make sure you're authenticated with gcloud:
   ```bash
   gcloud auth login
   ```

3. Run the deployment script:
   ```bash
   ./deploy_gcp.sh
   ```

   Or deploy manually:
   ```bash
   # Collect static files
   python manage.py collectstatic --noinput
   
   # Deploy to App Engine
   gcloud app deploy app.yaml --project=YOUR_PROJECT_ID
   ```

#### Step 4: Access your application

After deployment, your application will be available at:
`https://YOUR_PROJECT_ID.appspot.com`

### Option 2: Google Compute Engine (Virtual Machine)

#### Step 1: Create a Compute Engine instance

1. In the Google Cloud Console, go to Compute Engine > VM instances
2. Click "Create Instance"
3. Configure your instance:
   - Name: pawnshop-app
   - Machine type: e2-medium or higher (2 vCPU, 4 GB memory recommended)
   - Boot disk: Ubuntu 22.04 LTS
   - Firewall: Allow HTTP/HTTPS traffic

#### Step 2: SSH into your instance and install dependencies

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python and other dependencies
sudo apt install -y python3 python3-pip python3-venv nginx

# Install Python development headers (needed for some packages)
sudo apt install -y python3-dev build-essential
```

#### Step 3: Deploy your application

```bash
# Clone your repository
git clone https://github.com/sambathkumar0212/pawnshop.git
cd pawnshop

# Create and activate virtual environment
python3 -m venv pawnshop_env
source pawnshop_env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your settings

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

#### Step 4: Set up Gunicorn and Nginx

Create a Gunicorn configuration file `gunicorn.conf.py`:

```python
bind = "0.0.0.0:8000"
workers = 3
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
```

Create a systemd service file `/etc/systemd/system/pawnshop.service`:

```ini
[Unit]
Description=Gunicorn instance to serve pawnshop
After=network.target

[Service]
User=YOUR_USERNAME
Group=www-data
WorkingDirectory=/home/YOUR_USERNAME/pawnshop
Environment="PATH=/home/YOUR_USERNAME/pawnshop/pawnshop_env/bin"
ExecStart=/home/YOUR_USERNAME/pawnshop/pawnshop_env/bin/gunicorn --config gunicorn.conf.py pawnshop_management.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

Configure Nginx by creating `/etc/nginx/sites-available/pawnshop`:

```nginx
server {
    listen 80;
    server_name YOUR_SERVER_IP;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /home/YOUR_USERNAME/pawnshop;
    }
    
    location /media/ {
        root /home/YOUR_USERNAME/pawnshop;
    }

    location / {
        include proxy_params;
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and start the services:

```bash
# Enable the Nginx configuration
sudo ln -s /etc/nginx/sites-available/pawnshop /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Start and enable the Gunicorn service
sudo systemctl start pawnshop
sudo systemctl enable pawnshop
```

## Additional Considerations

1. **Database**: For production, consider using Google Cloud SQL (PostgreSQL) instead of SQLite:
   ```bash
   # In your .env file for Cloud SQL
   DATABASE_URL=postgres://USER:PASSWORD@/DATABASE_NAME?host=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME
   ```

2. **Security**: 
   - Set `DEBUG=False` in production
   - Use a strong `SECRET_KEY`
   - Configure proper SSL/HTTPS
   - Set up firewall rules in GCP

3. **Monitoring**: 
   - Set up Google Cloud Monitoring for your application
   - Configure logging with Google Cloud Logging

4. **Scaling**: 
   - For App Engine, configure automatic scaling in `app.yaml`
   - For Compute Engine, consider using managed instance groups for horizontal scaling
