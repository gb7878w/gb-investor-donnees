"""Sonde 4 : historique long et sociétés radiées. Statuts et débuts de réponse seulement."""
import sys, re, json
sys.path.insert(0, "outils")
from sonde import show, get

# Euronext : un titre vivant et un titre radié, début 2016
for nom, isin in [("LVMH vivant", "FR0000121014"), ("Suez radié 2022", "FR0010613471"), ("PSA radié 2021", "FR0000121501"), ("Gemalto", "NL0000400653")]:
    q = "format=csv&decimal_separator=.&date_form=d/m/Y&op=&adjusted=Y&startdate=27/10/2016&enddate=26/10/2026&iframe_mode=&stock_filter=&isin_type=&mic=XPAR"
    st, b = show(f"Euronext historique {nom}", f"https://live.euronext.com/en/ajax/AwlHistoricalPrice/getFullDownloadAjax/{isin}-XPAR?{q}", n=200)
    lignes = b.decode("utf-8", "replace").splitlines() if st == 200 else []
    print("lignes:", len(lignes), "première:", lignes[3][:30] if len(lignes) > 3 else "", "dernière:", lignes[-1][:30] if lignes else "")

# Euronext : listes de titres, radiés
for nom, url in [
    ("Liste actions Paris", "https://live.euronext.com/en/pd_es/data/stocks?mics=XPAR&display_datapoints=dp_stocks&display_filters=df_stocks"),
    ("Fiche radiée Suez", "https://live.euronext.com/en/product/equities/FR0010613471-XPAR"),
    ("Liste radiations", "https://live.euronext.com/en/markets/paris/equities/delisted"),
    ("Download liste", "https://live.euronext.com/en/pd/data/stocks/download?mics=XPAR&initialLetter=&iss=&resultsTitle=All+equities+in+Paris&format=csv"),
]:
    show(nom, url, n=250)

# Autres sources
for nom, url in [
    ("Yahoo chart 10 ans (LVMH)", "https://query1.finance.yahoo.com/v8/finance/chart/MC.PA?range=10y&interval=1d"),
    ("Yahoo chart radié (Suez)", "https://query1.finance.yahoo.com/v8/finance/chart/SEV.PA?range=max&interval=1d"),
    ("Alpha Vantage démo", "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=MC.PAR&outputsize=full&apikey=demo"),
    ("Tiingo", "https://api.tiingo.com/api/test"),
    ("EODHD démo", "https://eodhd.com/api/eod/MC.PA?api_token=demo&fmt=json&period=d"),
    ("FMP démo", "https://financialmodelingprep.com/api/v3/historical-price-full/MC.PA?apikey=demo"),
    ("Twelve Data démo", "https://api.twelvedata.com/time_series?symbol=MC&exchange=Euronext&interval=1day&outputsize=5000&apikey=demo"),
    ("Wikipédia radiées CAC40/SBF", "https://fr.wikipedia.org/w/api.php?action=query&list=search&srsearch=radiation+de+la+cote+Euronext+Paris&format=json&srlimit=3"),
    ("AMF GECO radiations", "https://geco.amf-france.org/"),
]:
    show(nom, url, n=250)
