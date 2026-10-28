"""Analyse graphique et technique : paramètres classiques des chartistes, calculés avec les seules séances jusqu'au jour considéré.

Cinq familles, essayées séparément (modele.NOMS_GROUPES) :
  - oscillateurs : stochastique, Williams %R, CCI, MFI, TRIX, oscillateur ultime, force d'Elder, divergences du RSI ;
  - tendance : ADX/DMI, Aroon, SAR parabolique, SuperTrend, Ichimoku, croisements de moyennes et du MACD, Heikin-Ashi,
    canal de régression, théorie de Dow (sommets et creux ascendants) ;
  - volume : OBV, accumulation/distribution, Chaikin, CMF, VWAP, volume des séances de hausse, force, facilité de mouvement,
    volume des cassures ;
  - bougies : chandeliers japonais (doji, marteau, pendu, étoile filante, avalement, harami, étoiles du matin et du soir,
    trois soldats et trois corbeaux, marubozu, ligne pénétrante, nuage noir, barres incluses et englobantes) ;
  - figures : supports et résistances, cassures (20 et 55 séances), Donchian, Keltner, compression des bandes de Bollinger,
    Fibonacci, points pivots, double sommet et double creux, tête-épaules (et inversée), triangles, drapeaux et fanions,
    rectangles, gaps non comblés, seuils psychologiques.
Les figures reposent sur les sommets et creux « confirmés » (plus haut ou plus bas des 5 séances de part et d'autre),
connus seulement 5 séances après : aucune information future n'entre dans le calcul.
"""
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as _fenetre

OSCILLATEURS = ["stoch_k", "stoch_d", "stoch_kd", "williams", "cci", "mfi", "trix", "ultime", "elder_achat", "elder_vente", "div_rsi"]
TENDANCE = ["adx", "di_ecart", "aroon", "sar_ecart", "sar_jours", "supertrend", "supertrend_jours", "ichi_tenkan", "ichi_kijun",
            "ichi_tk", "ichi_nuage", "ichi_futur", "ichi_chikou", "crois_mm", "crois_macd", "heikin", "canal_pente", "canal_r2",
            "canal_pos", "dow"]
VOLUME = ["obv_pente", "ad_pente", "chaikin", "cmf", "vwap20", "vol_hausse", "force13", "eom", "vol_cassure"]
BOUGIES = ["corps", "ombre_haute", "ombre_basse", "taille", "doji", "marteau", "marteau_inv", "avalement", "harami", "etoile",
           "soldats", "marubozu", "penetrante", "barre_incluse", "barre_englobante", "bougies_score"]
FIGURES = ["resistance", "support", "resistance_force", "support_force", "cassure_res", "cassure20", "cassure20_bas", "cassure55",
           "cassure55_bas", "donchian55", "keltner", "boll_largeur", "compression", "fibo_pos", "fibo_dist", "fibo_sens", "pivot",
           "double", "epaule_tete", "pente_sommets", "pente_creux", "triangle", "drapeau", "rectangle", "gaps_ouverts", "seuil_rond"]
GROUPES = {"oscillateurs": OSCILLATEURS, "tendance": TENDANCE, "volume": VOLUME, "bougies": BOUGIES, "figures": FIGURES}
NOMS = OSCILLATEURS + TENDANCE + VOLUME + BOUGIES + FIGURES

