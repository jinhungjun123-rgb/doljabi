"""Download full program lists from the three public APIs into data/programs/raw/<date>/ (keys from .env)."""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(sys.argv[1])
env = dotenv_values(ROOT / ".env")
DK, YK = env["DATA_GO_KR_SERVICE_KEY"], env["YOUTH_CENTER_API_KEY"]
OUT = ROOT / "data" / "programs" / "raw" / date.today().isoformat()
OUT.mkdir(parents=True, exist_ok=True)
B = "https://apis.data.go.kr/B554287/"


def get(url, params):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=60) as r:
                return r.read()
        except Exception as e:
            print("  retry", attempt, type(e).__name__)
            time.sleep(3)
    raise RuntimeError("failed: " + url)


def xml_items(raw):
    root = ET.fromstring(raw)
    total = int(root.findtext(".//totalCount") or 0)
    items = [{c.tag: (c.text or "").strip() for c in s} for s in root.iter("servList")]
    return total, items


def fetch_bokjiro(name, path, extra, rows=500):
    items, page = [], 1
    while True:
        total, got = xml_items(get(B + path, {"serviceKey": DK, "pageNo": page, "numOfRows": rows, **extra}))
        items += got
        print(f"{name}: page {page} → {len(items)}/{total}")
        if not got or len(items) >= total:
            break
        page += 1
    return items


def fetch_youth(rows=100):
    items, page = [], 1
    while True:
        d = json.loads(get("https://www.youthcenter.go.kr/go/ythip/getPlcy",
                           {"apiKeyNm": YK, "pageNum": page, "pageSize": rows, "rtnType": "json"}))
        got = d["result"]["youthPolicyList"] or []
        total = d["result"]["pagging"]["totCount"]
        items += got
        print(f"youth: page {page} → {len(items)}/{total}")
        if not got or len(items) >= total:
            break
        page += 1
    return items


for fname, fn in [("national.json", lambda: fetch_bokjiro("national", "NationalWelfareInformationsV001/NationalWelfarelistV001",
                                                           {"callTp": "L", "srchKeyCode": "001"})),
                  ("local.json", lambda: fetch_bokjiro("local", "LocalGovernmentWelfareInformations/LcgvWelfarelist", {})),
                  ("youth.json", fetch_youth)]:
    data = fn()
    (OUT / fname).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", fname, len(data))
