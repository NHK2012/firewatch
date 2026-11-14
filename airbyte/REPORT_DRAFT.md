# Report text drafts (B10) - fill the ____ with YOUR measured numbers, then adapt

Wording rule: say "active fire detection", never "confirmed wildfire"; no prediction.

## Ingestion (Airbyte)
Data comes from NASA FIRMS, VIIRS NOAA-20 375 m near-real-time active fire detections (`VIIRS_NOAA20_NRT`; the S-NPP product `VIIRS_SNPP_NRT` returned no data rows in our test and its latest available date was 2026-11-02, so NOAA-20 was chosen), via the FIRMS area API,
which returns CSV and allows at most five days per request. NASA has no ready-made Airbyte connector, so a custom source
was built (Airbyte Connector Builder / declarative manifest `airbyte/firms_connector.yaml`) [or: the Airbyte File source, see fallback].
The connector takes the MAP_KEY as a secret user input, requests the world in five-day slices, parses the CSV, and adds a
`product` column so near-real-time and later standard-processing records can be told apart. Incremental sync uses `acq_date` as the cursor.
One day of data held 12,795 rows; a five-day test sync took ____ minutes, so the loading window was set to ____ days.
Syncs run in Incremental | Append mode: overlapping windows and re-pulled days create duplicates on purpose, which dbt removes
(observation key + deduplication + unique test). A known limitation is that FIRMS answers an invalid key with a text message rather
than an error status, so the pipeline validates the source and the loaded data in Airflow instead of trusting the connector alone.

## Warehouse (BigQuery)
Three datasets form the layers: `firewatch_raw` (untouched Airbyte output, never edited by hand), `firewatch_staging` (cleaned views
and intermediate tables) and `firewatch_marts` (the only dataset the app may read). All datasets use the US location because Airbyte, dbt
and the app must match it. Access follows least privilege: `sa-airbyte` and `sa-dbt` can edit data and run jobs; `sa-app` can run queries
and only read `firewatch_marts` (verified: reading raw and writing marts are denied). Cost guardrails: bytes-billed caps in dbt and the app
[and a budget alert]. [Sandbox/billing decision and why: ____.]

## Orchestration (Airflow)
The DAG `firewatch_pipeline` runs daily and has six tasks: source check, Airbyte sync trigger, raw-data validation, `dbt seed` + `dbt run`,
`dbt test`, completion. The source check calls the FIRMS data-availability endpoint, so a wrong key or stale data fails before any load.
The Airbyte task starts the sync through Airbyte's API and polls until it succeeds, fails, or 60 minutes pass. Raw validation checks required
columns, a minimum row count for today's load, and coordinate sanity before dbt runs. Every task retries twice with a five-minute delay;
`catchup` is off because Airbyte's cursor already covers missed days and `max_active_runs` is 1 so two syncs never write at once. When a task
fails, downstream tasks are marked `upstream_failed`, so bad or missing data never reaches the marts. Credentials are passed as Airflow
Variables from environment variables (never committed) and are masked in logs. Failure demo: ____ (paste the log lines).
