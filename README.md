# FireWatch: Satellite-Based Active-Fire Monitoring and Analytics

FireWatch is a data engineering micro project. It automatically collects **NASA FIRMS VIIRS NOAA-20 near-real-time active-fire detections**, loads them into **Google BigQuery**, cleans and models them with **dbt**, and serves them through a **Streamlit** dashboard with a safe, restricted conversational interface. **Apache Airflow** runs the whole pipeline daily.

> **Wording rule.** Every record is an *active-fire detection* (a satellite thermal anomaly), **not** a confirmed wildfire.
> FRP classes (Low / Moderate / High) are project-defined, not official NASA severity classes.
> FireWatch describes observed activity. **It does not predict fires.**

```
NASA FIRMS Area API  ->  Airbyte Cloud  ->  BigQuery (raw)  ->  dbt (staging -> intermediate -> marts)  ->  Streamlit
 VIIRS_NOAA20_NRT        custom connector    firewatch_raw        firewatch_staging / firewatch_marts        dashboard + conversational BI
                                  \_______________ orchestrated daily by Apache Airflow (Docker Compose) ______________/
```

---

## Table of contents

1. [Project status and key results](#1-project-status-and-key-results)
2. [Architecture](#2-architecture)
3. [Technology stack](#3-technology-stack)
4. [Repository layout and ownership](#4-repository-layout-and-ownership)
5. [Data source](#5-data-source)
6. [BigQuery layout and the hand-over contract](#6-bigquery-layout-and-the-hand-over-contract)
7. [Prerequisites](#7-prerequisites)
8. [Setup and run](#8-setup-and-run)
9. [Pipeline details (Airbyte and Airflow)](#9-pipeline-details-airbyte-and-airflow)
10. [dbt models](#10-dbt-models)
11. [Streamlit application](#11-streamlit-application)
12. [Testing and validation](#12-testing-and-validation)
13. [Security and cost controls](#13-security-and-cost-controls)
14. [Troubleshooting](#14-troubleshooting)
15. [Known limitations](#15-known-limitations)
16. [Future work](#16-future-work)
17. [Team and Git workflow](#17-team-and-git-workflow)
18. [Data acknowledgement](#18-data-acknowledgement)

---

## 1. Project status and key results

Build window: 13 to 15 November 2026. Demo: 16 November 2026.

| Area | Result |
| --- | --- |
| Ingestion | Custom Airbyte Cloud connector for the FIRMS Area API, 5-day slices, incremental cursor on `acq_date` |
| Backfill | 90 days (2026-08-17 to 2026-11-14), world-wide, **6,162,207 rows** in 22 min 50 s, no missing days |
| Latest raw table | 6,245,635 rows (after later syncs) |
| Orchestration | Airflow DAG `firewatch_pipeline`, 6 tasks, daily, 2 retries per task |
| Transformation | 8 dbt models (1 view, 7 tables), 1 seed, **84 data tests** |
| Integrated validation | Pipeline run **twice** on `dev`: all 6 tasks green, 8/8 models built, 84/84 tests passed, identical row counts |
| Application | Dashboard + activity explorer + conversational BI with 8 fixed intents; 9 unit tests passing |

Latest reported row counts (identical after both integrated runs, 16 Nov 2026):

| Dataset / model | Rows |
| --- | --- |
| `firewatch_raw.active_fire_observations` | 6,245,635 |
| `stg_active_fires` | 6,245,631 |
| `int_fire_observations` | 6,204,267 |
| `dim_grid_cell` | 10,671 |
| `mart_daily_fire_activity` | 91 |
| `mart_monthly_fire_activity` | 4 |
| `mart_regional_fire_activity` | 12 |
| `mart_fire_intensity` | 3 |
| `mart_fire_anomalies` | 62,048 |

Reading the numbers: 4 rows are rejected by staging validation (negative FRP in the earlier validation; the latest 4 are not yet traced record by record), and 41,364 repeated records are removed by deduplication. The daily mart has 91 rows because the 90-day backfill (17 Aug to 14 Nov) plus 15 Nov were loaded.

**Still open before final submission:** verify the Google Cloud IAM roles of `sa-app` (read-only behaviour is enforced in application code, but IAM has not been independently inspected); capture the Streamlit screenshots E to H; confirm the integrated smoke test and the `dev` to `main` release; create the `demo-v1` tag.

---

## 2. Architecture

```
                   +-----------------------------+
                   |   Apache Airflow (Docker)   |  daily @ 00:00, retries x2, max_active_runs=1
                   +--------------+--------------+
                                  |
 check_data_source -> trigger_airbyte_sync -> validate_raw_data -> run_dbt_models -> run_dbt_tests -> pipeline_complete
        |                    |                       |                  |                  |
        v                    v                       v                  v                  v
  FIRMS availability   Airbyte Cloud API       BigQuery checks     dbt seed + run      dbt test
  endpoint             (sync job, polled)      (columns, rows,
                                                coordinates)

 NASA FIRMS --> Airbyte --> firewatch_raw --> stg_active_fires --> int_fire_observations --> 5 marts --> Streamlit
                              (all STRING)     (view, SAFE_CAST)   (dedup, is_reliable,    (firewatch_marts)
                                                                    grid cell + region)
```

**Two modules, one contract.** The *Data Platform* module (Airbyte, BigQuery set-up, Airflow) ends at the raw table. The *Analytics Engineering* module (dbt, Streamlit) starts at it. They meet at:

- the table `firewatch_raw.active_fire_observations` (column names never renamed, every value a string), and
- the commands `dbt seed && dbt run`, then `dbt test`, run by Airflow from the mounted dbt project.

---

## 3. Technology stack

| Layer | Technology | Why |
| --- | --- | --- |
| Source | NASA FIRMS Area API, `VIIRS_NOAA20_NRT` | Free, near-real-time, documented CSV |
| Ingestion | Airbyte Cloud (custom connector from a YAML manifest; BigQuery destination v3.1.0) | Declarative connector, built-in incremental state |
| Warehouse | Google BigQuery (project `firewatch-de`, location `US`) | Serverless, handles millions of rows |
| Transformation | dbt Core + `dbt-bigquery` | SQL models, tests, docs, lineage |
| Orchestration | Apache Airflow 3.0.2 on Docker Compose (PostgreSQL 16 metadata DB) | Retries, dependencies, run history |
| Application | Python, Streamlit, Plotly, Pandas | Fast interactive UI |
| Collaboration | Git and GitHub, feature branches and pull requests | Parallel module development |

Airflow runs dbt in its **own Python virtual environment** (`/home/airflow/dbt-venv`) inside the Airflow image to avoid dependency conflicts.

---

## 4. Repository layout and ownership

```
airbyte/              connector manifest, runbook, tools, notes            (Bhagyashri)
  firms_connector.yaml   FIRMS custom connector (declarative manifest)
  RUNBOOK.md, NOTES.md   step-by-step plan and decisions
  tools/                 setup_gcp.sh, firms_check.sh, airbyte_api.py, verify_warehouse.py,
                         grant_dataset.py, fetch_firms_to_gcs.py (fallback ingestion)
airflow/              Airflow environment and DAG                          (Bhagyashri)
  dags/firewatch_pipeline.py
  Dockerfile, docker-compose.yaml, .env.example, README.md
dbt/firewatch_dbt/    dbt project                                          (Neha)
  models/staging, models/intermediate, models/marts, seeds/region_bounds.csv,
  macros/generate_schema_name.sql, tests/generic/non_negative.sql
app/                  Streamlit application                                (Neha)
  streamlit_app.py, firewatch_bi/{dashboard,data,intents,visuals}.py, tests/test_intents.py
scripts/              make_sample_fixture.py (sample data for development) (Neha)
docs/                 plan, architecture, screenshots, report
CONTRIBUTING.md       Git workflow
```

| Person | Branch | Folders |
| --- | --- | --- |
| Bhagyashri | `feature/data-platform` | `airbyte/`, `airflow/` |
| Neha | `feature/analytics` | `dbt/`, `app/`, `scripts/` |

Shared: `README.md`, `docs/`, `.env.example`, `.gitignore`.

---

## 5. Data source

- **Product:** `VIIRS_NOAA20_NRT` (375 m, near-real-time). `VIIRS_SNPP_NRT` returned only a header row in an early test, so NOAA-20 was chosen.
- **API limits:** 1 to 5 days per request; a free `MAP_KEY` is required. An invalid key returns a text message rather than an error status, which is why Airflow validates the source and the loaded data.
- **Availability:** on 15 Nov 2026 the product was available from 2026-08-01 to 2026-11-15.
- **Fields (15):** `latitude`, `longitude`, `bright_ti4`, `bright_ti5`, `scan`, `track`, `acq_date`, `acq_time`, `satellite`, `instrument`, `confidence`, `frp`, `daynight`, `version`, plus `product` added by the connector. Airbyte also adds `_airbyte_extracted_at`.
- **Types:** the CSV decoder returns text, so all raw fields are declared as strings; dbt converts them with `SAFE_CAST`.

---

## 6. BigQuery layout and the hand-over contract

All datasets are in the **US** location. A location mismatch between Airbyte, dbt and the app makes queries fail.

| Dataset | Purpose | Contents |
| --- | --- | --- |
| `firewatch_raw` | Raw ingestion (never edited by hand) | `active_fire_observations` |
| `firewatch_staging` | Cleaned and intermediate data | `stg_active_fires`, `int_fire_observations`, `dim_grid_cell`, `region_bounds` |
| `firewatch_marts` | Analytical outputs (the only dataset the app reads) | five `mart_*` tables |
| `firewatch_raw_sample` | Development fixture | sample CSV (74,605 rows) |

**Service accounts (least privilege)**

| Account | Used by | Needs |
| --- | --- | --- |
| `sa-airbyte` | Airbyte destination | write to `firewatch_raw` |
| `sa-dbt` | dbt and the Airflow validation task | build models, run jobs |
| `sa-app` | Streamlit app | run queries, read `firewatch_marts` |

Key files live in git-ignored folders and are **never committed**.

---

## 7. Prerequisites

- Git, Python 3.10+, Docker Desktop (**at least 8 GB RAM** recommended for Airflow).
- A Google Cloud project with BigQuery enabled. The BigQuery sandbox is not enough: Airbyte's follow-up queries fail with `billingNotEnabled`, so enable free-trial billing and set a budget alert.
- A NASA FIRMS `MAP_KEY` (free, sent by email): https://firms.modaps.eosdis.nasa.gov/api/
- An Airbyte Cloud account (14-day free trial) with API client credentials.
- On Windows, use Git Bash, keep `.sh` and `.yaml` files with LF line endings, and use forward slashes in Docker mounts.

---

## 8. Setup and run

### 8.1 Clone and configure secrets

```bash
git clone https://github.com/NHK2012/firewatch.git && cd firewatch
git checkout dev
cp .env.example .env                 # fill in locally; never commit
mkdir -p keys                        # git-ignored; put sa-airbyte.json, sa-dbt.json, sa-app.json here
```

Root `.env` variables (names only):

| Variable | Meaning |
| --- | --- |
| `FIRMS_MAP_KEY` | NASA FIRMS key (for the check and fallback scripts) |
| `FIREWATCH_PROJECT` | GCP project id |
| `DBT_KEYFILE` | path to `sa-dbt.json` |
| `GOOGLE_APPLICATION_CREDENTIALS` | path to `sa-app.json` |

### 8.2 Google Cloud and the warehouse

```bash
PROJECT_ID=<your-project> TEAMMATE_EMAIL=<email> bash airbyte/tools/setup_gcp.sh
pip install google-cloud-bigquery requests
python airbyte/tools/verify_warehouse.py --project <your-project> --key keys/sa-airbyte.json
```

This creates the datasets and service accounts. Confirm that the key authenticates and all datasets are listed.

### 8.3 Airbyte Cloud (ingestion)

1. Test the source first: `export FIRMS_MAP_KEY=...; bash airbyte/tools/firms_check.sh` (expect HTTP 200 and a header row).
2. In Airbyte **Connector Builder**, import `airbyte/firms_connector.yaml`, test with your key (use the restricted area `68,6,98,36` for tests, because a world-wide test returns about 250,000 records and can freeze the browser), then **publish** it.
3. Create the **BigQuery destination** (standard loading method, project, location `US`, default dataset `firewatch_raw`, `sa-airbyte` key).
4. Create the **connection**: stream `active_fire_observations`, sync mode **Incremental | Append**, cursor `acq_date`, schedule **Manual** (Airflow triggers it). Append is deliberate: FIRMS has no natural primary key, so deduplication is done in dbt.
5. Copy the connection ID and create API client credentials for Airflow.

Time window rule used: a timed 5-day test sync took 1 min 53 s (249,771 records), so a **90-day window** was chosen. To backfill, set the source start date, clear the stream so the cursor resets, and run a full sync.

### 8.4 dbt (analytics layer)

```bash
cd dbt
pip install -r requirements.txt
cd firewatch_dbt
export FIREWATCH_PROJECT=<your-project>
export DBT_KEYFILE=../../keys/sa-dbt.json
dbt debug --profiles-dir .
dbt seed --profiles-dir . && dbt run --profiles-dir . && dbt test --profiles-dir .
```

While developing on the sample fixture instead of live data:

```bash
dbt run --profiles-dir . --vars '{raw_dataset: firewatch_raw_sample}'
```

Variables in `dbt_project.yml`: `raw_dataset=firewatch_raw`, `frp_moderate_min=10`, `frp_high_min=50`, `anomaly_percentile=99`.

### 8.5 Airflow (orchestration)

```bash
cd airflow
mkdir -p dags logs plugins config keys
cp .env.example .env                  # fill in values; never commit
cp ../keys/sa-dbt.json keys/sa-dbt.json
docker compose up airflow-init
docker compose up -d --build
# UI: http://localhost:8081   (published on 8081 because 8080 is often in use)
```

`airflow/.env` variables (names only):

| Variable | Meaning |
| --- | --- |
| `AIRFLOW_UID` | `50000` on Windows/macOS; `id -u` on Linux |
| `FIREWATCH_PROJECT` | GCP project id |
| `AIRFLOW_VAR_FIRMS_API_KEY` | NASA MAP_KEY (masked in logs) |
| `AIRFLOW_VAR_AIRBYTE_CONNECTION_ID` | Airbyte connection UUID |
| `AIRFLOW_VAR_AIRBYTE_CLIENT_ID` / `AIRFLOW_VAR_AIRBYTE_CLIENT_SECRET` | Airbyte API credentials |
| `AIRBYTE_API_URL` | for Airbyte Cloud: `https://api.airbyte.com/v1` |
| `FIRMS_PRODUCT` | default `VIIRS_NOAA20_NRT`; must match the Airbyte source input |
| `FIREWATCH_RETRY_DELAY_MIN` | default `5`; use `1` for the failure demo |
| `AIRFLOW_VAR_FIREWATCH_MIN_ROWS` | minimum rows per load (default `1000`) |

Open the UI, **unpause** `firewatch_pipeline` (a paused DAG stays queued), and trigger it. All six tasks should turn green.

### 8.6 Streamlit app

```bash
cd app
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml     # fill in the sa-app service account; git-ignored
streamlit run streamlit_app.py
```

The app can alternatively read the key file path from `FIREWATCH_APP_KEYFILE`. Run tests with `python -m pytest tests` from `app/`.

---

## 9. Pipeline details (Airbyte and Airflow)

### 9.1 Airbyte connector (`firms-nasa`)

- **User inputs:** `MAP_KEY` (secret), FIRMS product, area, start date.
- **Request:** HTTP GET to the FIRMS area endpoint, response decoded as CSV.
- **Slicing:** one request per 5-day window (the API maximum).
- **Cursor:** datetime cursor on `acq_date` (`%Y-%m-%d`).
- **Transformation:** adds `product` from the configured input.
- **Schema:** 15 fields, all strings (declaring numbers made Connector Builder report a schema mismatch because the CSV decoder returns text).

### 9.2 Airflow DAG `firewatch_pipeline`

Schedule `@daily`, `catchup=False` (the Airbyte cursor already covers missed days), `max_active_runs=1`, 2 retries per task.

| Task | What it does |
| --- | --- |
| `check_data_source` | Calls the FIRMS availability endpoint; fails fast on a wrong key or stale data |
| `trigger_airbyte_sync` | Requests an Airbyte token, starts a sync job via the REST API, polls every 20 s until it succeeds or fails |
| `validate_raw_data` | BigQuery checks: required columns exist, enough rows loaded, share of invalid coordinates |
| `run_dbt_models` | `dbt seed` and `dbt run` in the dbt virtualenv |
| `run_dbt_tests` | `dbt test` |
| `pipeline_complete` | Records completion |

If a task fails, all downstream tasks end as `upstream_failed`, so bad or missing data never reaches the marts.

**Failure demo.** Set `AIRFLOW_VAR_FIRMS_API_KEY=wrong` and `FIREWATCH_RETRY_DELAY_MIN=1`, recreate the containers and trigger the DAG. `check_data_source` fails, retries twice, and the other five tasks show `upstream_failed`. Afterwards **restore the real key and recreate the containers** (NASA returns 401 otherwise). Blur the key in any screenshot.

---

## 10. dbt models

Lineage: `source -> stg_active_fires -> int_fire_observations -> dim_grid_cell -> five marts`.

| Folder | Schema | Materialization |
| --- | --- | --- |
| `staging` | `firewatch_staging` | view |
| `intermediate` | `firewatch_staging` | table |
| `marts` | `firewatch_marts` | table |

### Staging: `stg_active_fires`
`SAFE_CAST` numeric and date fields; normalise date and time; map confidence (`l`, `n`, `h` to `low`, `nominal`, `high`); reject invalid coordinates, dates and times, unsupported confidence values and negative FRP. Source freshness: warn after 2 days, error after 7 days.

### Intermediate
- **`int_fire_observations`:** builds a deterministic observation key (including `product`), keeps the latest extracted copy with `ROW_NUMBER()`, adds `is_reliable` (confidence `nominal` or `high`). Partitioned daily by `_airbyte_extracted_at`, clustered by `grid_cell_id`, 59-day partition expiration (a BigQuery sandbox workaround; see limitations).
- **`dim_grid_cell`:** assigns each one-degree cell (`FLOOR` of latitude and longitude) to a region using the cell centre and the `region_bounds` seed; overlaps resolved by ascending priority; no match gives `Unclassified`.

### Marts

| Mart | Content |
| --- | --- |
| `mart_daily_fire_activity` | Daily detections, reliable / non-reliable, day / night, average and maximum FRP, 7-day rolling average over observed dates |
| `mart_monthly_fire_activity` | The same measures by calendar month |
| `mart_regional_fire_activity` | Per-region totals, reliable %, day / night, FRP, average position; keeps `Unclassified` |
| `mart_fire_intensity` | Counts by FRP class: Low (<10 MW), Moderate (10 to <50), High (>=50), Unknown |
| `mart_fire_anomalies` | Detections at or above the 99th-percentile FRP (`PERCENTILE_CONT(frp, 0.99)`), with region |

### Region seed (`seeds/region_bounds.csv`)
11 approximate bounding boxes: Central America & Caribbean, South America, North America, Europe, Middle East, Africa, Indian Subcontinent, Southeast Asia, East Asia, Northern Eurasia, Oceania. Labels are approximate grid-cell assignments, not official borders.

### Tests
84 data tests: not-null, accepted confidence values, non-negative FRP and regional metrics (generic `non_negative` test), valid required acquisition fields, and others declared in each `schema.yml`.

---

## 11. Streamlit application

Sections: **Overview** (KPIs and charts), **Activity Explorer** (all five marts with charts and tables, including the anomaly map and table), and **Conversational BI**.

**Conversational BI uses a fixed catalogue of eight intents; it is not text-to-SQL.**

| # | Intent | Source mart |
| --- | --- | --- |
| 1 | Overall detection statistics | daily and intensity |
| 2 | Daily activity | daily |
| 3 | Monthly activity | monthly |
| 4 | Regional activity | regional |
| 5 | FRP intensity | intensity |
| 6 | Highest-FRP anomalies | anomalies |
| 7 | Confidence / reliability | daily |
| 8 | Day versus night | daily |

How a question is answered: match it to an intent, run the predefined parameterised query on an approved mart, show a data-derived answer and chart, and offer an expander with the exact SQL and parameter values. Unsupported questions get a polite fallback and run no query.

Application modules: `streamlit_app.py` (entry), `firewatch_bi/dashboard.py` (sections), `data.py` (BigQuery client, caching, error handling, cost cap), `intents.py` (intent catalogue and router), `visuals.py` (Plotly charts).

---

## 12. Testing and validation

Results come from different stages and are **not additive**.

| Stage | Result |
| --- | --- |
| dbt, daily and regional marts (sample data) | 21 / 21 tests |
| dbt, monthly, intensity, anomalies (sample data) | 36 / 36 tests |
| dbt, all models, live data | 84 / 84 tests, 8 / 8 models built |
| Application unit tests | 9 passed (7 at N9, 9 at N10) |
| Conversational intents on live marts | 8 / 8 returned results; Overview and Explorer AppTest passed |
| Unsupported question | exact fallback, no query run |
| Airflow, two integrated runs | 6 / 6 tasks green both times; `validate_raw_data` reported 0 invalid coordinates |
| Idempotency | row counts identical after both runs |
| Failure test | invalid key: `check_data_source` fails, retried twice, rest `upstream_failed` |
| Append test | second sync did not replace the table; cursor prevented a full reload |

---

## 13. Security and cost controls

- **Secrets:** `.env`, `keys/`, `airflow/keys/`, `secrets.toml`, `target/` and `logs/` are git-ignored. Only `.env.example` files with variable names are committed. Airflow masks variables whose names contain `api_key` or `secret`, and the DAG never prints the FIRMS URL.
- **If a secret is committed or shared:** rotate it immediately and tell your teammate. Check `git status` before every commit; never `git add .` blindly.
- **Least privilege:** separate service accounts for ingestion, transformation and the app.
- **Application guardrails:** fixed intents, SQL allowlist, bound parameters (no user text in SQL), read-only behaviour enforced in code.
- **Cost cap:** every app query sets `maximum_bytes_billed = 5 GB`; results are cached for 5 minutes. The cap limits cost but a query over the cap fails by design.
- **To do:** independently verify that `sa-app` has only read access to `firewatch_marts` in Google Cloud IAM.

---

## 14. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `billingNotEnabled` on first Airbyte sync | BigQuery sandbox limitation: enable free-trial billing on the project |
| Destination check fails with a JSON error | Verify the `sa-airbyte` key with the Python BigQuery client (`verify_warehouse.py`), then recreate the destination with the verified key |
| Connector Builder page freezes | Test with a small area (`68,6,98,36`), then publish |
| Builder shows a schema mismatch warning | Declare all fields as strings |
| Sync mode asks for a primary key | Use Incremental | Append and deduplicate in dbt |
| Airflow UI does not start | Port 8080 in use: the UI is on **8081** |
| DAG run stays queued | The DAG is paused: unpause it |
| `validate_raw_data` fails with a missing key file | Put `sa-dbt.json` in `airflow/keys/` and recreate the containers |
| `KeyError: FIREWATCH_PROJECT` on DAG import | `airflow/.env` missing or not filled |
| `Signature verification failed` | All services must share the same `AIRFLOW__API_AUTH__JWT_SECRET`; `docker compose down && docker compose up -d` |
| Cannot reach Airbyte | Local Airbyte: check `localhost:8000`. Airbyte Cloud: check `AIRBYTE_API_URL` and the client credentials |
| NASA returns 401 after the failure test | Restore the real `MAP_KEY` and recreate the containers |
| dbt `Permission denied` on `target/` | dbt writes to `/tmp/dbt_target` inside the container; do not override `DBT_TARGET_PATH` |
| dbt cannot find the profile or key file | Check `FIREWATCH_PROJECT`, `DBT_KEYFILE` and that the key exists |
| BigQuery location errors | All datasets and tools must use `US` |

---

## 15. Known limitations

- **Short window:** 90 days of near-real-time data shows short-term patterns, not seasonal cycles or long-term trends. Daily counts are descriptive only.
- **NRT data can change** when NASA reprocesses it into standard-processing data.
- **Detections are not confirmed wildfires.** Thermal detections can include other heat sources.
- **FRP classes and regions are project-defined** and approximate.
- **Partitioning workaround:** the BigQuery sandbox rejected a 3,650-day partition expiration, so `int_fire_observations` uses `_airbyte_extracted_at` with a 59-day expiration. Revisit for production retention.
- **Deployment:** Airbyte Cloud runs on a 14-day trial and Airflow in local Docker; this is a development setup, not production.
- **Window end:** the backfill ended on 2026-11-14 although the source reported data to 2026-11-15.
- **Unreconciled records:** the 4 rows rejected by staging and the 2 raw rows beyond distinct detections are not yet traced record by record.
- **Conversational BI** supports only the eight fixed intents.
- **IAM** of `sa-app` is not yet independently verified.

---

## 16. Future work

- Add NOAA-21, Suomi NPP and MODIS products and compare satellites using the `product` column.
- Load a 12-month history and restore long partition retention outside the sandbox.
- Move Airflow to a managed service; add alerting on failed runs.
- Measure bytes billed and cost per run; add user testing for dashboard accessibility.
- Verify IAM least privilege and trace the unreconciled records.

---

## 17. Team and Git workflow

Team of two:

- **Bhagyashri:** Data Platform Engineering (NASA key, GCP and BigQuery set-up, Airbyte connector, destination and connection, backfill, Airflow DAG and Docker environment, integration runs).
- **Neha:** Analytics Engineering (dbt models, tests and docs, sample fixture, Streamlit dashboard and conversational BI, guardrails, application tests).

Workflow (see `CONTRIBUTING.md`):

1. Work only in your own folders on your feature branch (`feature/data-platform` or `feature/analytics`).
2. One feature, one commit, tested by hand first. Commit format: `<module>: <what> (<id>)`, for example `airflow: add raw validation task (B8)`.
3. Push after every commit; merge `origin/dev` regularly.
4. Never push directly to `dev` or `main`; open a pull request the other person reviews. Never force-push shared branches.
5. Both feature branches were merged into `dev` by pull requests (#1 analytics, #2 data platform). After the integrated smoke test, `dev` is merged into `main` and the demo-ready commit is tagged `demo-v1`.

---

## 18. Data acknowledgement

Active-fire data courtesy of **NASA's Fire Information for Resource Management System (FIRMS)**, operated by NASA's Earth Science Data and Information System (ESDIS) with funding from NASA's Earth Science Division. Please acknowledge FIRMS when reusing results.

---

## 19. Contributors
**Bhagyashri Joshi- D12B / 23 & Neha Karkhanis- D12B / 25** 
