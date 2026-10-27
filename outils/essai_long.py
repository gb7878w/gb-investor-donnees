"""Essai P6 : le modèle appris sur 10 ans, tout le marché et les radiées bat-il le modèle actuel et une référence simple ?

Trois versions, mêmes périodes de test jamais vues (6 blocs, écart égal à l'horizon), mêmes lignes de test (valeurs du SBF 120 encore cotées) :
  A. référence : régression logistique, apprise sur tout l'historique disponible avant le test ;
  B. modèle actuel : LightGBM appris sur les 2 années précédentes, valeurs du SBF 120 seulement ;
  C. nouveau modèle : LightGBM appris sur tout l'historique avant le test, tout Paris, radiées comprises.
Ne publie rien : affiche seulement des mesures (aucun cours).
"""
import os, sys, json, gzip, base64, time, urllib.request
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modele as M
import contexte

RAW = "https://raw.githubusercontent.com/gb7878w/gb-investor-donnees/historique/"
PAS = 7          # une ligne sur sept (les étiquettes se chevauchent de toute façon)
FENETRE_B = 520  # séances d'apprentissage du modèle actuel


def lire_bin(nom, cle):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    with urllib.request.urlopen(urllib.request.Request(RAW + nom, headers={"User-Agent": "GB-Investor-donnees/1.0"}), timeout=120) as r:
        brut = r.read()
    if brut[:4] != b"GBI1":
        raise ValueError("en-tête inattendu")
    return json.loads(gzip.decompress(AESGCM(cle).decrypt(brut[4:16], brut[16:], b"GBI1")))


def charger(cle):
    series, secteurs, sbf = {}, {}, set()
    univers = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "univers", "sbf120.json"), encoding="utf-8"))
    sect_isin = {v["isin"]: v.get("secteur") for v in univers["valeurs"]}
    for k in range(1, 5):
        for v in lire_bin(f"historique-{k}.bin", cle)["valeurs"]:
            series[v["id"]] = {"d": v["d"], "o": v["o"], "h": v["h"], "l": v["b"], "c": v["c"], "v": v["v"]}
            if v.get("isin") in sect_isin:
                secteurs[v["id"]] = sect_isin[v["isin"]]
                if not v["radiee"]:
                    sbf.add(v["id"])
    indices = lire_bin("historique-indices.bin", cle)["indices"]
    return series, indices, secteurs, sbf


def mesures(y, p):
    base = float(y.mean())
    return dict(auc=round(M._auc(y, p), 4), brier=round(float(np.mean((p - y) ** 2)), 5), brier_base=round(float(np.mean((base - y) ** 2)), 5), cas=int(len(y)))


def comparer(X, rang, ident_inv, etiq, sbf_mask, journal=print, blocs_n=6):
    rangs = np.unique(rang)
    debut = rangs[int(len(rangs) * 0.5)]
    blocs = np.array_split(rangs[rangs >= debut], blocs_n)
    X32 = X
    sortie = {}
    for h in M.HORIZONS:
        cibles = M._cibles(etiq, h)
        for cible in M.CIBLES:
            y = cibles[cible]
            res = {"A": ([], []), "B": ([], []), "C": ([], []), "C_tout": ([], [])}
            for bloc in blocs:
                tr = (rang <= bloc[0] - h) & ~np.isnan(y)
                te = np.isin(rang, bloc) & ~np.isnan(y)
                te_s = te & sbf_mask
                tr_b = tr & sbf_mask & (rang > bloc[0] - h - FENETRE_B)
                if te_s.sum() < 300 or tr.sum() < 5000 or tr_b.sum() < 2000 or len(np.unique(y[tr])) < 2 or len(np.unique(y[tr_b])) < 2:
                    continue
                pA = M._logistique(X32[tr], y[tr])(X32[te_s])
                pB = M._entrainer(X32[tr_b], y[tr_b]).predict(X32[te_s])
                mC = M._entrainer(X32[tr], y[tr])
                pC = mC.predict(X32[te_s])
                pCt = mC.predict(X32[te])
                for k, (p, yy) in {"A": (pA, y[te_s]), "B": (pB, y[te_s]), "C": (pC, y[te_s]), "C_tout": (pCt, y[te])}.items():
                    res[k][0].append(p); res[k][1].append(yy)
            if not res["A"][0]:
                journal(f"horizon {h} {cible} : pas assez de données")
                continue
            ligne = {k: mesures(np.concatenate(v[1]), np.concatenate(v[0])) for k, v in res.items()}
            sortie[f"{h}/{cible}"] = ligne
            journal(f"horizon {h} {cible} : " + " | ".join(f"{k} AUC {m['auc']} Brier {m['brier']}" for k, m in ligne.items()) + f" | base {ligne['A']['brier_base']} | {ligne['A']['cas']} cas SBF")
    return sortie


def main():
    cle = base64.b64decode(os.environ.get("CLE_DONNEES", ""))
    if len(cle) != 32:
        sys.exit("CLE_DONNEES absente ou invalide.")
    t0 = time.time()
    series, indices, secteurs, sbf = charger(cle)
    print(f"{len(series)} valeurs, dont {len(sbf)} du SBF 120 encore cotées ; chargé en {time.time() - t0:.0f} s")
    series_ctx, _, manq = contexte.charger()
    print("contexte manquant :", manq)
    X, noms, rang, ident, etiq, _ = M.construire(series, indices, secteurs, series_ctx)
    print(f"{X.shape[0]} lignes, {len(noms)} paramètres, construit en {time.time() - t0:.0f} s")
    uniques, inv = np.unique(ident, return_inverse=True)
    garde = ((rang + inv) % PAS) == 0
    sbf_mask_all = np.isin(ident, list(sbf))
    X, rang, etiq, sbf_mask = X[garde].astype(np.float32), rang[garde], etiq[garde], sbf_mask_all[garde]
    print(f"{X.shape[0]} lignes après échantillonnage, dont {int(sbf_mask.sum())} du SBF 120")
    M.PARAMS["num_threads"] = 4
    sortie = comparer(X, rang, None, etiq, sbf_mask)
    print("RÉSUMÉ", json.dumps(sortie), f"durée {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
