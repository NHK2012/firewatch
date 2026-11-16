#!/usr/bin/env python3
"""Checks for B3/B6/B8/B9 - run from anywhere with a service-account key.

  python airbyte/tools/verify_warehouse.py --project PROJECT_ID --key keys/sa-dbt.json
  python airbyte/tools/verify_warehouse.py --project PROJECT_ID --key keys/sa-dbt.json --marts
  python airbyte/tools/verify_warehouse.py --project PROJECT_ID --key keys/sa-app.json --check-roles

Default  : raw-table summary (row count, first/last day, days_loaded, satellite x confidence,
           product populated, exact-duplicate count). Take screenshot C from the BigQuery console.
--marts  : row counts of every table in firewatch_staging and firewatch_marts. Run once, run the
           DAG twice, run again: intermediate/mart counts must NOT grow (B9 / smoke test step 6).
--check-roles : proves least privilege for sa-app (B2): marts readable, raw NOT readable, marts NOT writable.
Prints no secrets.
"""
import argparse
import sys

from google.api_core.exceptions import Forbidden
from google.cloud import bigquery
from google.oauth2 import service_account


def client(project, key):
    creds = service_account.Credentials.from_service_account_file(key) if key else None
    return bigquery.Client(project=project, credentials=creds, location="US")


def q(bq, sql):
    return list(bq.query(sql).result())


def raw_summary(bq, p):
    t = f"`{p}.firewatch_raw.active_fire_observations`"
    r = q(bq, f"""select count(*) raw_rows, min(acq_date) first_day, max(acq_date) last_day,
                  count(distinct acq_date) days_loaded,
                  countif(product is null) rows_without_product,
                  count(*) - count(distinct to_json_string(t)) exact_duplicates
                  from (select * except(_airbyte_raw_id, _airbyte_extracted_at, _airbyte_meta,
                                        _airbyte_generation_id) from {t}) t""")[0]
    print("RAW TABLE firewatch_raw.active_fire_observations")
    for k, v in dict(r).items():
        print(f"  {k:22} {v}")
    print("  note: exact_duplicates > 0 is expected with Append (D3); dbt deduplicates.")
    print("\n  satellite x confidence:")
    for x in q(bq, f"select satellite, confidence, count(*) n from {t} group by 1,2 order by n desc"):
        print(f"    {x.satellite!s:4} {x.confidence!s:8} {x.n}")
    cols = [c.column_name for c in q(bq, f"select column_name from `{p}.firewatch_raw.INFORMATION_SCHEMA.COLUMNS` "
                                          "where table_name='active_fire_observations' order by ordinal_position")]
    print("\n  columns:", ", ".join(cols))


def table_counts(bq, p):
    for ds in ("firewatch_staging", "firewatch_marts"):
        print(f"\n{ds}")
        for t in q(bq, f"select table_name, table_type from `{p}.{ds}.INFORMATION_SCHEMA.TABLES` order by 1"):
            n = q(bq, f"select count(*) n from `{p}.{ds}.{t.table_name}`")[0].n
            print(f"  {t.table_name:36} {t.table_type:10} {n}")


def expect_forbidden(label, fn):
    try:
        fn()
    except Forbidden:
        print(f"  OK   {label}: denied (as intended)")
        return True
    except Exception as e:  # noqa: BLE001 - report any denial-like error
        if "Access Denied" in str(e) or "403" in str(e):
            print(f"  OK   {label}: denied (as intended)")
            return True
        print(f"  ??   {label}: unexpected error {type(e).__name__}")
        return False
    print(f"  FAIL {label}: was allowed - fix IAM")
    return False


def check_roles(bq, p):
    ok = True
    print("Role check for the key you passed (expected: sa-app)")
    try:
        q(bq, f"select 1 from `{p}.firewatch_marts.INFORMATION_SCHEMA.TABLES` limit 1")
        print("  OK   can list firewatch_marts")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"  FAIL cannot read firewatch_marts: {type(e).__name__}")
    ok &= expect_forbidden("read firewatch_raw", lambda: q(
        bq, f"select count(*) from `{p}.firewatch_raw.active_fire_observations`"))
    ok &= expect_forbidden("write firewatch_marts", lambda: q(
        bq, f"create table `{p}.firewatch_marts.__iam_probe` as select 1 x"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--key", help="service-account JSON (default: gcloud/ADC login)")
    ap.add_argument("--marts", action="store_true")
    ap.add_argument("--check-roles", action="store_true")
    a = ap.parse_args()
    bq = client(a.project, a.key)
    if a.check_roles:
        check_roles(bq, a.project)
    elif a.marts:
        table_counts(bq, a.project)
    else:
        raw_summary(bq, a.project)
