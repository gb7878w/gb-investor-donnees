"""Prépare chaque soir les séances des valeurs suivies par GB Investor.

Source : historique ajusté d'Euronext (téléchargement public « Historical data » de chaque valeur).
Sortie, dans le dossier donné en argument :
  - seances.bin : deux ans de séances (ouverture, plus haut, plus bas, clôture, volume) des 120 valeurs et des indices,
  - recentes.bin : les 15 dernières séances, pour la mise à jour quotidienne du téléphone,
  - univers.json : la liste des valeurs suivies (information publique),
  - etat.json : date de génération et valeurs manquantes (aucun cours).
Les deux fichiers .bin sont compressés puis chiffrés (AES-256-GCM) avec la clé du secret CLE_DONNEES :
les conditions d'Euronext interdisent de republier leurs cours, seul l'appli de Gilbert sait les lire.
"""
import base64, datetime as dt, gzip, json, os, re, sys, time, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

UA = "GB-Investor-donnees/1.0 (usage personnel; github.com/gb7878w/gb-investor-donnees)"
ENTETE = b"GBI1"
INDICES = [("FR0003500008", "XPAR", "CAC 40"), ("FR0003999481", "XPAR", "SBF 120")]
JOURS = 800  # un peu plus de deux ans de calendrier, soit environ 520 séances


