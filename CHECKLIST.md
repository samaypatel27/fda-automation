# FDA Automation Setup Checklist

Use this checklist to ensure everything is set up correctly.

## ✅ Pre-Setup Checklist

- [ ] Python 3.8+ installed on local machine (for testing)
- [ ] GitHub account created
- [ ] Git installed on local machine
- [ ] Supabase account created
- [ ] table5 exists in Supabase with schema:
  ```sql
  CREATE TABLE table5 (
    ndc TEXT PRIMARY KEY,
    duns TEXT NOT NULL
  );
  ```

## ✅ Local Testing Checklist

- [ ] Downloaded all files to a local directory
- [ ] Created `.env` file with Supabase credentials:
  ```
  SUPABASE_URL=https://bbeubpxzblifptgnsuyi.supabase.co
  SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  ```
- [ ] Installed dependencies: `pip install -r requirements.txt`
- [ ] Made test script executable: `chmod +x test_local.sh`
- [ ] Ran local test: `./test_local.sh`
- [ ] Verified script completed without errors
- [ ] Checked Supabase table5 for new data
- [ ] Verified NDC and DUNS values look correct

## ✅ GitHub Setup Checklist

- [ ] Created new repository on GitHub
- [ ] Initialized git in local directory: `git init`
- [ ] Added `.gitignore` to prevent committing sensitive files
- [ ] Committed all files:
  ```bash
  git add .
  git commit -m "Initial commit - FDA automation"
  ```
- [ ] Connected to GitHub repo:
  ```bash
  git remote add origin https://github.com/YOUR_USERNAME/fda-automation.git
  ```
- [ ] Pushed to GitHub: `git push -u origin main`
- [ ] Created `.github/workflows` directory structure
- [ ] Verified workflow file is in the correct location

## ✅ GitHub Secrets Checklist

- [ ] Navigated to: Settings → Secrets and variables → Actions
- [ ] Created `SUPABASE_URL` secret
- [ ] Created `SUPABASE_KEY` secret
- [ ] Verified secrets are listed (values are hidden)
- [ ] Secrets do NOT have quotes around them
- [ ] Secrets do NOT have trailing spaces

## ✅ GitHub Actions Checklist

- [ ] Workflow file is committed and pushed
- [ ] Navigated to Actions tab in GitHub repo
- [ ] See "Daily FDA Data Update" workflow listed
- [ ] Manually triggered workflow: Actions → workflow → "Run workflow"
- [ ] Workflow started successfully
- [ ] All steps show green checkmarks ✓
- [ ] Checked logs for any warnings or errors
- [ ] Workflow completed in reasonable time (30-60 min)

## ✅ Data Validation Checklist

- [ ] Opened Supabase dashboard
- [ ] Navigated to Table Editor → table5
- [ ] Verified new rows were added
- [ ] Checked NDC format (e.g., "12345-678-90")
- [ ] Checked DUNS format (9-digit number as text)
- [ ] Verified row count increased after run
- [ ] Spot-checked a few NDC-DUNS pairs for accuracy

## ✅ Automation Verification Checklist

- [ ] Workflow has run automatically on schedule
- [ ] Checked Actions tab for automatic runs (not just manual)
- [ ] Verified automatic runs completed successfully
- [ ] Checked email for any failure notifications
- [ ] Verified data is being updated in table5

## ✅ Schedule Configuration Checklist

**Current Testing Phase (Every 5 minutes)**
- [ ] Confirmed schedule is set to `*/5 * * * *`
- [ ] Observed at least 3 successful automatic runs
- [ ] Verified no errors in any of the runs
- [ ] Confirmed data quality is good

**Ready for Production (Daily)**
- [ ] Tested thoroughly for at least 1 day
- [ ] Ran `./change_schedule.sh` to update schedule
- [ ] Selected option 3 or 4 (daily schedule)
- [ ] Committed and pushed schedule change
- [ ] Verified new schedule shows in workflow file

## ✅ Monitoring Setup Checklist

- [ ] Enabled email notifications for GitHub Actions failures
  (Settings → Notifications → Actions)
- [ ] Bookmarked Actions page for easy monitoring
- [ ] Set calendar reminder to check runs weekly
- [ ] Documented where to find logs (in this repo)

## ✅ Documentation Checklist

- [ ] Read `README.md` for overview
- [ ] Read `QUICK_REFERENCE.md` for quick commands
- [ ] Read `SETUP_INSTRUCTIONS.md` for detailed setup
- [ ] Bookmarked these files for future reference
- [ ] Understand how to troubleshoot common issues

## ✅ Security Checklist

- [ ] `.env` file is in `.gitignore`
- [ ] `.env` file is NOT committed to git
- [ ] Verified no secrets in git history: `git log --all --full-history --source -- '*.env'`
- [ ] Supabase service role key is used (not anon key)
- [ ] GitHub secrets are encrypted (automatic)
- [ ] Local `.env` file has restricted permissions: `chmod 600 .env`

## ✅ Backup & Recovery Checklist

- [ ] Documented Supabase credentials in secure location (password manager)
- [ ] Workflow file backed up locally
- [ ] Know how to restore from GitHub if local files lost
- [ ] Understand how to manually run script if automation fails

## 🎯 Final Verification

Once ALL checkboxes above are complete:

- [ ] Script runs automatically every 5 minutes ✅
- [ ] Data appears in Supabase table5 ✅
- [ ] No errors in GitHub Actions logs ✅
- [ ] Email notifications working ✅
- [ ] Ready to switch to daily schedule ✅

---

## 📅 Post-Setup Tasks

### Week 1 (Testing Phase)
- [ ] Day 1: Monitor runs hourly
- [ ] Day 2-3: Monitor runs twice daily
- [ ] Day 4-7: Monitor runs once daily
- [ ] End of week: Verify data quality and consistency

### Week 2 (Production Phase)
- [ ] Switch to daily schedule
- [ ] Monitor first 3 daily runs closely
- [ ] Verify data continues to update correctly
- [ ] Set up weekly monitoring routine

### Ongoing Maintenance
- [ ] Check runs weekly
- [ ] Review Supabase data monthly
- [ ] Update dependencies quarterly: `pip install -U -r requirements.txt`
- [ ] Monitor FDA website for URL changes

---

## 🆘 If Something Goes Wrong

1. **Workflow fails:**
   - Check Actions logs for error messages
   - Verify secrets are correct
   - Test locally with `./test_local.sh`

2. **No data in Supabase:**
   - Check if workflow completed
   - Verify Supabase credentials
   - Check table5 exists with correct schema

3. **Need to start over:**
   - Delete and recreate GitHub repo
   - Re-add secrets
   - Re-run local test

---

## ✅ You're Done!

Once all items are checked, your FDA automation is:
- ✅ Fully automated
- ✅ Running in the cloud
- ✅ Monitored and logged
- ✅ Secure and reliable

**Congratulations!** 🎉
