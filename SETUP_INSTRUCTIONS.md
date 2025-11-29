# FDA Drug Label Data - Daily Automation Setup Guide

This guide will help you set up automated daily processing of FDA drug label data.

## 📋 What This Does

1. **Downloads** the latest FDA drug label ZIP file from DailyMed
2. **Extracts** the main ZIP and all prescription sub-ZIPs (~15,000+ files)
3. **Processes** XML files to extract NDC-to-DUNS manufacturer mappings
4. **Inserts** data into Supabase table5
5. **Cleans up** temporary files
6. **Runs automatically** every 5 minutes (configurable to daily)

---

## 🚀 Option 1: GitHub Actions (RECOMMENDED - Free & Easy)

### Prerequisites
- GitHub account (free)
- Your code in a GitHub repository

### Step-by-Step Setup

#### 1. Create GitHub Repository
```bash
# On your local machine
cd your-project-folder
git init
git add daily_automation.py requirements.txt
git commit -m "Initial commit - FDA automation script"

# Create a new repository on GitHub (github.com/new)
# Then push your code:
git remote add origin https://github.com/YOUR_USERNAME/fda-automation.git
git branch -M main
git push -u origin main
```

#### 2. Add GitHub Secrets
1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add two secrets:
   - Name: `SUPABASE_URL`
     Value: `https://bbeubpxzblifptgnsuyi.supabase.co`
   
   - Name: `SUPABASE_KEY`
     Value: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJiZXVicHh6YmxpZnB0Z25zdXlpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDM2OTY0NCwiZXhwIjoyMDY1OTQ1NjQ0fQ.So5sfuJO6GygLumfgqU8Qg1SIYE6xD3QZPNu6qCdTCY`

#### 3. Add GitHub Actions Workflow
```bash
# Create the workflow directory
mkdir -p .github/workflows

# Copy the workflow file
cp .github/workflows/daily_fda_update.yml .github/workflows/

# Commit and push
git add .github/workflows/daily_fda_update.yml
git commit -m "Add GitHub Actions workflow"
git push
```

#### 4. Verify Setup
1. Go to your repository → **Actions** tab
2. You should see "Daily FDA Data Update" workflow
3. Click **Run workflow** to test manually
4. Check the logs to see progress

#### 5. Adjust Schedule (After Testing)
Once you've confirmed it works with 5-minute intervals:

Edit `.github/workflows/daily_fda_update.yml`:
```yaml
on:
  schedule:
    # Run daily at 2 AM UTC
    - cron: '0 2 * * *'
```

Commit and push the change.

### ✅ Pros of GitHub Actions
- ✓ Completely free (2,000 minutes/month for free accounts)
- ✓ No server management needed
- ✓ Built-in logging and error tracking
- ✓ Can trigger manually for testing
- ✓ Email notifications on failures

### ❌ Limitations
- Must be in a GitHub repository
- 6-hour job timeout (should be fine - your job runs ~30-60 min)

---

## 🖥️ Option 2: Linux Cron (If You Have a Server)

### Prerequisites
- Linux server or VPS running 24/7
- Python 3.8+

### Setup

#### 1. Install Dependencies
```bash
# Install Python packages
pip install -r requirements.txt

# Or install individually:
pip install requests lxml python-dotenv supabase
```

#### 2. Create .env File
```bash
# Create .env in the same directory as daily_automation.py
cat > .env << EOF
SUPABASE_URL=https://bbeubpxzblifptgnsuyi.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJiZXVicHh6YmxpZnB0Z25zdXlpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDM2OTY0NCwiZXhwIjoyMDY1OTQ1NjQ0fQ.So5sfuJO6GygLumfgqU8Qg1SIYE6xD3QZPNu6qCdTCY
EOF
```

#### 3. Test the Script
```bash
# Run manually to test
python daily_automation.py

# Check if it completes successfully
echo $?  # Should output 0 if successful
```

#### 4. Set Up Cron Job
```bash
# Open crontab editor
crontab -e

# Add this line for every 5 minutes (testing):
*/5 * * * * cd /path/to/your/script && /usr/bin/python3 daily_automation.py >> /path/to/logs/automation.log 2>&1

