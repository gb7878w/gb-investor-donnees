"""Sonde 8 : sous quel identifiant de marché Euronext télécharge-t-on les valeurs de Growth ?"""
import sys, os, datetime as dt, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import donnees
fin = dt.date.today().isoformat(); debut = (dt.date.today() - dt.timedelta(days=40)).isoformat()
for nom, isin in [("Capital B", "FR0011053636"), ("Biophytis", "FR0012816825"), ("Sensorion", "FR0012596468"), ("Mediantechn", "FR0011049824"),
                  ("Keyrus", "FR0004029411"), ("OSE Pharma", "FR0012127173"), ("Adocia", "FR0011184241"), ("LVMH", "FR0000121014")]:
    for mic in ("XPAR", "ALXP", "XMLI", "ALXB", "XAMS", "MLXB"):
        try:
            t = donnees.telecharger(isin, mic, debut, fin, essais=1)
            try:
                n = len(donnees.lire(t))
            except Exception as e:
                n = f"lecture : {e} ; début : {t[:90]!r}"
            print(nom, mic, "->", n)
        except Exception as e:
            print(nom, mic, "erreur", type(e).__name__, str(e)[:80])
