"""Étape 1 : les paramètres tirés des cours (momentum long, volatilité, illiquidité, bêta, régime) améliorent-ils le modèle ?

Même protocole que l'essai précédent : 6 blocs de test jamais vus, écart égal à l'horizon, apprentissage sur tout l'historique avant le bloc.
  C : paramètres actuels ; F : paramètres actuels + 18 nouveaux (un seul groupe testé, donc une seule hypothèse).
Mesures sur les valeurs du SBF 120 encore cotées, puis sur tout Paris. Combien de blocs sur 6 en faveur de F, et poids des nouveaux paramètres.
Ne publie rien.
"""
import os, sys, json, base64, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modele as M
import contexte
import essai_long as L


def main():
    cle = base64.b64decode(os.environ.get("CLE_DONNEES", ""))
    if len(cle) != 32:
        sys.exit("CLE_DONNEES absente ou invalide.")
    t0 = time.time()
    series, indices, secteurs, sbf = L.charger(cle)
    series_ctx, _, _ = contexte.charger()
    M.ETENDU = False
    _, noms_c, _, _, _, _ = M.construire({k: series[k] for k in list(series)[:30]}, indices, secteurs, series_ctx)
    M.ETENDU = True
    X, noms, rang, ident, etiq, _ = M.construire(series, indices, secteurs, series_ctx)
    nouveaux = [n for n in noms if n not in noms_c]
    print(f"{X.shape[0]} lignes, {len(noms)} paramètres dont {len(nouveaux)} nouveaux : {nouveaux} ({time.time() - t0:.0f} s)")
    idx_c = [noms.index(n) for n in noms_c]
    uniques, inv = np.unique(ident, return_inverse=True)
    garde = ((rang + inv) % L.PAS) == 0
    sbf_mask = np.isin(ident, list(sbf))[garde]
    X, rang, etiq = X[garde].astype(np.float32), rang[garde], etiq[garde]
    M.PARAMS["num_threads"] = 4
    rangs = np.unique(rang)
    debut = rangs[int(len(rangs) * 0.5)]
    blocs = np.array_split(rangs[rangs >= debut], 6)
    sortie, poids = {}, np.zeros(len(noms))
    for h in M.HORIZONS:
        cibles = M._cibles(etiq, h)
        for cible in M.CIBLES:
            y = cibles[cible]
            res = {k: ([], []) for k in ("C", "F", "C_tout", "F_tout")}
            blocs_f = 0; blocs_n = 0
            for bloc in blocs:
                tr = (rang <= bloc[0] - h) & ~np.isnan(y)
                te = np.isin(rang, bloc) & ~np.isnan(y)
                te_s = te & sbf_mask
                if te_s.sum() < 300 or tr.sum() < 5000 or len(np.unique(y[tr])) < 2:
                    continue
                mC = M._entrainer(X[tr][:, idx_c], y[tr]); mF = M._entrainer(X[tr], y[tr])
                pC, pF = mC.predict(X[te_s][:, idx_c]), mF.predict(X[te_s])
                res["C"][0].append(pC); res["C"][1].append(y[te_s]); res["F"][0].append(pF); res["F"][1].append(y[te_s])
                res["C_tout"][0].append(mC.predict(X[te][:, idx_c])); res["C_tout"][1].append(y[te])
                res["F_tout"][0].append(mF.predict(X[te])); res["F_tout"][1].append(y[te])
                blocs_n += 1; blocs_f += int(M._auc(y[te_s], pF) > M._auc(y[te_s], pC))
                g = mF.feature_importance(importance_type="gain").astype(float); poids += g / max(g.sum(), 1)
            if not res["C"][0]:
                continue
            ligne = {k: L.mesures(np.concatenate(v[1]), np.concatenate(v[0])) for k, v in res.items()}
            ligne["blocs_F_meilleur"] = f"{blocs_f}/{blocs_n}"
            sortie[f"{h}/{cible}"] = ligne
            print(f"horizon {h} {cible} : SBF C {ligne['C']['auc']} F {ligne['F']['auc']} (Brier {ligne['C']['brier']} → {ligne['F']['brier']}, base {ligne['C']['brier_base']}) | tout Paris C {ligne['C_tout']['auc']} F {ligne['F_tout']['auc']} | blocs F meilleur {blocs_f}/{blocs_n}")
    poids = poids / max(poids.sum(), 1)
    top = sorted(zip(noms, poids), key=lambda x: -x[1])[:15]
    print("POIDS", json.dumps([(n, round(float(p) * 100, 1)) for n, p in top]))
    print("RÉSUMÉ", json.dumps(sortie), f"durée {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
