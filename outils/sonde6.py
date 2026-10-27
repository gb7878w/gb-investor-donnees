import re, html
from sonde import get
st, b, h = get("https://www.easybourse.com/indice-composition/sbf-120/FR0003999481-25")
t = b.decode("utf-8", "replace")
print(st, len(b))
paires = re.findall(r'href="[^"]*?/([A-Z]{2}[A-Z0-9]{9}\d)-\d+[^"]*"[^>]*>\s*([^<]{2,60}?)\s*<', t)
vus = {}
for isin, nom in paires:
    nom = html.unescape(nom).strip()
    if isin != "FR0003999481" and nom and isin not in vus: vus[isin] = nom
print(len(vus))
for isin, nom in vus.items(): print(f"{nom};{isin}")
