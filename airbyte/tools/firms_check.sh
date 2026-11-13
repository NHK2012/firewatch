#!/usr/bin/env bash
# B1 - NASA FIRMS test. Prints the header (your real column list) and the row count.
# Usage:  export FIRMS_MAP_KEY="..."   (never commit it)   then:
#         bash airbyte/tools/firms_check.sh [PRODUCT] [OUTFILE] [DAYS]
#   e.g.  bash airbyte/tools/firms_check.sh VIIRS_SNPP_NRT sample.csv 1
# Output: sample.csv in the current folder (*.csv is git-ignored) - Neha needs it for the fixture.
set -euo pipefail
: "${FIRMS_MAP_KEY:?Set FIRMS_MAP_KEY first (export FIRMS_MAP_KEY=...)}"
PRODUCT="${1:-VIIRS_SNPP_NRT}"
OUT="${2:-sample.csv}"
DAYS="${3:-1}"

code=$(curl -s -o "$OUT" -w '%{http_code}' \
  "https://firms.modaps.eosdis.nasa.gov/api/area/csv/${FIRMS_MAP_KEY}/${PRODUCT}/world/${DAYS}")
echo "HTTP status : $code"
[ "$code" = "200" ] || { echo "FAIL: expected HTTP 200"; exit 1; }

header=$(head -1 "$OUT" | tr -d '\r')
case "$header" in
  latitude,*) ;;
  *) echo "FAIL: first line is not a CSV header (wrong key?): ${header:0:80}"; exit 1 ;;
esac
echo "Header      : $header"

# awk counts the last line even without a trailing newline (wc -l does not)
rows=$(awk 'NR>1 && NF>0 {n++} END{print n+0}' "$OUT")
echo "File size   : $(wc -c < "$OUT") bytes"
echo "Rows ($DAYS day) : $rows   <- use this to size the window (guide 2.4)"
if [ "$rows" -lt 1 ]; then
  echo "FAIL: header only, NO data rows. Not usable. Try: a different product"
  echo "      (VIIRS_NOAA20_NRT), 2 days (3rd argument), or check the key/transaction limits."
  exit 1
fi
echo "Saved to    : $OUT   (do not commit; screenshot A = 'head -3 $OUT', key hidden)"