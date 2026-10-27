"""Sources gratuites de l'AMF, rendues « au jour près » (on n'utilise que ce qui était public la veille au soir).

- Positions courtes nettes publiées (data.gouv.fr, licence ouverte, depuis 2012) : total publié en % du capital,
  nombre de vendeurs à découvert déclarés, variation sur 30 jours.
- Communiqués réglementés (info-financière, DILA) : nombre de communiqués des 30 derniers jours, jours depuis
  la dernière publication de résultats, jours avant la prochaine (estimée un an après celle de l'an dernier).
"""
import bisect, csv, datetime as dt, io, json, time, urllib.parse, urllib.request
import numpy as np

from agenda import MOTS_RESULTATS, EXCLUS

UA = {"User-Agent": "GB-Investor-donnees/1.0 (usage personnel)"}
VAD = "https://www.data.gouv.fr/api/1/datasets/62738e33f1be79935d3e5553/"
DILA = "https://www.info-financiere.gouv.fr/api/explore/v2.1/catalog/datasets/flux-amf-new-prod/"
NOMS = ["vad_total", "vad_nb", "vad_var30", "com30", "res_depuis", "res_avant"]
LIBELLES = {"vad_total": "Ventes à découvert déclarées (% du capital)", "vad_nb": "Nombre de vendeurs à découvert déclarés",
            "vad_var30": "Variation des ventes à découvert sur 30 jours", "com30": "Communiqués officiels sur 30 jours",
            "res_depuis": "Jours depuis les derniers résultats", "res_avant": "Jours avant les prochains résultats (estimés)"}


def _lire(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def positions_courtes():
    """{isin: [(début de publication, fin de publication ou '', ratio, détenteur)]}"""
    meta = json.loads(_lire(VAD))
    url = next(r["url"] for r in meta["resources"] if (r.get("format") or "").lower() == "csv" or r["url"].endswith(".csv"))
    texte = _lire(url, 300).decode("utf-8-sig", "replace")
    sortie = {}
    for ligne in csv.DictReader(io.StringIO(texte), delimiter=";"):
        try:
            ratio = float((ligne.get("Ratio") or "").replace(",", "."))
        except ValueError:
            continue
        isin = (ligne.get("code ISIN") or "").strip()
        debut = (ligne.get("Date de debut de publication position") or "").strip()[:10]
        if len(isin) != 12 or len(debut) != 10:
            continue
        sortie.setdefault(isin, []).append((debut, (ligne.get("Date de fin de publication position") or "").strip()[:10], ratio,
                                            ligne.get("Detenteur de la position courte nette") or ""))
    return sortie


def communiques(isin, pause=0.25):
    """Dates (AAAA-MM-JJ) et titres des communiqués réglementés d'une société, tout l'historique."""
    p = {"where": f'identificationsociete_iso_cd_isi="{isin}"', "select": "uin_dat_amf,informationdeposee_inf_tit_inf"}
    def trier(res):
        return sorted(((r.get("uin_dat_amf") or "")[:10], r.get("informationdeposee_inf_tit_inf") or "") for r in res if r.get("uin_dat_amf"))
    try:
        res = json.loads(_lire(DILA + "exports/json?" + urllib.parse.urlencode(p)))
        time.sleep(pause)
        return trier(res)
    except Exception:
        pass
    # Repli : pages de 100 (l'API limite le décalage à 10 000 lignes)
    res, offset = [], 0
    for essai in range(3):
        try:
            while offset < 9900:
                page = json.loads(_lire(DILA + "records?" + urllib.parse.urlencode(dict(p, order_by="uin_dat_amf asc", limit=100, offset=offset))))["results"]
                res += page; offset += 100
                time.sleep(pause)
                if len(page) < 100:
                    break
            return trier(res)
        except Exception:
            time.sleep(2 * (essai + 1))
    return None


class Caracteristiques:
    """Fonction pour modele.EXTERNES : colonnes AMF pour une valeur et ses dates de séance."""

    def __init__(self, vad, coms, isin_de=lambda k: k):
        self.isin_de = isin_de
        self.vad = {}
        for isin, lignes in vad.items():
            ev = sorted([(d, r, 1) for d, f, r, _ in lignes] + [(f, -r, -1) for d, f, r, _ in lignes if f])
            cles = [e[0] for e in ev]
            self.vad[isin] = (cles, np.cumsum([e[1] for e in ev]), np.cumsum([e[2] for e in ev]))
        self.coms = {}
        for isin, liste in coms.items():
            if liste is None:
                continue
            tous = [d for d, _ in liste]
            res = []
            for d, t in liste:
                if MOTS_RESULTATS.search(t) and not EXCLUS.search(t):
                    if not res or (dt.date.fromisoformat(d) - dt.date.fromisoformat(res[-1])).days > 7:
                        res.append(d)
            self.coms[isin] = (tous, res)

    def _vad_a(self, isin, d):
        """Positions publiées strictement avant le jour d et pas encore remplacées."""
        if isin not in self.vad:
            return 0.0, 0.0
        cles, tot, nb = self.vad[isin]
        k = bisect.bisect_left(cles, d)  # événements datés avant d
        return (float(tot[k - 1]), float(nb[k - 1])) if k else (0.0, 0.0)

    def __call__(self, cle, dates):
        n = len(dates)
        cols = {nom: np.full(n, np.nan) for nom in NOMS}
        isin = self.isin_de(cle)
        if not isin:
            return cols
        for i, d in enumerate(dates):
            t, k = self._vad_a(isin, d)
            cols["vad_total"][i] = max(t, 0.0); cols["vad_nb"][i] = max(k, 0.0)
            avant = (dt.date.fromisoformat(d) - dt.timedelta(days=30)).isoformat()
            cols["vad_var30"][i] = max(t, 0.0) - max(self._vad_a(isin, avant)[0], 0.0)
        if isin in self.coms:
            tous, res = self.coms[isin]
            for i, d in enumerate(dates):
                jd = dt.date.fromisoformat(d)
                a = bisect.bisect_left(tous, (jd - dt.timedelta(days=30)).isoformat()); b = bisect.bisect_left(tous, d)
                cols["com30"][i] = b - a
                k = bisect.bisect_left(res, d)
                if k:
                    cols["res_depuis"][i] = (jd - dt.date.fromisoformat(res[k - 1])).days
                dernier = dt.date.fromisoformat(res[k - 1]) if k else None
                prochain = []
                for e in res[max(0, k - 8):k]:
                    p = dt.date.fromisoformat(e) + dt.timedelta(days=364)
                    # projection déjà « consommée » si une publication a eu lieu dans les 45 jours précédant la date prévue
                    if 0 <= (p - jd).days <= 120 and not (dernier and dernier > p - dt.timedelta(days=45)):
                        prochain.append((p - jd).days)
                if prochain:
                    cols["res_avant"][i] = min(prochain)
        return cols
