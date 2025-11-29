#!/bin/bash

# Quick Test Script for FDA Automation
# This script helps you test the automation locally before deploying

echo "=================================================="
echo "FDA Drug Label Automation - Quick Test"
echo "=================================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

echo "✓ Python found: $(python3 --version)"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating one..."
    cat > .env << EOF
SUPABASE_URL=https://bbeubpxzblifptgnsuyi.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJiZXVicHh6YmxpZnB0Z25zdXlpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDM2OTY0NCwiZXhwIjoyMDY1OTQ1NjQ0fQ.So5sfuJO6GygLumfgqU8Qg1SIYE6xD3QZPNu6qCdTCY
EOF
    echo "✓ .env file created"
else
    echo "✓ .env file found"
fi
echo ""

# Install dependencies
echo "Installing dependencies..."
pip3 install -q -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✓ Dependencies installed"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi
echo ""

# Run the script
echo "=================================================="
echo "Running FDA automation script..."
echo "This may take 30-60 minutes depending on your connection"
echo "=================================================="
echo ""

python3 daily_automation.py

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "=================================================="
    echo "✅ SUCCESS! Automation completed successfully"
    echo "=================================================="
    echo ""
    echo "Next steps:"
    echo "1. Check your Supabase table5 for new data"
    echo "2. Review the logs above for any warnings"
    echo "3. If everything looks good, deploy to GitHub Actions"
    echo ""
else
    echo ""
    echo "=================================================="
    echo "❌ FAILED! Automation encountered errors"
    echo "=================================================="
    echo ""
    echo "Check the error messages above"
    echo "Common issues:"
    echo "  - Network connectivity"
    echo "  - Invalid Supabase credentials"
    echo "  - Insufficient disk space"
    echo ""
    exit 1
fi
