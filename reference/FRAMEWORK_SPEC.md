# County Motivated Seller Intelligence System
## Full Replication Guide — Build Any County From Scratch

*Based on the Harris County build (harris-intel). Use this to replicate the same framework for Bexar County, Dallas County, Travis County, or any other Texas county.*

---

## OVERVIEW — What You're Building

A fully automated motivated seller intelligence pipeline that:
- Scrapes county clerk public records daily (lis pendens, foreclosures, tax liens, judgments, probate, deeds)
- Pulls dedicated foreclosure auction portals where they exist
- Enriches every record with property address and mailing address from the county appraisal district
- Scores and ranks leads by motivation level (0–100)
- Serves everything on a live black/gold dashboard at a public GitHub Pages URL
- Exports skip-trace-ready and GHL-ready CSV on demand
- Runs automatically every morning at 2AM Central via GitHub Actions — zero manual work after setup

**Total cost to run: $0/month** (GitHub free tier covers everything)

---

## PHASE 1 — RECONNAISSANCE

Before writing a single line of code, spend 30–60 minutes manually clicking through the county's public records portals. This is the most important phase. You're answering four questions:

### 1. What is the county clerk's public search URL?

Every Texas county has one. Common patterns:
- `https://www.cclerk.[county]tx.net/applications/websearch/` (Harris, many others)
- `https://[county]countyclerk.com/records`
- `https://[county].tx.publicsearch.us`
- County may use a third-party platform like Tyler Technologies (iDocMarket), Laredo, or CSC

Go to the county clerk's official website and look for "Official Public Records," "Property Records Search," or "Document Search."

**What to look for:**
- Does it require login/authentication? (Big problem — means scraping is harder)
- Does it use JavaScript rendering or is it server-side HTML? (Both work with Playwright)
- What document types exist? Look for codes like L/P, NOTICE, TRSALE, LIEN, T/L, PROB, DEED
- What does the date filter look like? Date range pickers, dropdowns, or free text?
- What does a result row look like? How many columns? Where is the grantor/grantee name?

**Workaround if login required:** Some counties have a public-facing portal AND a subscriber portal. Always try the public portal first. If everything requires login, check if there's a free account option.

### 2. Is there a dedicated Foreclosure Portal?

Harris County has `FRCL_R.aspx` separate from the main clerk search. Many counties have something similar — a dedicated trustee sale / foreclosure posting board.

Look for:
- "Foreclosure Postings" or "Trustee Sale Notices" in the clerk site nav
- A separate search form that lets you search by Sale Date rather than File Date
- Anything labeled FRCL, NOD, NTS, Trustee Sale

**This matters because:** The main clerk search may only show documents filed in the last 7 days, but the foreclosure portal shows the full auction calendar months ahead.

### 3. Where is the appraisal district data?

Every Texas county has a county appraisal district (CAD). You need this to match clerk records to property/mailing addresses.

Formula: `[county]cad.org` or search "[county name] appraisal district data download"

**What you're looking for:**
- A bulk data download page (usually labeled "Data Downloads," "Open Data," or "Public Data")
- Files you want: `real_acct` (property details, mailing address), `owners` (owner names), sometimes `parcel` or `legal`
- File format: usually `.zip` containing pipe-delimited `.txt` files

Harris County example: https://downloads.hcad.org/data/CAMA/

**Bexar County:** https://www.bcad.org/data-downloads/

**Dallas County:** https://www.dallascad.org/

Check if the data is updated annually or monthly. Annual is fine — it changes slowly.

**Workaround if no bulk download:** Use the individual property lookup via parcel number or address. This is much slower but workable for enrichment.

### 4. What are the field names in the appraisal district data?

Download the zip and open the `.txt` files. Look at the first row (header) and the first few data rows. Write down the field names for:
- Property (site) address
- Mailing address
- Owner name(s)
- Account/parcel number

These will be different for every county. Harris County uses `mail_addr_1`, `str_num`, `str` etc. Bexar County uses different names. You need to know these before writing the enrichment code.

---

## PHASE 2 — GITHUB SETUP

### Step 1: Create the repo

1. Go to github.com → New Repository
2. Name it `[county]-intel` (e.g., `bexar-intel`, `dallas-intel`)
3. Set to Public (required for free GitHub Pages)
4. Initialize with a README