def telecharger(isin, mic, debut, fin, essais=4):
    q = urllib.parse.urlencode({"format": "csv", "decimal_separator": ".", "date_form": "d/m/Y", "op": "", "adjusted": "Y",
                                "base100": "", "startdate": debut, "enddate": fin})
    url = f"https://live.euronext.com/en/ajax/AwlHistoricalPrice/getFullDownloadAjax/{isin}-{mic}?{q}"
    for n in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv,*/*"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8-sig", "replace")
        except Exception as e:  # réseau ou refus ponctuel : nouvel essai espacé
            if n == essais - 1:
                raise
            time.sleep(3 * (n + 1))


def nombre(v):
    v = v.strip().replace(",", "")
    if v in ("", "-"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def lire(csv_text):
    """Lit le CSV Euronext (Date;Open;High;Low;Last;Close;Number of Shares;...). Renvoie les séances triées."""
    lignes = csv_text.splitlines()
    entete = next((i for i, l in enumerate(lignes) if l.startswith("Date;")), None)
    if entete is None:
        raise ValueError("format inattendu")
    cols = [c.strip('"') for c in lignes[entete].split(";")]
    idx = {c: i for i, c in enumerate(cols)}
    seances = {}
    for l in lignes[entete + 1:]:
        if not re.match(r"\d\d/\d\d/\d{4};", l):
            continue
        c = l.split(";")
        j, m, a = c[0].split("/")
        date = f"{a}-{m}-{j}"
        cl = nombre(c[idx["Close"]]) or nombre(c[idx["Last"]])
        if cl is None or cl <= 0:
            continue
        o = nombre(c[idx["Open"]]) or cl
        h = nombre(c[idx["High"]]) or max(o, cl)
        b = nombre(c[idx["Low"]]) or min(o, cl)
        v = nombre(c[idx["Number of Shares"]]) if "Number of Shares" in idx else None
        seances[date] = (o, max(h, o, cl), min(b, o, cl), cl, v or 0.0)
    # Une séance en cours n'est pas une séance complète : on ne garde celle du jour qu'après la clôture (17 h 35 à Paris).
    paris = dt.datetime.now(ZoneInfo("Europe/Paris"))
    if paris.time() < dt.time(18, 0):
        seances.pop(paris.date().isoformat(), None)
    return sorted(seances.items())


def serie(seances):
    return {
        "d": [d for d, _ in seances],
        "o": [round(s[0], 4) for _, s in seances],
        "h": [round(s[1], 4) for _, s in seances],
        "l": [round(s[2], 4) for _, s in seances],
        "c": [round(s[3], 4) for _, s in seances],
        "v": [round(s[4]) for _, s in seances],
    }


def chiffrer(donnees, cle):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    return ENTETE + nonce + AESGCM(cle).encrypt(nonce, gzip.compress(donnees, 9, mtime=0), ENTETE)


HISTORIQUE = "https://raw.githubusercontent.com/gb7878w/gb-investor-donnees/historique/"
APPRENTISSAGE_10_ANS = True  # validé le 27 octobre 2026 par essai_final.py : meilleur que le modèle 2 ans pour 8 prévisions sur 9
PAS_APPRENTISSAGE = 7  # une ligne sur sept pour l'apprentissage sur 10 ans (les étiquettes se chevauchent de toute façon)


def _lire_historique(nom, cle):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    with urllib.request.urlopen(urllib.request.Request(HISTORIQUE + nom, headers={"User-Agent": "GB-Investor-donnees/1.0"}), timeout=180) as r:
        brut = r.read()
    if brut[:4] != ENTETE:
        raise ValueError(f"{nom} : en-tête inattendu")
    return json.loads(gzip.decompress(AESGCM(cle).decrypt(brut[4:16], brut[16:], ENTETE)))


def _prolonger(longue, recente):
    """Historique long (cours ajustés, figé) prolongé par les séances Euronext plus récentes, mises à la même échelle."""
    s = {"d": list(longue["d"]), "o": list(longue["o"]), "h": list(longue["h"]), "l": list(longue.get("l", longue.get("b"))), "c": list(longue["c"]), "v": list(longue["v"])}
    if not recente or not recente["d"] or not s["d"]:
        return s
    dernier = s["d"][-1]
    if dernier not in recente["d"]:
        return s
    k = recente["d"].index(dernier)
    f = s["c"][-1] / recente["c"][k] if recente["c"][k] else 1.0
    for i in range(k + 1, len(recente["d"])):
        s["d"].append(recente["d"][i])
        for a in ("o", "h", "l", "c"):
            s[a].append(round(recente[a][i] * f, 4))
        s["v"].append(recente["v"][i])
    return s


def series_10_ans(series, indices, cle):
    """Toutes les actions de Paris sur 10 ans, radiées comprises (apprentissage seulement), les valeurs suivies sous leur ISIN."""
    longues, radiees = {}, 0
    for k in range(1, 5):
        for v in _lire_historique(f"historique-{k}.bin", cle)["valeurs"]:
            if v.get("isin") in series:
                longues[v["isin"]] = _prolonger(v, series[v["isin"]])
            elif v.get("isin") not in longues:
                longues[v["id"]] = _prolonger(v, None)
                radiees += bool(v.get("radiee"))
    for isin, s in series.items():
        longues.setdefault(isin, s)  # valeur suivie absente de l'historique long : ses deux ans Euronext
    idx_longs = _lire_historique("historique-indices.bin", cle)["indices"]
    ind = dict(indices)
    for isin, s in idx_longs.items():
        # l'historique long des indices ne garde que les clôtures
        recent = indices.get(isin)
        d, c = list(s["d"]), list(s["c"])
        if recent and d and d[-1] in recent["d"]:
            k = recent["d"].index(d[-1])
            f = c[-1] / recent["c"][k] if recent["c"][k] else 1.0
            d += recent["d"][k + 1:]; c += [round(x * f, 4) for x in recent["c"][k + 1:]]
        ind[isin] = {"nom": (recent or {}).get("nom", isin), "d": d, "c": c}
    return longues, ind, radiees


def preparer_modele(univers, series, indices, genere, derniere, sortie, cle):
    """Contexte extérieur puis prévisions. Une panne ici ne doit jamais empêcher la publication des cours."""
    manquants = []
    try:
        import agenda
        calendrier, manq = agenda.construire(univers)
        manquants += manq
        json.dump(dict(calendrier, genere=genere), open(os.path.join(sortie, "calendrier.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        print(f"agenda : {len(calendrier['banques_centrales'])} réunions de banques centrales, résultats estimés pour {len(calendrier['resultats'])} valeurs")
    except Exception as e:
        manquants.append(f"agenda : {type(e).__name__} {str(e)[:120]}")
    try:
        import contexte, modele
        series_ctx, infos, manq = contexte.charger()
        manquants += manq
        resume = contexte.resume(series_ctx, infos)
        json.dump({"version": 1, "genere": genere, "indicateurs": resume}, open(os.path.join(sortie, "contexte.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        secteurs = {v["isin"]: v.get("secteur", "?") for v in univers["valeurs"]}
        apprentissage = {"base": "2 ans, SBF 120"}
        series_app, indices_app = series, indices
        try:
            if not APPRENTISSAGE_10_ANS:
                raise RuntimeError("désactivé")
            # Apprentissage sur 10 ans, tout Paris, radiées comprises (essais du 27 octobre 2026 : meilleur que 2 ans pour « mieux que le CAC 40 »).
            series_app, indices_app, radiees = series_10_ans(series, indices, cle)
            apprentissage = {"base": "10 ans, actions de Paris", "valeurs": len(series_app), "radiees": radiees}
        except Exception as e:
            series_app, indices_app = series, indices
            if APPRENTISSAGE_10_ANS:
                manquants.append(f"historique 10 ans : {type(e).__name__} {str(e)[:100]} (apprentissage sur 2 ans)")
                print(manquants[-1])
        import numpy as np
        long_actif = len(series_app) > len(series)
        modele.ETENDU = long_actif  # mêmes paramètres pour les deux bases ; les groupes retenus ne valent que pour la base 10 ans
        groupes = modele.GROUPES
        toutes = {(h, c) for h in modele.HORIZONS for c in modele.CIBLES}
        courtes = modele.BASE_COURTE & toutes if long_actif else toutes
        resultat = {"bulletin": {}, "modeles": {}, "colonnes": {}}
        if courtes:
            modele.GROUPES = {}
            X, noms, rang, _, etiq, derniers = modele.construire(series, indices, secteurs, series_ctx)
            print(f"modèle sur 2 ans : {X.shape[0]} lignes, {len(noms)} paramètres, {len(courtes)} prévisions")
            for k, v in modele.evaluer_et_prevoir(X, noms, rang, etiq, derniers, seulement=courtes).items():
                resultat[k].update(v)
            modele.GROUPES = groupes
        if toutes - courtes:
            X, noms, rang, ident, etiq, derniers_l = modele.construire(series_app, indices_app, secteurs, series_ctx)
            _, inv = np.unique(ident, return_inverse=True)
            garde = ((rang + inv) % PAS_APPRENTISSAGE) == 0
            X, rang, etiq = X[garde].astype(np.float32), rang[garde], etiq[garde]
            modele.PARAMS["num_threads"] = 4
            print(f"modèle sur 10 ans : {X.shape[0]} lignes, {len(noms)} paramètres, {len(toutes - courtes)} prévisions")
            for k, v in modele.evaluer_et_prevoir(X, noms, rang, etiq, derniers_l, seulement=toutes - courtes).items():
                resultat[k].update(v)
            derniers_l = {k: v for k, v in derniers_l.items() if k in series}
            for cle_p in toutes - courtes:
                resultat.setdefault("derniers", {})[cle_p] = derniers_l
            if not courtes:
                derniers = derniers_l
        apprentissage["prevision_sur_2_ans"] = sorted(f"{h}/{c}" for h, c in courtes)
        prevision = {"version": 1, "genere": genere, "derniere": derniere, "horizons": modele.HORIZONS, "seuil": modele.SEUIL, "apprentissage": apprentissage,
                     "libelles": {k: v for k, v in modele.LIBELLES.items() if k in noms}, "bulletin": modele.bulletin(resultat), "importance": modele.importance(resultat, noms),
                     "valeurs": modele.previsions(resultat, noms, derniers)}
        with open(os.path.join(sortie, "prevision.bin"), "wb") as f:
            f.write(chiffrer(json.dumps(prevision, separators=(",", ":")).encode(), cle))
    except Exception as e:  # le modèle est un plus : on publie les cours quoi qu'il arrive
        manquants.append(f"modèle : {type(e).__name__} {str(e)[:120]}")
        print("modèle indisponible :", manquants[-1])
    return manquants


def main(sortie):
    cle = base64.b64decode(os.environ.get("CLE_DONNEES", ""))
    if len(cle) != 32:
        sys.exit("Secret CLE_DONNEES absent ou invalide (32 octets en base64 attendus) : rien n'est publié.")
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    univers = json.load(open(os.path.join(racine, "univers", "sbf120.json"), encoding="utf-8"))
    aujourdhui = dt.date.today()
    debut, fin = (aujourdhui - dt.timedelta(days=JOURS)).isoformat(), aujourdhui.isoformat()
    series, indices, manquants = {}, {}, []
    for v in univers["valeurs"]:
        try:
            s = lire(telecharger(v["isin"], v.get("mic", "XPAR"), debut, fin))
            if len(s) < 5:
                raise ValueError(f"{len(s)} séances seulement")
            series[v["isin"]] = serie(s)
        except Exception as e:
            manquants.append(f"{v['nom']} ({v['isin']}) : {str(e)[:80]}")
        time.sleep(0.4)
    for isin, mic, nom in INDICES:
        try:
            indices[isin] = dict(nom=nom, **serie(lire(telecharger(isin, mic, debut, fin))))
        except Exception as e:
            manquants.append(f"{nom} ({isin}) : {str(e)[:80]}")
        time.sleep(0.4)
    total = len(univers["valeurs"])
    print(f"{len(series)}/{total} valeurs, {len(indices)}/{len(INDICES)} indices")
    for m in manquants:
        print("manquant :", m)
    if len(series) < total * 0.9:
        sys.exit("Moins de 90 % des valeurs reçues : publication annulée, la version précédente reste en place.")
    genere = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    derniere = max(s["d"][-1] for s in series.values())
    complet = {"version": 1, "genere": genere, "derniere": derniere, "series": series, "indices": indices}
    recent = {"version": 1, "genere": genere, "derniere": derniere,
              "series": {k: {c: v[-15:] for c, v in s.items()} for k, s in series.items()},
              "indices": {k: {c: (v if c == "nom" else v[-15:]) for c, v in s.items()} for k, s in indices.items()}}
    os.makedirs(sortie, exist_ok=True)
    manquants_modele = preparer_modele(univers, series, indices, genere, derniere, sortie, cle)
    for nom, contenu in [("seances.bin", complet), ("recentes.bin", recent)]:
        with open(os.path.join(sortie, nom), "wb") as f:
            f.write(chiffrer(json.dumps(contenu, separators=(",", ":")).encode(), cle))
    json.dump(univers, open(os.path.join(sortie, "univers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"genere": genere, "derniere_seance": derniere, "valeurs": len(series), "indices": len(indices), "manquants": manquants, "manquants_contexte_modele": manquants_modele},
              open(os.path.join(sortie, "etat.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("dernière séance :", derniere, "· tailles :", {n: os.path.getsize(os.path.join(sortie, n)) for n in os.listdir(sortie)})


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "publication")
