# NEISS Research Studio

A local research app for analyzing NEISS injury surveillance data.
Built with Streamlit + DuckDB. No coding experience required.

---

## Classmate setup (Mac, no Python needed)

**Requirements:** macOS 12+, internet connection, NEISS CSV files from [CPSC](https://www.cpsc.gov/Research--Statistics/NEISS-Injury-Data)

```bash
# 1. Download or clone this repo, then open Terminal in the folder
chmod +x build_mac_app.sh
./build_mac_app.sh          # ~10 min first time — downloads Python + packages

# 2. Open the app
open "dist/NEISS Research Studio.app"

# 3. Add your NEISS CSV files
# Double-click open_data_folder.command — paste your CSVs there

# 4. Click "Build / Refresh Database" in the sidebar
```

If macOS blocks the app: **System Preferences → Security & Privacy → Open Anyway**

---

## Developer setup (run from source)

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Study modes

| Mode | Use |
|------|-----|
| Case Search | Find matching cases, download CSV |
| Descriptive Cohort Study | Summarize one injury group |
| Comparative Cohort Study | Compare two groups with statistics |
| Annual Trend Study | Track changes over time |

---

## Updating the app after changes

```bash
./update_app_files.sh    # copies updated .py files into existing .app (~5 sec)
```

---

## Data files

Download NEISS CSV files here:
[NEISS Data (Google Drive)](https://drive.google.com/file/d/1twC-5RvXyj89hlHH0M__cluyCWjWS7iG/view?usp=sharing)

Unzip and place the CSV files in the `data/` folder inside the app bundle.

## Limitations

- Comparative statistics are unweighted — survey-weighted methods recommended before publication
- NEISS captures ED-treated injuries only
- Manuscript drafts require verification before submission
- Data files are not included — download from CPSC separately