### Step 2: Set up the folder structure

```
[county]-intel/
├── scraper/
│   ├── fetch.py
│   └── requirements.txt
├── dashboard/
│   └── index.html
├── data/
│   └── records.json
└── .github/
    └── workflows/
        └── scrape.yml
```

Create these folders by creating placeholder files in each (GitHub requires at least one file per folder).

### Step 3: Configure GitHub Pages

1. Go to repo Settings → Pages
2. Source: Deploy from a branch
3. Branch: `main`, Folder: `/dashboard`
4. Save — your dashboard URL will be `https://[username].github.io/[county]-intel/`

### Step 4: Set up GitHub Actions permissions

1. Settings → Actions → General
2. Workflow permissions: Read and write permissions
3. Save

---

## PHASE 3 — THE SCRAPER

Copy `scraper/fetch.py` from harris-intel as your starting template. The core architecture stays the same. Here's what you change per county:

### The main things to customize:

**1. The clerk search URL and form structure**

The Harris County clerk uses ASP.NET WebForms with specific field IDs (`ctl00_ContentPlaceHolder1_...`). Your county will have different field IDs.

Use the debug logging approach: on first run, dump all form element IDs and values with:
```python
inputs = await page.eval_on_selector_all(
    "input, select",
    "els => els.map(e => ({tag: e.tagName, id: e.id, name: e.name, type: e.type, value: e.value}))"
)
log.info(f"Form elements: {inputs[:15]}")
```

This tells you exactly what to target.

**2. The document type codes**

Every county has different instrument type codes. Harris County uses `L/P`, `NOTICE`, `TRSALE`, `LIEN`, `T/L`, `PROB`, `DEED` etc. Your county likely uses different labels.

Pull up the county clerk search, open the document type dropdown, and write down every type you care about. Map them to categories:
```python
DOC_TYPES = {
    "YOUR_LP_CODE":    ("lp",      "Lis Pendens"),
    "YOUR_FC_CODE":    ("fc",      "Foreclosure"),
    "YOUR_TAX_CODE":   ("tax",     "Tax Lien"),
    "YOUR_JUDG_CODE":  ("jud",     "Judgment"),
    "YOUR_LIEN_CODE":  ("lien",    "Lien"),
    "YOUR_PROB_CODE":  ("probate", "Probate"),
    "YOUR_DEED_CODE":  ("tax",     "Deed"),
}
```

**3. The row parsing logic**

The Harris County results table has rows that look like:
`['', 'RP-2026-132595', '04/08/2026', 'L/P', 'Grantor:OWNER NAME']`

Your county's table will have different columns in a different order. Add debug logging on first run:
```python
for ri, tr in enumerate(table.find_all("tr")[:5]):
    cells = [td.get_text(strip=True) for td in tr.find_all("td")]
    log.info(f"Row {ri}: {cells[:6]}")
```

This tells you exactly which column index has the doc number, date, type, and grantor.

**4. The HCAD/CAD field names**

In the enrichment section, change the field references to match your county's appraisal district field names:
```python
# Harris County
mail_addr = row.get('mail_addr_1', '')
prop_addr = f"{row.get('str_num','')} {row.get('str','')}"

# YOUR COUNTY — change these
mail_addr = row.get('YOUR_MAIL_FIELD', '')
prop_addr = row.get('YOUR_PROP_FIELD', '')
```

### The pagination problem (and how we solved it)

Harris County uses numbered page links (`1 2 3 4 5...`) in a table row. Other counties use different patterns:

- **"Next" button:** Look for `<a>` or `<input>` with text "Next" or ">"
- **Numbered links:** Find `<a>` tags where `.get_text(strip=True).isdigit()` — get the max page number and click each
- **URL-based pagination:** The URL has `?page=2` — construct URLs directly
- **Load more button:** Click until the button disappears

Always add logging to know how many pages were found and what each page returns:
```python
log.info(f"Pages detected: {max_page}")
log.info(f"Page {pg}: {len(rows)} rows")
```

### The ASP.NET overlay problem

Harris County uses ASP.NET UpdatePanel which shows a loading overlay (`<div id="overlay">`) between page clicks. If your county does too, you'll get `Element is not attached to the DOM` errors.

