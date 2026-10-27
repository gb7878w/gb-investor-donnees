"""Sonde 5 : profondeur réelle de l'historique Euronext (lignes reçues), valeurs vivantes et radiées."""
import sys
sys.path.insert(0, "outils")
import donnees

for nom, isin in [("LVMH", "FR0000121014"), ("Suez radié", "FR0010613471"), ("PSA radié", "FR0000121501"), ("Gemalto", "NL0000400653"), ("Technicolor", "FR0010918292"), ("Casino", "FR0000125585")]:
    for debut in ["2016-10-27", "2021-10-27", "2024-10-27"]:
        try:
            t = donnees.telecharger(isin, "XPAR", debut, "2026-10-26")
            l = [d for d, _ in donnees.lire(t)][::-1]
            print(nom, "début demandé", debut, "->", len(l), "séances", (l[-1] + " … " + l[0]) if l else "")
        except Exception as e:
            print(nom, debut, "erreur", type(e).__name__, str(e)[:80])
