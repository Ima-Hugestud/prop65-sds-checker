"""
prop65_list.py
Fetches and caches the official OEHHA Prop 65 chemical list.
"""

import csv
import json
import re
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

OEHHA_CSV_URL = "https://oehha.ca.gov/sites/default/files/media/2025-01/p65chemicalslist.csv"
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


def _fetch_csv_from_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        content = response.read().decode("utf-8-sig")
    return _parse_csv(content)


def load_prop65_list(force_refresh=False):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not force_refresh and CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            cached = json.load(f)
        fetched_at = datetime.fromisoformat(cached["fetched_at"])
        if datetime.now() - fetched_at < timedelta(days=CACHE_MAX_AGE_DAYS):
            print(f"[prop65] Using cached list ({len(cached['chemicals'])} chemicals)")
            return cached["chemicals"]

    if LOCAL_CSV.exists():
        print(f"[prop65] Loading from local CSV: {LOCAL_CSV}")
        with open(LOCAL_CSV, encoding="latin-1") as f:
            content = f.read()
        chemicals = _parse_csv(content)
        cache_data = {
            "fetched_at": datetime.now().isoformat(),
            "source": str(LOCAL_CSV),
            "chemicals": chemicals,
        }
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f, indent=2)
        print(f"[prop65] Cached {len(chemicals)} chemicals")
        return chemicals

    print(f"[prop65] Fetching Prop 65 list from OEHHA...")
    try:
        chemicals = _fetch_csv_from_url(OEHHA_CSV_URL)
        cache_data = {
            "fetched_at": datetime.now().isoformat(),
            "source": OEHHA_CSV_URL,
            "chemicals": chemicals,
        }
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f, indent=2)
        print(f"[prop65] Cached {len(chemicals)} chemicals")
        return chemicals
    except Exception as e:
        if CACHE_FILE.exists():
            print(f"[prop65] WARNING: Fetch failed ({e}). Using stale cache.")
            with open(CACHE_FILE) as f:
                return json.load(f)["chemicals"]
        raise RuntimeError(f"Cannot load Prop 65 list: {e}")


def build_lookup(chemicals):
    cas_lookup = {}
    name_lookup = {}
    for chem in chemicals:
        if chem["cas"]:
            cas_lookup[chem["cas"]] = chem
        name_lookup[chem["name_lower"]] = chem
    return cas_lookup, name_lookup
