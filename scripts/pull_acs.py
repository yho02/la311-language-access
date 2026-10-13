"""Pull ACS 5-year tract estimates (and margins of error) for LA County.

Usage: CENSUS_API_KEY=... python3 scripts/pull_acs.py [year]
Writes data/raw/acs5_<year>_la_tracts.csv
"""
import csv, json, os, ssl, sys, urllib.parse, urllib.request

YEAR = sys.argv[1] if len(sys.argv) > 1 else "2023"
KEY = os.environ["CENSUS_API_KEY"]
CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem")  # python.org builds ship without CA certs
BASE = f"https://api.census.gov/data/{YEAR}/acs/acs5"

# (api table path, variables). E = estimate, M = margin of error
GROUPS = {
    "detail": [
        "C16002_001", "C16002_004", "C16002_007", "C16002_010", "C16002_013",  # households, limited-English by language group
        "B25003_001", "B25003_002", "B25003_003",                              # occupied units, owner, renter
        "B19013_001",                                                          # median household income
        "B25034_001", "B25034_002", "B25034_003", "B25034_004", "B25034_005",  # year built
        "B25034_006", "B25034_007", "B25034_008", "B25034_009", "B25034_010", "B25034_011",
        "B01003_001",                                                          # total population
        "B25001_001",                                                          # housing units
    ],
    "subject": ["S1601_C01_001", "S1601_C05_001"],  # pop 5+, % speak English less than "very well"
}

def fetch(path, variables):
    names = [v + s for v in variables for s in ("E", "M")]
    params = {"get": "NAME," + ",".join(names), "for": "tract:*",
              "in": "state:06 county:037", "key": KEY}
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=120, context=CTX) as r:
        rows = json.load(r)
    header, data = rows[0], rows[1:]
    return {row[header.index("state")] + row[header.index("county")] + row[header.index("tract")]:
            dict(zip(header, row)) for row in data}

detail = fetch("", GROUPS["detail"])
subject = fetch("/subject", GROUPS["subject"])

out = os.path.join(os.path.dirname(__file__), "..", "data", "raw", f"acs5_{YEAR}_la_tracts.csv")
cols = ["geoid", "NAME"] + [c for c in next(iter(detail.values())) if c not in ("NAME", "state", "county", "tract")] \
       + [c for c in next(iter(subject.values())) if c not in ("NAME", "state", "county", "tract")]
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(cols)
    for geoid, d in detail.items():
        merged = {**d, **subject.get(geoid, {}), "geoid": geoid}
        w.writerow([merged.get(c, "") for c in cols])
print(f"wrote {len(detail)} tracts, {len(cols)} columns -> {os.path.normpath(out)}")
