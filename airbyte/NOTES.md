# Airbyte notes (Bhagyashri)

Infrastructure steps that live only in a cloud console / UI are recorded here. **Never paste keys,
client secrets or the MAP_KEY into this file.**

## Status board (tick as you go)
- [x] B1 NASA key + one-day test (`bash airbyte/tools/firms_check.sh`): **12,795 rows/day** (VIIRS_NOAA20_NRT, ~1.07 MB)
- [x] B2 GCP project, 3 datasets (location US), 3 service accounts, teammate added, keys shared privately (reported done; `--check-roles` result: ____)
- [x] B3 Sandbox check: Sandbox works / switched to billing-enabled free trial / Snowflake (circle one)
- [ ] B4 Airbyte installed (`abctl local install`), UI at http://localhost:8000
- [ ] B5 Source connector built and tested (Builder, time spent: ____ h) or File-source fallback
- [ ] B6 Destination + connection + first sync verified. Connection ID: (kept in `airflow/.env`, not here)
- [ ] B9 Window chosen: 30 / 90 days (5-day test sync took ____ min)

## NASA product test results (B1)
| Product | Result (tested Fri 13 Nov 2026) |
| --- | --- |
| `VIIRS_SNPP_NRT` | HTTP 200 but header only, 0 data rows (1 day and 2 days). `data_availability` says latest date is **2026-11-02**, so it is stale. |
| `VIIRS_NOAA20_NRT` | HTTP 200, **12,795 data rows** for 1 day (1,066,586 bytes) |

Default product everywhere (connector input `source`, `FIRMS_PRODUCT` for the DAG, fetch script, check script) = `VIIRS_NOAA20_NRT`.
This does not mean SNPP is universally unavailable; it is the product that returned data in our test. Set the Airbyte source input
`source` and Airflow `FIRMS_PRODUCT` to the same value.

Size check: ~12.8k rows/day -> 30 days ~ 0.4 M rows, 90 days ~ 1.2 M rows (fine for BigQuery).

## Decisions
- Connector: FireWatch NASA FIRMS (`firms_connector.yaml`, import via Builder > Import a YAML manifest).
  Fallback = File source (`tools/fetch_firms_to_gcs.py`) if the Builder costs more than ~3 hours.
- Sync mode: Incremental | Append, schedule Manual (Airflow triggers it). Duplicates are expected
  (overlapping windows, last cursor day re-pulled); dbt deduplicates.
- Raw table contract: `firewatch_raw.active_fire_observations` = FIRMS columns + `product` + `_airbyte_extracted_at`.

## Connector Builder settings (guide 3.2) - what `firms_connector.yaml` encodes
| Setting | Value |
| --- | --- |
| Base URL | `https://firms.modaps.eosdis.nasa.gov` |
| Inputs | `map_key` (secret), `source` (default `VIIRS_NOAA20_NRT`), `area` (default `world`), `start_date` |
| Path | `/api/area/csv/{{ config['map_key'] }}/{{ config['source'] }}/{{ config['area'] }}/5/{{ stream_interval.start_time }}` |
| Format | CSV decoder, no record selector needed |
| Incremental | datetime cursor `acq_date`, `%Y-%m-%d`, step `P5D`, granularity `P1D` |
| Transformation | add field `product = {{ config['source'] }}` |
| Types | numbers: latitude, longitude, bright_ti4, bright_ti5, scan, track, frp; strings: the rest (incl. `acq_date`, `acq_time`) |

### What was tested (offline, Airbyte CDK 7.48 against a mock FIRMS server)
- Manifest loads and `check` passes; 12 records over 3 five-day slices; `product` added; `acq_time` stays `'0123'`.
- Resume from saved state requests only from the last cursor day (state = `acq_date`).
- **Not tested:** the real NASA API, the Builder UI import (field names can differ between Airbyte versions),
  and large global responses (memory). Do the Builder test with your real key and fix in the UI if needed.

### Known gap: wrong MAP_KEY
FIRMS answers an invalid key with a plain-text message, not an error status, so the connector can
return **0 records instead of failing**. Guards: `firms_check.sh` (B1), the DAG `check_data_source`
(fails before Airbyte), and `validate_raw_data` (fails if the load is empty).

## BigQuery destination (guide 3.2)
Project ID = yours, location **US**, default dataset `firewatch_raw`, credentials = contents of
`keys/sa-airbyte.json`, standard loading (no GCS staging). Connection: Incremental | Append, Manual.
Airbyte also creates `airbyte_internal` (untyped copy) - that is normal.

## Updates due to unavailability of airbyte locally:
Airbyte Cloud is used, destination firewatch-bigquery, location US, the sandbox blocked sync (billingNotEnabled), and free-trial billing was enabled with a budget alert. No keys.

## Updates for B6:
connection name: firms-nasa
sync mode Incremental | Append
manual schedule
first sync 143,050 rows
first day: 2026-11-12
last day:2026-11-15
days_loaded: 4
raw rows: 143050

## Window decision (B9)
Run a 5-day test sync, time it (`python airbyte/tools/airbyte_api.py sync` prints elapsed minutes).
Under ~10 min -> `start_date` = 90 days back; otherwise 30. To change the window after a test: set the new
`start_date` on the source, then **Clear data** on the connection (UI, or `airbyte_api.py reset`) so the
cursor restarts, then sync again.

the 5-day test (1 min 53 s, 249,771 rows, 69.66 MB, about 50,000 rows per day), the decision (90 days from 2026-08-17), and later the final first day, last day and total rows.

the 90 day test:
days_loaded = 90
22mins50sec
raw rows = 6162207
first day = 2026-08-17
last day = 2026-11-14

Row	month	n	days
1	2026-08	1631834	15
2	2026-09	2017679	30
3	2026-10	1746913	31
4	2026-11	765781	14	

## Useful tools (`airbyte/tools/`)
| Tool | For |
| --- | --- |
| `firms_check.sh` | B1: HTTP 200, header present, rows per day, saves `sample.csv` |
| `setup_gcp.sh` | B2: datasets, service accounts, roles, dataset-level read for `sa-app`, keys |
| `verify_warehouse.py` | B3/B6/B9: raw summary; `--marts` row counts; `--check-roles` least-privilege proof |
| `airbyte_api.py` | B6/B9: trigger a timed sync or reset from the terminal |
| `fetch_firms_to_gcs.py` | Fallback ingestion (Airbyte File source) |
