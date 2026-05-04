SurplusIQ
Surplus Funds Intelligence System
System Architecture & Build Framework
Built by Jarvis LLC
for Excess Elite LLC
May 4, 2026

# 1. Executive Overview
SurplusIQ is an automated lead-generation system built for Excess Elite LLC that identifies surplus funds opportunities from foreclosure and tax-deed auctions across 10 high-volume counties in Florida and Ohio. The system replaces manual research workflows currently performed by 30 virtual assistants with an end-to-end pipeline that scrapes, scores, enriches, and delivers actionable leads via a hosted dashboard and Excel export.
## Current State

## Contract Status
Contract value: $10,000 flat fee, signed April 11, 2026
Delivery window: 4 weeks (due May 9, 2026)
Current day: Day 23 of 28
Phase 1 status: Auction layer complete; verification layers in build

# 2. System Architecture
SurplusIQ is structured as a 6-layer pipeline. Each layer is independent, testable, and swappable. Data flows from county auction sites through verification, enrichment, and scoring before reaching the user-facing outputs.
## Pipeline Layers

## Data Flow
Each lead moves through the pipeline as follows:
County auction site
    ↓
Daily scraper (Layer 1)
    ↓
Surplus filter — 3rd-party wins ≥ $10K (Layer 2)
    ↓
Clerk docket lookup — real debt + claim status (Layer 3)  ⏳
    ↓
PropertyRadar enrichment — owner + liens (Layer 4)  ⏳
    ↓
Lead scoring — A+/A/B/C tier assignment (Layer 5)
    ↓
Output: Dashboard + Excel + Excess Elite CRM (Layer 6)

# 3. County Coverage
Ten counties are currently operational across two states. Each county has been profiled, tested, and validated for daily scraping. The two states use different surplus calculation rules, which the system handles separately.
## Florida — RealForeclose Platform
All five Florida counties run on the Grant Street Group RealForeclose platform. Florida's opening bid in foreclosure auctions equals the actual final judgment amount (the debt owed). This means apparent surplus closely matches real surplus.

## Ohio — SheriffSaleAuction Platform
All five Ohio counties run on sheriffsaleauction.ohio.gov, also a Grant Street Group platform. Ohio's opening bid is set to two-thirds of appraised value, NOT the actual debt owed. This means the apparent surplus shown in the dashboard is inflated until the real debt (prayer amount) is pulled from the clerk docket. This is the single largest data accuracy issue in Phase 1 and is the reason Layer 3 (clerk docket verification) is the highest-priority pending deliverable.


# 4. Technical Stack
## Core Technologies

## Project Structure
~/Desktop/surplusiq/
├── core/
│   ├── auction/
│   │   └── universal.py        ← scraper for all 10 counties
│   ├── enrichment/
│   │   └── propertyradar.py    ← Layer 4 (in progress)
│   ├── loader.py               ← unified data loader
│   ├── excel_export.py         ← Excel generator
│   └── dashboard_data.py       ← JSON exporter for dashboard
├── config/
│   └── counties.py             ← all 10 county definitions
├── data/
│   ├── raw/                    ← daily JSONL per county
│   ├── enriched/               ← after PropertyRadar (pending)
│   ├── output/                 ← generated Excel files
│   └── diagnostics/            ← debug screenshots + HTML
├── docs/                       ← GitHub Pages site
│   ├── index.html              ← dashboard UI
│   └── data/
│       ├── leads.json          ← live data feed
│       └── summary.json        ← KPIs and aggregates
└── .venv/                      ← Python 3.12 virtualenv

# 5. Lead Scoring Methodology
Every qualifying lead receives a tier rating from A+ down to C. In Phase 1 the score is based purely on apparent gross surplus. Once enrichment (Layer 4) and docket verification (Layer 3) are live, the score will weight real net surplus, equity position, and claim status.
## Phase 1 Scoring (Current)

## Phase 2 Scoring (Planned)
After Layers 3 and 4 ship, scoring will incorporate the following additional signals:
Real net surplus: Sale price minus actual debt (prayer amount) minus encumbrances
Equity position: Owner equity at time of foreclosure — high equity = stronger lead
Claim status: Whether homeowner has already filed a surplus claim
Lien-free flag: No 2nd mortgage, no involuntary liens — clean payout
Property type: Residential prioritized over commercial
Owner contact quality: Mailing address, phone, email all present

