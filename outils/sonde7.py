"""Sonde 7 : données gratuites de l'AMF (positions courtes, déclarations de dirigeants, rachats d'actions)."""
import sys, json, re
sys.path.insert(0, "outils")
from sonde import show, get

st, b = show("data.gouv positions courtes (métadonnées)", "https://www.data.gouv.fr/api/1/datasets/62738e33f1be79935d3e5553/", n=80)
if st == 200:
    d = json.loads(b)
    print("titre :", d.get("title"), "| mis à jour :", d.get("last_update"), "| licence :", d.get("license"))
    for r in d.get("resources", [])[:8]:
        print("  ressource :", r.get("title"), r.get("format"), r.get("filesize"), r.get("url"))
        if r.get("format") in ("csv", "CSV") or str(r.get("url", "")).endswith(".csv"):
            st2, b2, _ = get(r["url"], limit=2500)
            print("  entête :", b2[:600].decode("utf-8", "replace").replace("\n", " ⏎ "))
for q in ["declarations dirigeants", "operations dirigeants", "rachat actions", "programme de rachat"]:
    st, b = show(f"data.gouv recherche « {q} »", "https://www.data.gouv.fr/api/1/datasets/?q=" + q.replace(" ", "+") + "&page_size=5", n=60)
    if st == 200:
        for x in json.loads(b).get("data", [])[:5]:
            print("  -", x.get("title"), "|", x.get("organization", {}).get("name") if x.get("organization") else "", "|", x.get("page"))
st, b = show("DILA métadonnées", "https://www.info-financiere.gouv.fr/api/explore/v2.1/catalog/datasets/flux-amf-new-prod", n=60)
if st == 200:
    print("champs :", [f.get("name") for f in json.loads(b).get("fields", [])])
st, b = show("DILA un enregistrement dirigeants", "https://www.info-financiere.gouv.fr/api/explore/v2.1/catalog/datasets/flux-amf-new-prod/records?where=search(informationdeposee_inf_tit_inf%2C%22dirigeant%22)&limit=2", n=1500)
st, b = show("DILA catégories (group_by)", "https://www.info-financiere.gouv.fr/api/explore/v2.1/catalog/datasets/flux-amf-new-prod/records?group_by=typeinformation_inf_cod&limit=40", n=1800)
