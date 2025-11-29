# Troubleshooting Guide

Common issues and solutions for the FDA automation system.

---

## 🔍 Quick Diagnostics

Run these commands to quickly diagnose issues:

```bash
# Check if workflow file is in correct location
ls -la .github/workflows/daily_fda_update.yml

# Check if .env file exists (for local testing)
ls -la .env

# Verify Python dependencies
pip list | grep -E "requests|lxml|supabase|dotenv"

# Test Supabase connection
python -c "from supabase import create_client; print('✓ Supabase module works')"
```

---

## ❌ Error: "Workflow not found" or "No workflows"

### Symptoms
- Actions tab shows no workflows
- Cannot trigger workflow manually

### Causes
1. Workflow file not in correct directory
2. YAML syntax error
3. Not pushed to GitHub

### Solutions

**Check file location:**
```bash
# Correct location:
.github/workflows/daily_fda_update.yml

# If in wrong location, move it:
mkdir -p .github/workflows
mv daily_fda_update.yml .github/workflows/
```

**Validate YAML syntax:**
```bash
# Online validator: https://www.yamllint.com/
# Or use Python:
python -c "import yaml; yaml.safe_load(open('.github/workflows/daily_fda_update.yml'))"
```

**Push to GitHub:**
```bash
git add .github/workflows/daily_fda_update.yml
git commit -m "Add workflow file"
git push
```

---

## ❌ Error: "Invalid workflow file"

### Symptoms
- Red X next to workflow in Actions tab
- "Invalid workflow" error message

### Cause
YAML indentation or syntax error

### Solution

**Common YAML mistakes:**
```yaml
# ❌ Wrong (mixed tabs and spaces)
on:
	schedule:
    - cron: '*/5 * * * *'

# ✅ Correct (consistent spaces)
on:
  schedule:
    - cron: '*/5 * * * *'
```

**Fix indentation:**
1. Copy the workflow file from `SETUP_INSTRUCTIONS.md`
2. Paste into `.github/workflows/daily_fda_update.yml`
3. Save and push

---

## ❌ Error: "Supabase connection failed" or "401 Unauthorized"

### Symptoms
- Workflow runs but fails at insertion step
- Error: "Invalid API key" or "401 Unauthorized"

### Causes
1. Secrets not set in GitHub
2. Wrong secret values
3. Expired or invalid Supabase key

### Solutions

**Verify secrets exist:**
1. Go to: `https://github.com/YOUR_USERNAME/fda-automation/settings/secrets/actions`
2. Should see: `SUPABASE_URL` and `SUPABASE_KEY`

**Check secret values:**
```
SUPABASE_URL should be:
https://bbeubpxzblifptgnsuyi.supabase.co

SUPABASE_KEY should start with:
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Common mistakes:**
- Adding quotes around secrets: `"https://..."` ❌
- Adding extra spaces or newlines ❌
- Using anon key instead of service_role key ❌
- Copying incomplete key (key is very long!) ❌

**Re-add secrets:**
1. Delete existing secrets
2. Re-create with exact values from `.env`
3. No quotes, no extra spaces

**Test Supabase key locally:**
```bash
python -c "
from supabase import create_client
import os
client = create_client('YOUR_URL', 'YOUR_KEY')
result = client.table('table5').select('*').limit(1).execute()
print('✓ Connection successful!')
"
```

---

## ❌ Error: "No such table: table5"

### Symptoms
- Error: "relation 'table5' does not exist"
- Workflow fails at insertion step

### Cause
Table doesn't exist in Supabase

### Solution

**Create table in Supabase:**
1. Go to Supabase dashboard
2. Table Editor → New table
3. Name: `table5`
4. Columns:
   - `ndc` (text, PRIMARY KEY)
   - `duns` (text, NOT NULL)

**Or use SQL Editor:**
```sql
CREATE TABLE table5 (
    ndc TEXT PRIMARY KEY,
    duns TEXT NOT NULL
);
```

**Verify table exists:**
```bash
python -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
result = client.table('table5').select('*').limit(1).execute()
print(f'✓ Table exists! Rows: {len(result.data)}')
"
```

---

## ❌ Error: "Download failed" or "HTTP 404"

### Symptoms
- Workflow fails at download step
- Error: "File not found" or "404"

### Cause
FDA changed the download URL

### Solution

**Check if URL is still valid:**
```bash
# Test download URL
curl -I https://dailymed-data.nlm.nih.gov/public-release-files/dm_spl_release_human_rx_part1.zip

# Should return: HTTP/1.1 200 OK
```

**If URL changed:**
1. Go to: https://dailymed.nlm.nih.gov/dailymed/spl-resources-all-drug-labels.cfm
2. Find new download link
3. Update `DOWNLOAD_URL` in `daily_automation.py`:
   ```python
   DOWNLOAD_URL = "NEW_URL_HERE"
   ```
4. Commit and push changes

---

## ❌ Error: "Timeout" or "Job exceeded maximum time"

### Symptoms
- Workflow runs for 6+ hours then fails
- "Job exceeded maximum time limit"

### Cause
Processing taking too long (rare)

### Solution

**Increase timeout (in workflow file):**
```yaml
jobs:
  update-fda-data:
    runs-on: ubuntu-latest
    timeout-minutes: 360  # 6 hours (default)
