# FireWatch report notes — N10

## Analytics engineering and dbt

The analytics pipeline is **Airbyte-loaded FIRMS data → dbt staging → dbt intermediate models → five BigQuery marts**. The production source is `firewatch-de.firewatch_raw.active_fire_observations`; the Streamlit app reads only the published `firewatch_marts` tables.

- Staging uses safe casts for source values that arrive as strings, normalizes confidence, parses acquisition date/time, and filters invalid coordinates, dates/times, confidence values, and negative FRP.
- The intermediate observations model derives a deterministic observation key and uses `ROW_NUMBER()` to keep the latest extracted copy. A one-degree grid-cell dimension supports regional assignment; priority-ordered bounds from the `region_bounds` seed resolve overlaps, with `Unclassified` as the fallback.
- The five marts are `mart_daily_fire_activity`, `mart_regional_fire_activity`, `mart_monthly_fire_activity`, `mart_fire_intensity`, and `mart_fire_anomalies`.
- dbt schema tests and project documentation cover the model contracts and data quality checks.

### Live validation results (N8)

- Live source freshness passed. The backfill covers **2026-08-17 through 2026-11-14**.
- Counts: raw **6,162,207**; staging **6,162,203**; intermediate **6,162,203**. The four excluded records had negative FRP; no valid duplicate observations were removed in this snapshot.
- All eight dbt models built, and all **84 dbt data tests passed**.
- Mart row counts: daily **90**; regional **12**; monthly **4**; intensity **3**; anomalies **61,645**.

## Conversational BI

The Streamlit app uses a BigQuery client configured for project `firewatch-de`. The live validation used the existing `sa-app` key through `FIREWATCH_APP_KEYFILE`; credentials are not embedded in source, shown in the UI, or written to application logs. Application code routes questions to fixed query templates and rejects SQL outside the exact intent-query allowlist. It does not insert question text into SQL. All query execution passes through one function that sets `maximum_bytes_billed` to **5,000,000,000 bytes (5 GB)**. Regional and anomaly row limits are bound parameters, not interpolated text.

The dashboard is divided into an overview, an activity explorer, and conversational intelligence. The overview derives KPIs and charts from live daily, regional, and intensity marts. The explorer covers all five marts with daily/monthly trends, regional and intensity comparisons, and a high-FRP anomaly map/table. Query results are cached for five minutes; the refresh control clears that cache.

Eight supported conversational intents:

1. **Overall statistics** — daily and intensity marts.
2. **Daily activity** — daily mart.
3. **Monthly activity** — monthly mart.
4. **Regional activity** — regional mart.
5. **FRP intensity** — intensity mart.
6. **Highest-FRP anomalies** — anomalies mart.
7. **Confidence/reliability** — daily mart.
8. **Day versus night** — daily mart.

Each supported response includes a concise data-derived answer, chart or table, and an expander with the fixed SQL and bound parameter values. Unsupported input receives the specified polite fallback and does not execute a query. Loading indicators, empty states, refresh, and sanitized authentication/query errors are implemented.

### N9/N10 application validation results

- The existing application tests and the added N10 guardrail tests pass: **9 unit tests**.
- The eight intent queries were run against live marts; each produced a result and chart. Result sizes were: overall **1**, daily **90**, monthly **4**, regional **12**, intensity **3**, anomalies **20** (bounded), reliability **1**, and day/night **1** row.
- Streamlit AppTest verified the overview (four live KPIs and five charts), explorer (five charts and five tables), and a clickable conversational question with a data-derived answer and SQL expander. A separate AppTest exercised each of the eight examples and its SQL expander; unsupported input returned the exact fallback without a new SQL result.
- Read-only-policy tests reject unapproved SQL and unsafe row limits. Tests verify the 5 GB cap is attached to every intent query and the 100-row explorer anomaly query.
- Python compilation and syntax checks passed; the local Streamlit health endpoint returned `ok` and its HTTP page returned **200**.
- The app enforces read-only SQL in application code. The service account's GCP IAM policy was **not independently inspected**, so its IAM permissions should not be described as verified read-only.

## Limitations and interpretation

- FIRMS records represent satellite-observed thermal anomalies; a detection is **not necessarily a confirmed wildfire**.
- FRP categories are project-defined: Low below 10 MW, Moderate from 10 MW to below 50 MW, and High at or above 50 MW; these are not official NASA fire classifications.
- FireWatch describes historical activity and anomalies; it does **not** predict fires.
- Regional labels are approximate grid-cell assignments based on configured geographic bounds.
- The intermediate model's 59-day extraction-partition expiration is a BigQuery Sandbox-era development workaround, not the intended production retention design. In the N8 validation, extraction timestamps were from the backfill run and no intermediate rows were older than the expiration cutoff. Revisit retention policy for production history requirements.

## Manual screenshot checklist

- [ ] **E — Overview:** capture the overview dashboard with live KPIs.
- [ ] **F — Explorer:** capture the activity explorer with a chart and data table.
- [ ] **G — Conversation:** capture a supported natural-language question and its live answer.
- [ ] **H — SQL transparency:** expand and capture the executed fixed SQL and bound parameters.

Capture these screenshots manually from the running application; no screenshots are generated by this report.
