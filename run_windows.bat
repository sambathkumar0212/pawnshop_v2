@echo off
echo "--- Starting PawnShop Management System on Windows ---"

REM Activate the virtual environment
call pawnshop_env\Scripts\activate.bat

REM Install dependencies
echo "--- Installing dependencies ---"
pip install -r requirements.txt

REM Run database migrations
echo "--- Running database migrations ---"
python manage.py migrate

REM Start the development server in the background
echo "--- Starting the development server ---"
start /b python manage.py runserver

REM Wait a few seconds for the server to start
timeout /t 5 /nobreak >nul

REM Open the default browser
echo "--- Opening the default browser ---"
start http://127.0.0.1:8000/

echo "--- Server is running in the background ---"
echo "--- Press Ctrl+C to stop the server ---"