# Or for daily at 2 AM:
0 2 * * * cd /path/to/your/script && /usr/bin/python3 daily_automation.py >> /path/to/logs/automation.log 2>&1
```

**Important:** Replace `/path/to/your/script` with the actual path.

#### 5. Verify Cron Job
```bash
# Check if cron job is scheduled
crontab -l

# Monitor logs
tail -f /path/to/logs/automation.log
```

### ✅ Pros of Cron
- ✓ Full control over execution environment
- ✓ No external dependencies
- ✓ Can run very resource-intensive tasks

### ❌ Cons of Cron
- ✗ Requires a server running 24/7
- ✗ Manual setup and monitoring
- ✗ No built-in error notifications

---

## ☁️ Option 3: Google Cloud Run (Serverless)

### Quick Setup
1. Create a Google Cloud account (free tier available)
2. Install Google Cloud SDK
3. Deploy:

```bash
# Create Dockerfile
cat > Dockerfile << EOF
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY daily_automation.py .
CMD ["python", "daily_automation.py"]
EOF

# Deploy to Cloud Run
gcloud run deploy fda-automation \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars SUPABASE_URL=https://bbeubpxzblifptgnsuyi.supabase.co \
  --set-env-vars SUPABASE_KEY=eyJhbGciOi... \
  --no-allow-unauthenticated

# Set up Cloud Scheduler (every 5 minutes for testing)
gcloud scheduler jobs create http fda-daily-job \
  --schedule="*/5 * * * *" \
  --uri="YOUR_CLOUD_RUN_URL" \
  --http-method=GET
```

---

## 📊 Monitoring & Troubleshooting

### Check GitHub Actions Logs
1. Repository → **Actions** tab
2. Click on a workflow run
3. Expand steps to see detailed logs

### Common Issues

#### Issue: "No XML files found"
- **Cause:** Download or extraction failed
- **Fix:** Check download URL is still valid

#### Issue: "Supabase connection error"
- **Cause:** Invalid credentials or network issue
- **Fix:** Verify secrets are set correctly

#### Issue: "Out of memory"
- **Cause:** Processing too many files at once
- **Fix:** GitHub Actions has 7GB RAM, should be sufficient. If not, add batching.

### Email Notifications (GitHub Actions)
GitHub automatically emails you when workflows fail. Enable in:
Settings → Notifications → Actions

---

## 🔧 Customization

### Change Schedule to Daily
Edit `.github/workflows/daily_fda_update.yml`:
```yaml
schedule:
  # Daily at 2 AM UTC (9 PM EST)
  - cron: '0 2 * * *'
  
  # Or daily at 6 AM UTC (1 AM EST)
  - cron: '0 6 * * *'
```

### Change to Weekly
```yaml
schedule:
  # Every Monday at 2 AM UTC
  - cron: '0 2 * * 1'
```

### Add Slack/Discord Notifications
Add this to your workflow:
```yaml
- name: Notify on success
  if: success()
  run: |
    curl -X POST YOUR_WEBHOOK_URL \
      -H 'Content-Type: application/json' \
      -d '{"text":"✅ FDA data updated successfully"}'
```

---

## 🎯 Recommended Setup for Your Use Case

**Use GitHub Actions** because:
1. ✓ Free and reliable
2. ✓ No server maintenance
3. ✓ Built-in logging
4. ✓ Easy to test with manual triggers
5. ✓ Automatic email notifications on failure

---

## 📝 Testing Checklist

- [ ] Script runs successfully locally
- [ ] GitHub secrets are configured
- [ ] First automated run completes successfully
- [ ] Data appears in Supabase table5
- [ ] Logs are clear and informative
- [ ] Error handling works (test with invalid URL)
- [ ] Schedule is set correctly (every 5 min → daily after testing)

---

## 🆘 Support

If you encounter issues:
1. Check GitHub Actions logs
2. Verify Supabase credentials
3. Test the download URL manually
4. Check if table5 schema matches expected format

---

## 📅 Migration Timeline

**Week 1 (Testing):** Run every 5 minutes
- Verify data quality
- Check for errors
- Monitor resource usage

**Week 2 (Production):** Switch to daily at 2 AM
- Update cron schedule
- Monitor first few runs
- Set up alerts

**Ongoing:**
- Monitor logs weekly
- Check data completeness
- Update if FDA changes URL or format
