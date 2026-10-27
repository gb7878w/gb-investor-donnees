"""Essai P6 bis : classements du jour (chaque titre comparé aux autres du même jour) et cibles relatives.

Variantes évaluées sur les mêmes périodes jamais vues que l'essai précédent, lignes de test = valeurs du SBF 120 encore cotées :
  C : paramètres bruts, apprentissage sur tout l'historique (rappel du précédent essai) ;
  D : paramètres bruts + rang du jour (0 à 1) de 12 paramètres parmi tout Paris ;
  E : comme D mais appris sur « fait mieux que la médiane du jour » (cible relative), jugé sur « mieux que le CAC 40 ».
Ne publie rien : affiche seulement des mesures.
"""
import os, sys, json, base64, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modele as M
import contexte
import essai_long as L

A_CLASSER = ["ret5", "ret21", "ret63", "rsi", "d_mm50", "d_mm200", "volrel", "atr", "d_haut", "d_bas", "macd", "boll"]


def ajouter_rangs(X, noms, rang):
    idx = [noms.index(n) for n in A_CLASSER if n in noms]
    df = pd.DataFrame(X[:, idx], columns=[noms[i] for i in idx])
    df["rang"] = rang
    r = df.groupby("rang").rank(pct=True).to_numpy(dtype=np.float32)
    return np.hstack([X.astype(np.float32), r]), noms + ["rg_" + noms[i] for i in idx]


def cible_mediane(etiq, rang):
    sortie = []
    for k in range(len(M.HORIZONS)):
        fut = pd.Series(etiq[:, k])
        med = fut.groupby(rang).transform("median")
        lab = np.where(np.isnan(fut.to_numpy()), np.nan, (fut.to_numpy() > med.to_numpy()).astype(float))
        sortie.append(lab)
    return sortie


def comparer(X, Xd, rang, etiq, lab_med, sbf_mask, journal=print, blocs_n=6):
    rangs = np.unique(rang)
    debut = rangs[int(len(rangs) * 0.5)]
    blocs = np.array_split(rangs[rangs >= debut], blocs_n)
    sortie = {}
    for ih, h in enumerate(M.HORIZONS):
        cibles = M._cibles(etiq, h)
        for cible in M.CIBLES:
            y = cibles[cible]
            variantes = ["C", "D"] + (["E"] if cible == "mieux" else [])
            res = {v: ([], []) for v in variantes}
            for bloc in blocs:
                tr = (rang <= bloc[0] - h) & ~np.isnan(y)
                te_s = np.isin(rang, bloc) & ~np.isnan(y) & sbf_mask
                if te_s.sum() < 300 or tr.sum() < 5000 or len(np.unique(y[tr])) < 2:
                    continue
                for v in variantes:
                    Xv = X if v == "C" else Xd
                    yv = y
                    trv = tr
                    if v == "E":
                        yv = lab_med[ih]
                        trv = (rang <= bloc[0] - h) & ~np.isnan(yv)
                    p = M._entrainer(Xv[trv], yv[trv]).predict(Xv[te_s])
                    res[v][0].append(p); res[v][1].append(y[te_s])
            if not res["C"][0]:
                continue
            ligne = {v: L.mesures(np.concatenate(r[1]), np.concatenate(r[0])) for v, r in res.items()}
            sortie[f"{h}/{cible}"] = ligne
            journal(f"horizon {h} {cible} : " + " | ".join(f"{v} AUC {m['auc']} Brier {m['brier']}" for v, m in ligne.items()) + f" | base {ligne['C']['brier_base']}")
    return sortie


def main():
    cle = base64.b64decode(os.environ.get("CLE_DONNEES", ""))
    if len(cle) != 32:
        sys.exit("CLE_DONNEES absente ou invalide.")
    t0 = time.time()
    series, indices, secteurs, sbf = L.charger(cle)
    series_ctx, _, manq = contexte.charger()
    X, noms, rang, ident, etiq, _ = M.construire(series, indices, secteurs, series_ctx)
    print(f"{X.shape[0]} lignes construites en {time.time() - t0:.0f} s")
    Xd, noms_d = ajouter_rangs(X, noms, rang)
    lab_med = cible_mediane(etiq, rang)
    uniques, inv = np.unique(ident, return_inverse=True)
    garde = ((rang + inv) % L.PAS) == 0
    sbf_mask = np.isin(ident, list(sbf))[garde]
    X, Xd, rang, etiq = X[garde].astype(np.float32), Xd[garde], rang[garde], etiq[garde]
    lab_med = [l[garde] for l in lab_med]
    print(f"{X.shape[0]} lignes après échantillonnage, {len(noms_d)} paramètres avec rangs")
    M.PARAMS["num_threads"] = 4
    sortie = comparer(X, Xd, rang, etiq, lab_med, sbf_mask)
    print("RÉSUMÉ", json.dumps(sortie), f"durée {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
