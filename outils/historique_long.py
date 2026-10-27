"""Historique long (10 ans) de toutes les actions de Paris, radiées comprises, d'après EODHD.

Usage personnel : les cours ne sont jamais publiés en clair. Ils sont chiffrés (AES-256-GCM, en-tête GBI1) comme les autres fichiers
et ne servent qu'à l'apprentissage du modèle ; l'appli ne les télécharge pas. Seule la couverture (noms, dates de début et de fin,
séances manquantes) est publiée en clair, sans aucun cours.
La clé du service (CLE_EODHD) vient des secrets et n'est jamais affichée ni écrite.
"""
import os, sys, json, time, base64, datetime as dt, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from donnees import chiffrer

DEBUT = "2016-10-27"
PARTS = 4
UA = "GB-Investor-donnees/1.0 (usage personnel)"


def api(cle, chemin, essais=3, **params):
    params.update(api_token=cle, fmt="json")
    url = f"https://eodhd.com/api/{chemin}?{urllib.parse.urlencode(params)}"
    for n in range(essais):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if n == essais - 1:
                raise RuntimeError(type(e).__name__ + " " + str(getattr(e, "code", ""))) from None  # jamais l'URL : elle contient la clé
            time.sleep(2 * (n + 1))


def construire_valeur(code, nom, isin, radiee, lignes):
    """Séries ajustées (divisions et dividendes) : open, high et low suivent le rapport adjusted_close / close."""
    d, o, h, b, c, v = [], [], [], [], [], []
    for x in lignes:
        cl, aj = x.get("close"), x.get("adjusted_close")
        if not cl or cl <= 0 or not aj or aj <= 0:
            continue
        f = aj / cl
        op = (x.get("open") or cl) * f
        hi = (x.get("high") or cl) * f
        lo = (x.get("low") or cl) * f
        d.append(x["date"]); o.append(round(op, 4)); h.append(round(max(hi, op, aj), 4)); b.append(round(min(lo, op, aj), 4))
        c.append(round(aj, 4)); v.append(int(x.get("volume") or 0))
    return dict(id=f"PA:{code}", isin=isin, nom=nom, radiee=radiee, d=d, o=o, h=h, b=b, c=c, v=v)


def main(sortie):
    cle = os.environ.get("CLE_EODHD", "").strip()
    if not cle:
        sys.exit("CLE_EODHD absent : rien n'est téléchargé.")
    cle_chiffrement = base64.b64decode(os.environ.get("CLE_DONNEES", ""))
    if len(cle_chiffrement) != 32:
        sys.exit("CLE_DONNEES absent ou invalide : rien n'est publié.")
    fin = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    symboles = []
    for radiee in (False, True):
        liste = api(cle, "exchange-symbol-list/PA", **({"delisted": 1} if radiee else {}))
        for x in liste:
            if x.get("Type") == "Common Stock":
                symboles.append((x["Code"], x.get("Name", "")[:60], x.get("Isin"), radiee))
    vus, uniques = set(), []
    for s in symboles:  # une valeur à la fois dans les deux listes : la liste « radiées » l'emporte seulement si elle n'est pas cotée
        if s[0] not in vus:
            vus.add(s[0]); uniques.append(s)
    print(f"{len(uniques)} actions à télécharger (dont {sum(1 for s in uniques if s[3])} radiées)")
    valeurs, couverture, echecs = [], [], []
    for i, (code, nom, isin, radiee) in enumerate(uniques):
        try:
            lignes = api(cle, f"eod/{code}.PA", **{"from": DEBUT, "to": fin, "period": "d"})
            v = construire_valeur(code, nom, isin, radiee, lignes if isinstance(lignes, list) else [])
        except Exception as e:
            echecs.append(f"{code} : {e}")
            continue
        n = len(v["d"])
        if n < 60:
            couverture.append(dict(id=v["id"], isin=isin, nom=nom, radiee=radiee, seances=n, ecartee="moins de 60 séances"))
            continue
        valeurs.append(v)
        couverture.append(dict(id=v["id"], isin=isin, nom=nom, radiee=radiee, seances=n, debut=v["d"][0], fin=v["d"][-1]))
        if i % 50 == 0:
            print(f"{i}/{len(uniques)}")
        time.sleep(0.08)
    os.makedirs(sortie, exist_ok=True)
    genere = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    tailles = {}
    for k in range(PARTS):
        part = valeurs[k::PARTS]
        brut = json.dumps({"version": 1, "genere": genere, "valeurs": part}, separators=(",", ":")).encode()
        chemin = os.path.join(sortie, f"historique-{k + 1}.bin")
        with open(chemin, "wb") as f:
            f.write(chiffrer(brut, cle_chiffrement))
        tailles[f"historique-{k + 1}.bin"] = os.path.getsize(chemin)
    json.dump({"version": 1, "genere": genere, "debut_demande": DEBUT, "fin_demandee": fin, "valeurs": len(valeurs),
               "radiees": sum(1 for v in valeurs if v["radiee"]), "ecartees": sum(1 for c in couverture if c.get("ecartee")),
               "echecs": echecs[:100], "couverture": couverture},
              open(os.path.join(sortie, "couverture.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(valeurs)} valeurs retenues, {len(echecs)} échecs ; tailles : {tailles}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "historique")
