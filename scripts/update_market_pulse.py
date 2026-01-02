import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "data")
OUT_PATH = os.path.join(DATA_DIR, "market.json")
MANUAL_PATH = os.path.join(DATA_DIR, "manual.json")

TE_API_KEY = os.environ.get("TE_API_KEY", "").strip()  # set as GitHub secret if you want
TE_BASE = "https://api.tradingeconomics.com"

FREIGHTOS_PAGE = "https://www.freightos.com/freight-resources/container-shipping-cost-calculator-free-tool/"


def http_get(url: str, headers=None, timeout=25) -> bytes:
    headers = headers or {}
    req = Request(url, headers={"User-Agent": "ykcapitalholdings-market-pulse/1.0", **headers})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path: str, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def te_url(path: str) -> str:
    # TradingEconomics API uses `c=` for credentials; docs show `f=` for format. :contentReference[oaicite:1]{index=1}
    key = TE_API_KEY or "guest:guest"  # if guest is disabled, add TE_API_KEY as a secret
    sep = "&" if "?" in path else "?"
    return f"{TE_BASE}{path}{sep}c={quote(key)}&f=json"


def te_market_search(term: str):
    # Markets search endpoint: /markets/search/{term} :contentReference[oaicite:2]{index=2}
    url = te_url(f"/markets/search/{quote(term)}")
    data = json.loads(http_get(url).decode("utf-8"))
    return data if isinstance(data, list) else []


def te_quote_by_symbol(symbol: str):
    # Quotes by symbol endpoint: /markets/symbol/{symbol} :contentReference[oaicite:3]{index=3}
    url = te_url(f"/markets/symbol/{quote(symbol)}")
    data = json.loads(http_get(url).decode("utf-8"))
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict):
        return data
    return {}


def pick_symbol(search_results, keywords):
    kw = [k.lower() for k in keywords]
    for row in search_results:
        name = str(row.get("Name", "")).lower()
        sym = str(row.get("Symbol", "")).lower()
        if all(k in (name + " " + sym) for k in kw) and row.get("Symbol"):
            return row["Symbol"]
    # fallback: first symbol
    for row in search_results:
        if row.get("Symbol"):
            return row["Symbol"]
    return ""


def parse_freightos_fbx(html: str):
    """
    Parse weekly FBX lane values from Freightos page (public weekly section). :contentReference[oaicite:4]{index=4}
    We extract:
      FBX01 (Asia-US West), FBX03 (Asia-US East), FBX11 (Asia-N. Europe), FBX13 (Asia-Med)
    """
    # Find the section "Week of <Month> <Day>..." then capture lane bullets.
    week_m = re.search(r"Week of\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th),\s+\d{4})", html)
    week = week_m.group(1) if week_m else ""

    def lane(pattern):
        m = re.search(pattern, html, re.IGNORECASE)
        if not m:
            return None
        # e.g. "$2,127/FEU" -> 2127
        num = m.group(1).replace(",", "")
        try:
            return float(num)
        except ValueError:
            return None

    fbx01 = lane(r"FBX01[^$]*\$\s*([0-9,]+)")
    fbx03 = lane(r"FBX03[^$]*\$\s*([0-9,]+)")
    fbx11 = lane(r"FBX11[^$]*\$\s*([0-9,]+)")
    fbx13 = lane(r"FBX13[^$]*\$\s*([0-9,]+)")

    return {
        "week_label": week,
        "FBX01": fbx01,
        "FBX03": fbx03,
        "FBX11": fbx11,
        "FBX13": fbx13,
    }


