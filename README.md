# Pawnshop Management System

A comprehensive Django-based management system for pawn shops with multiple branches, biometric authentication, and extensive reporting capabilities.

[![Run Project (Windows)](https://img.shields.io/badge/Run_Project-Windows_BAT-0078D4?logo=windows&logoColor=white)](./run_project.bat)

## Features

- **Multi-User Access**: Role-based permissions system with different access levels
- **Branch Management**: Track operations across multiple physical locations
- **Inventory Management**: Comprehensive item tracking with appraisal system
- **Loan Processing**: Complete pawn loan life-cycle management
- **Sales Management**: Item sales tracking and reporting
- **Customer Management**: Customer database with biometric identification
- **Biometric Authentication**: Facial recognition for staff and customers
- **Reporting & Analytics**: Customizable reports and interactive dashboards
- **External Integrations**: Connect with POS, accounting, and CRM systems

## Requirements

- Python 3.9+
- Django 5.2+
- Additional dependencies listed in requirements.txt

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/sambathkumar0212/pawnshop.git
   cd pawnshop
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv pawnshop_env
   source pawnshop_env/bin/activate  # On Windows: pawnshop_env\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```
   cp .env.example .env
   # Edit .env file with your database and other settings
   ```

5. Run database migrations:
   ```
   python manage.py migrate
   ```

6. Create a superuser:
   ```
   python manage.py createsuperuser
   ```

7. Run the development server:
   ```
   python manage.py runserver
   ```

8. Access the admin interface at http://127.0.0.1:8000/admin/ and the application at http://127.0.0.1:8000/

## Quick Development Setup

1. Make the setup script executable:
   ```bash
   chmod +x dev_setup.sh
   ```

2. Run the development setup script:
   ```bash
   ./dev_setup.sh
   ```

   This will:
   - Create and activate virtual environment
   - Install dependencies
   - Set up development environment
   - Run migrations
   - Create default superuser (if needed)
   - Start the development server

   Default superuser credentials:
   - Username: admin
   - Password: admin
   - Email: admin@example.com

3. Access the application:
   - Admin interface: http://127.0.0.1:8000/admin/
   - Main application: http://127.0.0.1:8000/

## Getting Started

After installation, follow these steps to set up your pawnshop:

1. **Create Roles**: Define user roles (Admin, Manager, Cashier, etc.)
2. **Create Branches**: Set up your pawnshop locations
3. **Create Users**: Add staff members and assign them to branches
4. **Configure Settings**: Set loan durations, interest rates, biometric settings, etc.
5. **Create Categories**: Set up inventory categories
6. **Start using the system**: Begin recording loans, sales, and inventory

## Biometric Setup

To use facial recognition features:

1. Make sure you have dlib and face_recognition packages properly installed
2. Create required directories:
   ```
   mkdir -p media/faces
   ```

3. Enable biometric settings for your branch in the admin interface

## Deployment

For production deployment:

1. Set `DEBUG=False` in the environment
2. Configure a proper database (PostgreSQL recommended)
3. Set up static files serving with Whitenoise or a web server
4. Use Gunicorn or uWSGI as the application server
5. Set up a reverse proxy with Nginx or Apache

Example Gunicorn command:
```
gunicorn pawnshop_management.wsgi:application --bind 0.0.0.0:8000
```

## Deployment on Render

1. **Push to GitHub**  
   Make sure your code is pushed to a GitHub repository.

2. **Create a Render Web Service**  
   - Log in to [Render](https://render.com).
   - Select "New" and then "Web Service".
   - Connect your GitHub account and select the repository containing this project.

3. **Configure Render Settings**  
   - **Build Command:**  
     ```
     pip install -r requirements.txt && python manage.py migrate
     ```
   - **Start Command:**  
     ```
     gunicorn pawnshop_management.wsgi:application --bind 0.0.0.0:$PORT
     ```
   - **Environment Variables:**  
     Set the necessary variables from your `.env.example` (e.g., `SECRET_KEY`, `ALLOWED_HOSTS`, database settings, etc.) in Render's dashboard.

4. **Deploy**  
   Render will automatically build and deploy your Django application.  
   

## License

[Insert License Information]

## Contact

[Your Contact Information]


## to enter postgresql
psql -d postgres

## To exit
\q

## roles and access 
Administrator - Full system access
Branch Manager - Branch operations and staff management
Loan Officer - Loan processing and valuations
Cashier - Payment processing
Inventory Manager - Item tracking and inventory
Accountant - Financial reporting and analysis
Customer Service - Customer support
Appraiser - Item valuation specialist

To use different environments:

Development: DJANGO_ENV=development python manage.py runserver
Production: DJANGO_ENV=production python manage.py runserver
Don't forget to:

Add both .env files to .gitignore
Install python-dotenv: pip install python-dotenv
Never commit production credentials
Keep a .env.example template in version control

## To Run project in development env
chmod +x dev_setup.sh
./dev_setup.sh
