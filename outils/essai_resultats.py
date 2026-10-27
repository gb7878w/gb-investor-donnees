"""Étude d'événements : le cours monte-t-il plus vite avant la publication des résultats ?

Dates de publication : base officielle info-financière (AMF/DILA), titres contenant résultats, chiffre d'affaires, trimestre, semestre…
Rendements : cours ajustés de l'historique long, moins le CAC 40 (rendement anormal). Fenêtres en séances autour du jour J de dépôt :
  [-20,-11], [-10,-6], [-5,-1] (avant), [0,+1] (réaction), [+2,+5] (après).
Référence : rendement anormal moyen sur des fenêtres de même durée choisies hors événements, pour chaque valeur.
Ne publie rien : affiche seulement des statistiques.
"""
import os, sys, json, re, time, base64, bisect, datetime as dt, urllib.parse, urllib.request
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import essai_long as L
from agenda import MOTS_RESULTATS, EXCLUS

UA = {"User-Agent": "GB-Investor-donnees/1.0 (usage personnel)"}
BASE = "https://www.info-financiere.gouv.fr/api/explore/v2.1/catalog/datasets/flux-amf-new-prod/records?"
FENETRES = {"-20..-11": (-20, -11), "-10..-6": (-10, -6), "-5..-1": (-5, -1), "-10..-1": (-10, -1), "0..+1": (0, 1), "+2..+5": (2, 5)}


def dila(isin, annee):
    p = {"where": f'identificationsociete_iso_cd_isi="{isin}" and uin_dat_amf>=date\'{annee}-01-01\' and uin_dat_amf<date\'{annee + 1}-01-01\'',
         "order_by": "uin_dat_amf asc", "limit": 100, "select": "uin_dat_amf,informationdeposee_inf_tit_inf"}
    sortie, offset = [], 0
    while True:
        p["offset"] = offset
        req = urllib.request.Request(BASE + urllib.parse.urlencode(p), headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read()).get("results", [])
        sortie += res
        if len(res) < 100 or offset >= 900:
            return sortie
        offset += 100


def type_publication(titre):
    t = titre.lower()
    if re.search(r"semestr|half.year|\bh1\b|\bs1\b", t):
        return "semestre"
    if re.search(r"annuel|full.year|exercice", t):
        return "annuel"
    return "trimestre/CA"


def evenements(isin, annees):
    par_jour = {}
    for a in annees:
        for r in dila(isin, a):
            d = (r.get("uin_dat_amf") or "")[:10]; t = r.get("informationdeposee_inf_tit_inf") or ""
            if len(d) == 10 and MOTS_RESULTATS.search(t) and not EXCLUS.search(t):
                par_jour.setdefault(d, type_publication(t))
        time.sleep(0.25)
    sortie = []  # un seul événement par grappe de 7 jours
    for d in sorted(par_jour):
        if not sortie or (dt.date.fromisoformat(d) - dt.date.fromisoformat(sortie[-1][0])).days > 7:
            sortie.append((d, par_jour[d]))
    return sortie


def rendements_anormaux(s, cac_idx, cac_c):
    d = s["d"]; c = np.array(s["c"], dtype=float)
    r = np.full(len(d), np.nan); r[1:] = c[1:] / c[:-1] - 1
    cr = np.full(len(d), np.nan)
    for i in range(1, len(d)):
        a, b = cac_idx.get(d[i - 1]), cac_idx.get(d[i])
        if a is not None and b is not None:
            cr[i] = cac_c[b] / cac_c[a] - 1
    return r - cr


def car(ar, j, a, b):
    i0, i1 = j + a, j + b
    if i0 < 1 or i1 >= len(ar):
        return np.nan
    x = ar[i0:i1 + 1]
    return np.nan if np.isnan(x).any() else float(np.sum(x))


def main():
    cle = base64.b64decode(os.environ.get("CLE_DONNEES", ""))
    if len(cle) != 32:
        sys.exit("CLE_DONNEES absente ou invalide.")
    series, indices, secteurs, sbf = L.charger(cle)
    cac = indices["FR0003500008"]; cac_c = np.array(cac["c"], dtype=float); cac_idx = {d: i for i, d in enumerate(cac["d"])}
    isins = {}
    for k in range(1, 5):
        for v in L.lire_bin(f"historique-{k}.bin", cle)["valeurs"]:
            isins[v["id"]] = v.get("isin")
    large = os.environ.get("ETENDU") == "1"
    cibles = [i for i in series if isins.get(i) and isins[i].startswith("FR") and (large or i in sbf)]
    print(f"{len(cibles)} valeurs étudiées (étendu={large})")
    annees = list(range(2016, dt.date.today().year + 1))
    lignes, base_par_fen, vus = [], {k: [] for k in FENETRES}, 0
    for n, ident in enumerate(cibles):
        s = series[ident]
        try:
            evs = evenements(isins[ident], annees)
        except Exception as e:
            print("échec DILA", ident, type(e).__name__, str(e)[:60]); continue
        if not evs:
            continue
        ar = rendements_anormaux(s, cac_idx, cac_c)
        dates = s["d"]
        pos = []
        for d, typ in evs:
            j = bisect.bisect_left(dates, d)
            if j < len(dates) and j > 25:
                pos.append((j, typ, d))
        bloques = np.zeros(len(ar), dtype=bool)
        for j, _, _ in pos:
            bloques[max(0, j - 25):j + 10] = True
        for nom, (a, b) in FENETRES.items():  # référence : mêmes durées hors événements, pas de 3 séances
            larg = b - a + 1
            for i in range(30, len(ar) - larg, 3):
                if not bloques[i:i + larg].any():
                    x = ar[i:i + larg]
                    if not np.isnan(x).any():
                        base_par_fen[nom].append(float(np.sum(x)))
        for j, typ, d in pos:
            lignes.append(dict(id=ident, date=d, type=typ, **{nom: car(ar, j, a, b) for nom, (a, b) in FENETRES.items()}))
        if n % 20 == 0:
            print(f"{n}/{len(cibles)} valeurs, {len(lignes)} événements")
    print(f"{len(lignes)} événements de résultats sur {len({l['id'] for l in lignes})} valeurs")
    rng = np.random.default_rng(0)
    resume = {}
    for groupe in ["tous", "annuel", "semestre", "trimestre/CA"]:
        sel = [l for l in lignes if groupe == "tous" or l["type"] == groupe]
        resume[groupe] = {}
        for nom in FENETRES:
            x = np.array([l[nom] for l in sel if not np.isnan(l[nom])]) * 100
            ref = np.array(base_par_fen[nom]) * 100
            if len(x) < 30:
                continue
            exces = x - ref.mean()
            boots = [rng.choice(exces, len(exces)).mean() for _ in range(2000)]
            resume[groupe][nom] = dict(n=int(len(x)), moyenne=round(float(x.mean()), 3), mediane=round(float(np.median(x)), 3),
                                       reference=round(float(ref.mean()), 3), exces=round(float(exces.mean()), 3),
                                       ic95=[round(float(np.percentile(boots, 2.5)), 3), round(float(np.percentile(boots, 97.5)), 3)],
                                       part_positifs=round(float((x > 0).mean()), 3))
            m = resume[groupe][nom]
            print(f"{groupe:13s} {nom:9s} n={m['n']:4d} moy {m['moyenne']:+.2f} % méd {m['mediane']:+.2f} % réf {m['reference']:+.2f} % excès {m['exces']:+.2f} % IC95 {m['ic95']} positifs {m['part_positifs']:.0%}")
    print("RÉSUMÉ", json.dumps(resume))


if __name__ == "__main__":
    main()