def append_series(existing_series, value):
    if value is None:
        return existing_series
    if not isinstance(existing_series, list):
        existing_series = []
    # avoid duplicate if last value same
    if existing_series and isinstance(existing_series[-1], dict) and existing_series[-1].get("v") == value:
        return existing_series
    existing_series.append({"t": now_iso(), "v": value})
    # keep last 120 points
    return existing_series[-120:]


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    existing = load_json(OUT_PATH, {"generated_at": None, "items": []})
    items_by_key = {it.get("key"): it for it in existing.get("items", []) if isinstance(it, dict)}

    def upsert(key, name, unit, fmt, value, source_url=""):
        it = items_by_key.get(key, {
            "key": key,
            "name": name,
            "unit": unit,
            "format": fmt,
            "source_url": source_url,
            "series": []
        })
        it["name"] = name
        it["unit"] = unit
        it["format"] = fmt
        if source_url:
            it["source_url"] = source_url
        it["series"] = append_series(it.get("series", []), value)
        items_by_key[key] = it

    # ---------- USDTRY (TradingEconomics) ----------
    # Use search to find the correct symbol, then quote-by-symbol. :contentReference[oaicite:5]{index=5}
    try:
        fx_search = te_market_search("USDTRY")
        fx_symbol = pick_symbol(fx_search, ["usdtry"])
        fx_quote = te_quote_by_symbol(fx_symbol) if fx_symbol else {}
        fx_value = fx_quote.get("Last")
        upsert(
            "usdtry",
            "USD/TRY FX",
            "TRY per USD",
            "fx",
            float(fx_value) if fx_value is not None else None,
            "https://tradingeconomics.com/"
        )
    except Exception:
        upsert("usdtry", "USD/TRY FX", "TRY per USD", "fx", None, "https://tradingeconomics.com/")

    # ---------- BDI (Baltic Dry Index) ----------
    try:
        bdi_search = te_market_search("Baltic Dry")
        bdi_symbol = pick_symbol(bdi_search, ["baltic", "dry"])
        bdi_quote = te_quote_by_symbol(bdi_symbol) if bdi_symbol else {}
        bdi_value = bdi_quote.get("Last")
        upsert(
            "bdi",
            "Baltic Dry Index (BDI)",
            "Index points",
            "number",
            float(bdi_value) if bdi_value is not None else None,
            "https://tradingeconomics.com/"
        )
    except Exception:
        upsert("bdi", "Baltic Dry Index (BDI)", "Index points", "number", None, "https://tradingeconomics.com/")

    # ---------- Freightos FBX (parse public weekly page) ----------
    try:
        html = http_get(FREIGHTOS_PAGE).decode("utf-8", errors="ignore")
        fbx = parse_freightos_fbx(html)

        # show 4 lanes as separate cards
        upsert("fbx01", "Freightos FBX01 (Asia → US West)", "USD / FEU", "usd", fbx.get("FBX01"), FREIGHTOS_PAGE)
        upsert("fbx03", "Freightos FBX03 (Asia → US East)", "USD / FEU", "usd", fbx.get("FBX03"), FREIGHTOS_PAGE)
        upsert("fbx11", "Freightos FBX11 (Asia → N. Europe)", "USD / FEU", "usd", fbx.get("FBX11"), FREIGHTOS_PAGE)
        upsert("fbx13", "Freightos FBX13 (Asia → Med)", "USD / FEU", "usd", fbx.get("FBX13"), FREIGHTOS_PAGE)
    except Exception:
        upsert("fbx01", "Freightos FBX01 (Asia → US West)", "USD / FEU", "usd", None, FREIGHTOS_PAGE)
        upsert("fbx03", "Freightos FBX03 (Asia → US East)", "USD / FEU", "usd", None, FREIGHTOS_PAGE)
        upsert("fbx11", "Freightos FBX11 (Asia → N. Europe)", "USD / FEU", "usd", None, FREIGHTOS_PAGE)
        upsert("fbx13", "Freightos FBX13 (Asia → Med)", "USD / FEU", "usd", None, FREIGHTOS_PAGE)

    # ---------- Drewry WCI (manual fallback) ----------
    manual = load_json(MANUAL_PATH, {})
    wci = manual.get("drewry_wci", {})
    wci_val = wci.get("value", None)
    upsert(
        "wci",
        wci.get("name", "Drewry WCI (manual)"),
        wci.get("unit", "USD / 40ft"),
        "usd",
        float(wci_val) if isinstance(wci_val, (int, float)) else None,
        wci.get("source_url", "")
    )

    out = {
        "generated_at": now_iso(),
        "items": list(items_by_key.values())
    }
    save_json(OUT_PATH, out)
    print("Wrote", OUT_PATH)


if __name__ == "__main__":
    main()
