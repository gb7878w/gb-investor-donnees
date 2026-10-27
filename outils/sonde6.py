"""Sonde 6 : EODHD, couverture des sociétés radiées de Paris. La clé n'est jamais affichée."""
import os, sys, json, urllib.request, urllib.parse
cle = os.environ.get("CLE_EODHD", "").strip()
if not cle:
    print("CLE_EODHD absent : rien à sonder.")
    sys.exit(0)

def api(chemin, **params):
    params.update(api_token=cle, fmt="json")
    url = f"https://eodhd.com/api/{chemin}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "GB-Investor-donnees/1.0"}), timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200].decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)[:200]

st, user = api("user")
print("compte :", st, {k: user.get(k) for k in ("subscriptionType", "dailyRateLimit", "apiRequests", "apiRequestsDate")} if isinstance(user, dict) else user)
for nom, delisted in [("cotées", None), ("radiées", 1)]:
    p = {"delisted": 1} if delisted else {}
    st, liste = api("exchange-symbol-list/PA", **p)
    print(f"liste Paris {nom} :", st, len(liste) if isinstance(liste, list) else liste)
    if isinstance(liste, list) and liste:
        print("  champs :", sorted(liste[0].keys()))
        print("  types :", sorted({x.get("Type") for x in liste}))
        print("  exemples :", [(x.get("Code"), x.get("Name", "")[:25], x.get("Isin")) for x in liste[:8]])
        if delisted:
            noms = {x.get("Code"): x for x in liste}
            for code in ("SEV", "UG", "CO", "TCH", "GTO", "ALO"):
                print("  ", code, "présent" if code in noms else "absent", (noms[code].get("Name"), noms[code].get("Isin")) if code in noms else "")
for sym in ("MC.PA", "SEV.PA", "UG.PA", "TCH.PA"):
    st, d = api(f"eod/{sym}", **{"from": "2016-10-27", "to": "2026-10-26", "period": "d"})
    if isinstance(d, list):
        print(sym, st, len(d), "séances", (d[0].get("date"), d[-1].get("date")) if d else "")
    else:
        print(sym, st, d)
