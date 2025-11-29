# FDA Automation - Quick Reference

## 📦 Files You Have

1. **`daily_automation.py`** - Main script that does everything
2. **`.github/workflows/daily_fda_update.yml`** - GitHub Actions config
3. **`requirements.txt`** - Python dependencies
4. **`SETUP_INSTRUCTIONS.md`** - Detailed setup guide
5. **`test_local.sh`** - Quick local testing script

---

## ⚡ Quick Start (3 Steps)

### Step 1: Test Locally (Optional but Recommended)
```bash
chmod +x test_local.sh
./test_local.sh
```

### Step 2: Push to GitHub
```bash
git init
git add .
git commit -m "FDA automation initial commit"
git remote add origin https://github.com/YOUR_USERNAME/fda-automation.git
git push -u origin main
```

### Step 3: Add Secrets to GitHub
1. Go to: `https://github.com/YOUR_USERNAME/fda-automation/settings/secrets/actions`
2. Add two secrets:
   - `SUPABASE_URL` = `https://bbeubpxzblifptgnsuyi.supabase.co`
   - `SUPABASE_KEY` = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (your full key)

**Done!** It will now run every 5 minutes automatically.

---

## 🔄 Current Schedule

**Testing Mode:** Every 5 minutes
```yaml
cron: '*/5 * * * *'
```

**To Change to Daily (after testing):**
Edit `.github/workflows/daily_fda_update.yml`:
```yaml
cron: '0 2 * * *'  # Daily at 2 AM UTC
```

---

## 📊 What Happens Each Run

```
1. Download FDA ZIP (~500MB)
   ↓
2. Extract main ZIP
   ↓
3. Extract 15,000+ prescription ZIPs
   ↓
4. Process XML files for NDC-DUNS mappings
   ↓
5. Insert into Supabase table5
   ↓
6. Clean up temporary files
```

**Duration:** 30-60 minutes per run

---

## 🔍 Check If It's Working

### GitHub Actions
1. Go to: `https://github.com/YOUR_USERNAME/fda-automation/actions`
2. Click latest workflow run
3. Check for green checkmarks ✓

### Supabase
1. Go to: `https://bbeubpxzblifptgnsuyi.supabase.co`
2. Open Table Editor
3. View `table5`
4. Should see new NDC-DUNS records

---

## 🚨 Troubleshooting

### "Workflow not running"
- Check if secrets are set correctly
- Verify workflow file is in `.github/workflows/` directory
- Check Actions tab for error messages

### "No data in Supabase"
- Check GitHub Actions logs for errors
- Verify Supabase credentials
- Test locally with `./test_local.sh`

### "Out of memory"
- Unlikely with GitHub Actions (7GB RAM)
- If it happens, let me know - we can add batching

---

## 📞 Need Help?

1. Check `SETUP_INSTRUCTIONS.md` for detailed guides
2. Review GitHub Actions logs
3. Test locally with `test_local.sh`
4. Check Supabase connection manually

---

## 🎯 Success Criteria

- [x] Script runs without errors
- [x] Data appears in table5
- [x] Runs automatically every 5 minutes
- [x] Logs are clear and informative

After you confirm these, change schedule to daily!

---

## 📝 Important Notes

- **Free tier limits:** GitHub Actions gives 2,000 minutes/month (plenty for daily runs)
- **Disk space:** Temporary files are cleaned up after each run
- **Data updates:** Old NDCs are updated (upsert), new ones are inserted
- **Error handling:** Script continues even if some files fail

---

## 🔐 Security

- Supabase credentials stored as GitHub Secrets (encrypted)
- Never commit `.env` file to git
- Service role key is used (required for upsert operations)

---

## ⏱️ Recommended Timeline

**Day 1-2:** Set up and test locally
**Day 3-7:** Run every 5 minutes on GitHub Actions (verify data quality)
**Week 2+:** Switch to daily schedule

---

## 🎉 You're All Set!

Your FDA data will now be automatically updated every 5 minutes (or daily after you change the schedule).

The automation:
✓ Runs in the cloud (no server needed)
✓ Emails you if it fails
✓ Keeps logs of each run
✓ Cleans up after itself
✓ Handles errors gracefully
