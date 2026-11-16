# airflow/dags/firewatch_pipeline.py  (Airflow 3 syntax)
#
# FireWatch pipeline: FIRMS source check -> Airbyte sync -> raw validation
#                     -> dbt seed + run -> dbt test -> finish
#
# Secrets come only from Airflow Variables (AIRFLOW_VAR_* env vars). Nothing is hard-coded.
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, Variable, task

PROJECT = os.environ["FIREWATCH_PROJECT"]
DBT_DIR = "/opt/airflow/dbt/firewatch_dbt"
DBT = "/home/airflow/dbt-venv/bin/dbt"
AIRBYTE = os.environ.get("AIRBYTE_API_URL", "http://host.docker.internal:8000/api/public/v1")
# Must be the same product as the Airbyte source input `source` (default VIIRS_NOAA20_NRT).
FIRMS_PRODUCT = os.environ.get("FIRMS_PRODUCT", "VIIRS_NOAA20_NRT")

# Retry delay is 5 min by default. For the failure demo set FIREWATCH_RETRY_DELAY_MIN=1
# in airflow/.env so the two retries are visible in about 2 minutes instead of 10.
RETRY_DELAY_MIN = int(os.environ.get("FIREWATCH_RETRY_DELAY_MIN", "5"))

# Columns the dbt staging model needs (names are never renamed upstream).
REQUIRED = {"latitude", "longitude", "acq_date", "acq_time", "frp",
            "confidence", "daynight", "satellite"}

# dbt: use its own virtualenv; keep target/ and logs/ out of the mounted repo folder.
DBT_ENV = {"DBT_TARGET_PATH": "/tmp/dbt_target", "DBT_LOG_PATH": "/tmp/dbt_logs"}

with DAG(
    dag_id="firewatch_pipeline",
    start_date=datetime(2026, 11, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "firewatch",
        "retries": 2,
        "retry_delay": timedelta(minutes=RETRY_DELAY_MIN),
    },
    tags=["firewatch", "de-microproject"],
    doc_md=__doc__,
) as dag:

    @task
    def check_data_source():
        """Fail early (before Airbyte) if the NASA key is wrong or the data is stale."""
        # The key is NEVER stored in a local variable: Airflow's failure log prints a task's
        # local variables, which would put the key on screen. The Variable is also named
        # *_api_key, so Airflow masks its value in logs as a second layer.
        failed = None
        try:
            resp = requests.get(
                "https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv/"
                f"{Variable.get('firms_api_key')}/{FIRMS_PRODUCT}", timeout=60)
            resp.raise_for_status()
        except requests.RequestException as exc:
            failed = type(exc).__name__      # exception text contains the URL (= the key): drop it
        if failed:
            raise RuntimeError(f"FIRMS request failed ({failed}); check the key and the network")

        rows = resp.text.strip().splitlines()
        if len(rows) < 2 or "invalid" in resp.text.lower():
            raise ValueError("FIRMS returned no availability row (invalid MAP_KEY or product?)")
        try:
            latest = datetime.strptime(rows[1].split(",")[-1].strip(), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("FIRMS availability response not understood "
                             f"(first line: {rows[0][:80]!r})") from None
        age = (datetime.now(timezone.utc).date() - latest).days
        print(f"FIRMS {FIRMS_PRODUCT}: latest day {latest} ({age} day(s) old)")
        if age > 3:
            raise ValueError(f"FIRMS data looks stale (latest day {latest})")

    def _auth():
        """Airbyte API bearer token (tokens are short-lived, so fetch per call)."""
        r = requests.post(f"{AIRBYTE}/applications/token", timeout=30, json={
            "client_id": Variable.get("airbyte_client_id"),
            "client_secret": Variable.get("airbyte_client_secret"),
            "grant-type": "client_credentials"})
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    @task
    def trigger_airbyte_sync():
        """Start the Airbyte connection and wait. Fails cleanly if Airbyte is down/fails."""
        job = requests.post(f"{AIRBYTE}/jobs", headers=_auth(), timeout=30, json={
            "connectionId": Variable.get("airbyte_connection_id"), "jobType": "sync"})
        if not job.ok:
            raise RuntimeError(f"Airbyte refused the sync: HTTP {job.status_code} {job.text[:200]}")
        job_id = job.json()["jobId"]

        deadline = time.time() + 3600
        while time.time() < deadline:          # poll every 20 s, give up after 60 min
            status = requests.get(f"{AIRBYTE}/jobs/{job_id}", headers=_auth(),
                                  timeout=30).json()["status"]
            print(f"Airbyte job {job_id}: {status}")
            if status == "succeeded":
                return job_id
            if status in ("failed", "cancelled", "incomplete"):
                raise RuntimeError(f"Airbyte sync {status} (job {job_id})")
            time.sleep(20)
        raise TimeoutError("Airbyte sync took longer than 60 minutes")

    @task
    def validate_raw_data():
        """Stop before dbt if the raw table is missing columns, empty today, or has bad values."""
        from google.cloud import bigquery

        # Tunable without editing code: Admin > Variables, or AIRFLOW_VAR_FIREWATCH_MIN_ROWS
        min_rows = int(Variable.get("firewatch_min_rows", default=1000))

        bq = bigquery.Client(project=PROJECT)
        ds = f"{PROJECT}.firewatch_raw"

        cols = {r.column_name for r in bq.query(
            f"select column_name from `{ds}.INFORMATION_SCHEMA.COLUMNS` "
            "where table_name = 'active_fire_observations'").result()}
        if REQUIRED - cols:
            raise ValueError(f"Raw table missing columns: {sorted(REQUIRED - cols)}")

        # Row count of this load + a cheap sanity check on coordinates.
        # SAFE_CAST: raw columns may arrive as numbers or strings.
        row = list(bq.query(f"""
            select
              count(*) as n,
              countif(safe_cast(latitude as float64) is null
                      or abs(safe_cast(latitude as float64)) > 90
                      or safe_cast(longitude as float64) is null
                      or abs(safe_cast(longitude as float64)) > 180) as bad_coords
            from `{ds}.active_fire_observations`
            where date(_airbyte_extracted_at) = current_date()""").result())[0]
        n, bad = row.n, row.bad_coords
        print(f"{n} rows loaded today, {bad} with invalid coordinates")
        if n < min_rows:
            raise ValueError(f"Only {n} rows loaded today (< {min_rows}); stopping before dbt")
        if bad > 0.05 * n:
            raise ValueError(f"{bad} of {n} rows have invalid coordinates (> 5%); stopping before dbt")

    # `dbt deps` only runs if Neha adds a packages.yml. Seeds first, then models.
    run_dbt_models = BashOperator(
        task_id="run_dbt_models",
        env=DBT_ENV, append_env=True,
        bash_command=(f"cd {DBT_DIR} && "
                      f"if [ -f packages.yml ]; then {DBT} deps --profiles-dir .; fi && "
                      f"{DBT} seed --profiles-dir . && {DBT} run --profiles-dir ."))

    run_dbt_tests = BashOperator(
        task_id="run_dbt_tests",
        env=DBT_ENV, append_env=True,
        bash_command=f"cd {DBT_DIR} && {DBT} test --profiles-dir .")

    @task
    def pipeline_complete(airbyte_job_id):
        print(f"FireWatch run complete at {datetime.now(timezone.utc).isoformat()} "
              f"(Airbyte job {airbyte_job_id})")

    sync = trigger_airbyte_sync()
    (check_data_source() >> sync >> validate_raw_data()
     >> run_dbt_models >> run_dbt_tests >> pipeline_complete(sync))
