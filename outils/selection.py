"""Page « Sélection » de GB Investor : une valeur est mise en avant quand plusieurs paramètres sont favorables ensemble.

Six paramètres, chacun jugé favorable (+1), défavorable (−1) ou incertain (0) :
  modèle (prévision « mieux que le CAC 40 à 1 mois », rang parmi les valeurs du jour), tendance, volume, force relative,
  contexte de marché, liquidité.
Les critères sont testés sur l'historique : chaque semaine, on repère les valeurs qui les remplissent, on les « achète » à la clôture
de la séance suivante (délai), on les « revend » 21 séances plus tard, frais et écart acheteur-vendeur déduits, puis on compare au CAC 40
et à l'ensemble des valeurs liquides. L'essai ne porte que sur les périodes jamais vues par le modèle (même découpage que sa validation).
Rien n'est réglé d'après le résultat : les variantes sont toutes publiées, la retenue est fixée à l'avance (VARIANTE_RETENUE).
"""
import math
import numpy as np

HORIZON = 21
SEMAINE = 5                  # séances : une cohorte par semaine
FRAIS_ALLER_RETOUR = 0.004   # 0,4 % : courtage et taxes
ECART_PEU_LIQUIDE = 0.003    # 0,3 % de plus quand la valeur échange moins d'un million d'euros par jour
LIQ_FORTE = 6.0              # log10 des euros échangés par jour (1 000 000)
LIQ_MOYENNE = math.log10(200_000)
LIQ_FAIBLE = math.log10(50_000)
PCT_FAVORABLE, PCT_DEFAVORABLE = 0.70, 0.30
VARIANTE_RETENUE = {"min_favorables": 4, "max_defavorables": 0, "contexte": False}
PARAMETRES = ["modele", "tendance", "volume", "relative", "contexte", "liquidite"]
NOMS = {"modele": "Prévisions du modèle", "tendance": "Tendance", "volume": "Volume", "relative": "Force relative", "contexte": "Contexte de marché", "liquidite": "Liquidité"}
REGLES = {
    "modele": "Favorable si la valeur est dans les 30 % les mieux classées par le modèle pour « mieux que le CAC 40 à 1 mois » ; défavorable dans les 30 % les moins bien classées.",
    "tendance": "Favorable si le cours est au-dessus de ses moyennes de 50 et 200 séances et que la moyenne de 50 monte ; défavorable s'il est en dessous des deux.",
    "volume": "Favorable si le volume moyen augmente et que la valeur a monté sur 1 mois ; défavorable si le volume augmente alors que la valeur a baissé de plus de 3 % (des vendeurs pressés).",
    "relative": "Favorable si la valeur bat le CAC 40 de plus de 3 points sur 3 mois et fait mieux que lui sur 1 mois ; défavorable dans le cas inverse.",
    "contexte": "Favorable si le CAC 40 est au-dessus de sa moyenne de 200 séances et la volatilité (VIX) sous 22 ; défavorable s'il est en dessous ou si le VIX dépasse 30.",
    "liquidite": "Favorable au-dessus d'un million d'euros échangés par jour ; incertain entre 200 000 et un million ; défavorable en dessous ou si la valeur varie de plus de 90 % par an (données insuffisantes).",
}


def _col(M, noms, nom):
    return M[:, noms.index(nom)].astype(float) if nom in noms else np.full(len(M), np.nan)


def rang_centile(p, groupe):
    """Rang de chaque prévision parmi celles du même groupe (0 = la plus basse, 1 = la plus haute)."""
    sortie = np.full(len(p), np.nan)
    ordre = np.lexsort((p, groupe))
    g_tri = groupe[ordre]
    debuts = np.r_[0, np.flatnonzero(np.diff(g_tri)) + 1, len(p)]
    for a, b in zip(debuts[:-1], debuts[1:]):
        n = b - a
        sortie[ordre[a:b]] = np.arange(n) / max(n - 1, 1)
    return sortie


