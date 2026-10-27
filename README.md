# GB Investor · données

Données préparées chaque soir de semaine pour l'appli GB Investor (usage personnel de Gilbert).

- `univers/sbf120.json` : les valeurs suivies (SBF 120), revues à la main à chaque révision trimestrielle de l'indice.
- `univers/elargi.json` : périmètre élargi (SBF 120 + valeurs de Paris et d'Euronext Growth Paris les plus échangées, Access exclu), produit par `outils/perimetre.py` (tâche `perimetre.yml`, à relancer à la main à chaque révision trimestrielle). Le marché de chaque valeur est lu dans sa page produit publique d'Euronext.
- `outils/selection.py` : page Sélection de l'appli (six paramètres, test sur l'historique frais déduits, verdict publié dans `selection.bin`).
- `outils/donnees.py` : télécharge l'historique ajusté de chaque valeur et des indices CAC 40 et SBF 120 chez Euronext,
  le vérifie, puis le **chiffre** (AES-256-GCM, secret `CLE_DONNEES`) avant de le publier sur la branche `publication`.

Les cours restent illisibles dans ce dépôt public : les conditions d'Euronext interdisent de les republier.
Seule l'appli GB Investor, qui connaît la clé, peut les lire, et le chiffrement empêche toute modification.
La branche `publication` est remplacée à chaque passage, sans historique, pour garder le dépôt léger.

© Euronext N.V. pour les données de cours. Rien ici ne constitue un conseil en investissement.
