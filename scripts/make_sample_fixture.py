# Gives Neha realistic data to build dbt models before Airbyte is ready.
# Usage: python scripts/make_sample_fixture.py sample.csv fixture.csv
import sys

import pandas as pd

src, out = sys.argv[1], sys.argv[2]
df = pd.read_csv(src, dtype={"acq_time": str})
df["product"] = "VIIRS_SNPP_NRT"                      # added by Airbyte later
df["_airbyte_extracted_at"] = pd.Timestamp.now(tz="UTC")
df.to_csv(out, index=False)
print(f"wrote {len(df)} rows to {out}")

# then, in a terminal:
#   bq --location=US mk --dataset <PROJECT_ID>:firewatch_raw_sample
#   bq load --source_format=CSV --skip_leading_rows=1 --autodetect \
#       firewatch_raw_sample.active_fire_observations fixture.csv
