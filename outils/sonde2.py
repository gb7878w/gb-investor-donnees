"""Sonde 2 : composition Wikipedia du SBF 120 et vérification des ISIN candidats auprès d'Euronext."""
import json, re, time, urllib.parse
from sonde import get

w = get("https://fr.wikipedia.org/w/index.php?title=SBF_120&action=raw")[1].decode("utf-8", "replace")
i = w.find("== Composition")
print(w[i:i+9000] if i >= 0 else w[2000:11000])

def hist(isin, mic, start="2026-10-01", end="2026-10-26"):
    q = urllib.parse.urlencode({"format": "csv", "decimal_separator": ".", "date_form": "d/m/Y", "op": "", "adjusted": "Y", "base100": "", "startdate": start, "enddate": end})
    st, body, _ = get(f"https://live.euronext.com/en/ajax/AwlHistoricalPrice/getFullDownloadAjax/{isin}-{mic}?{q}")
    lignes = [l for l in body.decode("utf-8-sig", "replace").splitlines() if re.match(r"\d\d/\d\d/\d{4};", l)]
    return st, len(lignes)

for code in ["FR0003500008-XPAR", "FR0003999481-XPAR", "QS0011131735-XPAR", "FR0003502079-XPAR"]:
    isin, mic = code.split("-")
    print("indice", code, hist(isin, mic))
candidats = json.load(open("../univers/candidats.json"))
for c in candidats:
    res = None
    for mic in ["XPAR", "XAMS", "XBRU", "XMIL", "XLIS"]:
        st, n = hist(c["isin"], mic)
        if n > 0:
            res = (mic, n); break
        time.sleep(0.3)
    print("OK " if res else "?? ", c["isin"], c["code"], c["nom"], res)
    time.sleep(0.3)