The fix is to wait for the overlay to disappear before clicking the next page:
```python
await page.wait_for_selector("#overlay", state="hidden", timeout=15000)
await page.wait_for_timeout(1000)
```

Or simply add longer waits after each click:
```python
await page.wait_for_load_state("domcontentloaded", timeout=20000)
await page.wait_for_timeout(2500)
```

### The FRCL (Foreclosure Portal) equivalent

If your county has a dedicated foreclosure portal, add a separate scraping method like `_scrape_frcl()`. The pattern:

1. Navigate to the portal URL
2. Log all form elements on first visit (debug)
3. Select the search type (Sale Date vs File Date)
4. Select year and month
5. Click search
6. Parse results
7. Handle pagination
8. Loop through 3 months (previous, current, next)

Key insight from Harris County: The portal shows a `'12345678910...'` pagination row at the top of the results table. This is your page count. Scan for `<a>` tags with digit text to find the max page.

---

## PHASE 4 — THE ENRICHMENT ENGINE

### How it works

The enrichment engine does name-based matching between clerk records (which have owner names but no addresses) and the appraisal district data (which has addresses and names).

The three-strategy approach:
1. **Legal description match** (HIGH confidence) — if the clerk record has a legal description that matches a parcel record exactly
2. **Name prefix match** (MEDIUM/LOW confidence) — index every owner name by their first 2 and 3 word prefixes, then look up the clerk record's grantor name
3. **No match** — return the HCAD lookup URL so the user can check manually

### The name prefix indexing trick (how we got to 87% fill rate)

The key insight: instead of exact name matching (which fails on abbreviations, middle initials, etc.), we build an index keyed by the first 2-3 words of every name.

```python
for name in all_owner_names:
    parts = normalize(name).split()
    if len(parts) >= 2:
        key2 = ' '.join(parts[:2])
        name_index[key2].append(account_record)
    if len(parts) >= 3:
        key3 = ' '.join(parts[:3])
        name_index[key3].append(account_record)
```

Then when looking up `"ESCAMILLA GABRIELLA"`, we search for `"ESCAMILLA GABRIELLA"` (2-word prefix) and find any record where the owner starts with those words.

### Name normalization — the strip list

Before indexing or matching, strip these suffixes and noise words from every name:
```python
STRIP = {'INC','INCORPORATED','LLC','CORP','CORPORATION',
         'ASSOCIATION','HOMEOWNERS','COMMUNITY','ASSOC',
         'TRUST','TRUSTEE','LIMITED','OWNERS','COMMITTEE',
         'FOUNDATION','ETAL','ET AL','ET UX','JR','SR'}
```

Also: apostrophes followed by S become nothing (`HOMEOWNER'S` → `HOMEOWNERS` not `HOMEOWNER S`), and normalize all whitespace.

### What to do when the legal description field is useless

Harris County's `parcel_tieback.txt` has a `dscr` field that sounds like it would contain legal descriptions, but actually contains relationship types like "Child," "Parent," "Tieback," "Undivided Interest Master." Completely useless for matching.

Your county may be different. Check the actual content of the field:
```python
for row in tieback_data[:20]:
    log.info(f"dscr sample: '{row.get('dscr','')}'")
```

If it's not legal descriptions (lot/block/subdivision), the legal index will stay at 0 keys and you'll rely entirely on name matching. That's fine — 87% fill rate is achievable on name matching alone.

### Confidence levels

Return a confidence score with each match:
- **HIGH** — Legal description match (exact parcel)
- **MEDIUM** — Name match with 3+ word prefix AND single result (unambiguous)
- **LOW** — Name match with 2-word prefix OR multiple results
- **NONE** — No match found

Show this in the dashboard as a badge on each record.

---

## PHASE 5 — THE SCORING SYSTEM

### Base scoring logic

