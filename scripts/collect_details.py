"""For each candidate: bokjiro detail API (national or local) + the matching 온통청년 record → raw/<date>/details.json"""
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from dotenv import dotenv_values

ROOT, CAND = Path(sys.argv[1]), Path(sys.argv[2])
DK = dotenv_values(ROOT / ".env")["DATA_GO_KR_SERVICE_KEY"]
RAW = ROOT / "data" / "programs" / "raw" / date.today().isoformat()
B = "https://apis.data.go.kr/B554287/"
youth = json.loads((RAW / "youth.json").read_text(encoding="utf-8"))


def detail(serv_id: str, local: bool) -> dict:
    path = ("LocalGovernmentWelfareInformations/LcgvWelfaredetailed" if local
            else "NationalWelfareInformationsV001/NationalWelfaredetailedV001")
    params = {"serviceKey": DK, "servId": serv_id, **({} if local else {"callTp": "D"})}
    root = ET.fromstring(urllib.request.urlopen(B + path + "?" + urllib.parse.urlencode(params), timeout=60).read())
    out, extra = {}, []
    for el in root.iter():
        if len(el):
            if any(c.tag == "servSeDetailNm" for c in el):   # 첨부, 연락처, 근거법령 같은 반복 항목
                extra.append({c.tag: (c.text or "").strip() for c in el})
            continue
        if (el.text or "").strip() and el.tag not in out:
            out[el.tag] = el.text.strip()
    out["_list"] = extra
    return out


def youth_record(c: dict) -> dict | None:
    if c.get("youth"):
        return next((p for p in youth if p["plcyNo"] == c["youth"]), None)
    if c.get("youth_name"):
        rx = re.compile(c["youth_name"])
        hits = [p for p in youth if rx.match(p["plcyNm"].strip()) and c["youth_inst"] in (p.get("sprvsnInstCdNm") or "")]
        return max(hits, key=lambda p: p["plcyNo"]) if hits else None   # plcyNo 앞 8자리 = 등록일 → 최신
    return None


out = []
for c in json.loads(CAND.read_text(encoding="utf-8")):
    rec = {"candidate": c}
    if c.get("bokjiro"):
        rec["bokjiro"] = detail(c["bokjiro"], local=False)
    if c.get("local"):
        rec["bokjiro"] = detail(c["local"], local=True)
    rec["youth"] = youth_record(c)
    out.append(rec)
    print(c["id"], c["name"][:30], "| bokjiro:", bool(rec.get("bokjiro")), "| youth:", bool(rec["youth"]))
(RAW / "details.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
