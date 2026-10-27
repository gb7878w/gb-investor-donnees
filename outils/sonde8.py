"""Sonde 8 : comment savoir si une valeur cote sur le marché réglementé, sur Growth ou sur Access ?"""
import sys, os, re, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import donnees

def get(url, n=400):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": donnees.UA, "Accept": "text/html,application/json"}), timeout=40)
        b = r.read().decode("utf-8", "replace")
        return r.status, b
    except Exception as e:
        return getattr(e, "code", 0), str(e)[:150]

VALEURS = [("Capital B", "FR0011053636"), ("Biophytis", "FR0012816825"), ("Mediantechn", "FR0011049824"), ("Keyrus", "FR0004029411"),
           ("OSE Pharma", "FR0012127173"), ("Adocia", "FR0011184241"), ("LVMH", "FR0000121014"), ("Archos", "FR0014007XT1")]
for nom, isin in VALEURS:
    for mic in ("XPAR", "ALXP", "XMLI"):
        st, b = get(f"https://live.euronext.com/en/product/equities/{isin}-{mic}")
        m = re.findall(r"(Euronext (?:Growth|Access|Expert)[^<\"]{0,25}|Euronext Paris|Regulated)", b) if st == 200 else []
        t = re.search(r"<title>([^<]{0,100})", b)
        print(nom, mic, st, len(b), (t.group(1).strip() if t else ""), sorted(set(m))[:6])
st, b = get("https://live.euronext.com/en/pd_es/data/stocks?mics=ALXP&iDisplayLength=5")
print("liste Growth", st, b[:300].replace("\n", " "))
