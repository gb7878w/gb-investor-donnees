"""Modèle de prévision : apprend, sur deux ans de séances, quelles combinaisons de paramètres précèdent une hausse ou une baisse.

Cibles (pour chaque horizon de 5, 21 et 63 séances) :
  - « mieux » : la valeur fait mieux que le CAC 40,
  - « hausse » : gain d'au moins 5 %,
  - « baisse » : perte d'au moins 5 %.
Méthode : arbres de décision combinés (LightGBM). Validation « walk-forward » : le modèle est toujours testé sur une période
qu'il n'a jamais vue, avec un écart (embargo) d'une durée égale à l'horizon entre apprentissage et test.
La confiance affichée mesure ce que le modèle a réellement réussi sur ces périodes inconnues, jamais ce qu'il a vu en apprentissage.
"""
import datetime as dt, math

import numpy as np

import contexte as ctx

HORIZONS = [5, 21, 63]
DATES = []
CIBLES = ["mieux", "hausse", "baisse"]
SEUIL = 0.05  # 5 %
LIBELLES = {
    "ret1": "variation de la veille", "ret5": "variation sur 1 semaine", "ret21": "variation sur 1 mois", "ret63": "variation sur 3 mois",
    "d_mm20": "écart à la moyenne 20 séances", "d_mm50": "écart à la moyenne 50 séances", "d_mm200": "écart à la moyenne 200 séances",
    "pente20": "pente de la moyenne 20", "pente50": "pente de la moyenne 50",
    "rsi": "RSI", "macd": "MACD", "boll": "position dans les bandes de Bollinger", "atr": "agitation habituelle (ATR)",
    "volrel": "volume relatif", "gap": "écart d'ouverture", "d_haut": "distance au plus haut annuel", "d_bas": "distance au plus bas annuel",
    "serie": "séances consécutives dans le même sens",
    "cac5": "CAC 40 sur 1 semaine", "cac21": "CAC 40 sur 1 mois", "cac63": "CAC 40 sur 3 mois", "ampleur": "part des valeurs en hausse",
    "rel21": "force relative vs CAC 40 (1 mois)", "rel63": "force relative vs CAC 40 (3 mois)", "relsect21": "force relative vs secteur (1 mois)",
    "jour": "jour de la semaine", "mois": "mois de l'année", "finmois": "fin de mois",
    "vix": "volatilité (VIX)", "vix5": "volatilité sur 1 semaine", "brent21": "pétrole sur 1 mois", "eurusd21": "euro/dollar sur 1 mois",
    "us10": "taux américain à 10 ans", "us10_21": "taux américain à 10 ans sur 1 mois", "sp5": "S&P 500 sur 1 semaine",
    "ez10": "taux à 10 ans zone euro", "ez10_21": "taux à 10 ans zone euro sur 1 mois",
}


def _sma(x, n):
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        c = np.cumsum(np.insert(x, 0, 0.0))
        out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def _ema(x, n):
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    k = 2.0 / (n + 1)
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def _rsi(c, n=14):
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    d = np.diff(c)
    hausse, baisse = np.maximum(d, 0), np.maximum(-d, 0)
    h, b = hausse[:n].mean(), baisse[:n].mean()
    out[n] = 100.0 if b == 0 else 100 - 100 / (1 + h / b)
    for i in range(n, len(d)):
        h = (h * (n - 1) + hausse[i]) / n; b = (b * (n - 1) + baisse[i]) / n
        out[i + 1] = 50.0 if (h == 0 and b == 0) else (100.0 if b == 0 else 100 - 100 / (1 + h / b))
    return out


def _ret(c, n):
    out = np.full(len(c), np.nan)
    if len(c) > n:
        out[n:] = c[n:] / c[:-n] - 1
    return out


def _avant(c, n):
    out = np.full(len(c), np.nan)
    if len(c) > n:
        out[n:] = c[:-n]
    return out


def _rolling(f, x, n):
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        out[i] = f(x[i - n + 1:i + 1])
    return out


