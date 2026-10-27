"""Sonde de l'envoi 2 : contexte, agenda, presse, profondeur d'historique. N'affiche jamais de série de cours complète."""
import re, sys, datetime as dt, urllib.parse
sys.path.insert(0, "outils")
from sonde import get

def head(name, url, n=300, **kw):
    st, body, hd = get(url, **kw)
    txt = body[:n].decode("utf-8", "replace").replace("\n", " ⏎ ")
    print(f"\n### {name}\n{st} {len(body)} o {hd.get('Content-Type','')}\n{url}\n{txt}")
    return st, body

def euronext(isin, debut, adjusted="Y", mic="XPAR"):
    q = urllib.parse.urlencode({"format": "csv", "decimal_separator": ".", "date_form": "d/m/Y", "op": "", "adjusted": adjusted,
                                "base100": "", "startdate": debut, "enddate": dt.date.today().isoformat()})
    st, body, _ = get(f"https://live.euronext.com/en/ajax/AwlHistoricalPrice/getFullDownloadAjax/{isin}-{mic}?{q}")
    dates = re.findall(rb"^(\d\d/\d\d/\d{4});", body, re.M)
    print(f"\n### Euronext {isin} depuis {debut} ajusté={adjusted} : {st}, {len(dates)} séances, de {dates[-1].decode() if dates else '-'} à {dates[0].decode() if dates else '-'}")
    return body

# 1. Profondeur d'historique
for debut in ["2016-10-01", "2006-01-01", "1995-01-01"]:
    euronext("FR0000120271", debut)
euronext("FR0003500008", "2006-01-01")
# Dividendes : comparaison ajusté / brut sur TotalEnergies
a = euronext("FR0000120271", "2024-01-01", "Y"); b = euronext("FR0000120271", "2024-01-01", "N")
def closes(body):
    out = {}
    for l in body.decode("utf-8", "replace").splitlines():
        c = l.split(";")
        if re.match(r"\d\d/\d\d/\d{4}$", c[0] or "") and len(c) > 5:
            try: out[c[0]] = float(c[5] or c[4])
            except ValueError: pass
    return out
ca, cb = closes(a), closes(b)
ratios = [(d, round(ca[d] / cb[d], 5)) for d in cb if d in ca and cb[d]]
sauts = [(ratios[i][0], ratios[i][1], ratios[i + 1][1]) for i in range(len(ratios) - 1) if abs(ratios[i][1] - ratios[i + 1][1]) > 0.002]
print("sauts du rapport ajusté/brut (dates de détachement probables) :", sauts[:12])

# 2. Contexte
fred = ["DGS10", "DCOILBRENTEU", "VIXCLS", "SP500", "NASDAQCOM", "DEXUSEU", "DEXCHUS", "PCOPPUSDM", "PNGASEUUSDM", "CPIAUCSL", "FEDFUNDS",
        "IRLTLT01FRM156N", "IRLTLT01DEM156N", "GOLDAMGBD228NLBM", "DJIA", "NIKKEI225", "UNRATE", "DFEDTARU"]
for s in fred:
    st, body, _ = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}")
    lignes = body.decode("utf-8", "replace").strip().splitlines()
    print(f"FRED {s}: {st} {len(lignes)} lignes, {lignes[1] if len(lignes) > 1 else ''} … {lignes[-1] if lignes else ''}")
ecb = {"EUR/USD": "EXR/D.USD.EUR.SP00.A", "EUR/CNY": "EXR/D.CNY.EUR.SP00.A", "Taux de dépôt": "FM/B.U2.EUR.4F.KR.DFR.LEV",
       "Inflation zone euro": "ICP/M.U2.N.000000.4.ANR", "Inflation France": "ICP/M.FR.N.000000.4.ANR",
       "10 ans France": "IRS/M.FR.L.L40.CI.0000.EUR.N.Z", "10 ans Allemagne": "IRS/M.DE.L.L40.CI.0000.EUR.N.Z",
       "Courbe AAA 10 ans": "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", "PIB zone euro": "MNA/Q.Y.I9.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.GY"}
for n, k in ecb.items():
    st, body, _ = get(f"https://data-api.ecb.europa.eu/service/data/{k}?format=csvdata&lastNObservations=3")
    lignes = body.decode("utf-8", "replace").strip().splitlines()
    print(f"BCE {n}: {st} {len(lignes)} lignes, {lignes[-1][:160] if lignes else ''}")
head("INSEE BDM (inflation)", "https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/001759970?lastNObservations=2", 400)
head("Eurostat PIB", "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/namq_10_gdp?geo=FR&unit=CLV_PCH_PRE&na_item=B1GQ&s_adj=SCA&lastTimePeriod=2&format=JSON", 300)
head("Or (LBMA)", "https://prices.lbma.org.uk/json/gold_pm.json", 200)
head("Gaz TTF (EIA ?)", "https://api.eia.gov/v2/natural-gas/pri/fut/data/", 200)

# 3. Agenda
head("BCE calendrier", "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html", 200)
head("Fed calendrier", "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", 200)
st, body, _ = get("https://www.info-financiere.gouv.fr/api/explore/v2.1/catalog/datasets/flux-amf-new-prod/records?where=identificationsociete_iso_cd_isi%3D%22FR0000133308%22&order_by=informationdeposee_inf_dat_emt%20desc&limit=40&select=informationdeposee_inf_dat_emt,informationdeposee_inf_tit_inf,typeinformation_type_inf_cd")
print("\n### DILA historique Orange", st, body[:1500].decode("utf-8", "replace"))
head("Euronext agenda société", "https://live.euronext.com/en/ajax/getCompanyEvents/FR0000133308-XPAR", 300)

# 4. Presse
for n, u in [("AMF", "https://www.amf-france.org/fr/flux-rss/display/21"), ("AMF actualités", "https://www.amf-france.org/fr/rss.xml"),
             ("Fed", "https://www.federalreserve.gov/feeds/press_all.xml"), ("Commission européenne", "https://ec.europa.eu/commission/presscorner/api/rss?language=fr"),
             ("La Tribune", "https://www.latribune.fr/feed.xml"), ("La Tribune bourse", "https://www.latribune.fr/bourse/feed.xml"),
             ("Boursorama", "https://www.boursorama.com/rss/actualites/economie"), ("Zonebourse", "https://www.zonebourse.com/rss/"),
             ("Investing fr", "https://fr.investing.com/rss/news_25.rss"), ("Le Figaro bourse", "https://www.lefigaro.fr/rss/figaro_bourse.xml"),
             ("Les Echos", "https://services.lesechos.fr/rss/les-echos-finance-marches.xml"), ("Capital", "https://feed.prismamediadigital.com/v1/cap/rss?sources=capital&categories=bourse"),
             ("ABC Bourse", "https://www.abcbourse.com/rss/displaynews/FR"), ("Reuters", "https://www.reutersagency.com/feed/?best-topics=business-finance"),
             ("GDELT", "https://api.gdeltproject.org/api/v2/doc/doc?query=%22TotalEnergies%22%20sourcelang:french&mode=artlist&maxrecords=3&format=json")]:
    head(n, u, 160)
for site in ["https://www.latribune.fr/robots.txt", "https://www.boursorama.com/robots.txt", "https://fr.investing.com/robots.txt", "https://www.lefigaro.fr/robots.txt", "https://www.abcbourse.com/robots.txt"]:
    head("robots " + site, site, 700)
