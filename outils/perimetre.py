"""Périmètre de GB Investor : toutes les actions cotées à Paris (Euronext Paris, Euronext Growth Paris et Euronext Access Paris).

Deux listes sont réunies pour ne rien oublier :
- la couverture de l'historique long (couverture.json, publique, sans aucun cours) : toutes les actions de Paris connues d'EODHD ;
- la liste officielle des actions de Paris publiée par Euronext (si elle répond), qui rattrape les valeurs absentes d'EODHD.
Chaque valeur est rattachée à son marché (XPAR réglementé, ALXP Growth, XMLI Access), lu dans la liste officielle ou, à défaut,
dans sa page produit publique chez Euronext ; une valeur sans page ni marché de Paris est écartée (radiée ou cotée ailleurs).
Aucun plancher de liquidité : la liquidité (médiane des euros échangés par jour sur 60 séances) est seulement notée, et c'est la
page Sélection qui écarte les valeurs trop peu échangées.
Sortie : univers/elargi.json, relu chaque soir par donnees.py. À relancer à la main à chaque révision trimestrielle du SBF 120,
ou quand une introduction en Bourse doit apparaître dans l'appli.
"""
import base64, datetime as dt, html, json, os, re, statistics, sys, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import donnees

SEANCES_LIQUIDITE = 60
FORMES = re.compile(r"\s+(S\.?A\.?S?\.?|S\.?C\.?A\.?|S\.?E\.?|N\.?V\.?|PLC|SA|SAS|SCA|SE)\.?$", re.I)
MARCHES = {"XPAR": "Euronext Paris", "ALXP": "Euronext Growth Paris", "XMLI": "Euronext Access Paris"}
ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def nom_propre(nom):
    nom = nom.strip()
    for _ in range(2):
        nom = FORMES.sub("", nom).strip(" .,")
    return nom[:60] or "?"


def lire_couverture():
    url = donnees.HISTORIQUE + "couverture.json"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": donnees.UA}), timeout=120) as r:
        return json.loads(r.read())


def liquidites(cle, isins):
    """Médiane des euros échangés par jour sur les dernières séances, pour chaque ISIN demandé."""
    sortie = {}
    for k in range(1, 5):
        for v in donnees._lire_historique(f"historique-{k}.bin", cle)["valeurs"]:
            if v.get("isin") in isins and not v.get("radiee") and v["d"]:
                chiffres = [c * q for c, q in zip(v["c"][-SEANCES_LIQUIDITE:], v["v"][-SEANCES_LIQUIDITE:])]
                if chiffres:
                    sortie[v["isin"]] = statistics.median(chiffres)
    return sortie


LIEN = re.compile(r"/product/equities/([A-Z]{2}[A-Z0-9]{9}[0-9])-([A-Z]{4})[^>]*>\s*([^<]+?)\s*<")


