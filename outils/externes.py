"""Paramètres extérieurs gratuits de l'étape 3, « au jour près » (seulement ce qui était connu à la clôture de Paris).

- Marchés : Bourse de Tokyo du jour même (close avant l'ouverture de Paris), Nasdaq sur 1 semaine, cuivre et gaz européen
  (séries mensuelles FRED), calendrier des échéances d'options (troisième vendredi du mois, trimestrielle en mars, juin, septembre, décembre).
- Attention du public : consultations quotidiennes de la page Wikipédia de la société (API Wikimedia, depuis juillet 2015),
  article trouvé par l'ISIN dans Wikidata. Seules les journées complètes (veille et avant) sont utilisées.
"""
import bisect, datetime as dt, json, math, time, urllib.parse, urllib.request
import numpy as np

import contexte as ctx

UA = {"User-Agent": "GB-Investor-donnees/1.0 (usage personnel; https://github.com/gb7878w/gb-investor-donnees)"}


def _troisieme_vendredi(an, mois):
    j = dt.date(an, mois, 15)
    return j + dt.timedelta(days=(4 - j.weekday()) % 7)


class Marches:
    def __init__(self, series_ctx):
        self.s = series_ctx
        self.cache = {}

    def _jour(self, d):
        if d in self.cache:
            return self.cache[d]
        s = self.s
        x = {}
        nk = s.get("NIKKEI225")
        if nk:
            a = ctx.valeur_avant(nk, d, 0); b = ctx.valeur_avant(nk, d)  # jour même (inclus) contre veille
            x["nikkei_j"] = (a / b - 1) * 100 if a and b and nk[0][bisect.bisect_right(nk[0], d) - 1] == d else None
        nq = s.get("NASDAQCOM")
        x["nasdaq5"] = ctx.variation(nq, d, 7) if nq else None
        cu, gz = s.get("PCOPPUSDM"), s.get("PNGASEUUSDM")
        # séries mensuelles : la valeur d'un mois est publiée plus tard ; prudence, on décale de 45 jours
        x["cuivre_m"] = ctx.variation(cu, (dt.date.fromisoformat(d) - dt.timedelta(days=45)).isoformat(), 31) if cu else None
        x["gaz_m"] = ctx.variation(gz, (dt.date.fromisoformat(d) - dt.timedelta(days=45)).isoformat(), 31) if gz else None
        j = dt.date.fromisoformat(d)
        e = _troisieme_vendredi(j.year, j.month)
        if e < j:
            e = _troisieme_vendredi(j.year + (j.month == 12), j.month % 12 + 1)
        x["echeance"] = (e - j).days
        x["echeance_trim"] = float(e.month in (3, 6, 9, 12) and (e - j).days <= 7)
        self.cache[d] = x
        return x

    def __call__(self, cle, dates):
        noms = ["nikkei_j", "nasdaq5", "cuivre_m", "gaz_m", "echeance", "echeance_trim"]
        cols = {n: np.full(len(dates), np.nan) for n in noms}
        for i, d in enumerate(dates):
            x = self._jour(d)
            for n in noms:
                v = x.get(n)
                if v is not None:
                    cols[n][i] = v
        return cols


def articles_wikipedia(isins):
    """ISIN -> (langue, titre) d'après Wikidata (P946), en privilégiant le français."""
    sortie = {}
    isins = sorted(isins)
    for k in range(0, len(isins), 200):
        valeurs = " ".join(f'"{i}"' for i in isins[k:k + 200])
        q = f"""SELECT ?isin ?article WHERE {{ VALUES ?isin {{ {valeurs} }} ?item wdt:P946 ?isin .
          ?article schema:about ?item ; schema:isPartOf ?site . VALUES ?site {{ <https://fr.wikipedia.org/> <https://en.wikipedia.org/> }} }}"""
        req = urllib.request.Request("https://query.wikidata.org/sparql", data=urllib.parse.urlencode({"query": q, "format": "json"}).encode(),
                                     headers=dict(UA, Accept="application/sparql-results+json"))
        with urllib.request.urlopen(req, timeout=120) as r:
            for b in json.loads(r.read())["results"]["bindings"]:
                url = b["article"]["value"]; isin = b["isin"]["value"]
                langue = url.split("//")[1].split(".")[0]
                titre = urllib.parse.unquote(url.split("/wiki/", 1)[1])
                if isin not in sortie or (langue == "fr" and sortie[isin][0] != "fr"):
                    sortie[isin] = (langue, titre)
        time.sleep(1)
    return sortie


def consultations(langue, titre, debut="20160101", fin=None):
    fin = fin or dt.date.today().strftime("%Y%m%d")
    url = (f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{langue}.wikipedia/all-access/user/"
           f"{urllib.parse.quote(titre.replace(' ', '_'), safe='')}/daily/{debut}/{fin}")
    for essai in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                items = json.loads(r.read())["items"]
            return {f"{x['timestamp'][:4]}-{x['timestamp'][4:6]}-{x['timestamp'][6:8]}": x["views"] for x in items}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            time.sleep(2 * (essai + 1))
        except Exception:
            time.sleep(2 * (essai + 1))
    return None


class Attention:
    def __init__(self, vues, isin_de=lambda k: k):
        """vues : ISIN -> {date: consultations}"""
        self.isin_de = isin_de
        self.vues = {}
        for isin, v in vues.items():
            if not v:
                continue
            ds = sorted(v)
            self.vues[isin] = (ds, np.cumsum([v[d] for d in ds], dtype=float))

    def _somme(self, isin, debut, fin):
        """Consultations des jours dans [debut, fin[ et nombre de jours connus."""
        ds, cs = self.vues[isin]
        a = bisect.bisect_left(ds, debut); b = bisect.bisect_left(ds, fin)
        if b <= a:
            return 0.0, 0
        return cs[b - 1] - (cs[a - 1] if a else 0.0), b - a

    def __call__(self, cle, dates):
        cols = {"wiki7_90": np.full(len(dates), np.nan), "wiki90": np.full(len(dates), np.nan)}
        isin = self.isin_de(cle)
        if not isin or isin not in self.vues:
            return cols
        for i, d in enumerate(dates):
            j = dt.date.fromisoformat(d)
            s7, n7 = self._somme(isin, (j - dt.timedelta(days=7)).isoformat(), d)
            s90, n90 = self._somme(isin, (j - dt.timedelta(days=90)).isoformat(), d)
            if n90 >= 60 and n7 >= 5:
                m7, m90 = s7 / n7, s90 / n90
                cols["wiki90"][i] = math.log10(m90 + 1)
                cols["wiki7_90"][i] = math.log((m7 + 1) / (m90 + 1))
        return cols


class Ensemble:
    def __init__(self, *fonctions):
        self.fonctions = [f for f in fonctions if f is not None]

    def __call__(self, cle, dates):
        cols = {}
        for f in self.fonctions:
            cols.update(f(cle, dates))
        return cols
