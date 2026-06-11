"""
prop65_list.py
Loads the OEHHA Prop 65 chemical list from a local CSV file.
Caches the parsed list to docs/prop65_cache.json for performance.

To update the list:
  1. Go to: https://oehha.ca.gov/proposition-65/proposition-65-list
  2. Download the CSV file
  3. Save it to: docs/p65chemicalslist.csv
  4. Delete docs/prop65_cache.json to force a fresh parse
  5. Re-run: python src/main.py
"""

import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

LOCAL_CSV = Path(__file__).parent.parent / "docs" / "p65chemicalslist.csv"
CACHE_FILE = Path(__file__).parent.parent / "docs" / "prop65_cache.json"
CACHE_MAX_AGE_DAYS = 30


def _parse_csv(content):
    lines = content.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if line.startswith("Chemical,"):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("Could not find header row in Prop 65 CSV")
    reader = csv.DictReader(lines[header_idx:])
    chemicals = []
    for row in reader:
        name = row.get("Chemical", "").strip()
        cas = row.get("CAS No.", "").strip()
        toxicity = row.get("Type of Toxicity", "").strip()
        date_listed = row.get("Date Listed", "").strip()
        if name:
            chemicals.append({
                "name": name,
                "cas": cas,
                "toxicity": toxicity,
                "date_listed": date_listed,
                "name_lower": name.lower(),
                "name_words": list(re.findall(r"[a-z0-9]+", name.lower())),
            })
    return chemicals


def load_prop65_list():
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Use cache if fresh
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            cached = json.load(f)
        fetched_at = datetime.fromisoformat(cached["fetched_at"])
        if datetime.now() - fetched_at < timedelta(days=CACHE_MAX_AGE_DAYS):
            print(f"[prop65] Using cached list ({len(cached['chemicals'])} chemicals, "
                  f"fetched {fetched_at.strftime('%Y-%m-%d')})")
            return cached["chemicals"]

    # Load from local CSV
    if not LOCAL_CSV.exists():
        print("""
[prop65] ERROR: Prop 65 chemical list not found.

To install the list:
  1. Go to: https://oehha.ca.gov/proposition-65/proposition-65-list
  2. Download the CSV file
  3. Save it to: docs/p65chemicalslist.csv
  4. Re-run: python src/main.py
""")
        import sys; sys.exit(1)

    print(f"[prop65] Loading from local CSV: {LOCAL_CSV}")
    with open(LOCAL_CSV, encoding="latin-1") as f:
        content = f.read()
    chemicals = _parse_csv(content)
    cache_data = {
        "fetched_at": datetime.now().isoformat(),
        "source": str(LOCAL_CSV),
        "chemicals": chemicals,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2)
    print(f"[prop65] Cached {len(chemicals)} chemicals")
    return chemicals


def build_lookup(chemicals):
    cas_lookup = {}
    name_lookup = {}
    for chem in chemicals:
        if chem["cas"]:
            cas_lookup[chem["cas"]] = chem
        name_lookup[chem["name_lower"]] = chem
    return cas_lookup, name_lookup
