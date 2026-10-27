"""Sonde 3 de l'envoi 2 : champs DILA, calendriers BCE et Fed."""
import json, re, sys, html
sys.path.insert(0, "outils")
from sonde import get

url = ("https://www.info-financiere.gouv.fr/api/explore/v2.1/catalog/datasets/flux-amf-new-prod/records?"
       "where=identificationsociete_iso_cd_isi%3D%22FR0000133308%22&order_by=uin_dat_amf%20desc&limit=60")
st, body, _ = get(url)
print("DILA", st, len(body))
rows = json.loads(body).get("results", [])
print("champs :", sorted(rows[0].keys()) if rows else None)
for r in rows[:60]:
    print(r.get("uin_dat_amf", "")[:10], "|", r.get("informationdeposee_inf_tit_inf", "")[:90], "|", {k: v for k, v in r.items() if "typ" in k or "cat" in k or "nat" in k})

st, body, _ = get("https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html")
t = body.decode("utf-8", "replace")
print("BCE", st, len(t))
for m in list(re.finditer(r"[Mm]onetary policy meeting", t))[:6]:
    print("…", re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t[max(0, m.start() - 300): m.end() + 300])))[:500])
print("dates:", re.findall(r"\d{1,2}[-–]?\d{0,2}\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s*2026", t)[:20])
st, body, _ = get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
t = body.decode("utf-8", "replace")
i = t.find("2026 FOMC Meetings")
print("Fed", st, len(t), i)
print(re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t[i:i + 6000])))[:1500])
