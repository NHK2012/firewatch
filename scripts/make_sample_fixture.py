"""Generate a BigQuery-ready fixture from a NASA FIRMS CSV.

Usage:
    $fixture = "fixture.csv"
    python scripts/make_sample_fixture.py input.csv $fixture

After generation, in PowerShell with FIREWATCH_PROJECT and DBT_KEYFILE set:
    $env:GOOGLE_APPLICATION_CREDENTIALS = $env:DBT_KEYFILE
    $dataset = "${env:FIREWATCH_PROJECT}:firewatch_raw_sample"
    bq --location=US mk --dataset $dataset
    bq load --location=US --replace --source_format=CSV --skip_leading_rows=1 --autodetect `
        "$dataset.active_fire_observations" $fixture
    $table = "$($env:FIREWATCH_PROJECT).firewatch_raw_sample.active_fire_observations"
    bq query --use_legacy_sql=false `
        "SELECT COUNT(*) FROM ``$table``"
    bq show --schema --format=prettyjson `
        "${env:FIREWATCH_PROJECT}:firewatch_raw_sample.active_fire_observations"

Compare the query count with the generated row count and inspect the returned schema.
"""

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Sequence


PRODUCT = "VIIRS_SNPP_NRT"
METADATA_COLUMNS = {"product", "_airbyte_extracted_at"}


def generate_fixture(input_path: Path, output_path: Path) -> int:
    if not input_path.is_file():
        raise FileNotFoundError(f"Input CSV does not exist: {input_path}")
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Input and output paths must be different.")

    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        try:
            headers = next(reader)
        except StopIteration as exc:
            raise ValueError("Input CSV is empty.") from exc

        if not headers or any(not header.strip() for header in headers):
            raise ValueError("Input CSV must have non-empty column names.")
        normalized_headers = [header.casefold() for header in headers]
        if len(normalized_headers) != len(set(normalized_headers)):
            raise ValueError("Input CSV contains duplicate column names.")
        existing_metadata = METADATA_COLUMNS.intersection(normalized_headers)
        if existing_metadata:
            names = ", ".join(sorted(existing_metadata))
            raise ValueError(
                f"Input CSV already contains reserved metadata column(s): {names}."
            )

        extracted_at = (
            datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        row_count = 0
        temporary_path = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=output_path.parent,
                delete=False,
            ) as fixture:
                temporary_path = Path(fixture.name)
                writer = csv.writer(fixture)
                writer.writerow(headers + ["product", "_airbyte_extracted_at"])
                for line_number, row in enumerate(reader, start=2):
                    if len(row) != len(headers):
                        raise ValueError(
                            f"CSV row {line_number} has {len(row)} fields; "
                            f"expected {len(headers)}."
                        )
                    writer.writerow(row + [PRODUCT, extracted_at])
                    row_count += 1
            temporary_path.replace(output_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    return row_count


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input_csv", type=Path, help="NASA FIRMS sample CSV")
    parser.add_argument("output_csv", type=Path, help="path for the generated fixture CSV")
    args = parser.parse_args(argv)

    try:
        row_count = generate_fixture(args.input_csv, args.output_csv)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        parser.error(str(exc))

    print(f"Generated {row_count} rows: {args.output_csv.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
