import re
from sonde import get
for url in ["https://live.euronext.com/en/ajax/getIndexComposition/FR0003999481-XPAR",
            "https://live.euronext.com/en/ajax/getIndexCompositionFull/FR0003999481-XPAR"]:
    st, b, h = get(url)
    t = b.decode("utf-8", "replace")
    isins = re.findall(r"[A-Z]{2}[A-Z0-9]{9}\d", t)
    print("\n###", st, len(b), h.get("Content-Type"), url, "ISIN:", len(set(isins)))
    print(t[:1500].replace("\n", " "))
    print(sorted(set(isins)))