LIBELLES = {
    "stoch_k": "stochastique %K", "stoch_d": "stochastique %D", "stoch_kd": "stochastique %K moins %D", "williams": "Williams %R",
    "cci": "CCI (Commodity Channel Index)", "mfi": "MFI (indice des flux monétaires)", "trix": "TRIX", "ultime": "oscillateur ultime",
    "elder_achat": "force des acheteurs (Elder)", "elder_vente": "force des vendeurs (Elder)", "div_rsi": "divergence cours/RSI",
    "adx": "force de la tendance (ADX)", "di_ecart": "sens de la tendance (DI+ moins DI-)", "aroon": "oscillateur Aroon",
    "sar_ecart": "écart au SAR parabolique", "sar_jours": "séances depuis le retournement du SAR", "supertrend": "écart au SuperTrend",
    "supertrend_jours": "séances depuis le retournement du SuperTrend", "ichi_tenkan": "écart à la Tenkan (Ichimoku)",
    "ichi_kijun": "écart à la Kijun (Ichimoku)", "ichi_tk": "Tenkan contre Kijun (Ichimoku)", "ichi_nuage": "position par rapport au nuage (Ichimoku)",
    "ichi_futur": "couleur du nuage à venir (Ichimoku)", "ichi_chikou": "Chikou (Ichimoku)",
    "crois_mm": "séances depuis le croisement des moyennes 50 et 200 (croix dorée ou de la mort)", "crois_macd": "séances depuis le croisement du MACD",
    "heikin": "bougies Heikin-Ashi consécutives de même couleur", "canal_pente": "pente du canal de tendance (50 séances)",
    "canal_r2": "netteté du canal de tendance", "canal_pos": "position dans le canal de tendance", "dow": "sommets et creux ascendants (Dow)",
    "obv_pente": "OBV (volume cumulé) sur 1 mois", "ad_pente": "accumulation/distribution sur 1 mois", "chaikin": "oscillateur de Chaikin",
    "cmf": "flux monétaire de Chaikin (CMF)", "vwap20": "écart au prix moyen pondéré par les volumes (VWAP 20)",
    "vol_hausse": "part du volume échangé en séances de hausse", "force13": "indice de force (Elder)", "eom": "facilité de mouvement (EOM)",
    "vol_cassure": "volume lors d'une cassure", "corps": "corps de la bougie", "ombre_haute": "mèche haute", "ombre_basse": "mèche basse",
    "taille": "taille de la bougie (en ATR)", "doji": "doji", "marteau": "marteau ou pendu", "marteau_inv": "marteau inversé ou étoile filante",
    "avalement": "avalement", "harami": "harami", "etoile": "étoile du matin ou du soir", "soldats": "trois soldats blancs ou trois corbeaux noirs",
    "marubozu": "marubozu", "penetrante": "ligne pénétrante ou nuage noir", "barre_incluse": "barre incluse", "barre_englobante": "barre englobante",
    "bougies_score": "bilan des chandeliers japonais sur 3 séances", "resistance": "distance à la résistance la plus proche",
    "support": "distance au support le plus proche", "resistance_force": "solidité de la résistance", "support_force": "solidité du support",
    "cassure_res": "cassure d'un support ou d'une résistance", "cassure20": "cassure du plus haut 20 séances", "cassure20_bas": "cassure du plus bas 20 séances",
    "cassure55": "cassure du plus haut 55 séances", "cassure55_bas": "cassure du plus bas 55 séances", "donchian55": "position dans le canal de Donchian",
    "keltner": "position dans le canal de Keltner", "boll_largeur": "largeur des bandes de Bollinger", "compression": "compression des bandes de Bollinger",
    "fibo_pos": "retracement de Fibonacci (6 mois)", "fibo_dist": "distance au niveau de Fibonacci le plus proche", "fibo_sens": "sens du dernier mouvement (Fibonacci)",
    "pivot": "position par rapport aux points pivots", "double": "double sommet ou double creux", "epaule_tete": "tête-épaules (ou inversée)",
    "pente_sommets": "pente des derniers sommets", "pente_creux": "pente des derniers creux", "triangle": "resserrement du triangle",
    "drapeau": "drapeau ou fanion", "rectangle": "largeur de la consolidation (en ATR)", "gaps_ouverts": "gaps non comblés",
    "seuil_rond": "distance au seuil psychologique le plus proche",
}

K_SOMMET = 5  # un sommet est le plus haut des 5 séances de part et d'autre, connu 5 séances après


def _vide(n):
    return np.full(n, np.nan)


def _avant(x, k):
    out = _vide(len(x))
    if len(x) > k:
        out[k:] = x[:-k]
    return out


def _glisse(f, x, n):
    """f appliquée sur les n dernières valeurs (NaN si une valeur manque)."""
    out = _vide(len(x))
    if len(x) >= n:
        out[n - 1:] = f(_fenetre(x, n), axis=1)
    return out


def _sma(x, n):
    return _glisse(np.mean, x, n)


def _somme(x, n):
    return _glisse(np.sum, x, n)


def _ema(x, n):
    """Moyenne exponentielle qui démarre à la première fenêtre complète et saute les manquants."""
    out = _vide(len(x))
    k = 2.0 / (n + 1)
    prec, vus, acc = np.nan, 0, 0.0
    for i, v in enumerate(x):
        if v != v:
            out[i] = prec
            continue
        if vus < n:
            acc += v; vus += 1
            if vus == n:
                prec = acc / n
        else:
            prec = v * k + prec * (1 - k)
        out[i] = prec
    return out


