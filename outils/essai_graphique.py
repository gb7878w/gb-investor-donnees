"""Analyse graphique et technique : ses cinq familles de paramètres (outils/graphique.py) améliorent-elles le modèle ?

Base : le modèle de production (10 ans, tout Paris, groupes déjà retenus dans modele.GROUPES).
Variantes testées séparément : base + chaque famille (oscillateurs, tendance, volume, bougies, figures), puis base + toutes.
Même protocole que les étapes 1 à 3 : 6 périodes jamais vues, écart égal à l'horizon, test sur les valeurs du SBF 120 encore cotées.
Une variante n'est retenue pour une prévision que si elle fait mieux sur au moins 5 périodes sur 6 (exigence relevée car six essais)
ET réduit l'erreur (Brier). Ne publie rien.
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
    series_ctx, _, manq = contexte.charger()
    print("contexte manquant :", manq)
    M.ETENDU = True
    M.GRAPHIQUE = True
    X, noms, rang, ident, etiq, _ = M.construire(series, indices, secteurs, series_ctx)
    print(f"{X.shape[0]} lignes, {len(noms)} paramètres ({time.time() - t0:.0f} s)")
    _, inv = np.unique(ident, return_inverse=True)
    garde = ((rang + inv) % L.PAS) == 0
    sbf_mask = np.isin(ident, list(sbf))[garde]
    X, rang, etiq = X[garde].astype(np.float32), rang[garde], etiq[garde]
    for n in graphique.NOMS:
        x = X[:, noms.index(n)]
        ok = ~np.isnan(x)
        print(f"  {n} : renseigné {100 * ok.mean():.0f} %, non nul {100 * np.mean(x[ok] != 0) if ok.any() else 0:.0f} %")
    M.PARAMS["num_threads"] = 4
    rangs = np.unique(rang)
    debut = rangs[int(len(rangs) * 0.5)]
    blocs = np.array_split(rangs[rangs >= debut], 6)
    base_groupes = {k: set(v) for k, v in M.GROUPES.items()}
    familles = {f: {f} for f in graphique.GROUPES} | {"complet": set(graphique.GROUPES)}
    sortie, retenus, gains = {}, {}, {}
    for h in M.HORIZONS:
        cibles = M._cibles(etiq, h)
        for cible in M.CIBLES:
            y = cibles[cible]
            g0 = base_groupes.get((h, cible), set())
            M.GROUPES = {(h, cible): g0}; i0 = M.colonnes(noms, h, cible)
            variantes = {}
            for nom, g in familles.items():
                M.GROUPES = {(h, cible): g0 | g}; variantes[nom] = M.colonnes(noms, h, cible)
            res = {k: ([], [], 0) for k in ["base"] + list(variantes)}
            for bloc in blocs:
                tr = (rang <= bloc[0] - h) & ~np.isnan(y)
                te = np.isin(rang, bloc) & ~np.isnan(y) & sbf_mask
                if te.sum() < 300 or tr.sum() < 5000:
                    continue
                p0 = M._entrainer(X[tr][:, i0], y[tr]).predict(X[te][:, i0])
                a0 = M._auc(y[te], p0)
                res["base"][0].append(p0); res["base"][1].append(y[te])
                for k, idx in variantes.items():
                    m = M._entrainer(X[tr][:, idx], y[tr])
                    p = m.predict(X[te][:, idx])
                    pr, yr, g = res[k]
                    pr.append(p); yr.append(y[te]); res[k] = (pr, yr, g + int(M._auc(y[te], p) > a0))
                    if k == "complet":  # part du gain apportée par chaque paramètre graphique
                        gain = m.feature_importance(importance_type="gain").astype(float)
                        gain = gain / gain.sum() if gain.sum() > 0 else gain
                        for j, col in enumerate(idx):
                            if noms[col] in graphique.NOMS:
                                gains[noms[col]] = gains.get(noms[col], 0.0) + float(gain[j])
            if not res["base"][0]:
                continue
            n = len(res["base"][0])
            ligne = {k: dict(L.mesures(np.concatenate(v[1]), np.concatenate(v[0])), periodes_meilleur=f"{v[2]}/{n}") for k, v in res.items()}
            for k in variantes:
                if res[k][2] >= 5 and ligne[k]["brier"] < ligne["base"]["brier"]:
                    retenus.setdefault(f"{h}/{cible}", []).append(k)
            sortie[f"{h}/{cible}"] = ligne
            print(f"horizon {h} {cible} : " + " | ".join(f"{k} AUC {m['auc']} Brier {m['brier']} ({m['periodes_meilleur']})" for k, m in ligne.items()), flush=True)
    total = sum(gains.values()) or 1.0
    print("POIDS (part du gain des paramètres graphiques dans les modèles « complet ») :")
    for k, v in sorted(gains.items(), key=lambda kv: -kv[1])[:30]:
        print(f"  {k} : {100 * v / total:.1f} %")
    print("RETENUS", json.dumps(retenus))
    print("RÉSUMÉ", json.dumps(sortie), f"durée {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
