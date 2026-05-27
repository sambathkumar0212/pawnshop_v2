#!/bin/bash

# Define variables
VENV_NAME=".venv"
REQUIREMENTS="requirements.txt"

echo "📦 Setting up PawnShop Management System"

# Check if virtual environment exists, create if it doesn't
if [ ! -d "$VENV_NAME" ]; then
    echo "🔧 Creating virtual environment..."
    python3 -m venv $VENV_NAME
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment. Make sure python3-venv is installed."
        exit 1
    fi
    echo "✅ Virtual environment created successfully!"
else
    echo "✅ Virtual environment already exists."
fi

# Activate the virtual environment
echo "🔌 Activating virtual environment..."
source $VENV_NAME/bin/activate

if [ $? -ne 0 ]; then
    echo "❌ Failed to activate virtual environment."
    exit 1
fi
echo "✅ Virtual environment activated."

# Check if requirements.txt exists and install dependencies
if [ -f "$REQUIREMENTS" ]; then
    echo "📥 Installing dependencies from $REQUIREMENTS..."
    pip install -r $REQUIREMENTS
    if [ $? -ne 0 ]; then
        echo "⚠️ Some dependencies may have failed to install."
    else
        echo "✅ Dependencies installed successfully!"
    fi
else
    echo "⚠️ No requirements.txt found. Skipping dependency installation."
fi

# Set PORT environment variable if not already set
if [ -z "$PORT" ]; then
    export PORT=8000
    echo "🔌 Set PORT to default value: $PORT"
fi

# Make start.sh executable if it's not already
if [ ! -x "start.sh" ]; then
    chmod +x start.sh
    echo "✅ Made start.sh executable."
fi

# Run the start script
echo "🚀 Starting the application..."
./start.sh

# Deactivate virtual environment when the script exits
deactivate
