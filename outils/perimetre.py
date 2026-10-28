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

JOURNAL = []


def noter(*morceaux):
    """Affiche et garde la ligne pour univers/perimetre-journal.txt (les journaux d'Actions ne sont pas toujours lisibles)."""
    ligne = " ".join(str(m) for m in morceaux)
    print(ligne)
    JOURNAL.append(ligne)

SEANCES_LIQUIDITE = 60
FORMES = re.compile(r"\s+(S\.?A\.?S?\.?|S\.?C\.?A\.?|S\.?E\.?|N\.?V\.?|PLC|SA|SAS|SCA|SE)\.?$", re.I)
MARCHES = {"XPAR": "Euronext Paris", "ALXP": "Euronext Growth Paris", "XMLI": "Euronext Access Paris"}
ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
ISIN_DANS = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")


def nom_propre(nom):
    nom = nom.strip()
    for _ in range(2):
        nom = FORMES.sub("", nom).strip(" .,")
    return nom[:60] or "?"


def cle_nom(nom):
    return re.sub(r"[^a-z0-9]", "", nom_propre(nom).lower())


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


LIEN = re.compile(r"/product/equities/([A-Z]{2}[A-Z0-9]{9}[0-9])-([A-Z]{4})")


def liste_euronext():
    """Liste officielle des actions de Paris (tableau « Equities » d'Euronext) : {isin: (nom, code, mic)}. Vide si la page ne répond pas."""
    mics = urllib.parse.quote(",".join(MARCHES))
    essais = [  # le tableau ne remplit ses colonnes qu'avec display_datapoints ; le téléchargement CSV sert de repli
        ("tableau", f"https://live.euronext.com/en/pd_es/data/stocks?mics={mics}&display_datapoints=dp_stocks&display_filters=df_stocks",
         {"draw": 1, "start": 0, "length": 5000, "iDisplayStart": 0, "iDisplayLength": 5000}),
        ("csv", f"https://live.euronext.com/pd_es/data/stocks/download?mics={mics}",
         {"iDisplayLength": 5000, "iDisplayStart": 0, "args[initialLetter]": "", "args[fe_type]": "csv", "args[fe_decimal]": ".",
          "args[fe_date_format]": "d/m/Y"}),
    ]
    lignes = []
    for nom_essai, url, champs in essais:
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode(champs).encode(),
                                         headers={"User-Agent": donnees.UA, "Accept": "application/json, text/csv, */*",
                                                  "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest"})
            with urllib.request.urlopen(req, timeout=120) as r:
                brut = r.read().decode("utf-8-sig", "replace")
        except Exception as e:
            noter(f"liste officielle Euronext ({nom_essai}) indisponible : {type(e).__name__} {str(e)[:80]}")
            continue
        if nom_essai == "tableau":
            try:
                lignes = [l for l in json.loads(brut).get("aaData", []) if l]
            except ValueError:
                lignes = []
        else:
            lignes = [l.split(";") for l in brut.splitlines() if ISIN_DANS.search(l)]
        noter(f"liste officielle Euronext ({nom_essai}) : {len(lignes)} lignes utiles ; début : {brut[:300]!r}")
        if lignes:
            break
    if lignes:
        noter("  première ligne :", str(lignes[0])[:600])
    sortie = {}
    for ligne in lignes:
        cellules = [str(c) for c in ligne] if isinstance(ligne, list) else [str(c) for c in dict(ligne).values()]
        texte = [html.unescape(re.sub(r"<[^>]+>", " ", c)).strip() for c in cellules]
        texte = [re.sub(r"\s+", " ", t) for t in texte]
        k = next((j for j, t in enumerate(texte) if ISIN.match(t)), None)
        lien = LIEN.search(" ".join(cellules))
        isin = texte[k] if k is not None else (lien.group(1) if lien else None)
        if not isin:
            continue
        mic = lien.group(2) if lien and lien.group(1) == isin else None
        if mic not in MARCHES:
            marche_txt = " ".join(texte).lower()
            mic = "XMLI" if "access" in marche_txt else "ALXP" if "growth" in marche_txt else "XPAR" if "euronext paris" in marche_txt else None
        if mic not in MARCHES:
            continue
        j_nom = next((j for j, c in enumerate(cellules) if "/product/equities/" in c and texte[j]), None)
        nom = texte[j_nom] if j_nom is not None else (texte[k - 1] if k else "?")
        code = texte[k + 1] if k is not None and k + 1 < len(texte) and re.fullmatch(r"[A-Z0-9]{1,8}", texte[k + 1]) else ""
        sortie[isin] = (nom, code, mic)
    noter(f"liste officielle Euronext : {len(sortie)} actions de Paris")
    return sortie