```python
score = 30  # base

# Per distress type
if cat == 'lp':   score += 15  # lis pendens
if cat == 'fc':   score += 25  # foreclosure
if cat == 'tax':  score += 20  # tax lien
if cat == 'jud':  score += 15  # judgment
if cat == 'probate': score += 20

# Per flag
for flag in flags:
    score += 10

# Combo bonus
if 'lp' in cats and 'fc' in cats:
    score += 20  # LP + FC combo = very motivated

# Amount thresholds
if amount >= 100000: score += 15
elif amount >= 50000: score += 10

# Recency
if days_since_filed <= 7: score += 5

# Has address
if has_address: score += 5

# Stacked (appears on multiple lists)
score += 30 * (num_sources - 1)

score = min(score, 100)
```

### Scoring tiers for dashboard display

- **Hot (≥70):** Red badge — prioritize immediately
- **Warm (50–69):** Gold badge — follow up this week
- **Active (30–49):** Blue badge — add to nurture sequence
- **Below 30:** Gray — low priority

---

## PHASE 6 — GITHUB ACTIONS AUTOMATION

### The workflow file (`.github/workflows/scrape.yml`)

```yaml
name: Daily Scrape

on:
  schedule:
    - cron: '0 7 * * *'  # 7AM UTC = 2AM Central
  workflow_dispatch:       # Manual trigger button

permissions:
  contents: write
  pages: write
  id-token: write

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r scraper/requirements.txt

      - name: Install Playwright browsers
        run: python -m playwright install --with-deps chromium

      - name: Create output directories
        run: mkdir -p dashboard data

      - name: Run scraper
        run: python scraper/fetch.py

      - name: Print results
        run: |
          echo "=== Scrape Results ==="
          python -c "
          import json
          with open('data/records.json') as f:
              d = json.load(f)
          print(f'Total records: {d[\"total\"]}')
          print(f'With address:  {len([r for r in d[\"records\"] if r.get(\"prop_address\")])}')
          "

      - name: Commit results
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add dashboard/records.json data/records.json dashboard/ghl_export_*.csv data/ghl_export_*.csv
          git diff --cached --quiet || git commit -m "chore: update records $(date -u +'%Y-%m-%d %H:%M UTC')"
          git push

  deploy-pages:
    needs: scrape
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: './dashboard'
      - uses: actions/deploy-pages@v4
        id: deployment
```

### Node.js deprecation warning

You will see this warning:
```
Warning: Node.js 20 actions are deprecated...
```

It does not break anything until June 2026. To silence it now, add to the workflow's `env:` section:
```yaml
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
```

### The Google Drive trick for large data files