def _caracteristiques(s):
    """Paramètres propres à la valeur, calculés avec les seules séances jusqu'au jour considéré."""
    o, h, l, c, v = (np.array(s[k], dtype=float) for k in "ohlcv")
    n = len(c)
    mm20, mm50, mm200 = _sma(c, 20), _sma(c, 50), _sma(c, 200)
    e12, e26 = _ema(c, 12), _ema(c, 26)
    ligne = e12 - e26
    valides = ~np.isnan(ligne)
    signal = np.full(n, np.nan)
    if valides.sum() >= 9:
        idx = np.where(valides)[0]
        signal[idx] = _ema(ligne[idx], 9)
    ecart = _rolling(np.std, c, 20)
    bas = mm20 - 2 * ecart
    larg = 4 * ecart
    veille = _avant(c, 1)
    vrai = np.maximum.reduce([h - l, np.abs(h - np.where(np.isnan(veille), h, veille)), np.abs(l - np.where(np.isnan(veille), l, veille))])
    atr = np.full(n, np.nan)
    if n > 14:
        atr[14] = vrai[1:15].mean()
        for i in range(15, n):
            atr[i] = (atr[i - 1] * 13 + vrai[i]) / 14
    vol_moy = np.concatenate([[np.nan], _sma(v, 20)[:-1]])
    haut = _rolling(np.max, h, 252) if n >= 252 else np.full(n, np.nan)
    basan = _rolling(np.min, l, 252) if n >= 252 else np.full(n, np.nan)
    serie = np.zeros(n)
    for i in range(1, n):
        if c[i] > c[i - 1]:
            serie[i] = serie[i - 1] + 1 if serie[i - 1] > 0 else 1
        elif c[i] < c[i - 1]:
            serie[i] = serie[i - 1] - 1 if serie[i - 1] < 0 else -1
    with np.errstate(divide="ignore", invalid="ignore"):
        cols = {
            "ret1": _ret(c, 1), "ret5": _ret(c, 5), "ret21": _ret(c, 21), "ret63": _ret(c, 63),
            "d_mm20": c / mm20 - 1, "d_mm50": c / mm50 - 1, "d_mm200": c / mm200 - 1,
            "pente20": mm20 / _avant(mm20, 5) - 1, "pente50": mm50 / _avant(mm50, 10) - 1,
            "rsi": _rsi(c), "macd": (ligne - signal) / c, "boll": np.where(larg > 0, (c - bas) / larg, np.nan), "atr": atr / c,
            "volrel": np.where(vol_moy > 0, v / vol_moy, np.nan), "gap": o / veille - 1,
            "d_haut": c / haut - 1, "d_bas": c / basan - 1, "serie": serie,
        }
    return cols


def _recherche(dates, valeurs, cible):
    """Valeur de la série `valeurs` à la date `cible` (ou la dernière avant), None si absente."""
    import bisect
    i = bisect.bisect_right(dates, cible) - 1
    return valeurs[i] if i >= 0 else None


