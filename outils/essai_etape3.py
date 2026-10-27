"""Étape 3 : marchés (Tokyo du jour, Nasdaq, cuivre, gaz, échéances d'options) et attention du public (Wikipédia) améliorent-ils le modèle ?

Base : le candidat de production (10 ans, tout Paris, groupes déjà retenus dans modele.GROUPES).
Deux groupes testés séparément (deux hypothèses) : base + « marches », base + « attention ».
Même protocole : 6 périodes jamais vues, écart égal à l'horizon, test sur les valeurs du SBF 120 encore cotées.
Un groupe n'est retenu pour une prévision que s'il fait mieux sur au moins 5 périodes sur 6 (exigence relevée car plusieurs essais) ET réduit l'erreur.
Ne publie rien.
"""
import os, sys, json, base64, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modele as M
import contexte
import essai_long as L
import externes


def main():
    cle = base64.b64decode(os.environ.get("CLE_DONNEES", ""))
    if len(cle) != 32:
        sys.exit("CLE_DONNEES absente ou invalide.")
    t0 = time.time()
    series, indices, secteurs, sbf = L.charger(cle)
    series_ctx, _, manq = contexte.charger()
    print("contexte manquant :", manq)
    couverture = json.loads(L.lire_clair("couverture.json"))["couverture"]
    isin_de = {c["id"]: c.get("isin") for c in couverture}
    isins = sorted({i for k, i in isin_de.items() if i and k in series})
    articles = externes.articles_wikipedia(isins)
    print(f"Wikipédia : {len(articles)} articles trouvés pour {len(isins)} ISIN ({time.time() - t0:.0f} s)")
    vues, echecs = {}, 0
    for n, (isin, (langue, titre)) in enumerate(articles.items()):
        v = externes.consultations(langue, titre)
        echecs += v is None
        vues[isin] = v or {}
        time.sleep(0.05)
    print(f"consultations : {sum(1 for v in vues.values() if v)} séries, {echecs} échecs ({time.time() - t0:.0f} s)")
    M.EXTERNES = externes.Ensemble(externes.Marches(series_ctx), externes.Attention(vues, isin_de.get))
    M.ETENDU = True
    X, noms, rang, ident, etiq, _ = M.construire(series, indices, secteurs, series_ctx)
    print(f"{X.shape[0]} lignes, {len(noms)} paramètres ({time.time() - t0:.0f} s)")
    for n in M.NOMS_MARCHES + M.NOMS_ATTENTION:
        j = noms.index(n); print(f"  {n} : renseigné {100 * np.mean(~np.isnan(X[:, j])):.0f} %")
    _, inv = np.unique(ident, return_inverse=True)
    garde = ((rang + inv) % L.PAS) == 0
    sbf_mask = np.isin(ident, list(sbf))[garde]
    X, rang, etiq = X[garde].astype(np.float32), rang[garde], etiq[garde]
    M.PARAMS["num_threads"] = 4
    rangs = np.unique(rang)
    debut = rangs[int(len(rangs) * 0.5)]
    blocs = np.array_split(rangs[rangs >= debut], 6)
    base_groupes = {k: set(v) for k, v in M.GROUPES.items()}
    sortie, retenus = {}, {}
    for h in M.HORIZONS:
        cibles = M._cibles(etiq, h)
        for cible in M.CIBLES:
            y = cibles[cible]
            g0 = base_groupes.get((h, cible), set())
            M.GROUPES = {(h, cible): g0}; i0 = M.colonnes(noms, h, cible)
            variantes = {}
            for groupe in ("marches", "attention"):
                M.GROUPES = {(h, cible): g0 | {groupe}}; variantes[groupe] = M.colonnes(noms, h, cible)
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
                    p = M._entrainer(X[tr][:, idx], y[tr]).predict(X[te][:, idx])
                    pr, yr, g = res[k]
                    pr.append(p); yr.append(y[te]); res[k] = (pr, yr, g + int(M._auc(y[te], p) > a0))
            if not res["base"][0]:
                continue
            n = len(res["base"][0])
            ligne = {k: dict(L.mesures(np.concatenate(v[1]), np.concatenate(v[0])), periodes_meilleur=f"{v[2]}/{n}") for k, v in res.items()}
            for k in variantes:
                if res[k][2] >= 5 and ligne[k]["brier"] < ligne["base"]["brier"]:
                    retenus.setdefault(f"{h}/{cible}", []).append(k)
            sortie[f"{h}/{cible}"] = ligne
            print(f"horizon {h} {cible} : " + " | ".join(f"{k} AUC {m['auc']} Brier {m['brier']} ({m['periodes_meilleur']})" for k, m in ligne.items()))
    print("RETENUS", json.dumps(retenus))
    print("RÉSUMÉ", json.dumps(sortie), f"durée {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