If your appraisal district data is >100MB (Harris County's is 207.5MB), you can't commit it to GitHub — the limit is 100MB per file. Solution:

1. Upload the zip to Google Drive
2. Get the direct download link: `https://drive.google.com/uc?export=download&id=YOUR_FILE_ID`
3. In the scraper, download it at runtime:

```python
import requests, io, zipfile

url = "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID"
resp = requests.get(url, stream=True)
z = zipfile.ZipFile(io.BytesIO(resp.content))
```

The file downloads fresh on every run. At ~200MB it takes about 3 seconds on GitHub Actions' connection.

**Alternative:** If the CAD provides a direct download URL (not Google Drive), use that instead. Bexar County has direct download URLs.

---

## PHASE 7 — THE DASHBOARD

### Copy the harris-intel dashboard as your template

The `dashboard/index.html` is self-contained — no external build step, no npm, just one HTML file. Copy it and make these changes:

**1. Branding**
- Change "HARRIS INTEL" to "[COUNTY] INTEL" in the header
- Update the footer text

**2. The `records.json` path**
The dashboard fetches `records.json` from the same folder:
```javascript
const r = await fetch('records.json?t=' + Date.now());
```
This works automatically — no change needed.

**3. Category colors and labels**
Update the breakdown categories if your county has different document types.

### Dashboard features that are already built

- **Search** — searches owner, address, doc number, legal description simultaneously
- **Filters** — by category (LP, FC, Tax, Judgment, Lien, Probate) and score tier
- **Sort** — by score, date filed, or amount
- **Import Tax Delinquent List** — drag and drop an xlsx to merge into the dashboard
- **Record Stacking** — automatic when same property appears on multiple lists
- **6 REI Calculators** — Fix & Flip, Subject To, Creative Finance, Mortgage, Cash on Cash, Cap Rate
- **Export CSV** — Skip Trace format and GHL format

### Critical JavaScript rule — don't break the variable names

The dashboard uses a variable called `filtered` (not `FILTERED_RECORDS`). If you add any new JavaScript that references the filtered records, use `filtered`. This is the single most common way to break the dashboard.

The `applyFilters()` function populates `filtered`, then calls `renderTable()`. Don't reassign `applyFilters` or wrap it — add a separate `updateExportCount()` call inside it instead.

---

## PHASE 8 — DEBUGGING PLAYBOOK

### Problem: Records not populating on dashboard

**Symptom:** Dashboard loads, stats show dashes, table is empty, "Loading..." never resolves.

**Cause 1:** JavaScript error in the `<script>` block crashing before `applyFilters()` runs.
**Fix:** Open browser DevTools → Console. Look for the red error. 99% of the time it's a variable reference to something that doesn't exist.

**Cause 2:** `records.json` not found or malformed.
**Fix:** In browser, go to `https://[your-url]/records.json` directly. If it 404s, the scraper didn't run or didn't commit. If it loads but shows an error, it's invalid JSON.

**Cause 3:** You injected new JavaScript that runs before the DOM is ready.
**Fix:** Any code that does `document.getElementById(...)` at the top level of a script (not inside a function) will crash if the element doesn't exist yet. Wrap it in `document.addEventListener('DOMContentLoaded', function() { ... })`.

### Problem: 0 records from a document type

**Symptom:** Log shows `Page 1: 0 rows` for a type you expect to have data.

**Cause 1:** The form didn't fill correctly — wrong field IDs.
**Fix:** Add the form element debug dump and verify the selectors match actual IDs.

**Cause 2:** The date range is wrong — either no records in that period or the date filter is named differently.
**Fix:** Log the URL after navigation and verify the date params are in the query string or form values.

**Cause 3:** The result table is identified wrong — the parser is looking at a navigation table or header table.
**Fix:** Log `Tables on page: N` and `First table with [doc pattern]: index X`. Verify the index is correct.

### Problem: FRCL shows N pages detected but only parses first page

**Symptom:** `FRCL pages detected: 10` but result count is 38 (one page's worth).

**Cause:** The page number link click is failing silently. The `<a>` tag likely uses ASP.NET `__doPostBack` and needs a different selector.

**Fix:** Try clicking by the link text directly:
```python
pg_link = page.locator(f"a:text-is('{pg}')")
```
Or evaluate the click via JavaScript:
```python
await page.evaluate(f"document.querySelector('a[href*=\"Page${pg}\"]').click()")
```

### Problem: High NONE confidence (address fill rate below 60%)

**Symptom:** Log shows `Confidence: HIGH=0 MEDIUM=50 LOW=800 NONE=2000+`

**Cause 1:** Name normalization stripping too aggressively — turning real name parts into noise words.
**Fix:** Log a sample of stripped names and compare to HCAD names. Add or remove words from the STRIP list.

**Cause 2:** The grantor field isn't being parsed correctly — getting partial names or HOA names instead of owner names.
**Fix:** For LP records, use the grantee (the homeowner being sued) not the grantor (the HOA/lender filing suit). Switch `contact` field based on document type.

**Cause 3:** The CAD data field names don't match what you coded.
**Fix:** Always log the actual field names from the first row of the CAD file on startup.

### Problem: GitHub Actions times out

**Symptom:** Workflow runs for 6+ hours and gets killed. (Default timeout is 6 hours.)

**Cause:** Too many pages being scraped with too much wait time between clicks.

**Fix options:**
- Reduce `await page.wait_for_timeout()` from 2500ms to 1500ms
- Add `timeout: 360` (6 hours) to the workflow step
- Narrow the date range for the RP.aspx scrape (7 days is usually enough)
- Run FRCL and RP scrapes in separate jobs in the workflow

---

## PHASE 9 — THE `records.json` CONTRACT

The dashboard expects this exact shape from `records.json`:

```json
{
  "total": 4347,
  "fetched_at": "2026-04-08T23:19:58.828442",
  "date_range": {
    "from": "2026-04-01",
    "to": "2026-04-08"
  },
  "records": [
    {
      "doc_num": "RP-2026-132595",
      "doc_type": "L/P",
      "filed": "2026-04-08",
      "cat": "lp",
      "cat_label": "Lis Pendens",
      "owner": "ESCAMILLA GABRIELLA",
      "contact": "ESCAMILLA GABRIELLA",
      "grantee": "",
      "amount": null,
      "legal": "LOT 12 BLK 3 GREENWOOD FOREST SEC 14",
      "prop_address": "5823 HAVENWOODS DR",
      "prop_city": "HOUSTON",
      "prop_state": "TX",
      "prop_zip": "77066",
      "mail_address": "5823 HAVENWOODS DR",
      "mail_city": "HOUSTON",
      "mail_state": "TX",
      "mail_zip": "77066-2348",
      "score": 90,
      "flags": ["Lis pendens", "LLC / corp owner", "New this week"],
      "sources": ["RP"],
      "match_confidence": "LOW",
      "match_reason": "name_prefix_2",
      "clerk_url": "https://...",
      "hcad_url": "https://...",
      "frcl_sale_date": "",
      "first_name": "",
      "last_name": ""
    }
  ]
}
```

Any field can be `null` or `""` — the dashboard handles missing data gracefully.

---

## QUICK REFERENCE — County-Specific Starting Points

### Bexar County (San Antonio)

- **Clerk search:** https://bexar.tx.publicsearch.us/
- **Instrument types:** Look for Lis Pendens, Deed of Trust, Abstract of Judgment, Tax Lien
- **Appraisal district:** https://www.bcad.org/data-downloads/
- **CAD data format:** Pipe-delimited, different field names than HCAD — log them on first run
- **Foreclosure portal:** Check https://www.bexar.org/1448/Foreclosure-Sales for trustee sale listings

### Dallas County

- **Clerk search:** https://deeds.dallascounty.org/
- **Appraisal district:** https://www.dallascad.org/SearchResults.aspx
- **Note:** Dallas uses a different platform (likely Laredo) — form selectors will be different

### Travis County (Austin)

- **Clerk search:** https://deed.co.travis.tx.us/
- **Appraisal district:** https://travis.prodigycad.com/

---

## LESSONS LEARNED FROM THE HARRIS COUNTY BUILD

1. **Always log form elements on first run.** Don't guess at field IDs. One debug run saves hours of trial and error.

2. **The pagination row IS the data.** Harris County's `'12345678910...'` row is the pagination control. Any table row that looks like numbers is probably navigation — check it before assuming it's data.

3. **38 records per page × 10 pages = 380 per search.** If you're getting exactly 38 records from a portal that should have hundreds, pagination is not working.

4. **RP.aspx and FRCL_R.aspx are completely separate systems.** The main clerk search is not the same as the foreclosure portal. Always check both.

5. **Grantee vs Grantor matters.** For Lis Pendens, the grantor is the HOA or lender filing the suit — not who you want to call. The grantee is the homeowner. Flip the contact field for LP records.

6. **Apostrophe stripping must be clean.** `HOMEOWNER'S` → remove the apostrophe and S together → `HOMEOWNER`, not `HOMEOWNER S`. One space left by a naive replace breaks the name index match.

7. **Never inject JavaScript into an existing file without auditing the variable names first.** The dashboard uses `filtered` not `FILTERED_RECORDS`. Always read the existing code before adding to it.

8. **The backup file is your best friend.** Before any major change to `index.html`, copy it to `index_backup.html`. Costs nothing, saves everything.

9. **GitHub Pages caches aggressively.** After pushing a fix, always hard refresh (`Cmd+Shift+R`) before concluding something is broken.

10. **Top-level DOM access crashes on load.** Any `document.getElementById()` call at the top level of a `<script>` block (not inside a function) will crash if the element renders after the script. Wrap it in `DOMContentLoaded` or make it a function called from an `onclick`.

11. **The Google Drive 207MB trick works.** GitHub won't store files over 100MB. Download the CAD data at runtime from Google Drive. It takes 3 seconds on GitHub Actions' fast connection.

12. **"File Date" and "Sale Date" give different foreclosure records.** Always search both. A property filed in January with a sale date in April shows up in the January File Date search AND the April Sale Date search — these are different views of the same data and you want both.

---

*Built by Dispo Lab — Quentin's operator-first REI intelligence stack*
