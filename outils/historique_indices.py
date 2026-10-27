"""Ajoute l'indice CAC 40 sur 10 ans (EODHD) à l'historique long, chiffré comme le reste. Clés jamais affichées."""
import os, sys, json, base64, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from donnees import chiffrer
from historique_long import api, DEBUT

cle = os.environ.get("CLE_EODHD", "").strip()
ch = base64.b64decode(os.environ.get("CLE_DONNEES", ""))
if not cle or len(ch) != 32:
    sys.exit("CLE_EODHD ou CLE_DONNEES absente : rien n'est fait.")
fin = (dt.date.today() - dt.timedelta(days=1)).isoformat()
sortie = sys.argv[1]
indices = {}
for ident, symbole in [("FR0003500008", "FCHI.INDX")]:
    lignes = api(cle, f"eod/{symbole}", **{"from": DEBUT, "to": fin, "period": "d"})
    d = [x["date"] for x in lignes if x.get("close")]
    c = [round(x["close"], 4) for x in lignes if x.get("close")]
    print(ident, symbole, len(d), "séances", (d[0], d[-1]) if d else "")
    if len(d) > 1000:
        indices[ident] = {"d": d, "c": c}
if "FR0003500008" not in indices:
    sys.exit("CAC 40 indisponible : fichier non écrit.")
with open(os.path.join(sortie, "historique-indices.bin"), "wb") as f:
    f.write(chiffrer(json.dumps({"version": 1, "indices": indices}, separators=(",", ":")).encode(), ch))
