"""Périmètre élargi de GB Investor : SBF 120 + valeurs liquides d'Euronext Paris (marché réglementé) et d'Euronext Growth Paris.

Euronext Access est exclu (très peu échangé, peu d'information). La liste vient de la couverture de l'historique long
(couverture.json, publique, sans aucun cours) ; la liquidité est mesurée sur les 60 dernières séances de l'historique chiffré
(médiane des euros échangés par jour), puis chaque valeur retenue est classée d'après sa page produit publique chez Euronext :
marché réglementé (XPAR) ou Growth (ALXP) acceptés, Access (XMLI) refusé.
Sortie : univers/elargi.json, relu chaque soir par donnees.py. À relancer à la main à chaque révision trimestrielle du SBF 120.
"""
import base64, datetime as dt, json, os, re, statistics, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import donnees

TOTAL_VISE = 330           # SBF 120 compris
PLANCHER_EUROS = 50_000    # euros échangés par jour (médiane sur 60 séances) : en dessous, une valeur n'est jamais retenue
SEANCES_LIQUIDITE = 60
FORMES = re.compile(r"\s+(S\.?A\.?S?\.?|S\.?C\.?A\.?|S\.?E\.?|N\.?V\.?|PLC|SA|SAS|SCA|SE)\.?$", re.I)


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
                if len(chiffres) >= 30:
                    sortie[v["isin"]] = statistics.median(chiffres)
    return sortie


MARCHES = {"XPAR": "Euronext Paris", "ALXP": "Euronext Growth Paris"}   # XMLI (Euronext Access Paris) est volontairement absent
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
    candidats = {c["isin"]: c for c in lire_couverture()["couverture"]
                 if c.get("isin") and not c.get("radiee") and c.get("fin", "") >= limite and c.get("seances", 0) >= 250 and c["isin"] not in deja}
    liq = liquidites(cle, set(candidats) | deja)
    classes = sorted(((liq[i], i) for i in candidats if i in liq and liq[i] >= PLANCHER_EUROS), reverse=True)
    print(f"{len(candidats)} candidates vivantes, {len(classes)} au-dessus de {PLANCHER_EUROS} €/jour")
    valeurs_liq = sorted(liq.values())
    for q in (10, 25, 50, 75, 90):
        print(f"  liquidité médiane des valeurs, centile {q} : {valeurs_liq[len(valeurs_liq) * q // 100]:,.0f} €/jour")
    for seuil in (10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000):
        print(f"  au moins {seuil:>9,} € par jour : {sum(1 for e, _ in ((liq[i], i) for i in candidats if i in liq) if e >= seuil)} valeurs de plus que le SBF 120")
    besoin = TOTAL_VISE - len(sbf["valeurs"])
    retenues, ecartees, marches = [], [], {}
    for euros, isin in classes:
        if len(retenues) >= besoin:
            break
        mic = marche(isin)
        c = candidats[isin]
        if mic not in MARCHES:
            ecartees.append(f"{c['nom']} ({isin}) : " + (f"marché {mic}, hors périmètre (Access ou autre)" if mic else "page Euronext introuvable ou sans marché"))
            continue
        marches[mic] = marches.get(mic, 0) + 1
        nom = nom_propre(c["nom"])
        retenues.append({"isin": isin, "nom": nom, "code": c["id"].split(":")[1][:8], "secteur": "Autres valeurs", "alias": [nom.lower()],
                         "cac40": False, "sbf120": False, "mic": mic, "liquidite": round(euros)})
    seuil = retenues[-1]["liquidite"] if retenues else PLANCHER_EUROS
    print(f"{len(retenues)} valeurs ajoutées (dernière : {seuil:,} €/jour), {len(ecartees)} écartées ; marchés des ajoutées : {marches}")
    for e in ecartees[:60]:
        print("  écartée :", e)
    tout = []
    for v in sbf["valeurs"]:
        tout.append(dict(v, sbf120=True, liquidite=round(liq.get(v["isin"], 0))))
    tout += sorted(retenues, key=lambda v: v["nom"].lower())
    res = {"revue": aujourdhui.isoformat(), "source": "SBF 120 (sbf120.json) + valeurs de Paris les plus échangées (Euronext Paris et Euronext Growth Paris, Access exclu)",
           "plancher_liquidite_euros": PLANCHER_EUROS, "seuil_liquidite_euros": seuil, "valeurs": tout}
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    json.dump(res, open(sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(tout)} valeurs au total, dont {sum(1 for v in tout if v['mic'] == 'ALXP')} sur Growth")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "univers/elargi.json")
