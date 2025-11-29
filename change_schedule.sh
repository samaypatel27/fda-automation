#!/bin/bash

# Schedule Configuration Helper
# Easily change the automation schedule

echo "=================================================="
echo "FDA Automation - Schedule Configuration"
echo "=================================================="
echo ""
echo "Current schedules you can choose from:"
echo ""
echo "1) Every 5 minutes (testing)"
echo "   cron: '*/5 * * * *'"
echo ""
echo "2) Every hour"
echo "   cron: '0 * * * *'"
echo ""
echo "3) Daily at 2 AM UTC (9 PM EST previous day)"
echo "   cron: '0 2 * * *'"
echo ""
echo "4) Daily at 6 AM UTC (1 AM EST)"
echo "   cron: '0 6 * * *'"
echo ""
echo "5) Weekly on Monday at 2 AM UTC"
echo "   cron: '0 2 * * 1'"
echo ""
echo "6) Custom (you'll enter your own cron expression)"
echo ""
echo "=================================================="
echo ""

read -p "Select a schedule (1-6): " choice

case $choice in
    1)
        cron_schedule="*/5 * * * *"
        description="every 5 minutes"
        ;;
    2)
        cron_schedule="0 * * * *"
        description="every hour"
        ;;
    3)
        cron_schedule="0 2 * * *"
        description="daily at 2 AM UTC"
        ;;
    4)
        cron_schedule="0 6 * * *"
        description="daily at 6 AM UTC"
        ;;
    5)
        cron_schedule="0 2 * * 1"
        description="weekly on Monday at 2 AM UTC"
        ;;
    6)
        echo ""
        echo "Enter your custom cron expression:"
        echo "(Format: minute hour day month weekday)"
        echo "Example: '0 2 * * *' for daily at 2 AM"
        read -p "Cron expression: " cron_schedule
        description="custom schedule"
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "=================================================="
echo "Updating workflow to run: $description"
echo "Cron expression: $cron_schedule"
echo "=================================================="
echo ""

# Update the workflow file
workflow_file=".github/workflows/daily_fda_update.yml"

if [ ! -f "$workflow_file" ]; then
    echo "❌ Error: Workflow file not found at $workflow_file"
    exit 1
fi

# Create backup
cp "$workflow_file" "${workflow_file}.backup"
echo "✓ Created backup: ${workflow_file}.backup"

# Update the cron schedule
sed -i.tmp "s|cron: '.*'|cron: '$cron_schedule'|g" "$workflow_file"
rm -f "${workflow_file}.tmp"

echo "✓ Updated workflow file"
echo ""
echo "=================================================="
echo "Next steps:"
echo "=================================================="
echo ""
echo "1. Review the changes:"
echo "   cat $workflow_file"
echo ""
echo "2. Commit and push:"
echo "   git add $workflow_file"
echo "   git commit -m 'Update schedule to $description'"
echo "   git push"
echo ""
echo "3. Verify on GitHub:"
echo "   https://github.com/YOUR_USERNAME/fda-automation/actions"
echo ""
echo "=================================================="
echo "✅ Schedule updated successfully!"
echo "=================================================="