def etats(M, noms, centile):
    """États (−1, 0, +1) des six paramètres pour chaque ligne de M ; centile = rang du modèle (NaN si inconnu)."""
    c = lambda n: _col(M, noms, n)
    with np.errstate(invalid="ignore"):
        s = {}
        s["modele"] = np.where(centile >= PCT_FAVORABLE, 1, np.where(centile <= PCT_DEFAVORABLE, -1, 0))
        fav = (c("d_mm50") > 0) & (c("d_mm200") > 0) & (c("pente50") > 0)
        dfv = (c("d_mm50") < 0) & (c("d_mm200") < 0)
        s["tendance"] = np.where(fav, 1, np.where(dfv, -1, 0))
        vol_monte = c("voltrend") >= 1.05
        s["volume"] = np.where(vol_monte & (c("ret21") > 0), 1, np.where(vol_monte & (c("ret21") < -0.03), -1, 0))
        s["relative"] = np.where((c("rel63") > 0.03) & (c("rel21") > 0), 1, np.where((c("rel63") < -0.03) & (c("rel21") < 0), -1, 0))
        s["contexte"] = np.where((c("cac_d200") > 0) & (c("vix") < 22), 1, np.where((c("cac_d200") < 0) | (c("vix") > 30), -1, 0))
        liq, v63 = c("liq_eur"), c("vol63")
        s["liquidite"] = np.where((liq < LIQ_MOYENNE) | (v63 > 0.9), -1, np.where(liq >= LIQ_FORTE, 1, 0))
    return {k: np.nan_to_num(v).astype(int) for k, v in s.items()}


def retenues(s, variante):
    """Valeurs retenues : assez de paramètres favorables, pas trop de défavorables, jamais une valeur trop peu liquide."""
    nf = sum((v == 1).astype(int) for v in s.values())
    nd = sum((v == -1).astype(int) for v in s.values())
    ok = (nf >= variante["min_favorables"]) & (nd <= variante["max_defavorables"]) & (s["liquidite"] >= 0)
    if variante.get("contexte"):
        ok &= s["contexte"] >= 0
    return ok, nf, nd


def phrase(param, etat, M, noms, i, centile):
    """Une phrase claire, avec les valeurs, pour l'écran de la valeur."""
    def c(n):
        v = float(M[i, noms.index(n)]) if n in noms else float("nan")
        return None if np.isnan(v) else v
    pc = lambda v: "n.d." if v is None else f"{v * 100:+.1f} %".replace(".", ",")
    if param == "modele":
        if np.isnan(centile[i]):
            return "Pas de prévision pour cette valeur"
        r = round((1 - centile[i]) * 100)
        return ("Parmi les mieux classées par le modèle" if etat > 0 else "Parmi les moins bien classées par le modèle" if etat < 0 else "Classement du modèle dans la moyenne") + f" (rang {r} % du haut)"
    if param == "tendance":
        return (f"Au-dessus des moyennes 50 et 200 séances ({pc(c('d_mm50'))} et {pc(c('d_mm200'))}), la moyenne 50 monte" if etat > 0
                else f"Sous les moyennes 50 et 200 séances ({pc(c('d_mm50'))} et {pc(c('d_mm200'))})" if etat < 0
                else f"Tendance partagée : {pc(c('d_mm50'))} de la moyenne 50, {pc(c('d_mm200'))} de la moyenne 200")
    if param == "volume":
        return ("Volume en hausse et cours en progression sur 1 mois" if etat > 0 else "Volume en hausse alors que le cours baisse (" + pc(c("ret21")) + " sur 1 mois)" if etat < 0
                else "Volume sans signal net")
    if param == "relative":
        return (f"Bat le CAC 40 : {pc(c('rel63'))} sur 3 mois, {pc(c('rel21'))} sur 1 mois" if etat > 0 else f"Fait moins bien que le CAC 40 : {pc(c('rel63'))} sur 3 mois, {pc(c('rel21'))} sur 1 mois" if etat < 0
                else f"Proche du CAC 40 ({pc(c('rel63'))} sur 3 mois)")
    if param == "contexte":
        v = c("vix")
        vx = "n.d." if v is None else f"{v:.0f}"
        return (f"Marché porteur : CAC 40 au-dessus de sa moyenne 200 séances, volatilité {vx}" if etat > 0 else f"Marché fragile : CAC 40 sous sa moyenne 200 séances ou volatilité forte ({vx})" if etat < 0
                else f"Marché indécis, volatilité {vx}")
    liq, v63 = c("liq_eur"), c("vol63")
    eur = "n.d." if liq is None else f"{10 ** liq:,.0f}".replace(",", " ")
    return (f"Très échangée : environ {eur} € par jour" if etat > 0 else f"Données insuffisantes : environ {eur} € par jour" + (", cours très agité" if v63 is not None and v63 > 0.9 else "") if etat < 0
            else f"Assez échangée : environ {eur} € par jour")


