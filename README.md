# FireWatch: Global Wildfire Monitoring & Risk Analytics

Data Engineering microproject (group of 2). An automated ELT pipeline that turns NASA FIRMS
VIIRS 375 m active fire detections into analytical tables and a conversational BI app.

```
NASA FIRMS API -> Airbyte -> BigQuery (raw) -> dbt (staging -> intermediate -> marts) -> Streamlit
                     orchestrated by Apache Airflow
```

> A detection is a thermal anomaly, not a confirmed wildfire. FRP bins are project-defined.
> This project monitors and analyses; it does not predict wildfires.

## Team and ownership

| Person | Branch | Folders |
| --- | --- | --- |
| Bhagyashri | `feature/data-platform` | `airbyte/`, `airflow/` |
| Neha | `feature/analytics` | `dbt/`, `app/`, `scripts/` |

Shared: `README.md`, `docs/`, `.env.example`, `.gitignore`. See `CONTRIBUTING.md` for the Git workflow.

## Repository layout

```
airbyte/            connector YAML + NOTES.md            (Bhagyashri)
airflow/            Dockerfile, compose, dags/           (Bhagyashri)
dbt/firewatch_dbt/  dbt project: models, seeds, tests    (Neha)
app/                Streamlit conversational BI          (Neha)
scripts/            helper scripts (fixture builder)     (Neha)
docs/               team plan, architecture, screenshots, report
```

## Quick start

1. `cp .env.example .env` and fill in values (never commit `.env`).
2. Create `keys/` locally and put service-account JSON files there (git-ignored).
3. dbt: `cd dbt && pip install -r requirements.txt && cd firewatch_dbt && dbt debug --profiles-dir .`
4. App: `cd app && pip install -r requirements.txt && streamlit run streamlit_app.py`

## Contracts between the two modules

- Raw table: `firewatch_raw.active_fire_observations` (FIRMS columns + `product`, `_airbyte_extracted_at`).
- Airflow runs `dbt seed && dbt run`, then `dbt test`, from `/opt/airflow/dbt/firewatch_dbt`.
- Marts: `mart_daily_fire_activity`, `mart_monthly_fire_activity`, `mart_regional_fire_activity`,
  `mart_fire_intensity`, `mart_fire_anomalies`.
