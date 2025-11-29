# FDA Drug Label Data - Automated Daily Processing

Automated system to download, process, and store FDA drug label data in Supabase.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Actions                            │
│                   (Runs everyday at 5AM EST)                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   daily_automation.py                            │
│                                                                   │
│  Step 1: Download dm_spl_release_human_rx_part1.zip (~500MB)   │
│          from dailymed-data.nlm.nih.gov                         │
│          │                                                        │
│          ▼                                                        │
│  Step 2: Extract main ZIP                                       │
│          │                                                        │
│          ▼                                                        │
│  Step 3: Extract 15,000+ prescription sub-ZIPs                  │
│          │                                                        │
│          ▼                                                        │
│  Step 4: Process XML files                                      │
│          • Find DUNS (manufacturer IDs)                         │
│          • Find NDCs (drug codes)                               │
│          • Link NDC → DUNS (manufacturer mapping)               │
│          │                                                        │
│          ▼                                                        │
│  Step 5: Insert into Supabase                                   │
│          │                                                        │
│          ▼                                                        │
│  Step 6: Cleanup temporary files                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Supabase (table5)                           │
│                                                                   │
│   ndc (packager + labeler)  │  duns                                    │
│   ─────────────────────────────────────────                     │
│   12345-678          │  123456789                               │
│   98765-432          │  987654321                               │
│   ...                │  ...                                      │
└─────────────────────────────────────────────────────────────────┘
```

## 📊 Data Flow

```
DailyMed Website
    │
    │ (1) Download ZIP
    ▼
dm_spl_release_human_rx_part1.zip (500MB)
    │
    │ (2) Extract
    ▼
dm_spl_release_human_rx_part1/
    └── prescription/
        ├── 001234.zip
        ├── 001235.zip
        ├── ... (15,000+ ZIPs)
        │
        │ (3) Extract all
        ▼
    xml_files/
        ├── 001234_document.xml
        ├── 001235_document.xml
        ├── ... (15,000+ XMLs)
        │
        │ (4) Parse & Extract
        ▼
    {
      "12345-678-90": {"ndc": "12345-678-90", "duns": "123456789"},
      "98765-432-10": {"ndc": "98765-432-10", "duns": "987654321"},
      ...
    }
        │
        │ (5) Upsert
        ▼
Supabase table5
```

## 🚀 Quick Start

1. **Clone this repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/fda-automation.git
   cd fda-automation
   ```

2. **Add GitHub Secrets**
   - Go to Settings → Secrets and variables → Actions
   - Add `SUPABASE_URL` and `SUPABASE_KEY`

3. **That's it!** The automation will run every 5 minutes automatically.

## 📁 Project Structure

```
fda-automation/
├── daily_automation.py          # Main script (all-in-one)
├── .github/
│   └── workflows/
│       └── daily_fda_update.yml # GitHub Actions config
├── requirements.txt              # Python dependencies
├── .gitignore                    # Ignore sensitive files
├── SETUP_INSTRUCTIONS.md         # Detailed setup guide
├── QUICK_REFERENCE.md            # Quick command reference
├── test_local.sh                 # Local testing script
└── README.md                     # This file
```

## 🔧 Configuration

### Change Schedule

Edit `.github/workflows/daily_fda_update.yml`:

```yaml
# Every 5 minutes (testing)
cron: '*/5 * * * *'

# Daily at 2 AM UTC
cron: '0 2 * * *'

# Weekly on Monday at 2 AM UTC
cron: '0 2 * * 1'
```

### Environment Variables

Required in GitHub Secrets:
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Your Supabase service role key

## 📊 Monitoring

### GitHub Actions
- View runs: `https://github.com/YOUR_USERNAME/fda-automation/actions`
- Email notifications on failure (automatic)

### Supabase
- View data: Table Editor → table5
- Check row count to verify updates

## 🎯 What Gets Extracted

**From FDA XML files:**
- **NDC (National Drug Code)** - Unique identifier for each drug product
- **DUNS (Data Universal Numbering System)** - Unique identifier for the manufacturer

**Filtering:**
- ✅ Only includes actual **manufacturers**
- ❌ Excludes repackers, labelers, API manufacturers

## 📈 Performance

- **Files processed:** ~15,000 XML files
- **Run duration:** 30-60 minutes
- **Data extracted:** ~10,000-50,000 NDC-DUNS mappings
- **GitHub Actions cost:** Free (within 2,000 min/month limit)

## 🔒 Security

- Credentials stored as encrypted GitHub Secrets
- `.env` file in `.gitignore` (never committed)
- Service role key used for database operations
- Temporary files cleaned up after each run

## 🆘 Troubleshooting

See `SETUP_INSTRUCTIONS.md` for detailed troubleshooting.

**Common issues:**
- Script fails → Check GitHub Actions logs
- No data in Supabase → Verify secrets are correct
- Timeout → Increase timeout in workflow (unlikely)

## 📝 License

This is a data processing script for FDA public data. Use responsibly.

## 🤝 Contributing

This is a personal automation project, but improvements are welcome!

## 📞 Support

For setup help, see:
- `QUICK_REFERENCE.md` - Quick commands and tips
- `SETUP_INSTRUCTIONS.md` - Detailed setup guide

---

**Status:** ✅ Automated and running every 5 minutes

**Last updated:** November 2024
