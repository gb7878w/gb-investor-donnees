import re
from sonde import get
w = get("https://fr.wikipedia.org/w/index.php?title=SBF_120&action=raw")[1].decode("utf-8", "replace")
for m in re.finditer(r"^==+[^=\n]+==+", w, re.M): print("TITRE", m.start(), m.group(0))
i = w.find("== Composition")
j = w.find("\n==", i + 20)
comp = w[i:j]
liens = re.findall(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", comp)
print("NB liens composition", len(liens))
print(" ; ".join((b or a) for a, b in liens))
print("ISIN dans la page :", sorted(set(re.findall(r"[A-Z]{2}[A-Z0-9]{9}\d", w))))
k = w.find("Historique", j)
print(w[j:j+3500])