def construire(series, indices, secteurs, series_ctx, aujourdhui_dernier=None):
    """Tableau d'apprentissage : une ligne par valeur et par séance. Renvoie X, noms, dates (rang), isin, étiquettes."""
    cac = indices.get("FR0003500008")
    if not cac or len(cac["d"]) < 100:
        raise ValueError("indice CAC 40 absent")
    cac_dates, cac_c = cac["d"], np.array(cac["c"], dtype=float)
    cac_idx = {d: i for i, d in enumerate(cac_dates)}
    cac_cols = {"cac5": _ret(cac_c, 5), "cac21": _ret(cac_c, 21), "cac63": _ret(cac_c, 63)}
    # Ampleur du marché : part des valeurs en hausse sur 5 séances, jour par jour.
    ampleur_tmp = {}
    pre = {}
    for isin, s in series.items():
        pre[isin] = _caracteristiques(s)
        for d, r in zip(s["d"], pre[isin]["ret5"]):
            if not math.isnan(r):
                ampleur_tmp.setdefault(d, []).append(r > 0)
    ampleur = {d: sum(v) / len(v) for d, v in ampleur_tmp.items() if len(v) >= 30}
    # Variation à 1 mois de chaque secteur (moyenne des valeurs), pour la force relative sectorielle.
    sect_r21 = {}
    for isin, s in series.items():
        for d, r in zip(s["d"], pre[isin]["ret21"]):
            if not math.isnan(r):
                sect_r21.setdefault((secteurs.get(isin, "?"), d), []).append(r)
    sect_moy = {k: sum(v) / len(v) for k, v in sect_r21.items() if len(v) >= 2}
    noms = None
    X, rang, ident, etiq, derniers = [], [], [], [], {}
    toutes_dates = sorted({d for s in series.values() for d in s["d"]})
    rang_date = {d: i for i, d in enumerate(toutes_dates)}
    global DATES
    DATES = toutes_dates
    for isin, s in series.items():
        n = len(s["d"])
        if n < 120:
            continue
        cols = dict(pre[isin])
        dates = s["d"]
        c = np.array(s["c"], dtype=float)
        nb = len(dates)
        for nom in ("cac5", "cac21", "cac63"):
            cols[nom] = np.array([cac_cols[nom][cac_idx[d]] if d in cac_idx else np.nan for d in dates])
        cols["ampleur"] = np.array([ampleur.get(d, np.nan) for d in dates])
        cols["rel21"] = cols["ret21"] - cols["cac21"]
        cols["rel63"] = cols["ret63"] - cols["cac63"]
        cols["relsect21"] = np.array([cols["ret21"][i] - sect_moy.get((secteurs.get(isin, "?"), dates[i]), np.nan) for i in range(nb)])
        dts = [dt.date.fromisoformat(d) for d in dates]
        cols["jour"] = np.array([x.weekday() for x in dts], dtype=float)
        cols["mois"] = np.array([x.month for x in dts], dtype=float)
        cols["finmois"] = np.array([(dt.date(x.year + (x.month == 12), x.month % 12 + 1, 1) - x).days for x in dts], dtype=float)
        for nom, ident_ctx, mode, jours in [("vix", "VIXCLS", "niveau", 0), ("vix5", "VIXCLS", "var", 7), ("brent21", "DCOILBRENTEU", "var", 30),
                                            ("eurusd21", "DEXUSEU", "var", 30), ("us10", "DGS10", "niveau", 0), ("us10_21", "DGS10", "diff", 30),
                                            ("sp5", "SP500", "var", 7), ("ez10", "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", "niveau", 0),
                                            ("ez10_21", "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", "diff", 30)]:
            ser = series_ctx.get(ident_ctx)
            if ser is None:
                cols[nom] = np.full(nb, np.nan); continue
            vals = []
            for d in dates:
                if mode == "niveau":
                    x = ctx.valeur_avant(ser, d)
                elif mode == "var":
                    x = ctx.variation(ser, d, jours)
                else:
                    a = ctx.valeur_avant(ser, d); b = ctx.valeur_avant(ser, (dt.date.fromisoformat(d) - dt.timedelta(days=jours)).isoformat())
                    x = None if a is None or b is None else a - b
                vals.append(np.nan if x is None else x)
            cols[nom] = np.array(vals)
        if noms is None:
            noms = list(cols)
        mat = np.column_stack([cols[k] for k in noms])
        # Étiquettes : gain futur de la valeur, et écart avec le CAC 40 sur la même période.
        for h in HORIZONS:
            fut = np.full(nb, np.nan); fut[:nb - h] = c[h:] / c[:nb - h] - 1
            cf = np.full(nb, np.nan)
            for i in range(nb - h):
                a, b = cac_idx.get(dates[i]), cac_idx.get(dates[i + h])
                if a is not None and b is not None:
                    cf[i] = cac_c[b] / cac_c[a] - 1
            cols[f"fut{h}"] = fut; cols[f"cf{h}"] = cf
        lab = np.column_stack([cols[f"fut{h}"] for h in HORIZONS] + [cols[f"cf{h}"] for h in HORIZONS])
        debut = 25
        X.append(mat[debut:]); etiq.append(lab[debut:])
        rang.extend(rang_date[d] for d in dates[debut:]); ident.extend([isin] * (nb - debut))
        derniers[isin] = (mat[-1], dates[-1])
    return np.vstack(X), noms, np.array(rang), np.array(ident), np.vstack(etiq), derniers


def _cibles(etiq, h):
    k = HORIZONS.index(h)
    fut, cf = etiq[:, k], etiq[:, len(HORIZONS) + k]
    ok = ~np.isnan(fut)
    mieux = np.where(np.isnan(cf), np.nan, (fut - cf > 0).astype(float))
    hausse = np.where(ok, (fut >= SEUIL).astype(float), np.nan)
    baisse = np.where(ok, (fut <= -SEUIL).astype(float), np.nan)
    return {"mieux": mieux, "hausse": hausse, "baisse": baisse}