def liste_euronext():
    """Liste officielle des actions de Paris (tableau « Equities » d'Euronext) : {isin: (nom, code, mic)}. Vide si la page ne répond pas."""
    url = "https://live.euronext.com/en/pd_es/data/stocks?mics=" + urllib.parse.quote(",".join(MARCHES))
    donnees_post = urllib.parse.urlencode({"draw": 1, "start": 0, "length": 5000, "iDisplayStart": 0, "iDisplayLength": 5000}).encode()
    try:
        req = urllib.request.Request(url, data=donnees_post, headers={"User-Agent": donnees.UA, "Accept": "application/json, */*",
                                                                     "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                                                                     "X-Requested-With": "XMLHttpRequest"})
        with urllib.request.urlopen(req, timeout=120) as r:
            lignes = json.loads(r.read().decode("utf-8", "replace")).get("aaData", [])
    except Exception as e:
        print(f"liste officielle Euronext indisponible ({type(e).__name__} {str(e)[:80]}) : couverture EODHD seule")
        return {}
    sortie = {}
    for ligne in lignes:
        cellules = [str(c) for c in ligne] if isinstance(ligne, list) else [str(c) for c in dict(ligne).values()]
        m = LIEN.search(" ".join(cellules))
        if not m or m.group(2) not in MARCHES:
            continue
        isin = m.group(1)
        texte = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in cellules]
        code = next((t for t in texte if t != isin and re.fullmatch(r"[A-Z0-9]{1,8}", t)), "")
        sortie[isin] = (html.unescape(m.group(3)), code, m.group(2))
    print(f"liste officielle Euronext : {len(sortie)} actions de Paris")
    return sortie


DESCRIPTION = re.compile(r'content="Stock [^"]*? ([A-Z]{2}[A-Z0-9]{9}[0-9]) ([A-Z]{4}) Euronext ')


def marche(isin):
    """Marché de cotation lu dans la page produit publique d'Euronext (balise description : « … ISIN MIC Euronext … Live quotes »).
    Renvoie le code MIC (XPAR marché réglementé, ALXP Growth, XMLI Access…) ou None si la valeur n'existe plus."""
    try:
        req = urllib.request.Request(f"https://live.euronext.com/en/product/equities/{isin}-XPAR", headers={"User-Agent": donnees.UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            page = r.read().decode("utf-8", "replace")
    except Exception:
        return None
    finally:
        time.sleep(0.4)
    m = DESCRIPTION.search(page)
    return m.group(2) if m and m.group(1) == isin else None


def main(sortie):
    cle = base64.b64decode(os.environ.get("CLE_DONNEES", ""))
    if len(cle) != 32:
        sys.exit("CLE_DONNEES absent ou invalide : rien n'est fait.")
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sbf = json.load(open(os.path.join(racine, "univers", "sbf120.json"), encoding="utf-8"))
    deja = {v["isin"] for v in sbf["valeurs"]}
    aujourdhui = dt.date.today()
    limite = (aujourdhui - dt.timedelta(days=12)).isoformat()
    # Toutes les actions vivantes de la couverture, y compris les introductions récentes (moins de 60 séances, sans date de fin)
    couverture = {c["isin"]: c for c in lire_couverture()["couverture"]
                  if c.get("isin") and ISIN.match(c["isin"]) and not c.get("radiee") and c.get("fin", limite) >= limite and c["isin"] not in deja}
    officielle = {i: x for i, x in liste_euronext().items() if i not in deja}
    absentes_eodhd = sorted(set(officielle) - set(couverture))
    print(f"{len(couverture)} actions vivantes dans la couverture, {len(officielle)} dans la liste officielle, "
          f"{len(absentes_eodhd)} seulement dans la liste officielle")
    candidats = sorted(set(couverture) | set(officielle))
    liq = liquidites(cle, set(candidats) | deja)
    retenues, ecartees, marches = [], [], {}
    for isin in candidats:
        mic = officielle[isin][2] if isin in officielle else marche(isin)
        if mic not in MARCHES:
            c = couverture[isin]
            ecartees.append(f"{c['nom']} ({isin}) : " + (f"marché {mic}, hors Paris" if mic else "page Euronext introuvable (radiée ?)"))
            continue
        marches[mic] = marches.get(mic, 0) + 1
        if isin in couverture:
            nom, code = couverture[isin]["nom"], couverture[isin]["id"].split(":")[1]
        else:
            nom, code = officielle[isin][0], officielle[isin][1]
        nom = nom_propre(nom)
        retenues.append({"isin": isin, "nom": nom, "code": code[:8], "secteur": "Autres valeurs", "alias": [nom.lower()],
                         "cac40": False, "sbf120": False, "mic": mic, "liquidite": round(liq.get(isin, 0))})
    print(f"{len(retenues)} valeurs hors SBF 120 retenues, {len(ecartees)} écartées ; marchés : {marches}")
    for e in ecartees[:80]:
        print("  écartée :", e)
    for i in absentes_eodhd[:80]:
        print("  sans historique long :", officielle[i][0], f"({i}, {officielle[i][2]})")
    tout = []
    for v in sbf["valeurs"]:
        tout.append(dict(v, sbf120=True, liquidite=round(liq.get(v["isin"], 0))))
    tout += sorted(retenues, key=lambda v: v["nom"].lower())
    res = {"revue": aujourdhui.isoformat(),
           "source": "Toutes les actions de Paris : SBF 120 (sbf120.json) + Euronext Paris, Euronext Growth Paris et Euronext Access Paris",
           "plancher_liquidite_euros": None, "seuil_liquidite_euros": None, "valeurs": tout}
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    json.dump(res, open(sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(tout)} valeurs au total : " + ", ".join(f"{sum(1 for v in tout if v['mic'] == m)} {n}" for m, n in MARCHES.items()))
    for nom in ("Sensorion",):
        print(f"  contrôle {nom} :", "présente" if any(nom.lower() in v["nom"].lower() for v in tout) else "ABSENTE")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "univers/elargi.json")
