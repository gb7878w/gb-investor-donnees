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
        X, noms, rang, _, etiq, derniers = modele.construire(series, indices, secteurs, series_ctx)
        print(f"modèle : {X.shape[0]} lignes, {len(noms)} paramètres")
        resultat = modele.evaluer_et_prevoir(X, noms, rang, etiq, derniers)
        prevision = {"version": 1, "genere": genere, "derniere": derniere, "horizons": modele.HORIZONS, "seuil": modele.SEUIL,
                     "libelles": {k: v for k, v in modele.LIBELLES.items() if k in noms}, "bulletin": modele.bulletin(resultat),
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