def essai(X, noms, rang, ident, etiq, p_oos, series, cac, dates):
    """Rejeu hebdomadaire sur les lignes jamais vues par le modèle. Renvoie le rapport (toutes variantes) ou None si impossible."""
    if p_oos is None or "liq_eur" not in noms or "voltrend" not in noms:
        return None
    rang_oos, ident_oos, p = p_oos["rang"], p_oos["ident"], p_oos["p"]
    # Les lignes jamais vues portent la prévision ; on les retrouve par (valeur, séance).
    cle = {(a, int(b)): k for k, (a, b) in enumerate(zip(ident, rang))}
    lignes = np.array([cle.get((a, int(b)), -1) for a, b in zip(ident_oos, rang_oos)])
    bon = lignes >= 0
    lignes, p, rg, idn = lignes[bon], p[bon], rang_oos[bon], ident_oos[bon]
    M = X[lignes]
    semaine = (rg // SEMAINE).astype(int)
    centile = rang_centile(p, semaine)
    # Rendement net, entrée à la clôture de la séance suivante, sortie 21 séances plus tard.
    cac_d = np.array(cac["d"]); cac_c = np.array(cac["c"], dtype=float)
    entree = np.full(len(lignes), np.nan); sortie = np.full(len(lignes), np.nan); cac_r = np.full(len(lignes), np.nan)
    date_ligne = np.array([dates[int(r)] for r in rg])
    for isin in np.unique(idn):
        m = np.flatnonzero(idn == isin)
        s = series[isin]; d = np.array(s["d"]); c = np.array(s["c"], dtype=float)
        k = np.searchsorted(d, date_ligne[m]) + 1
        k2 = k + HORIZON
        ok = k2 < len(c)
        entree[m[ok]] = c[k[ok]]; sortie[m[ok]] = c[k2[ok]]
        a = np.searchsorted(cac_d, d[k[ok]]); b = np.searchsorted(cac_d, d[k2[ok]])
        bonne = (a < len(cac_d)) & (b < len(cac_d))
        idx = m[ok][bonne]
        cac_r[idx] = cac_c[b[bonne]] / cac_c[a[bonne]] - 1
    brut = sortie / entree - 1
    liq = _col(M, noms, "liq_eur")
    net = brut - FRAIS_ALLER_RETOUR - np.where(liq < LIQ_FORTE, ECART_PEU_LIQUIDE, 0.0)
    valide = ~np.isnan(net) & ~np.isnan(cac_r) & (liq >= LIQ_MOYENNE)   # univers de l'essai : valeurs assez liquides
    s = etats(M, noms, centile)
    exces = net - cac_r
    annee = np.array([d[:4] for d in date_ligne])
    univers_moy = {int(w): float(np.nanmean(exces[valide & (semaine == w)])) for w in np.unique(semaine[valide])}

    def resumer(masque):
        masque = masque & valide
        if masque.sum() < 30:
            return {"cas": int(masque.sum()), "semaines": 0}
        par = {}
        for w, e, u in zip(semaine[masque], exces[masque], np.vectorize(lambda w: univers_moy.get(int(w), np.nan))(semaine[masque])):
            par.setdefault(int(w), []).append((e, e - u))
        cohortes = np.array([np.mean([x[0] for x in v]) for v in par.values()])
        rel = np.array([np.mean([x[1] for x in v]) for v in par.values()])
        n_eff = max(len(cohortes) / (HORIZON / SEMAINE), 1.0)   # les cohortes voisines se chevauchent
        sd = float(np.std(cohortes, ddof=1)) if len(cohortes) > 2 else float("nan")
        t = float(np.mean(cohortes) / (sd / math.sqrt(n_eff))) if sd and not math.isnan(sd) else float("nan")
        par_an = {}
        for a in np.unique(annee[masque]):
            m = masque & (annee == a)
            par_an[str(a)] = round(float(np.mean(exces[m])) * 100, 2)
        return {"cas": int(masque.sum()), "semaines": len(cohortes), "ecart_cac_pct": round(float(np.mean(exces[masque])) * 100, 2),
                "ecart_univers_pct": round(float(np.mean(rel)) * 100, 2), "rendement_net_pct": round(float(np.mean(net[masque])) * 100, 2),
                "part_gagnantes": round(float(np.mean(net[masque] > 0)), 3), "part_bat_cac": round(float(np.mean(exces[masque] > 0)), 3),
                "t": None if math.isnan(t) else round(t, 2), "par_annee": par_an,
                "par_semaine": round(masque.sum() / max(len(univers_moy), 1), 2),
                "periodes_positives": f"{int((np.array(list(par_an.values())) > 0).sum())}/{len(par_an)}"}

    variantes = []
    for k in (3, 4, 5):
        for d in (0, 1):
            for ctx in (False, True):
                v = {"min_favorables": k, "max_defavorables": d, "contexte": ctx}
                ok, _, _ = retenues(s, v)
                variantes.append(dict(v, **resumer(ok)))
    ref_tous = resumer(np.ones(len(lignes), dtype=bool))
    ref_modele = resumer(centile >= PCT_FAVORABLE)
    return {"periode": [str(date_ligne.min()), str(date_ligne.max())], "horizon": HORIZON, "frais": FRAIS_ALLER_RETOUR,
            "ecart_peu_liquide": ECART_PEU_LIQUIDE, "variantes": variantes, "reference_toutes_valeurs": ref_tous, "reference_modele_seul": ref_modele}


def verdict(rapport):
    """Verdict écrit d'avance : la variante retenue n'est « validée » que si son avantage est net, durable et mesuré sur assez de cas."""
    if rapport is None:
        return {"valide": False, "texte": "Essai impossible : critères non validés."}
    v = next((x for x in rapport["variantes"] if all(x[k] == VARIANTE_RETENUE[k] for k in VARIANTE_RETENUE)), None)
    if v is None or v.get("semaines", 0) < 40:
        return {"valide": False, "texte": "Trop peu de cas pour juger les critères."}
    pos, tot = (int(x) for x in v["periodes_positives"].split("/"))
    ok = v["ecart_univers_pct"] > 0 and v["ecart_cac_pct"] > 0 and pos / tot >= 0.6 and (v["t"] or 0) >= 1.5
    if ok:
        return {"valide": True, "texte": f"Sur l'historique jamais vu par le modèle, les valeurs retenues ont fait en moyenne {v['ecart_cac_pct']:+.1f} point(s) de mieux que le CAC 40 à 1 mois, frais déduits ({v['periodes_positives']} années positives)."}
    return {"valide": False, "texte": f"Avantage non démontré : écart moyen au CAC 40 {v['ecart_cac_pct']:+.1f} point(s) à 1 mois, frais déduits ({v['periodes_positives']} années positives). Les critères restent affichés mais ne prouvent rien."}


def aujourdhui(derniers, noms, prevision, series, secteurs=None):
    """Évaluation du jour pour chaque valeur cotée suivie : états, phrases, nombre de paramètres favorables, rang."""
    isins = sorted(i for i in derniers if i in series)
    M = np.vstack([derniers[i][0] for i in isins])
    p = np.array([prevision.get(i, {}).get("21", {}).get("mieux", {}).get("brut", np.nan) for i in isins], dtype=float)
    centile = np.full(len(isins), np.nan)
    ok = ~np.isnan(p)
    if ok.sum() > 10:
        centile[ok] = rang_centile(p[ok], np.zeros(ok.sum(), dtype=int))
    s = etats(M, noms, centile)
    retenue, nf, nd = retenues(s, VARIANTE_RETENUE)
    score = nf - nd + np.nan_to_num(centile, nan=0.5) * 0.5
    ordre = np.argsort(-score)
    rang_valeur = {isins[j]: r + 1 for r, j in enumerate(ordre)}
    sortie = {}
    for j, isin in enumerate(isins):
        sortie[isin] = {"s": [int(s[k][j]) for k in PARAMETRES], "t": [phrase(k, int(s[k][j]), M, noms, j, centile) for k in PARAMETRES],
                        "nf": int(nf[j]), "nd": int(nd[j]), "sel": bool(retenue[j]), "rang": rang_valeur[isin], "score": round(float(score[j]), 3)}
    return sortie


def construire(rapport, derniers, noms, prevision, series, genere, derniere):
    """Contenu de selection.bin (chiffré comme le reste)."""
    v = verdict(rapport)
    return {"version": 1, "genere": genere, "derniere": derniere, "horizon": HORIZON,
            "parametres": [{"id": k, "nom": NOMS[k], "regle": REGLES[k]} for k in PARAMETRES],
            "retenue": VARIANTE_RETENUE, "validation": v, "essai": rapport,
            "valeurs": aujourdhui(derniers, noms, prevision, series)}
