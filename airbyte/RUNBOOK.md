# Bhagyashri's runbook (B1-B10) - branch `feature/data-platform`

Deadlines from the team plan: ingestion working **Sat 14, 7 PM** -> PR into `dev` -> smoke test -> you merge `dev` to `main` Sat night.
Sunday = window/backfill, failure demo, screenshots A-D, report, two clean dry runs. Freeze Sun 6 PM. Demo Mon 16.
Priority if time runs short: **B1-B8 first**, then B9, then B10.

## Order of work (one commit per finished + hand-tested feature, then push)
| # | Do | Prove it works (edge cases from the plan) | Commit message |
| --- | --- | --- | --- |
| B1 | Request MAP_KEY (arrives by email). `export FIRMS_MAP_KEY=...; bash airbyte/tools/firms_check.sh` | HTTP 200; header row present; wrong key -> script fails (not an empty file); row count noted | `airbyte: add FIRMS key and source test script (B1)` |
| B2 | Create project `firewatch-de-<initials>`; run `PROJECT_ID=... TEAMMATE_EMAIL=... bash airbyte/tools/setup_gcp.sh` | Teammate can query; `python airbyte/tools/verify_warehouse.py --project P --key keys/sa-app.json --check-roles` prints OK x3; all datasets in US | `airbyte: add GCP set-up and role check scripts (B2)` |
| B3 | Gate: Airbyte BigQuery destination + one-day sync on Sandbox | Sync succeeds, or switch to billing-enabled free trial (set a budget alert) / Snowflake. **Decide Fri night** | (notes only: tick B3 in `NOTES.md`) |
| B4 | `abctl local install` (Docker >= 8 GB RAM), `abctl local credentials` | UI opens at localhost:8000; client id/secret saved privately (-> `airflow/.env`) | `airbyte: record install and notes (B4)` |
| B5 | Builder > Import YAML `airbyte/firms_connector.yaml` > test with real key. **Time-box 3 h**, else File source (`tools/fetch_firms_to_gcs.py`) | Builder test shows records; one slice per 5-day window; big response does not run out of memory | `airbyte: add FIRMS connector manifest (B5)` |
| B6 | BigQuery destination + connection (Incremental \| Append, Manual) + first sync. Copy connection ID | `verify_warehouse.py` -> `days_loaded` matches window; **second sync appends**, not replaces; `product` populated | `airbyte: add Airbyte API and warehouse check tools (B6)` |
| B7 | Follow the start steps in `airflow/README.md` | UI at localhost:8080; Airflow can reach Airbyte; key masked in logs | `airflow: add Docker Compose with dbt venv and mounts (B7)` |
| B8 | Trigger `firewatch_pipeline` manually | All 6 tasks green; wrong key -> `check_data_source` fails, retries twice, rest `upstream_failed`; stopped Airbyte fails cleanly | `airflow: add firewatch_pipeline DAG (B8)` |
| B9 | Timed 5-day test sync (`airbyte_api.py sync`); <10 min -> start 90 days back, else 30; Clear data; backfill | Final date range recorded; run DAG twice: `verify_warehouse.py --marts` counts identical before/after | `airbyte: record window and backfill (B9)` |
| B10 | Failure demo log text; screenshots A-D (blur key); report text (`REPORT_DRAFT.md`) | No key visible in any screenshot | `docs: add data-platform report sections (B10)` (docs is shared: tell Neha, small PR) |

Commands for every commit:
```bash
git add <the files of that feature>
git commit -m "<message from the table>"
git push -u origin feature/data-platform
```
Never `git add .` blindly: check `git status` shows no `.env`, `keys/`, `*.csv`, `logs/`.

## Setup once
```bash
git clone https://github.com/NHK2012/firewatch.git && cd firewatch
git checkout dev && git pull && git checkout -b feature/data-platform
# copy the airbyte/ and airflow/ folders from this package over the repo's
pip install google-cloud-bigquery requests          # for the tools
```

## Decision gates (from the plan)
| When | If | Do |
| --- | --- | --- |
| Fri night | Airbyte BigQuery destination fails on Sandbox | Free-trial billing + budget alert, or Snowflake trial |
| Sat 6 PM | Connector Builder returns no records | File-source fallback |
| Sat 10 PM | No live raw data yet | Neha continues on the fixture; keep trying |
| Sun 12 PM | Airflow cannot trigger Airbyte via API | Try the provider operator, else trigger Airbyte by hand and let Airflow run validation + dbt + tests |

## Tell Neha (contract)
- Raw table `firewatch_raw.active_fire_observations`: FIRMS columns + `product` + `_airbyte_extracted_at`. Tell her immediately if columns or types differ from the first real file (Airbyte may deliver numbers as strings; her staging uses `safe_cast`).
- Airflow runs `dbt seed && dbt run`, then `dbt test`, in `/opt/airflow/dbt/firewatch_dbt` using `sa-dbt.json`. She keeps both working from a clean checkout. dbt output goes to `/tmp` in the container (not into her repo folder).
- Send `sa-dbt.json` and `sa-app.json` privately (never Git/screenshots/report).

## Smoke test on `dev` (Sat after merge, ~15 min) - your parts
1. Airbyte and Airflow start from a clean restart; connection shows a successful last sync.
2. Raw table has rows; record count, first and last day (`verify_warehouse.py`).
3. Trigger `firewatch_pipeline`: six tasks green, no manual step.
8. Failure path: wrong key or stopped Airbyte -> fails, retries twice, downstream `upstream_failed`. Restore afterwards.
9. No key/password/JSON visible in repo, logs or screenshots.
(4-7 are shared with Neha: dbt test, row counts, second DAG run does not grow counts, Streamlit.)

## Demo (your ~4 minutes)
NASA FIRMS data and the flow Airbyte -> BigQuery -> dbt -> Streamlit orchestrated by Airflow; Airbyte connection with a successful sync;
raw table in BigQuery; trigger the DAG live and show it turning green; show failure + retry. Say clearly: active fire **detections**, not confirmed wildfires; no prediction; short data window.
Keep a backup of the raw CSV and screenshots for demo day.
