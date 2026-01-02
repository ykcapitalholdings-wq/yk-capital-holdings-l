#!/usr/bin/env python3
import json
import os
import datetime as dt
from urllib.request import urlopen, Request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(_file_)))
MANUAL_PATH = os.path.join(ROOT, "data", "manual.json")
OUT_PATH = os.path.join(ROOT, "data", "market.json")

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=TRY"

def utc_now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

def fetch_usdtry():
    req = Request(FRANKFURTER_URL, headers={"User-Agent": "ykcapitalholdings-market-pulse"})
    with urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))

    # Expected shape:
    # { "base":"USD", "date":"YYYY-MM-DD", "rates": { "TRY": <number> } }
    rate = data["rates"]["TRY"]
    as_of = data.get("date")
    return {
        "label": "USD/TRY",
        "value": float(rate),
        "unit": "TRY per USD",
        "as_of": as_of,
        "source": "frankfurter",
        "url": "https://api.frankfurter.dev"
    }

def load_manual():
    if not os.path.exists(MANUAL_PATH):
        return {}
    with open(MANUAL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    manual = load_manual()

    series = {}
    # manual series (BDI/WCI/FBX)
    for k, v in manual.items():
        series[k] = v

    # auto series (USDTRY)
    try:
        series["usdtry"] = fetch_usdtry()
    except Exception as e:
        # If API fails, keep old value if it exists
        series["usdtry"] = {
            "label": "USD/TRY",
            "value": None,
            "unit": "TRY per USD",
            "as_of": None,
            "source": "frankfurter",
            "error": str(e)
        }

    out = {
        "updated_at": utc_now_iso(),
        "series": series
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_PATH}")

if _name_ == "_main_":
    main()
