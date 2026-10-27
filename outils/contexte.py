"""Contexte extérieur : taux, change, énergie, indices étrangers, volatilité.

Sources publiques et gratuites : FRED (Réserve fédérale de Saint-Louis) et API de données de la BCE.
Toutes les séries sont des données macroéconomiques ou de marché publiées en accès libre ; elles sont publiées en clair.
"""
import bisect, csv, datetime as dt, io, time

from sonde import get

# (identifiant, libellé, unité, nombre de décimales, sens « hausse = tension » pour le commentaire)
FRED = [
    ("VIXCLS", "Volatilité des marchés (VIX)", "pts", 1),
    ("DCOILBRENTEU", "Pétrole (Brent)", "$/baril", 1),
    ("DEXUSEU", "Euro en dollars", "$", 4),
    ("DEXCHUS", "Dollar en yuans", "¥", 3),
    ("DGS10", "Taux à 10 ans américain", "%", 2),
    ("SP500", "S&P 500", "pts", 0),
    ("NASDAQCOM", "Nasdaq", "pts", 0),
    ("DJIA", "Dow Jones", "pts", 0),
    ("NIKKEI225", "Nikkei 225", "pts", 0),
    ("DFEDTARU", "Taux directeur de la Fed (haut)", "%", 2),
    ("PCOPPUSDM", "Cuivre (mensuel)", "$/t", 0),
    ("PNGASEUUSDM", "Gaz européen (mensuel)", "$/MBtu", 1),
    ("IRLTLT01FRM156N", "Taux à 10 ans France (mensuel)", "%", 2),
    ("IRLTLT01DEM156N", "Taux à 10 ans Allemagne (mensuel)", "%", 2),
    ("UNRATE", "Chômage américain (mensuel)", "%", 1),
]
BCE = [
    ("YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", "Taux à 10 ans zone euro (courbe AAA)", "%", 2),
    ("EXR/D.CNY.EUR.SP00.A", "Euro en yuans", "¥", 3),
]
BCE_NIVEAU = [
    ("FM/B.U2.EUR.4F.KR.DFR.LEV", "Taux de dépôt de la BCE", "%", 2),
    ("ICP/M.U2.N.000000.4.ANR", "Inflation zone euro (annuelle)", "%", 1),
    ("ICP/M.FR.N.000000.4.ANR", "Inflation France (annuelle)", "%", 1),
    ("MNA/Q.Y.I9.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.GY", "Croissance zone euro (trimestre, annualisée)", "%", 1),
]


def _serie_fred(ident):
    st, body, _ = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={ident}")
    if st != 200:
        raise ValueError(f"FRED {ident} : HTTP {st}")
    lignes = list(csv.reader(io.StringIO(body.decode("utf-8", "replace"))))
    dates, valeurs = [], []
    for ligne in lignes[1:]:
        if len(ligne) < 2 or ligne[1] in ("", "."):
            continue
        try:
            dates.append(ligne[0]); valeurs.append(float(ligne[1]))
        except ValueError:
            pass
    if len(dates) < 10:
        raise ValueError(f"FRED {ident} : série trop courte")
    return dates, valeurs


def _date_iso(periode):
    """Les séries mensuelles de la BCE donnent « 2025-12 » : on les date du dernier jour du mois."""
    if len(periode) == 7 and periode[4:6] == "-Q":
        an, trimestre = int(periode[:4]), int(periode[6])
        return (dt.date(an + (trimestre == 4), (trimestre * 3) % 12 + 1, 1) - dt.timedelta(days=1)).isoformat()
    if len(periode) == 7:
        an, mois = int(periode[:4]), int(periode[5:7])
        return (dt.date(an + (mois == 12), mois % 12 + 1, 1) - dt.timedelta(days=1)).isoformat()
    return periode


