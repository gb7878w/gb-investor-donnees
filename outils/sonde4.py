import re
from sonde import get
for url in ["https://live.euronext.com/en/popout-page/getIndexComposition/FR0003999481-XPAR",
            "https://live.euronext.com/en/product/indices/FR0003999481-XPAR",
            "https://live.euronext.com/en/ajax/getIndexComposition/FR0003999481-XPAR",
            "https://live.euronext.com/en/ajax/getIndexCompositionFull/FR0003999481-XPAR",
            "https://live.euronext.com/fr/product/indices/FR0003999481-XPAR/market-information"]:
    st, b, h = get(url)
    t = b.decode("utf-8", "replace")
    print("\n###", st, len(b), url)
    for mot in ["TOTALENERGIES", "TotalEnergies", "ACCOR", "Accor", "<table", "data-url", "drupal-settings-json"]:
        k = t.find(mot)
        print(mot, k, t[max(0, k-150):k+250].replace("\n", " ") if k >= 0 and mot in ("<table", "data-url", "TOTALENERGIES", "Accor") else "")
    print("chemins :", sorted(set(re.findall(r'"(/(?:en|fr)/(?:ajax|popout-page)[^"]{3,120})"', t)))[:40])
