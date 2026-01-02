#!/usr/bin/env python3
import json
import os
from datetime import datetime, timezone
from urllib.request import urlopen, Request

DATA_DIR = "data"
OUT_PATH = os.path.join(DATA_DIR, "market.json")
MANUAL_PATH = os.path.join(DATA_DIR, "manual.json")

# Free, no-key FX source (ECB-based). Docs: frankfurter.dev
FX_URL = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=TRY"


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "ykcapitalholdings-market-pulse"})
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def safe_load_manual() -> dict:
    if not os.path.exists(MANUAL_PATH):
        return {}
    try:
        with open(MANUAL_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    # 1) Auto: USD/TRY
    usdtry = {
        "value": None,
        "unit": "TRY per USD",
        "source": "auto (frankfurter.dev)",
        "as_of": None,
    }

    try:
        fx = fetch_json(FX_URL)
        rate = fx.get("rates", {}).get("TRY")
        date = fx.get("date")  # e.g. "2024-11-25" (latest working day)
        if rate is not None:
            usdtry["value"] = float(rate)
            usdtry["as_of"] = date
    except Exception as e:
        # keep None values if fetch fails
        usdtry["source"] = f"auto failed: {type(e).__name__}"

    # 2) Manual series (WCI/BDI/FBX)
    manual = safe_load_manual()
    manual_series = (manual.get("series") or {}) if isinstance(manual, dict) else {}

    def manual_entry(key, default_unit):
        obj = manual_series.get(key) or {}
        return {
            "value": obj.get("value"),
            "unit": obj.get("unit", default_unit),
            "source": obj.get("source", "manual"),
            "as_of": obj.get("as_of") or manual.get("as_of") or None,
        }

    out = {
        "generated_at": utc_now_iso(),
        "series": {
            "usdtry": usdtry,
            "wci": manual_entry("wci", "USD/40ft"),
            "bdi": manual_entry("bdi", "Index"),
            "fbx": manual_entry("fbx", "Index"),
        },
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
