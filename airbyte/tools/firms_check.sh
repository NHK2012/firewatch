#!/usr/bin/env bash
# B1 - one-day NASA FIRMS test. Prints the header (your real column list) and the row count.
# Usage:  export FIRMS_MAP_KEY="..."   (never commit it)   then:  bash airbyte/tools/firms_check.sh
# Output: sample.csv in the current folder (*.csv is git-ignored) - Neha needs it for the fixture.
set -euo pipefail
: "${FIRMS_MAP_KEY:?Set FIRMS_MAP_KEY first (export FIRMS_MAP_KEY=...)}"
PRODUCT="${1:-VIIRS_SNPP_NRT}"
OUT="${2:-sample.csv}"

code=$(curl -s -o "$OUT" -w '%{http_code}' \
  "https://firms.modaps.eosdis.nasa.gov/api/area/csv/${FIRMS_MAP_KEY}/${PRODUCT}/world/1")
echo "HTTP status : $code"
[ "$code" = "200" ] || { echo "FAIL: expected HTTP 200"; exit 1; }

header=$(head -1 "$OUT")
case "$header" in
  latitude,*) ;;
  *) echo "FAIL: first line is not a CSV header (wrong key?): ${header:0:80}"; exit 1 ;;
esac
echo "Header      : $header"
echo "Rows (1 day): $(( $(wc -l < "$OUT") - 1 ))   <- use this to size the window (guide 2.4)"
echo "Saved to    : $OUT   (do not commit; screenshot A = 'head -3 $OUT', key blurred/hidden)"
