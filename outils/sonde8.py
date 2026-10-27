"""Sonde 8 : où la page produit Euronext indique-t-elle le marché de cotation (réglementé, Growth, Access) ?"""
import sys, os, re, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import donnees

def page(isin):
    r = urllib.request.urlopen(urllib.request.Request(f"https://live.euronext.com/en/product/equities/{isin}-XPAR", headers={"User-Agent": donnees.UA}), timeout=40)
    return r.read().decode("utf-8", "replace")

for nom, isin in [("Keyrus", "FR0004029411"), ("OSE", "FR0012127173"), ("LVMH", "FR0000121014")]:
    h = page(isin)
    print("=====", nom, len(h))
    for motif in ("Growth Paris", "Access Paris", "Euronext Paris", "Market</", "Regulated", "market-name", "Trading location", "Segment"):
        trouves = [m.start() for m in re.finditer(re.escape(motif), h)]
        print(f"  {motif!r}: {len(trouves)} fois")
        for p in trouves[:3]:
            print("     ...", re.sub(r"\s+", " ", h[max(0, p - 110):p + 90]))