DESCRIPTION = re.compile(r'content="Stock [^"]*? ([A-Z]{2}[A-Z0-9]{9}[0-9]) ([A-Z]{4}) Euronext ')


def marche(isin):
    """Marché de cotation lu dans la page produit publique d'Euronext (balise description : « … ISIN MIC Euronext … Live quotes »).
    Essaie l'adresse de chaque marché de Paris, deux fois en cas d'erreur réseau.
    Renvoie le code MIC (XPAR marché réglementé, ALXP Growth, XMLI Access…) ou None si la valeur n'existe plus."""
    for suffixe in MARCHES:
        for essai in range(2):
            try:
                req = urllib.request.Request(f"https://live.euronext.com/en/product/equities/{isin}-{suffixe}", headers={"User-Agent": donnees.UA})
                with urllib.request.urlopen(req, timeout=40) as r:
                    page = r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                page = ""
                if e.code < 500 and e.code != 429:
                    break
                time.sleep(3 * (essai + 1))
                continue
            except Exception:
                page = ""
                time.sleep(3 * (essai + 1))
                continue
            finally:
                time.sleep(0.4)
            m = DESCRIPTION.search(page)
            if m and m.group(1) == isin:
                return m.group(2)
            break
    return None


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
    noter(f"{len(couverture)} actions vivantes dans la couverture, {len(officielle)} dans la liste officielle, "
          f"{len(absentes_eodhd)} seulement dans la liste officielle")
    candidats = sorted(set(couverture) | set(officielle))
    # Une société qui a regroupé ses actions change d'ISIN : l'ancien reste dans la couverture, le nouveau vient de la liste officielle
    ancien_nom = {cle_nom(c["nom"]): c["nom"] for c in couverture.values()}
    ancien_isin = {cle_nom(c["nom"]): i for i, c in couverture.items()}
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
            nom = ancien_nom.get(cle_nom(nom), nom.title() if nom.isupper() else nom)
        nom = nom_propre(nom)
        retenues.append({"isin": isin, "nom": nom, "code": code[:8], "secteur": "Autres valeurs", "alias": [nom.lower()],
                         "cac40": False, "sbf120": False, "mic": mic, "liquidite": round(liq.get(isin) or liq.get(ancien_isin.get(cle_nom(nom)), 0))})
    noter(f"{len(retenues)} valeurs hors SBF 120 retenues, {len(ecartees)} écartées ; marchés : {marches}")
    for e in ecartees:
        noter("  écartée :", e)
    for i in absentes_eodhd:
        noter("  sans historique long :", officielle[i][0], f"({i}, {officielle[i][2]})")
    tout = []
    for v in sbf["valeurs"]:
        tout.append(dict(v, sbf120=True, liquidite=round(liq.get(v["isin"], 0))))
    tout += sorted(retenues, key=lambda v: v["nom"].lower())
    res = {"revue": aujourdhui.isoformat(),
           "source": "Toutes les actions de Paris : SBF 120 (sbf120.json) + Euronext Paris, Euronext Growth Paris et Euronext Access Paris",
           "plancher_liquidite_euros": None, "seuil_liquidite_euros": None, "valeurs": tout}
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    json.dump(res, open(sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    noter(f"{len(tout)} valeurs au total : " + ", ".join(f"{sum(1 for v in tout if v['mic'] == m)} {n}" for m, n in MARCHES.items()))
    for nom in ("Sensorion",):
        noter(f"  contrôle {nom} :", "présente" if any(nom.lower() in v["nom"].lower() for v in tout) else "ABSENTE")
    with open(os.path.join(os.path.dirname(sortie), "perimetre-journal.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(JOURNAL) + "\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "univers/elargi.json")