def _wilder(x, n):
    out = _vide(len(x))
    prec, vus, acc = np.nan, 0, 0.0
    for i, v in enumerate(x):
        if v != v:
            out[i] = prec
            continue
        if vus < n:
            acc += v; vus += 1
            if vus == n:
                prec = acc / n
        else:
            prec = (prec * (n - 1) + v) / n
        out[i] = prec
    return out


def _serie_signe(s):
    """Nombre de séances consécutives de même signe (positif ou négatif)."""
    out = np.zeros(len(s))
    for i in range(len(s)):
        if s[i] > 0:
            out[i] = out[i - 1] + 1 if i and out[i - 1] > 0 else 1
        elif s[i] < 0:
            out[i] = out[i - 1] - 1 if i and out[i - 1] < 0 else -1
    return out


def _depuis_croisement(a, b, plafond=250):
    """Séances depuis que a est passé au-dessus (positif) ou au-dessous (négatif) de b."""
    d = a - b
    out = _vide(len(d))
    compte, signe = np.nan, 0
    for i, v in enumerate(d):
        if v != v:
            compte, signe = np.nan, 0
            continue
        s = 1 if v > 0 else -1
        if s != signe:
            compte = 0 if signe else np.nan
            signe = s
        elif compte == compte:
            compte = min(compte + 1, plafond)
        out[i] = s * compte if compte == compte else s * plafond
    return out


def _sar(h, l, pas=0.02, maxi=0.2):
    n = len(h)
    sar, jours = _vide(n), _vide(n)
    if n < 3:
        return sar, jours
    haussier, af = True, pas
    ep, s, compte = h[0], l[0], 0
    for i in range(1, n):
        if h[i] != h[i] or l[i] != l[i]:
            continue
        s = s + af * (ep - s)
        if haussier:
            s = min(s, l[i - 1], l[i - 2] if i > 1 else l[i - 1])
            if l[i] < s:
                haussier, s, ep, af, compte = False, ep, l[i], pas, 0
            elif h[i] > ep:
                ep, af = h[i], min(af + pas, maxi)
        else:
            s = max(s, h[i - 1], h[i - 2] if i > 1 else h[i - 1])
            if h[i] > s:
                haussier, s, ep, af, compte = True, ep, h[i], pas, 0
            elif l[i] < ep:
                ep, af = l[i], min(af + pas, maxi)
        compte += 1
        sar[i] = s
        jours[i] = compte if haussier else -compte
    return sar, jours


def _supertrend(h, l, c, atr, mult=3.0):
    n = len(c)
    ligne, jours = _vide(n), _vide(n)
    milieu = (h + l) / 2
    haut_b, bas_b = milieu + mult * atr, milieu - mult * atr
    hf, bf, haussier, compte = np.nan, np.nan, True, 0
    for i in range(n):
        if haut_b[i] != haut_b[i] or c[i] != c[i]:
            continue
        prec = c[i - 1] if i else c[i]
        hf = haut_b[i] if hf != hf or haut_b[i] < hf or prec > hf else hf
        bf = bas_b[i] if bf != bf or bas_b[i] > bf or prec < bf else bf
        if haussier and c[i] < bf:
            haussier, compte = False, 0
        elif not haussier and c[i] > hf:
            haussier, compte = True, 0
        compte += 1
        ligne[i] = bf if haussier else hf
        jours[i] = compte if haussier else -compte
    return ligne, jours


def _sommets(h, l, k=K_SOMMET):
    """Sommets et creux confirmés : indices où h (l) est le plus haut (bas) des k séances de part et d'autre."""
    n = len(h)
    if n < 2 * k + 1:
        return np.array([], int), np.array([], int)
    fh, fl = _fenetre(h, 2 * k + 1), _fenetre(l, 2 * k + 1)
    centre = np.arange(k, n - k)
    with np.errstate(invalid="ignore"):
        som = centre[(h[k:n - k] >= np.max(fh, axis=1)) & ~np.isnan(h[k:n - k])]
        cre = centre[(l[k:n - k] <= np.min(fl, axis=1)) & ~np.isnan(l[k:n - k])]
    # deux sommets égaux côte à côte : on garde le premier
    som = som[np.r_[True, np.diff(som) > k]] if len(som) else som
    cre = cre[np.r_[True, np.diff(cre) > k]] if len(cre) else cre
    return som, cre