```

**Or optimize processing:**
Add this to `daily_automation.py` to skip already processed files:
```python
# Before processing XML files, check which NDCs already exist
existing_ndcs = set()
result = supabase.table("table5").select("ndc").execute()
existing_ndcs = {row['ndc'] for row in result.data}

# Then skip processing files that would only produce existing NDCs
```

---

## ❌ Error: "Out of disk space"

### Symptoms
- "No space left on device"
- Fails during extraction

### Cause
GitHub Actions runners have limited disk space

### Solution

**Add cleanup between steps (in workflow):**
```yaml
- name: Clean up after extraction
  run: |
    rm -rf temp_work/extracted
    rm -rf temp_work/downloaded.zip
```

**Or process in batches** (modify `daily_automation.py`):
```python
# Process ZIPs in batches of 1000
for batch in range(0, len(zip_files), 1000):
    batch_files = zip_files[batch:batch+1000]
    # process batch
    # cleanup temp files
```

---

## ❌ Error: "XML parsing failed" or "lxml error"

### Symptoms
- Error processing specific XML files
- "XMLSyntaxError" or "ParseError"

### Cause
Malformed XML files from FDA

### Solution

**Already handled!** The script has try/except blocks:
```python
try:
    tree = etree.parse(str(xml_file), parser)
    # process...
except Exception as e:
    return {}  # Skip bad files
```

**If many files fail:**
- Check logs to see which files
- Download those files manually
- Verify they're valid XML
- Report to FDA if consistently bad

---

## ❌ Error: "No NDC-DUNS mappings extracted"

### Symptoms
- Script runs successfully but finds 0 mappings
- Empty data inserted to Supabase

### Causes
1. FDA changed XML structure
2. Download was corrupted
3. Wrong file downloaded

### Solutions

**Verify download:**
```bash
# Check file size (should be ~500MB)
ls -lh temp_work/downloaded.zip

# Check if it's a valid ZIP
unzip -t temp_work/downloaded.zip
```

**Manually inspect XML:**
```bash
# Extract one file manually
cd temp_work/xml_files
head -n 100 *.xml | less

# Look for NDC codes (should see codeSystem="2.16.840.1.113883.6.69")
# Look for DUNS (should see root="1.3.6.1.4.1.519.1")
```

**If FDA changed structure:**
- Contact me to update extraction logic
- Or inspect new structure and modify XPath queries

---

## ❌ Error: "Permission denied" or "Access denied"

### Symptoms
- Cannot write files
- Cannot create directories

### Cause
File permissions issue

### Solution

**For local testing:**
```bash
# Fix permissions
chmod +x test_local.sh
chmod +x change_schedule.sh
chmod 755 daily_automation.py
```

**For GitHub Actions:**
- Should not happen (runners have full permissions)
- If it does, report as bug to GitHub

---

## 🔧 Debugging Tips

### Enable verbose logging

**Modify `daily_automation.py`:**
```python
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

### Test individual components

**Test download only:**
```python
if __name__ == "__main__":
    setup_work_directory()
    download_fda_data()
    # Stop here - check if file downloaded
```

**Test extraction only:**
```python
# Assuming you already have the ZIP downloaded
if __name__ == "__main__":
    extract_main_zip()
    # Check extracted files
```

### Monitor resource usage

**Add to workflow:**
```yaml
- name: Check disk space
  run: df -h

- name: Check memory
  run: free -h
```

---

## 📊 Performance Issues

### Script takes too long

**Current:** ~30-60 minutes (normal)
**Problem:** >2 hours

**Solutions:**
1. Use multiprocessing for XML parsing
2. Process in batches
3. Skip already-processed NDCs

### Too many API calls to Supabase

**Current:** Batch inserts of 1000 records
**Problem:** Rate limiting

**Solutions:**
1. Increase batch size to 5000
2. Add delay between batches
3. Use Supabase bulk operations

---

## 🆘 Last Resort: Start Fresh

If nothing works:

1. **Delete everything:**
   ```bash
   rm -rf .github temp_work
   ```

2. **Re-download files:**
   - Get fresh copies of all scripts
   - Verify .gitignore is correct

3. **Re-create secrets:**
   - Delete old secrets in GitHub
   - Re-add with fresh values

4. **Test locally first:**
   ```bash
   ./test_local.sh
   ```

5. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Fresh setup"
   git push --force
   ```

---

## 📞 Getting More Help

If you're still stuck:

1. **Check logs:**
   - GitHub Actions → Latest run → Expand each step
   - Look for the first error (not the last)

2. **Verify environment:**
   - Python version: `python --version` (should be 3.8+)
   - Dependencies: `pip list`
   - File locations: `find . -name "*.yml"`

3. **Isolate the problem:**
   - Does it work locally? → GitHub setup issue
   - Does it fail locally too? → Code or dependencies issue
   - Does it work manually but not on schedule? → Workflow config issue

4. **Common patterns:**
   - Red X on workflow → YAML syntax error
   - Workflow doesn't appear → File not in .github/workflows/
   - 401 error → Secrets incorrect
   - 404 error → URL changed
   - Timeout → Too slow, needs optimization

---

## ✅ Preventive Maintenance

To avoid issues:

- **Weekly:** Check Actions tab for failures
- **Monthly:** Verify data in Supabase looks correct
- **Quarterly:** Update dependencies
- **Yearly:** Verify FDA URL still works

---

**Remember:** Most issues are configuration problems, not code bugs!
