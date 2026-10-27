"""Sonde des sources gratuites : statut, taille, début de réponse. Aucune donnée de cours complète n'est affichée."""
import json, sys, urllib.request, urllib.parse, gzip, io, zipfile

UA = "GB-Investor-donnees/0.1 (usage personnel; github.com/gb7878w/gb-investor-donnees)"

def get(url, data=None, headers=None, limit=600):
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return r.status, body, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:limit], dict(e.headers or {})
    except Exception as e:
        return 0, str(e).encode(), {}

def show(name, url, data=None, headers=None, n=500):
    st, body, hd = get(url, data, headers)
    globals()["dernier"] = body
    print(f"\n### {name}\n{st} {len(body)} octets {hd.get('Content-Type','')}\n{url}")
    try:
        txt = body[:n].decode("utf-8", "replace")
    except Exception:
        txt = repr(body[:n])
    print(txt.replace("\n", " ⏎ "))
    return st, body

if __name__ == "__main__":
    st, body = show("Composition SBF120", "https://live.euronext.com/en/popout-page/getIndexComposition/FR0003999481-XPAR", n=300)
    if st == 200:
        open("composition.html", "wb").write(body)
        import re
        print("chemins ajax :", sorted(set(re.findall(rb"/(?:en/)?ajax/[A-Za-z0-9_/.-]+", body)))[:40])
        print("antibot visible :", b"antibot-message" in body)
        print("ISIN trouvés :", len(set(re.findall(rb"[A-Z]{2}[A-Z0-9]{9}[0-9]", body))))
    show("Composition CAC40", "https://live.euronext.com/en/popout-page/getIndexComposition/FR0003500008-XPAR", n=200)
    form = urllib.parse.urlencode({"format": "csv", "decimal_separator": ".", "date_form": "d/m/Y", "op": "", "adjusted": "Y", "base100": "", "startdate": "2024-10-25", "enddate": "2026-10-26"}).encode()
    st, body = show("Euronext historique (POST)", "https://live.euronext.com/en/ajax/AwlHistoricalPrice/getFullDownloadAjax/FR0000133308-XPAR", data=form,
         headers={"Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest"}, n=250)
    if st == 200: print("lignes :", body.count(b"\n"))
    for variant, url, data in [
        ("GET", "https://live.euronext.com/en/ajax/AwlHistoricalPrice/getFullDownloadAjax/FR0000133308-XPAR?" + form.decode(), None),
        ("POST nl", "https://live.euronext.com/nl/ajax/AwlHistoricalPrice/getFullDownloadAjax/FR0000133308-XPAR", form),
    ]:
        st, body = show("Euronext historique " + variant, url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest", "Referer": "https://live.euronext.com/en/product/equities/FR0000133308-XPAR"}, n=250)
        if st == 200: print("lignes :", body.count(b"\n"))
    st, body = show("Euronext historique bloc", "https://live.euronext.com/en/ajax/getHistoricalPriceBlock/FR0000133308-XPAR", n=250)
    if st == 200:
        import re
        print("formulaire :", sorted(set(re.findall(rb'(?:name|action|value)="[^"]{1,80}"', body)))[:60])
    show("Wikipedia SBF120", "https://fr.wikipedia.org/w/index.php?title=SBF_120&action=raw", n=1500)
    show("Wikidata SBF120", "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote('SELECT ?c ?cLabel ?isin WHERE { ?c wdt:P361 wd:Q1323478 . OPTIONAL { ?c wdt:P946 ?isin } SERVICE wikibase:label { bd:serviceParam wikibase:language "fr". } }'), n=600)
    st, body = show("Stooq", "https://stooq.com/q/d/l/?s=ora.fr&i=d", n=120)
    if st == 200: print("lignes :", body.count(b"\n"))
    st, body = show("Euronext indice CAC (POST)", "https://live.euronext.com/en/ajax/AwlHistoricalPrice/getFullDownloadAjax/FR0003500008-XPAR", data=form,
         headers={"Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest"}, n=250)
    if st == 200: print("lignes :", body.count(b"\n"))
    st, body, _ = get("https://marketdata.euronext.com/data-reporting-service/trades-file/download/EQUITIES/PREVIOUS_TRADING_DAY/PAR")
    print("\n### Euronext séance précédente PAR\n", st, len(body))
    if st == 200:
        z = zipfile.ZipFile(io.BytesIO(body)); n = z.namelist(); print(n)
        with z.open(n[0]) as f:
            for i, line in enumerate(io.TextIOWrapper(f, "utf-8")):
                if i < 3 or line.startswith("TradingDateTime"): print(line.strip()[:400])
                if i > 8: break
    for loc in ["AMS", "BRU", "LIS", "MIL", "DUB", "OSL"]:
        st, body, _ = get(f"https://marketdata.euronext.com/data-reporting-service/trades-file/download/EQUITIES/PREVIOUS_TRADING_DAY/{loc}")
        print(loc, st, len(body))
    isins = '("FR0000133308","FR0000120271")'
    show("DILA filtre ISIN", "https://www.info-financiere.gouv.fr/api/explore/v2.1/catalog/datasets/flux-amf-new-prod/records?" + urllib.parse.urlencode({"limit": 5, "where": f"identificationsociete_iso_cd_isi in {isins}", "order_by": "uin_dat_amf DESC", "select": "identificationsociete_iso_nom_soc,informationdeposee_inf_tit_inf,uin_dat_amf"}), n=700)
    for name, url in [
        ("BCE taux dépôt", "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?lastNObservations=2&format=csvdata"),
        ("BCE EURUSD", "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=2&format=csvdata"),
        ("BCE rendement 10 ans zone euro", "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?lastNObservations=2&format=csvdata"),
        ("FRED 10 ans US", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"),
        ("FRED Brent", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU"),
        ("FRED VIX", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"),
        ("Fed RSS", "https://www.federalreserve.gov/feeds/press_all.xml"),
        ("Eurostat HICP", "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_manr?geo=FR&coicop=CP00&lastTimePeriod=2"),
        ("INSEE BDM", "https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/001759970?lastNObservations=2"),
        ("GDELT", "https://api.gdeltproject.org/api/v2/doc/doc?query=%22Orange%22%20sourcecountry:FR&mode=artlist&format=json&maxrecords=3&timespan=1d"),
        ("XBRL filings", "https://filings.xbrl.org/api/filings?filter=%5B%7B%22name%22%3A%22country%22%2C%22op%22%3A%22eq%22%2C%22val%22%3A%22FR%22%7D%5D&page%5Bsize%5D=2"),
        ("Bluesky public search", "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=TotalEnergies&limit=2"),
        ("Bluesky api search", "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=TotalEnergies&limit=2"),
        ("Mastodon tag", "https://mastodon.social/api/v1/timelines/tag/bourse?limit=2"),
        ("Reddit sans compte", "https://www.reddit.com/r/vosfinances/new.json?limit=2"),
        ("Zonebourse RSS", "https://www.zonebourse.com/rss/"),
        ("Boursorama RSS", "https://www.boursorama.com/rss/actualites/economie/"),
        ("Investing RSS", "https://fr.investing.com/rss/news_25.rss"),
        ("La Tribune RSS", "https://www.latribune.fr/rss/rubriques/bourse.html"),
        ("AMF RSS", "https://www.amf-france.org/fr/flux-rss/display/21"),
        ("Les Echos RSS", "https://services.lesechos.fr/rss/les-echos-finance-marches.xml"),
        ("BFM", "https://www.tradingsat.com/rssbourse.xml"),
    ]:
        show(name, url, n=300)