def _pente(xs, ys):
    xs = np.asarray(xs, float); ys = np.asarray(ys, float)
    xm = xs.mean()
    sxx = ((xs - xm) ** 2).sum()
    return 0.0 if sxx == 0 else float(((xs - xm) * (ys - ys.mean())).sum() / sxx)


def _figures_sommets(h, l, c, v_rel):
    """Supports, résistances et figures tirées des sommets et creux confirmés."""
    n = len(c)
    noms = ["resistance", "support", "resistance_force", "support_force", "cassure_res", "double", "epaule_tete",
            "pente_sommets", "pente_creux", "triangle", "dow"]
    out = {k: _vide(n) for k in noms}
    som, cre = _sommets(h, l)
    k = K_SOMMET
    js, jc = 0, 0
    S, C = [], []  # (indice, niveau) des sommets et creux déjà connus
    res_veille, sup_veille = np.nan, np.nan
    for t in range(n):
        while js < len(som) and som[js] + k <= t:
            S.append((int(som[js]), float(h[som[js]]))); js += 1
        while jc < len(cre) and cre[jc] + k <= t:
            C.append((int(cre[jc]), float(l[cre[jc]]))); jc += 1
        x = c[t]
        if x != x:
            continue
        # niveaux des 250 dernières séances, sommets et creux confondus (une résistance cassée devient support)
        niveaux = [p for i, p in S[-40:] if i >= t - 250] + [p for i, p in C[-40:] if i >= t - 250]
        dessus = [p for p in niveaux if p > x]
        dessous = [p for p in niveaux if p < x]
        res = min(dessus) if dessus else np.nan
        sup = max(dessous) if dessous else np.nan
        out["resistance"][t] = res / x - 1 if res == res else np.nan
        out["support"][t] = x / sup - 1 if sup == sup else np.nan
        if res == res:
            out["resistance_force"][t] = sum(1 for p in niveaux if abs(p / res - 1) < 0.015)
        if sup == sup:
            out["support_force"][t] = sum(1 for p in niveaux if abs(p / sup - 1) < 0.015)
        cas = 0.0
        if t and res_veille == res_veille and x > res_veille and c[t - 1] <= res_veille:
            cas = 1.0
        elif t and sup_veille == sup_veille and x < sup_veille and c[t - 1] >= sup_veille:
            cas = -1.0
        out["cassure_res"][t] = cas * (v_rel[t] if v_rel[t] == v_rel[t] else 1.0)
        # seuls les niveaux touchés au moins deux fois comptent pour une cassure
        res_veille = res if res == res and out["resistance_force"][t] >= 2 else np.nan
        sup_veille = sup if sup == sup and out["support_force"][t] >= 2 else np.nan
        # théorie de Dow : derniers sommets et creux ascendants ou descendants
        if len(S) >= 2 and len(C) >= 2:
            out["dow"][t] = (1 if S[-1][1] > S[-2][1] else -1) + (1 if C[-1][1] > C[-2][1] else -1)
        # double sommet / double creux (encore récents) ; 2 = confirmé par la cassure de la ligne de cou
        dbl = 0
        if len(S) >= 2 and t - S[-1][0] <= 60:
            (i1, p1), (i2, p2) = S[-2], S[-1]
            if i2 - i1 >= 10 and abs(p2 / p1 - 1) < 0.03:
                cou = np.nanmin(l[i1:i2 + 1])
                if cou < min(p1, p2) * 0.95:
                    dbl = -2 if x < cou else -1
        if not dbl and len(C) >= 2 and t - C[-1][0] <= 60:
            (i1, p1), (i2, p2) = C[-2], C[-1]
            if i2 - i1 >= 10 and abs(p2 / p1 - 1) < 0.03:
                cou = np.nanmax(h[i1:i2 + 1])
                if cou > max(p1, p2) * 1.05:
                    dbl = 2 if x > cou else 1
        out["double"][t] = dbl
        # tête-épaules (sommet central dépassant les deux épaules de 3 %, épaules à moins de 5 % l'une de l'autre)
        te = 0
        if len(S) >= 3 and t - S[-1][0] <= 60:
            (a, pa), (b, pb), (d, pd) = S[-3:]
            if pb > pa * 1.03 and pb > pd * 1.03 and abs(pa / pd - 1) < 0.05:
                cou = min(np.nanmin(l[a:b + 1]), np.nanmin(l[b:d + 1]))
                te = -2 if x < cou else -1
        if not te and len(C) >= 3 and t - C[-1][0] <= 60:
            (a, pa), (b, pb), (d, pd) = C[-3:]
            if pb < pa * 0.97 and pb < pd * 0.97 and abs(pa / pd - 1) < 0.05:
                cou = max(np.nanmax(h[a:b + 1]), np.nanmax(h[b:d + 1]))
                te = 2 if x > cou else 1
        out["epaule_tete"][t] = te
        # triangles : pente des trois derniers sommets et creux, et largeur restante
        if len(S) >= 3 and len(C) >= 3 and t - min(S[-3][0], C[-3][0]) <= 120:
            si, sp = zip(*S[-3:]); ci, cp = zip(*C[-3:])
            ps, pc = _pente(si, sp), _pente(ci, cp)
            out["pente_sommets"][t] = ps * 20 / x
            out["pente_creux"][t] = pc * 20 / x
            haut_proj = np.mean(sp) + ps * (t - np.mean(si))
            bas_proj = np.mean(cp) + pc * (t - np.mean(ci))
            out["triangle"][t] = (haut_proj - bas_proj) / x
    return out


