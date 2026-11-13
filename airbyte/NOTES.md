# Airbyte notes (Bhagyashri)

- Connector: FireWatch NASA FIRMS (export YAML to `firms_connector.yaml`)
- Connection ID: (fill in after first sync; never paste secrets here)
- Sync mode: Incremental | Append, schedule Manual (Airflow triggers it)
- Decision: Connector Builder; fallback = File source if it costs more than ~3 hours