def _auc(y, p):
    """Aire sous la courbe ROC (0,5 = hasard, 1 = parfait), égalités traitées par rang moyen."""
    y = np.asarray(y); p = np.asarray(p)
    n1, n0 = int((y == 1).sum()), int((y == 0).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    ordre = np.argsort(p, kind="mergesort")
    tri = p[ordre]
    rangs_tri = np.arange(1, len(p) + 1, dtype=float)
    debuts = np.r_[0, np.flatnonzero(np.diff(tri)) + 1, len(p)]
    for a, b in zip(debuts[:-1], debuts[1:]):
        rangs_tri[a:b] = (a + 1 + b) / 2
    rangs = np.empty(len(p)); rangs[ordre] = rangs_tri
    return float((rangs[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=150, feature_fraction=0.8, bagging_fraction=0.8,
              bagging_freq=1, lambda_l2=5.0, verbose=-1, num_threads=2, seed=7)
TOURS = 150


def _entrainer(X, y):
    import lightgbm as lgb
    return lgb.train(PARAMS, lgb.Dataset(X, label=y), num_boost_round=TOURS)


def _logistique(Xtr, ytr, tours=8, l2=1.0):
    """Référence simple : régression logistique régularisée (Newton), manquants remplacés par la médiane."""
    med = np.nanmedian(Xtr, axis=0); med = np.where(np.isnan(med), 0.0, med)
    def prep(X, mu=None, sd=None):
        Z = np.where(np.isnan(X), med, X)
        return Z
    Z = prep(Xtr); mu = Z.mean(axis=0); sd = Z.std(axis=0); sd[sd == 0] = 1.0
    Z = np.hstack([(Z - mu) / sd, np.ones((len(Z), 1))])
    w = np.zeros(Z.shape[1])
    for _ in range(tours):
        p = 1.0 / (1.0 + np.exp(-np.clip(Z @ w, -30, 30)))
        g = Z.T @ (p - ytr) + l2 * w
        H = (Z * (p * (1 - p))[:, None]).T @ Z + l2 * np.eye(len(w))
        w -= np.linalg.solve(H, g)
    def predire(X):
        Zt = np.hstack([(prep(X) - mu) / sd, np.ones((len(X), 1))])
        return 1.0 / (1.0 + np.exp(-np.clip(Zt @ w, -30, 30)))
    return predire


def _pav(x, y, k=60.0):
    """Régression isotonique (plus un score est haut, plus la probabilité est haute), points de repère interpolables.
    Chaque palier est ramené vers le taux de base quand il repose sur peu de cas."""
    ordre = np.argsort(x, kind="stable")
    xs, ys = x[ordre].astype(float), y[ordre].astype(float)
    base = float(ys.mean())
    blocs = []  # [somme y, effectif, somme x]
    for xi, yi in zip(xs, ys):
        blocs.append([yi, 1.0, xi])
        while len(blocs) > 1 and blocs[-2][0] / blocs[-2][1] >= blocs[-1][0] / blocs[-1][1]:
            b = blocs.pop(); blocs[-1][0] += b[0]; blocs[-1][1] += b[1]; blocs[-1][2] += b[2]
    centres = np.array([b[2] / b[1] for b in blocs])
    valeurs = np.array([(b[0] + base * k) / (b[1] + k) for b in blocs])
    valeurs = np.maximum.accumulate(valeurs)
    return centres, valeurs


def _appliquer(cal, p):
    centres, valeurs = cal
    return np.interp(p, centres, valeurs)


def _ancien(p, y, base):
    """Ancienne calibration par 10 tranches (conservée pour comparaison)."""
    bornes = np.unique(np.quantile(p, np.linspace(0, 1, 11)))
    cal = []
    for a, b in zip(bornes[:-1], bornes[1:]):
        dans = (p >= a) & ((p < b) | (b == bornes[-1]))
        cal.append((float(a), float(b), float((y[dans].sum() + base * 60) / (dans.sum() + 60))))
    return cal


def _appliquer_ancien(cal, p):
    sortie = np.empty(len(p))
    for k, v in enumerate(p):
        sortie[k] = cal[-1][2]
        for a, bb, f in cal:
            if v <= bb:
                sortie[k] = f; break
    return sortie


def _voisins(cal, p, largeur=1500):
    """Cas semblables : parmi les prévisions jamais vues de score voisin, part qui s'est vérifiée.
    n compte des cas indépendants (les étiquettes se chevauchent sur h séances)."""
    pt, yt = cal["p_tri"], cal["y_tri"]
    i = int(np.searchsorted(pt, p))
    a, b = max(0, i - largeur // 2), min(len(pt), i + largeur // 2)
    if b - a < 50:
        return None
    return {"n": int((b - a) / cal["h"]), "freq": round(float(yt[a:b].mean()), 4)}


def evaluer_et_prevoir(X, noms, rang, etiq, derniers, journal=print):
    """Walk-forward par horizon et cible, puis modèle final et prévisions du dernier jour."""
    import lightgbm as lgb
    rangs_uniques = np.unique(rang)
    debut_test = rangs_uniques[int(len(rangs_uniques) * 0.45)]
    blocs = np.array_split(rangs_uniques[rangs_uniques >= debut_test], 5)
    resultat = {"bulletin": {}, "modeles": {}}
    for h in HORIZONS:
        cibles = _cibles(etiq, h)
        for cible in CIBLES:
            y = cibles[cible]
            p_oos, y_oos, par_bloc, p_ref = [], [], [], []
            for bloc in blocs:
                if len(bloc) == 0:
                    continue
                tr = (rang <= bloc[0] - h) & ~np.isnan(y)
                te = np.isin(rang, bloc) & ~np.isnan(y)
                if tr.sum() < 3000 or te.sum() < 300 or len(np.unique(y[tr])) < 2:
                    continue
                m = _entrainer(X[tr], y[tr])
                p_bloc = m.predict(X[te])
                try:
                    p_ref.append(_logistique(X[tr], y[tr])(X[te]))
                except Exception:
                    p_ref.append(np.full(int(te.sum()), float(np.nanmean(y[tr]))))
                p_oos.append(p_bloc); y_oos.append(y[te])
                if len(np.unique(y[te])) == 2:
                    fin = int(bloc[-1])
                    par_bloc.append({"jusqu_a": DATES[fin] if fin < len(DATES) else "", "auc": round(_auc(y[te], p_bloc), 4), "cas": int(te.sum())})
            if not p_oos:
                resultat["bulletin"][(h, cible)] = None
                journal(f"horizon {h} {cible} : pas assez de données pour valider")
                continue
            # Le calibrage est appris sur les premiers blocs jamais vus et jugé sur le dernier, qu'il n'a pas vu.
            p_bloc = list(p_oos); y_bloc = list(y_oos)
            p_oos = np.concatenate(p_oos); y_oos = np.concatenate(y_oos)
            base = float(y_oos.mean())
            auc = _auc(y_oos, p_oos)
            brier = float(np.mean((p_oos - y_oos) ** 2)); brier_base = float(np.mean((base - y_oos) ** 2))
            n_eff = len(y_oos) / h  # les étiquettes se chevauchent : le nombre d'observations réellement indépendantes est bien plus petit
            auc_prudent = 0.5 + (auc - 0.5) * n_eff / (n_eff + 400.0)
            p_ref = np.concatenate(p_ref)
            reference = dict(auc=_auc(y_oos, p_ref), brier=float(np.mean((p_ref - y_oos) ** 2)))
            choix, comparaison = "brut", {}
            if len(p_bloc) >= 3:
                p_app, y_app = np.concatenate(p_bloc[:-1]), np.concatenate(y_bloc[:-1])
                p_jug, y_jug = p_bloc[-1], y_bloc[-1]
                base_app = float(y_app.mean())
                essais = {
                    "brut": p_jug,
                    "tranches": _appliquer_ancien(_ancien(p_app, y_app, base_app), p_jug),
                    "isotonique": _appliquer(_pav(p_app, y_app), p_jug),
                    "base": np.full(len(p_jug), base_app),
                }
                comparaison = {k: round(float(np.mean((v - y_jug) ** 2)), 5) for k, v in essais.items()}
                candidats = {k: v for k, v in comparaison.items() if k in ("brut", "tranches", "isotonique")}
                choix = min(candidats, key=candidats.get)
                if comparaison["base"] <= candidats[choix]:
                    choix = "isotonique"  # rien ne bat le taux de base : le calibrage lissé reste le plus prudent
            tri = np.argsort(p_oos, kind="stable")
            cal = {"methode": choix, "isotonique": _pav(p_oos, y_oos), "tranches": _ancien(p_oos, y_oos, base), "p_tri": p_oos[tri], "y_tri": y_oos[tri], "h": h}
            resultat["bulletin"][(h, cible)] = dict(auc=auc, auc_prudent=auc_prudent, base=base, brier=brier, brier_base=brier_base,
                                                  cas=int(len(y_oos)), independants=float(n_eff), calibration=cal, blocs=par_bloc, comparaison=comparaison, reference=reference)
            journal(f"horizon {h} {cible} : référence logistique AUC {reference['auc']:.3f}, calibrage {choix} {comparaison} ; AUC {auc:.3f} (prudent {auc_prudent:.3f}), taux de base {base:.3f}, Brier {brier:.4f} vs {brier_base:.4f}, {len(y_oos)} cas")
            ok = ~np.isnan(y)
            if ok.sum() > 3000 and len(np.unique(y[ok])) == 2:
                resultat["modeles"][(h, cible)] = _entrainer(X[ok], y[ok])
    return resultat


def previsions(resultat, noms, derniers, secteurs=None):
    """Probabilité calibrée, confiance et explications (SHAP) de chaque valeur pour chaque horizon et cible."""
    isins = sorted(derniers)
    M = np.vstack([derniers[i][0] for i in isins])
    sortie = {isin: {} for isin in isins}
    for (h, cible), modele in resultat["modeles"].items():
        b = resultat["bulletin"][(h, cible)]
        p = modele.predict(M)
        contrib = modele.predict(M, pred_contrib=True)[:, :-1]
        cal = b["calibration"]
        if cal["methode"] == "tranches":
            pcal = _appliquer_ancien(cal["tranches"], p)
        elif cal["methode"] == "isotonique":
            pcal = _appliquer(cal["isotonique"], p)
        else:
            pcal = p
        for k, isin in enumerate(isins):
            pc = float(pcal[k])
            voisins = _voisins(cal, float(p[k]))
            ordre = np.argsort(-np.abs(contrib[k]))[:4]
            pourquoi = [[noms[j], float(contrib[k][j]), None if np.isnan(M[k][j]) else float(M[k][j])] for j in ordre if abs(contrib[k][j]) > 1e-6]
            sortie[isin].setdefault(str(h), {})[cible] = {
                "p": round(float(pc), 4), "brut": round(float(p[k]), 4), "base": round(b["base"], 4),
                "confiance": round(float(b["auc_prudent"]) * 100, 1), "pourquoi": pourquoi, "voisins": voisins}
    return sortie


def importance(resultat, noms):
    """Poids de chaque paramètre dans les modèles finaux (gain moyen, ramené à 100 %)."""
    total = np.zeros(len(noms))
    for modele in resultat["modeles"].values():
        g = modele.feature_importance(importance_type="gain").astype(float)
        if g.sum() > 0:
            total += g / g.sum()
    if total.sum() == 0:
        return {}
    total = total / total.sum()
    return {noms[j]: round(float(total[j]) * 100, 2) for j in np.argsort(-total)}


def bulletin(resultat):
    sortie = []
    for (h, cible), b in sorted(resultat["bulletin"].items()):
        if b is None:
            sortie.append({"horizon": h, "cible": cible, "valide": False}); continue
        sortie.append({"horizon": h, "cible": cible, "valide": True, "auc": round(b["auc"], 4), "confiance": round(b["auc_prudent"] * 100, 1),
                       "base": round(b["base"], 4), "brier": round(b["brier"], 5), "brier_base": round(b["brier_base"], 5),
                       "cas": b["cas"], "independants": round(b["independants"]), "blocs": b["blocs"],
                       "calibration": b["calibration"]["methode"], "brier_calibrations": b["comparaison"],
                       "reference_auc": round(b["reference"]["auc"], 4), "reference_brier": round(b["reference"]["brier"], 5)})
    return sortie
