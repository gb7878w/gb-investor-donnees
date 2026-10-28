# GB Investor · données

Données préparées chaque soir de semaine pour l'appli GB Investor (usage personnel de Gilbert).

- `univers/sbf120.json` : les valeurs suivies (SBF 120), revues à la main à chaque révision trimestrielle de l'indice.
- `univers/elargi.json` : périmètre complet, **toutes les actions cotées à Paris** (SBF 120 + Euronext Paris, Euronext Growth Paris et Euronext Access Paris, sans plancher de liquidité), produit par `outils/perimetre.py` (tâche `perimetre.yml`, à relancer à la main à chaque révision trimestrielle ou après une introduction en Bourse). La liste réunit la couverture EODHD et la liste officielle d'Euronext ; le marché de chaque valeur vient d'Euronext. Les valeurs peu échangées sont suivies mais jamais retenues par la Sélection.
- `outils/selection.py` : page Sélection de l'appli (six paramètres, test sur l'historique frais déduits, verdict publié dans `selection.bin`).
- `outils/donnees.py` : télécharge l'historique ajusté de chaque valeur et des indices CAC 40 et SBF 120 chez Euronext,
  le vérifie, puis le **chiffre** (AES-256-GCM, secret `CLE_DONNEES`) avant de le publier sur la branche `publication`.

Les cours restent illisibles dans ce dépôt public : les conditions d'Euronext interdisent de les republier.
Seule l'appli GB Investor, qui connaît la clé, peut les lire, et le chiffrement empêche toute modification.
La branche `publication` est remplacée à chaque passage, sans historique, pour garder le dépôt léger.

© Euronext N.V. pour les données de cours. Rien ici ne constitue un conseil en investissement.
