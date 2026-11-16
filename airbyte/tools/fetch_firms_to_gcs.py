#!/usr/bin/env python3
"""FALLBACK ingestion (use only if the Connector Builder costs more than ~3 hours; guide 3.2).

Downloads FIRMS detections in 5-day windows, adds the `product` column, writes ONE CSV that the
Airbyte *File* source reads (stream name: active_fire_observations). Key comes from the environment only.

  export FIRMS_MAP_KEY=...
  python airbyte/tools/fetch_firms_to_gcs.py --days 30 --out firms_latest.csv
  python airbyte/tools/fetch_firms_to_gcs.py --days 30 --bucket gs://firewatch-de-xx-landing/firms_latest.csv

Airbyte File source: format csv, provider GCS (or a private HTTPS location), URL = the bucket path,
service-account JSON for the bucket. Use sa-airbyte and grant it Storage Object Viewer on that bucket.
Never put the MAP_KEY into any URL that Airbyte stores or that is public.
"""
import argparse
import csv
import io
import os
import sys
import time
from datetime import date, timedelta

import requests

BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def fetch(key, product, start, days):
    """One <=5-day window starting at `start`. Errors never echo the URL (it contains the key)."""
    try:
        r = requests.get(f"{BASE}/{key}/{product}/world/{days}/{start:%Y-%m-%d}", timeout=300)
        r.raise_for_status()
    except requests.RequestException as e:
        sys.exit(f"FIRMS request failed ({type(e).__name__}) for window {start}")
    if not r.text.startswith("latitude,"):
        sys.exit(f"FIRMS did not return CSV for window {start}: {r.text[:60]!r} (wrong key?)")
    return r.text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30, help="how many days back (window)")
    ap.add_argument("--product", default="VIIRS_NOAA20_NRT")
    ap.add_argument("--out", default="firms_latest.csv")
    ap.add_argument("--bucket", help="gs://bucket/path.csv - upload after writing")
    a = ap.parse_args()
    key = os.environ.get("FIRMS_MAP_KEY") or sys.exit("Set FIRMS_MAP_KEY")

    end = date.today()
    start = end - timedelta(days=a.days - 1)
    buf, header, n = io.StringIO(), None, 0
    w = None
    d = start
    while d <= end:
        span = min(5, (end - d).days + 1)
        rows = list(csv.reader(io.StringIO(fetch(key, a.product, d, span))))
        if header is None:
            header = rows[0] + ["product"]
            w = csv.writer(buf)
            w.writerow(header)
        for row in rows[1:]:
            w.writerow(row + [a.product])
            n += 1
        print(f"window {d} (+{span}d): {len(rows) - 1} rows")
        if len(rows) < 2:
            print("  warning: this window returned no data rows")
        d += timedelta(days=span)
        time.sleep(1)  # be polite to the API

    if n == 0:
        # Never write or upload an empty file: downstream tools would treat it as a valid extract.
        sys.exit(f"FAIL: NASA returned 0 data rows for {a.product} ({start} to {end}). Nothing written or uploaded. Check the product with the data_availability endpoint.")

    with open(a.out, "w", newline="") as f:
        f.write(buf.getvalue())
    print(f"wrote {n} rows to {a.out}")
    if a.bucket:
        from google.cloud import storage
        bkt, _, blob = a.bucket.removeprefix("gs://").partition("/")
        storage.Client().bucket(bkt).blob(blob).upload_from_filename(a.out)
        print(f"uploaded to {a.bucket}")


if __name__ == "__main__":
    main()