def _serie_bce(cle, depuis="2022-01-01"):
    st, body, _ = get(f"https://data-api.ecb.europa.eu/service/data/{cle}?format=csvdata&startPeriod={depuis}")
    if st != 200:
        raise ValueError(f"BCE {cle} : HTTP {st}")
    lecteur = csv.DictReader(io.StringIO(body.decode("utf-8", "replace")))
    dates, valeurs = [], []
    for r in lecteur:
        try:
            d = _date_iso(r["TIME_PERIOD"]); v = float(r["OBS_VALUE"])
            dt.date.fromisoformat(d)  # ignore les trimestres et tout format inattendu
            dates.append(d); valeurs.append(v)
        except (KeyError, ValueError):
            pass
    if len(dates) < 3:
        raise ValueError(f"BCE {cle} : série trop courte")
    return dates, valeurs


def charger(pause=0.4):
    """Renvoie (series, manquants). series : identifiant -> (dates ISO triées, valeurs), plus les libellés."""
    series, infos, manquants = {}, {}, []
    for ident, nom, unite, dec in FRED:
        try:
            series[ident] = _serie_fred(ident); infos[ident] = (nom, unite, dec, "FRED")
        except Exception as e:
            manquants.append(f"{ident} : {str(e)[:80]}")
        time.sleep(pause)
    for cle, nom, unite, dec in BCE + BCE_NIVEAU:
        try:
            series[cle] = _serie_bce(cle); infos[cle] = (nom, unite, dec, "BCE")
        except Exception as e:
            manquants.append(f"{cle} : {str(e)[:80]}")
        time.sleep(pause)
    return series, infos, manquants


def valeur_avant(serie, date_iso, decalage_jours=1):
    """Dernière valeur publiée strictement avant `date_iso - decalage_jours + 1` (aucune information du futur)."""
    dates, valeurs = serie
    limite = (dt.date.fromisoformat(date_iso) - dt.timedelta(days=decalage_jours - 1)).isoformat()
    i = bisect.bisect_left(dates, limite) - 1
    return valeurs[i] if i >= 0 else None


def variation(serie, date_iso, jours):
    a = valeur_avant(serie, date_iso); b = valeur_avant(serie, (dt.date.fromisoformat(date_iso) - dt.timedelta(days=jours)).isoformat())
    return None if a is None or b in (None, 0) else (a / b - 1) * 100


def resume(series, infos, aujourdhui=None):
    """Tableau « Contexte » de l'appli : dernier niveau, date et variations à 5 jours et 1 mois."""
    aujourdhui = aujourdhui or dt.date.today().isoformat()
    sortie = []
    for ident, (nom, unite, dec, source) in infos.items():
        dates, valeurs = series[ident]
        niveau = valeurs[-1]
        def avant(jours):
            limite = (dt.date.fromisoformat(dates[-1]) - dt.timedelta(days=jours)).isoformat()
            i = bisect.bisect_right(dates, limite) - 1
            return valeurs[i] if i >= 0 else None
        v5, v21 = avant(7), avant(30)
        niveau_seul = unite == "%" and ident in ("DFEDTARU", "FM/B.U2.EUR.4F.KR.DFR.LEV", "ICP/M.U2.N.000000.4.ANR", "ICP/M.FR.N.000000.4.ANR")
        sortie.append({
            "id": ident, "nom": nom, "unite": unite, "decimales": dec, "source": source, "date": dates[-1], "valeur": niveau,
            # Pour les taux, on donne l'écart en points ; pour les prix et indices, la variation en %.
            "mode": "points" if unite == "%" else "pourcent",
            "var7": None if v5 in (None, 0) else (niveau - v5 if unite == "%" else (niveau / v5 - 1) * 100),
            "var30": None if v21 in (None, 0) else (niveau - v21 if unite == "%" else (niveau / v21 - 1) * 100),
            "ancien": (dt.date.fromisoformat(aujourdhui) - dt.date.fromisoformat(dates[-1])).days > (70 if "M." in ident or ident in ("PCOPPUSDM", "PNGASEUUSDM", "IRLTLT01FRM156N", "IRLTLT01DEM156N", "UNRATE") or "Q." in ident else 10),
        })
    return sortie
