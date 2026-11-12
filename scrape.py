#!/usr/bin/env python3
"""Scrape MIT Bon Appétit dining-hall menus into site/data.json (today + tomorrow)."""
import datetime as dt, html as htmllib, json, re, sys, time
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

URL = "https://mit.cafebonappetit.com/cafe/{slug}/{date}/"
HALLS = [  # (url slug, display name) -- edit if a hall 404s
    ("the-howard-dining-hall-at-maseeh", "Maseeh"), ("new-vassar", "New Vassar"),
    ("baker", "Baker"), ("simmons", "Simmons"), ("next", "Next"), ("mccormick", "McCormick"),
]
DAYS_AHEAD = 1  # today plus this many more days
SKIP_STATIONS = ("condiment", "topping", "beverage", "coffee and tea", "golden waffle", "ice cream", "extras")
TAGS = (("vegan", "Vegan"), ("vegetarian", "Vegetarian"), ("gluten", "GF"), ("halal", "Halal"), ("kosher", "Kosher"))
DEC = json.JSONDecoder()

def clean(s):
    return htmllib.unescape(re.sub(r"<[^>]+>", "", s or "")).strip().lstrip("@").strip()

def t12(s):
    for f in ("%H:%M", "%H%M", "%H:%M:%S", "%I:%M %p"):
        try:
            return dt.datetime.strptime(str(s), f).strftime("%-I:%M %p").lower()
        except ValueError:
            pass
    return ""

def tags(item):
    icons = item.get("cor_icon") or {}
    names = [str(v).lower() for v in (icons.values() if isinstance(icons, dict) else [])]
    out = [t for k, t in TAGS if any(k in n for n in names)]
    return [t for t in out if not (t == "Vegetarian" and "Vegan" in out)]

def json_after(text, pos):
    return DEC.raw_decode(text[pos:].lstrip())[0]

def parse_page(text):
    """Return a list of meals, or None if the page has no embedded menu."""
    m = re.search(r"Bamco\.menu_items\s*=\s*", text)
    if not m:
        return None
    items = json_after(text, m.end())
    items = list(items.values()) if isinstance(items, dict) else items
    parts = {}
    for m in re.finditer(r"Bamco\.dayparts\[['\"]?(\w+)['\"]?\]\s*=\s*", text):
        try:
            obj = json_after(text, m.end())
        except ValueError:
            continue
        if isinstance(obj, dict) and "label" in obj:
            parts[m.group(1)] = obj
            parts[str(obj.get("id", m.group(1)))] = obj
        elif isinstance(obj, dict):
            parts.update({str(k): v for k, v in obj.items() if isinstance(v, dict) and "label" in v})
    meals = {}
    for it in items:
        if not isinstance(it, dict) or not it.get("label"):
            continue
        dp = str(it.get("daypart", ""))
        part = parts.get(dp, {})
        station = clean(it.get("station")) or "Other"
        if any(s in station.lower() for s in SKIP_STATIONS):
            continue
        a, b = t12(part.get("starttime")), t12(part.get("endtime"))
        meal = meals.setdefault(dp, {"label": clean(part.get("label")) or f"Meal {dp}",
                                     "hours": f"{a} – {b}" if a and b else "", "stations": {}})
        lst = meal["stations"].setdefault(station, [])
        name = clean(it["label"])
        if name and all(x["name"] != name for x in lst):
            lst.append({"name": name, "tags": tags(it)})
    def key(k):
        return (0, int(k)) if k.isdigit() else (1, 0)
    return [{"label": m["label"], "hours": m["hours"],
             "stations": [{"name": s, "items": i} for s, i in m["stations"].items()]}
            for _, m in sorted(meals.items(), key=lambda kv: key(kv[0]))]

def main():
    now = dt.datetime.now(ZoneInfo("America/New_York"))
    sess = requests.Session()
    sess.headers["User-Agent"] = "mit-menu-board (personal project)"
    days, ok = {}, 0
    for d in range(DAYS_AHEAD + 1):
        date = (now.date() + dt.timedelta(days=d)).isoformat()
        halls = []
        for slug, name in HALLS:
            entry = {"slug": slug, "name": name, "meals": []}
            try:
                r = sess.get(URL.format(slug=slug, date=date), timeout=30)
                r.raise_for_status()
                meals = parse_page(r.text)
                if meals is None:
                    raise ValueError("no Bamco.menu_items found in page")
                entry["meals"] = meals
                ok += 1
            except Exception as e:  # keep going; one bad hall shouldn't sink the run
                entry["error"] = str(e)
                print(f"WARN {slug} {date}: {e}", file=sys.stderr)
            halls.append(entry)
            time.sleep(1)
        days[date] = halls
    if not ok:
        sys.exit("No menus could be scraped; leaving the previous site in place.")
    out = Path("site/data.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"generated": now.isoformat(timespec="minutes"), "days": days}, ensure_ascii=False))
    print(f"Wrote {out} ({ok} hall-days scraped)")

if __name__ == "__main__":
    main()
