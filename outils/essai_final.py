"""Essai final avant mise en production : le modèle tel qu'il serait publié bat-il le modèle publié aujourd'hui ?

  B : modèle actuel (2 ans, SBF 120, paramètres de base, toutes les séances) ;
  P : candidat (10 ans, tout Paris et radiées, une séance sur sept, groupes de paramètres retenus par prévision dans modele.GROUPES).
Mêmes 6 périodes jamais vues, écart égal à l'horizon, mêmes lignes de test (toutes les séances des valeurs du SBF 120 encore cotées).
Règle : P est retenu pour une prévision s'il fait mieux sur la majorité des périodes ET a une erreur de Brier plus faible ;
sinon cette prévision reste apprise sur 2 ans (modele.BASE_COURTE). Ne publie rien.
"""
import os, sys, json, base64, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modele as M
import contexte
import essai_long as L
import graphique


def main():
    cle = base64.b64decode(os.environ.get("CLE_DONNEES", ""))
    if len(cle) != 32:
        sys.exit("CLE_DONNEES absente ou invalide.")
    t0 = time.time()
    series, indices, secteurs, sbf = L.charger(cle)
    series_ctx, _, _ = contexte.charger()
    if any("amf" in g for g in M.GROUPES.values()):
        import amf
        couverture = json.loads(L.lire_clair("couverture.json"))["couverture"]
        isin_de = {c["id"]: c.get("isin") for c in couverture}
        isins = sorted({i for k, i in isin_de.items() if i and k in series})
        M.EXTERNES = amf.Caracteristiques(amf.positions_courtes(), {i: amf.communiques(i) for i in isins}, isin_de.get)
    M.ETENDU = True
    M.GRAPHIQUE = any(g & set(graphique.GROUPES) for g in M.GROUPES.values())
    X, noms, rang, ident, etiq, _ = M.construire(series, indices, secteurs, series_ctx)
    X = X.astype(np.float32)
    print(f"{X.shape[0]} lignes, {len(noms)} paramètres ({time.time() - t0:.0f} s) ; groupes retenus : {M.GROUPES}")
    _, inv = np.unique(ident, return_inverse=True)
    garde = ((rang + inv) % L.PAS) == 0
    sbf_mask = np.isin(ident, list(sbf))
    groupes = M.GROUPES
    M.GROUPES = {}
    idx_base = M.colonnes(noms, 5, "mieux")
    M.GROUPES = groupes
    M.PARAMS["num_threads"] = 4
    rangs = np.unique(rang)
    debut = rangs[int(len(rangs) * 0.5)]
    blocs = np.array_split(rangs[rangs >= debut], 6)
    sortie, courtes = {}, []
    for h in M.HORIZONS:
        cibles = M._cibles(etiq, h)
        for cible in M.CIBLES:
            y = cibles[cible]
            idx_p = M.colonnes(noms, h, cible)
            pB, pP, yy, gagnes, n = [], [], [], 0, 0
            for bloc in blocs:
                te = np.isin(rang, bloc) & ~np.isnan(y) & sbf_mask
                tr_p = (rang <= bloc[0] - h) & ~np.isnan(y) & garde
                tr_b = (rang <= bloc[0] - h) & (rang > bloc[0] - h - L.FENETRE_B) & ~np.isnan(y) & sbf_mask
                if te.sum() < 300 or tr_b.sum() < 2000 or len(np.unique(y[tr_b])) < 2:
                    continue
                b = M._entrainer(X[tr_b][:, idx_base], y[tr_b]).predict(X[te][:, idx_base])
                p = M._entrainer(X[tr_p][:, idx_p], y[tr_p]).predict(X[te][:, idx_p])
                pB.append(b); pP.append(p); yy.append(y[te])
                n += 1; gagnes += int(M._auc(y[te], p) > M._auc(y[te], b))
            if not n:
                continue
            Y = np.concatenate(yy)
            mB, mP = L.mesures(Y, np.concatenate(pB)), L.mesures(Y, np.concatenate(pP))
            retenu = gagnes * 2 > n and mP["brier"] < mB["brier"]
            if not retenu:
                courtes.append((h, cible))
            sortie[f"{h}/{cible}"] = dict(B=mB, P=mP, periodes_P_meilleur=f"{gagnes}/{n}", retenu=retenu)
            print(f"horizon {h} {cible} : B AUC {mB['auc']} Brier {mB['brier']} | P AUC {mP['auc']} Brier {mP['brier']} | base {mB['brier_base']} | P meilleur {gagnes}/{n} → {'10 ans' if retenu else '2 ans'}")
    print("BASE_COURTE =", sorted(courtes))
    print("RÉSUMÉ", json.dumps(sortie), f"durée {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