An A+ lead in Phase 2 means: real net surplus over $100K, no junior liens, owner has not yet filed a claim, and full contact information is available. These are the leads where Eric's team can move immediately.

# 6. Data Outputs
## Live Dashboard
URL: https://xcerebroai.github.io/surplusiq/
Refresh: Manual today, daily 6 AM after CI/CD ships
Mobile-responsive: Yes — works on iOS and Android browsers
Authentication: Public for now; can be locked to allowlist if needed

Dashboard sections:
4 KPI cards: Total Leads, Total Surplus, A+ Count, Top Lead
County breakdown grid: 10 cards sorted by surplus, clickable to filter
Filterable lead table: by state, county, score tier, free-text search
Sortable columns: surplus, sale price, opening bid, sale date, etc.
Color-coded score badges (A+/A/B/C)

## Excel Export
Multi-tab workbook generated by core/excel_export.py:

## Excess Elite CRM Integration (Pending)
Once enrichment is complete, qualifying leads will be pushed to Eric's Excess Elite CRM via API. The system will dedupe against existing records to avoid pushing leads already in the CRM. This eliminates the manual entry step Eric's VAs currently perform.

# 7. Known Issues & Fixes In Flight
Below is a transparent list of every known data-quality issue in the current system, the impact, and the planned fix. This is the working punch list before delivery on May 9.
## Critical Issues



## Secondary Issues
Commercial vs residential mixing: $4.5M Montgomery lead at 2210 Arbor Blvd is a 22,000 sqft commercial building. Need a property-type flag to filter out commercial unless Eric wants those.
Address formatting inconsistency: Florida shows 'Property Address: 1234 Main St', Ohio shows '1234 Main St\nCity, ZIP'. Normalize to consistent format across all 10 counties.
Duval mixes auction types: Duval foreclosure feed includes both mortgage foreclosures and tax deed sales without flagging. Tax deed surplus has different distribution rules. Need separation.
No claim status verification: Leads are surfaced without checking whether the surplus has already been claimed or disbursed. Fixed by Layer 3 build.
Manual scrape trigger: Currently runs on demand. CI/CD pipeline (GitHub Actions, daily 6 AM) is on the punch list.

# 8. Roadmap to May 9 Delivery
Five days remain in the contract window. The work below is sequenced by client impact and dependency order. Items marked 'Phase 2' are nice-to-have if time permits but not blocking for delivery.

## Definition of Done
Phase 1 is considered complete when:
All 10 counties scrape successfully on a daily schedule
Every lead displays accurate sale date, real net surplus, and claim status
PropertyRadar enrichment populates owner contact and lien data
Dashboard updates daily without manual intervention
Excel export available for download in repo and via dashboard
Excess Elite CRM receives qualifying leads with no duplicates
Eric and his team have access credentials to all systems

# 9. Appendix — Key Commands
Reference commands for running the system end-to-end.
Run a single county scraper
cd ~/Desktop/surplusiq
python -m core.auction.universal montgomery-oh --headed --days=14
Refresh the entire pipeline
# Scrape all 10 counties
for c in miami-dade-fl broward-fl duval-fl lee-fl orange-fl \
         cuyahoga-oh franklin-oh montgomery-oh summit-oh hamilton-oh; do
  python -m core.auction.universal $c --days=14
done

# Generate Excel
python -m core.excel_export

# Update dashboard data
python -m core.dashboard_data

# Push to GitHub Pages
git add docs/ data/output/ && git commit -m 'Daily refresh' && git push
PropertyRadar enrichment (after credentials confirmed)
# Dry run — no credits charged
python -m core.enrichment.propertyradar --dry-run --top 10

# Live run on full lead set
python -m core.enrichment.propertyradar

## System URLs
Live dashboard: https://xcerebroai.github.io/surplusiq/
Repository: https://github.com/xcerebroai/surplusiq
GitHub Pages settings: github.com/xcerebroai/surplusiq/settings/pages

## Document Version
v1.0 — May 4, 2026 — Day 23 of 28 of contract delivery window