def _gaps_ouverts(h, l, n_jours=20):
    """Gaps de hausse non comblés moins gaps de baisse non comblés, ouverts depuis 20 séances au plus."""
    n = len(h)
    delta = np.zeros(n + 1)
    for j in range(1, n):
        if l[j] > h[j - 1]:  # gap de hausse : comblé quand un plus bas revient sous le plus haut d'avant
            seuil, signe = h[j - 1], 1
            suite = l[j + 1:j + n_jours]
            comble = np.flatnonzero(suite <= seuil)
        elif h[j] < l[j - 1]:
            seuil, signe = l[j - 1], -1
            suite = h[j + 1:j + n_jours]
            comble = np.flatnonzero(suite >= seuil)
        else:
            continue
        fin = min(n, j + 1 + (comble[0] if len(comble) else n_jours - 1))
        delta[j] += signe; delta[fin] -= signe
    return np.cumsum(delta)[:n]


def caracteristiques(o, h, l, c, v, rsi):
    n = len(c)
    o = np.where(np.isnan(o), c, o)
    h = np.fmax(np.where(np.isnan(h), c, h), np.fmax(o, c))
    l = np.fmin(np.where(np.isnan(l), c, l), np.fmin(o, c))
    v = np.where(np.isnan(v), 0.0, v)
    veille = _avant(c, 1)
    dc = c - veille
    cols = {}
    with np.errstate(divide="ignore", invalid="ignore"):
        vrai = np.fmax(h - l, np.fmax(np.abs(h - veille), np.abs(l - veille)))
        atr = _wilder(vrai, 14)
        vmoy = _sma(v, 20)
        vrel = np.where(_avant(vmoy, 1) > 0, v / _avant(vmoy, 1), np.nan)
        hh = {k: _glisse(np.max, h, k) for k in (9, 14, 20, 25, 26, 52, 55, 126)}
        ll = {k: _glisse(np.min, l, k) for k in (9, 14, 20, 25, 26, 52, 55, 126)}
        tp = (h + l + c) / 3

        # --- oscillateurs
        k_rapide = 100 * (c - ll[14]) / (hh[14] - ll[14])
        k_lent = _sma(k_rapide, 3)
        cols["stoch_k"] = k_lent
        cols["stoch_d"] = _sma(k_lent, 3)
        cols["stoch_kd"] = k_lent - cols["stoch_d"]
        cols["williams"] = k_rapide - 100
        tpm = _sma(tp, 20)
        ecart_moy = _vide(n)
        if n >= 20:
            f = _fenetre(tp, 20)
            ecart_moy[19:] = np.mean(np.abs(f - f.mean(axis=1, keepdims=True)), axis=1)
        cols["cci"] = (tp - tpm) / (0.015 * ecart_moy)
        flux = tp * v
        tp_v = _avant(tp, 1)
        pos, neg = _somme(np.where(tp > tp_v, flux, 0.0), 14), _somme(np.where(tp < tp_v, flux, 0.0), 14)
        cols["mfi"] = np.where(pos + neg > 0, 100 * pos / (pos + neg), np.nan)
        e3 = _ema(_ema(_ema(c, 15), 15), 15)
        cols["trix"] = e3 / _avant(e3, 1) - 1
        bas_v = np.fmin(l, np.where(np.isnan(veille), l, veille))
        haut_v = np.fmax(h, np.where(np.isnan(veille), h, veille))
        bp, tr = c - bas_v, haut_v - bas_v
        moy = [_somme(bp, k) / _somme(tr, k) for k in (7, 14, 28)]
        cols["ultime"] = 100 * (4 * moy[0] + 2 * moy[1] + moy[2]) / 7
        e13 = _ema(c, 13)
        cols["elder_achat"] = (h - e13) / c
        cols["elder_vente"] = (l - e13) / c
        cmax, cmin = _glisse(np.max, c, 40), _glisse(np.min, c, 40)
        rmax, rmin = _glisse(np.max, rsi, 40), _glisse(np.min, rsi, 40)
        div = np.where((c >= cmax) & (rsi < rmax - 5), -1.0, np.where((c <= cmin) & (rsi > rmin + 5), 1.0, 0.0))
        cols["div_rsi"] = np.where(np.isnan(rmax) | np.isnan(cmax), np.nan, div)

        # --- tendance
        hausse_m, baisse_m = h - _avant(h, 1), _avant(l, 1) - l
        dmp = np.where((hausse_m > baisse_m) & (hausse_m > 0), hausse_m, 0.0)
        dmm = np.where((baisse_m > hausse_m) & (baisse_m > 0), baisse_m, 0.0)
        dmp[0] = dmm[0] = np.nan
        dip, dim = 100 * _wilder(dmp, 14) / atr, 100 * _wilder(dmm, 14) / atr
        dx = 100 * np.abs(dip - dim) / (dip + dim)
        cols["adx"] = _wilder(np.where(np.isfinite(dx), dx, np.nan), 14)
        cols["di_ecart"] = dip - dim
        aroon = _vide(n)
        if n >= 26:
            fh, fl = _fenetre(h, 26), _fenetre(l, 26)
            aroon[25:] = 4 * (np.argmax(fh, axis=1) - np.argmin(fl, axis=1))  # (haut - bas) en % de 25 séances
        cols["aroon"] = aroon
        sar, sj = _sar(h, l)
        cols["sar_ecart"] = c / sar - 1
        cols["sar_jours"] = sj
        st, stj = _supertrend(h, l, c, _wilder(vrai, 10))
        cols["supertrend"] = c / st - 1
        cols["supertrend_jours"] = stj
        tenkan, kijun = (hh[9] + ll[9]) / 2, (hh[26] + ll[26]) / 2
        span_a, span_b = (tenkan + kijun) / 2, (hh[52] + ll[52]) / 2
        nuage_a, nuage_b = _avant(span_a, 26), _avant(span_b, 26)  # le nuage du jour a été tracé 26 séances plus tôt
        haut_n, bas_n = np.fmax(nuage_a, nuage_b), np.fmin(nuage_a, nuage_b)
        cols["ichi_tenkan"] = c / tenkan - 1
        cols["ichi_kijun"] = c / kijun - 1
        cols["ichi_tk"] = (tenkan - kijun) / c
        cols["ichi_nuage"] = np.where(c > haut_n, c / haut_n - 1, np.where(c < bas_n, c / bas_n - 1, 0.0))
        cols["ichi_nuage"][np.isnan(haut_n)] = np.nan
        cols["ichi_futur"] = (span_a - span_b) / c
        cols["ichi_chikou"] = c / _avant(c, 26) - 1
        cols["crois_mm"] = _depuis_croisement(_sma(c, 50), _sma(c, 200))
        ligne = _ema(c, 12) - _ema(c, 26)
        cols["crois_macd"] = _depuis_croisement(ligne, _ema(ligne, 9))
        ha_c = (o + h + l + c) / 4
        ha_o = np.empty(n); ha_o[0] = (o[0] + c[0]) / 2
        for i in range(1, n):
            ha_o[i] = (ha_o[i - 1] + ha_c[i - 1]) / 2 if ha_o[i - 1] == ha_o[i - 1] and ha_c[i - 1] == ha_c[i - 1] else (o[i] + c[i]) / 2
        cols["heikin"] = _serie_signe(ha_c - ha_o)
        lc = np.log(c)
        pente, r2, posi = _vide(n), _vide(n), _vide(n)
        if n >= 50:
            f = _fenetre(lc, 50)
            xs = np.arange(50) - 24.5
            sxx = (xs ** 2).sum()
            ym = f.mean(axis=1)
            b = (f * xs).sum(axis=1) / sxx
            resid = f - ym[:, None] - b[:, None] * xs
            sres = resid.std(axis=1)
            stot = f.std(axis=1)
            pente[49:] = b * 20
            r2[49:] = np.where(stot > 0, 1 - (sres / stot) ** 2, np.nan)
            posi[49:] = np.where(sres > 0, resid[:, -1] / sres, np.nan)
        cols["canal_pente"], cols["canal_r2"], cols["canal_pos"] = pente, r2, posi

        # --- volume
        vol20 = _somme(v, 20)
        obv = np.cumsum(np.sign(np.nan_to_num(dc)) * v)
        cols["obv_pente"] = np.where(vol20 > 0, (obv - _avant(obv, 20)) / vol20, np.nan)
        clv = np.where(h > l, ((c - l) - (h - c)) / (h - l), 0.0)
        ad = np.cumsum(clv * v)
        cols["ad_pente"] = np.where(vol20 > 0, (ad - _avant(ad, 20)) / vol20, np.nan)
        cols["chaikin"] = np.where(vmoy > 0, (_ema(ad, 3) - _ema(ad, 10)) / vmoy, np.nan)
        cols["cmf"] = np.where(vol20 > 0, _somme(clv * v, 20) / vol20, np.nan)
        pv = _somme(tp * v, 20)
        cols["vwap20"] = np.where(vol20 > 0, c / (pv / vol20) - 1, np.nan)
        cols["vol_hausse"] = np.where(vol20 > 0, _somme(np.where(dc > 0, v, 0.0), 20) / vol20, np.nan)
        cols["force13"] = _ema(np.where(np.isnan(dc), np.nan, dc * v), 13) / (c * vmoy)
        milieu = (h + l) / 2
        cols["eom"] = _sma((milieu - _avant(milieu, 1)) / c * ((h - l) / c) / np.where(vrel > 0, vrel, np.nan), 14) * 1e4
        haut_prec, bas_prec = _avant(hh[20], 1), _avant(ll[20], 1)
        cols["vol_cassure"] = np.where(c > haut_prec, vrel, np.where(c < bas_prec, -vrel, 0.0))
        cols["vol_cassure"][np.isnan(haut_prec)] = np.nan

        # --- chandeliers japonais
        rng = h - l
        corps = c - o
        rng_s = np.where(rng > 0, rng, np.nan)
        cols["corps"] = corps / rng_s
        cols["ombre_haute"] = (h - np.fmax(o, c)) / rng_s
        cols["ombre_basse"] = (np.fmin(o, c) - l) / rng_s
        cols["taille"] = rng / atr
        ac = np.abs(corps)
        tendance5 = c / _avant(c, 5) - 1
        cols["doji"] = (ac <= 0.1 * rng).astype(float)
        bas_ombre, haut_ombre = np.fmin(o, c) - l, h - np.fmax(o, c)
        forme_marteau = (bas_ombre >= 2 * ac) & (haut_ombre <= 0.3 * rng) & (rng > 0)
        forme_inv = (haut_ombre >= 2 * ac) & (bas_ombre <= 0.3 * rng) & (rng > 0)
        cols["marteau"] = np.where(forme_marteau, np.where(tendance5 < 0, 1.0, -1.0), 0.0)  # marteau après baisse, pendu après hausse
        cols["marteau_inv"] = np.where(forme_inv, np.where(tendance5 < 0, 1.0, -1.0), 0.0)  # marteau inversé, étoile filante
        o1, c1, h1, l1 = _avant(o, 1), _avant(c, 1), _avant(h, 1), _avant(l, 1)
        corps1 = c1 - o1
        cols["avalement"] = np.where((corps1 < 0) & (corps > 0) & (o <= c1) & (c >= o1), 1.0,
                                     np.where((corps1 > 0) & (corps < 0) & (o >= c1) & (c <= o1), -1.0, 0.0))
        dans = (np.fmax(o, c) < np.fmax(o1, c1)) & (np.fmin(o, c) > np.fmin(o1, c1)) & (np.abs(corps1) > 0.5 * atr)
        cols["harami"] = np.where(dans & (corps1 < 0) & (corps > 0), 1.0, np.where(dans & (corps1 > 0) & (corps < 0), -1.0, 0.0))
        o2, c2 = _avant(o, 2), _avant(c, 2)
        corps2 = c2 - o2
        petit1 = np.abs(corps1) < 0.3 * atr
        cols["etoile"] = np.where((corps2 < -0.6 * atr) & petit1 & (corps > 0.6 * atr) & (c > (o2 + c2) / 2), 1.0,
                                  np.where((corps2 > 0.6 * atr) & petit1 & (corps < -0.6 * atr) & (c < (o2 + c2) / 2), -1.0, 0.0))
        trois_h = (corps > 0) & (corps1 > 0) & (corps2 > 0) & (c > c1) & (c1 > c2) & (h - c < 0.25 * rng)
        trois_b = (corps < 0) & (corps1 < 0) & (corps2 < 0) & (c < c1) & (c1 < c2) & (c - l < 0.25 * rng)
        cols["soldats"] = np.where(trois_h, 1.0, np.where(trois_b, -1.0, 0.0))
        cols["marubozu"] = np.where((ac >= 0.95 * rng) & (rng > 0.5 * atr), np.sign(corps), 0.0)
        cols["penetrante"] = np.where((corps1 < -0.5 * atr) & (o < l1) & (c > (o1 + c1) / 2) & (c < o1), 1.0,
                                      np.where((corps1 > 0.5 * atr) & (o > h1) & (c < (o1 + c1) / 2) & (c > o1), -1.0, 0.0))
        cols["barre_incluse"] = ((h < h1) & (l > l1)).astype(float)
        cols["barre_englobante"] = ((h > h1) & (l < l1)).astype(float)
        signe = cols["marteau"] + cols["marteau_inv"] + cols["avalement"] + cols["harami"] + cols["etoile"] + cols["soldats"] + cols["marubozu"] + cols["penetrante"]
        cols["bougies_score"] = _somme(signe, 3)
        for k in ("doji", "marteau", "marteau_inv", "avalement", "harami", "etoile", "soldats", "marubozu", "penetrante", "barre_incluse", "barre_englobante"):
            cols[k][np.isnan(atr) | np.isnan(c)] = np.nan

        # --- supports, résistances et figures
        cols.update(_figures_sommets(h, l, c, vrel))
        cols["cassure20"] = c / _avant(hh[20], 1) - 1
        cols["cassure20_bas"] = c / _avant(ll[20], 1) - 1
        cols["cassure55"] = c / _avant(hh[55], 1) - 1
        cols["cassure55_bas"] = c / _avant(ll[55], 1) - 1
        cols["donchian55"] = (c - ll[55]) / (hh[55] - ll[55])
        cols["keltner"] = (c - _ema(c, 20)) / (2 * _wilder(vrai, 10))
        larg = _glisse(np.std, c, 20) * 4 / _sma(c, 20)
        cols["boll_largeur"] = larg
        comp = _vide(n)
        if n >= 126:
            f = _fenetre(larg, 126)
            comp[125:] = (f < f[:, -1:]).mean(axis=1)
            comp[125:][np.isnan(f).any(axis=1)] = np.nan
        cols["compression"] = comp
        fibo = (c - ll[126]) / (hh[126] - ll[126])
        cols["fibo_pos"] = fibo
        niveaux = np.array([0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0])
        cols["fibo_dist"] = np.min(np.abs(fibo[:, None] - niveaux[None, :]), axis=1)
        sens = _vide(n)
        if n >= 126:
            sens[125:] = np.where(np.argmax(_fenetre(h, 126), axis=1) > np.argmin(_fenetre(l, 126), axis=1), 1.0, -1.0)
        cols["fibo_sens"] = sens
        piv = (h1 + l1 + c1) / 3
        cols["pivot"] = (c - piv) / ((2 * piv - l1) - (2 * piv - h1))
        mat =_avant(c, 5) / _avant(c, 20) - 1  # le « mât » : hausse ou baisse des 15 séances précédentes
        cons = (_glisse(np.max, h, 5) - _glisse(np.min, l, 5)) / c
        cols["drapeau"] = np.where((np.abs(mat) >= 0.10) & (cons < 0.5 * np.abs(mat)) & (np.abs(c / _avant(c, 5) - 1) < 0.5 * np.abs(mat)),
                                   np.sign(mat), 0.0)
        cols["drapeau"][np.isnan(mat)] = np.nan
        cols["rectangle"] = (hh[20] - ll[20]) / atr
        cols["gaps_ouverts"] = _gaps_ouverts(h, l)
        pas = 10 ** np.floor(np.log10(np.where(c > 0, c, np.nan))) / 2
        cols["seuil_rond"] = (c - np.round(c / pas) * pas) / c
        for k, x in cols.items():
            cols[k] = np.where(np.isfinite(x), x, np.nan)
    return {k: cols[k] for k in NOMS}
