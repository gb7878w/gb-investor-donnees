"""Sonde 5 : profondeur réelle de l'historique Euronext (lignes reçues), valeurs vivantes et radiées."""
import sys
sys.path.insert(0, "outils")
import donnees

for nom, isin in [("LVMH", "FR0000121014"), ("Suez radié", "FR0010613471"), ("PSA radié", "FR0000121501"), ("Gemalto", "NL0000400653"), ("Technicolor", "FR0010918292"), ("Casino", "FR0000125585")]:
    for debut in ["27/10/2016", "27/10/2021", "27/10/2024"]:
        try:
            t = donnees.telecharger(isin, "XPAR", debut, "26/10/2026")
            l = [x for x in t.splitlines() if x[:2].isdigit()]
            print(nom, "début demandé", debut, "->", len(l), "séances", (l[-1][:10] + " … " + l[0][:10]) if l else "")
        except Exception as e:
            print(nom, debut, "erreur", type(e).__name__, str(e)[:80])
