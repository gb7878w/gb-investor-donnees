"""Agenda : réunions de la BCE et de la Fed (calendriers officiels) et dates de résultats estimées d'après les publications passées.

Les dates de résultats sont une ESTIMATION : même jour de la semaine, un an après la publication de l'an dernier,
tirée des communiqués réglementés d'Info-financière (DILA). Les sociétés publient leur vrai calendrier financier,
mais aucune source gratuite et autorisée ne le regroupe : l'appli l'indique clairement.
"""
import datetime as dt, html, json, re, time, urllib.parse

from sonde import get

MOTS_RESULTATS = re.compile(r"r[ée]sultats?|results?|chiffre d.affaires|revenues?|\bsales\b|earnings|rapport financier|trimestr|quarter|semestr|half.year|annuel|full.year|\bQ[1-4]\b|\bH[12]\b|\b9M\b", re.I)
MOIS = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])}


def _texte(url):
    st, body, _ = get(url)
    if st != 200:
        raise ValueError(f"HTTP {st} {url}")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body.decode("utf-8", "replace"))))


def bce():
    """Dates de décision de politique monétaire (jour 2 de la réunion)."""
    t = _texte("https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html")
    return sorted({f"{a}-{m}-{j}" for j, m, a in re.findall(r"(\d\d)/(\d\d)/(\d{4}) Governing Council of the ECB: monetary policy meeting in Frankfurt \(Day 2\)", t)})


def fed():
    """Dates de décision du FOMC (dernier jour de chaque réunion)."""
    t = _texte("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    sortie = set()
    morceaux = re.split(r"(20\d\d) FOMC Meetings", t)
    for k in range(1, len(morceaux) - 1, 2):
        an = int(morceaux[k]); bloc = morceaux[k + 1][:6000]
        for m1, j1, m2, j2 in re.findall(r"\b(" + "|".join(MOIS) + r")\s+(\d{1,2})\s*[-–]\s*(?:(" + "|".join(MOIS) + r")\s+)?(\d{1,2})\*?\s+Statement", bloc):
            mois = MOIS[m2 or m1]
            try:
                sortie.add(dt.date(an, mois, int(j2)).isoformat())
            except ValueError:
                pass
    return sorted(sortie)


def resultats(valeurs, aujourdhui, pause=0.35):
    """Dates de résultats probables des 120 prochains jours, par ISIN, d'après les publications d'il y a environ un an."""
    sortie, manquants = {}, []
    for v in valeurs:
        url = ("https://www.info-financiere.gouv.fr/api/explore/v2.1/catalog/datasets/flux-amf-new-prod/records?"
               + urllib.parse.urlencode({"where": f'identificationsociete_iso_cd_isi="{v["isin"]}"', "order_by": "uin_dat_amf desc", "limit": 100,
                                         "select": "uin_dat_amf,informationdeposee_inf_tit_inf"}))
        st, body, _ = get(url)
        time.sleep(pause)
        if st != 200:
            manquants.append(f"{v['nom']} : HTTP {st}"); continue
        try:
            lignes = json.loads(body).get("results", [])
        except ValueError:
            manquants.append(f"{v['nom']} : réponse illisible"); continue
        passees = {}
        for r in lignes:
            d = (r.get("uin_dat_amf") or "")[:10]; titre = r.get("informationdeposee_inf_tit_inf") or ""
            if len(d) == 10 and MOTS_RESULTATS.search(titre):
                passees.setdefault(d, titre[:120])
        projections = []
        for d, titre in sorted(passees.items()):
            base = dt.date.fromisoformat(d)
            suivante = base + dt.timedelta(days=364)  # même jour de la semaine, un an plus tard
            if aujourdhui <= suivante <= aujourdhui + dt.timedelta(days=120) and base >= aujourdhui - dt.timedelta(days=400):
                if all(abs((dt.date.fromisoformat(p["date"]) - suivante).days) > 5 for p in projections):
                    projections.append({"date": suivante.isoformat(), "base": d, "titre": titre})
        if projections:
            sortie[v["isin"]] = projections
    return sortie, manquants


def construire(univers, aujourdhui=None):
    aujourdhui = aujourdhui or dt.date.today()
    manquants = []
    try:
        b = [d for d in bce() if d >= aujourdhui.isoformat()][:6]
    except Exception as e:
        b = []; manquants.append(f"BCE : {str(e)[:80]}")
    try:
        f = [d for d in fed() if d >= aujourdhui.isoformat()][:6]
    except Exception as e:
        f = []; manquants.append(f"Fed : {str(e)[:80]}")
    try:
        r, m = resultats(univers["valeurs"], aujourdhui)
        manquants += m[:5]
    except Exception as e:
        r = {}; manquants.append(f"Résultats : {str(e)[:80]}")
    return {"version": 1, "banques_centrales": [{"date": d, "nom": "Décision de la BCE (taux)", "organisme": "BCE"} for d in b]
            + [{"date": d, "nom": "Décision de la Fed (taux)", "organisme": "Fed"} for d in f],
            "resultats": r, "limites": "Dates de résultats estimées d'après les publications de l'an dernier ; dividendes non disponibles gratuitement."}, manquants
