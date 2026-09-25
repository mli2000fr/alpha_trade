# Sprint 9 — Validation du panel CN 2018–2025

Date : 25 septembre 2026. Profil : `cn_price_v1`. Source des décisions :
univers `CN_A` point-in-time du Sprint 8. Benchmark : CSI 300
`sh.000300`. Aucun entraînement ni backtest n'a été lancé dans ce sprint.

## Verdict

L'[audit consolidé](../../artifacts/cn/features/sprint9_audit_2018_2025.json)
retourne **`PASS_PRICE_ONLY`** : huit artefacts annuels, même schéma de
features, SHA-256 valides, zéro clé `(date,instrument)` dupliquée et zéro
entrée publiée après la décision. Les contrôles unitaires couvrent le refus
du marché US, d'un secteur imputé avec l'information actuelle, d'une barre
future, d'une correction historique tardive et l'emploi de la colonne ST
canonique. Une réexécution identique est protégée contre tout écrasement
d'un artefact divergent. L'année 2018 a été effectivement rejouée :
**même empreinte d'entrée et même SHA-256 du Parquet**
(`4350796315b4a14c5715e433150b901fd87c3f42294f7b6b8fed3e33cc23a642`).

| Année | Lignes candidates | Séances avec candidats | Couverture prix H20 | Couverture CSI 300 | Position 52 semaines |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2018 | 658 311 | 203 | 98,92 % | 100 % | 0 % |
| 2019 | 870 013 | 244 | 99,08 % | 100 % | 42,37 % |
| 2020 | 925 095 | 243 | 99,14 % | 100 % | 22,90 % |
| 2021 | 1 033 398 | 243 | 99,25 % | 100 % | 20,89 % |
| 2022 | 1 127 826 | 242 | 99,45 % | 100 % | 22,99 % |
| 2023 | 1 196 479 | 242 | 99,64 % | 100 % | 26,10 % |
| 2024 | 1 225 195 | 242 | 99,63 % | 100 % | 26,03 % |
| 2025 | 1 242 050 | 243 | 99,39 % | 100 % | 23,76 % |
| **Total** | **8 278 367** | **1 902** | — | — | — |

La première partie de 2018 n'a pas de candidats : le contrat d'univers exige
un historique préalable, et les barres CN commencent en 2018. On ne
reconstruit pas artificiellement 2017. STAR apparaît seulement à partir de
2019, ce qui concorde avec les distributions par board dans les rapports.

## Limites avant la recherche ML

1. **Secteur PIT absent** : `sector_code` et `sector_return20_rank` sont
   volontairement manquants à 100 %. Le marché CN ne peut donc pas encore
   être neutralisé par secteur. La taxonomie `SW_2021` seule ne fournit pas
   les appartenances historiques.
2. **Prix bruts autour des corporate actions** : les SMA longs, le range et
   surtout la position 52 semaines sont masqués lorsqu'un facteur
   d'ajustement non classifié contamine la fenêtre. En 2018, 252 séances
   antérieures n'existent pas ; la position 52 semaines est donc nulle sur
   toute l'année. De 2020 à 2025, sa couverture reste proche de 21–26 %.
   Cette feature ne doit pas entrer telle quelle dans un modèle exigeant
   une disponibilité dense.
3. **Turnover du flottant absent** : le montant en CNY et le volume sont
   disponibles, mais pas un dénominateur PIT fiable de titres flottants.
4. **`instrument_id` et `provider_symbol` sont des clés de provenance**,
   jamais des features numériques destinées à l'entraînement. Les flags
   `prior_suspended` peuvent être constants parmi les candidats parce que
   la politique de l'univers exige déjà une barre négociée à J−1.

Le panel est donc **prêt pour construire des labels et une baseline
price-only**, pas pour conclure à un alpha, ni pour déclarer les familles
sectorielles et turnover disponibles. Les prochaines expériences doivent
sélectionner explicitement leurs colonnes et mesurer les résultats hors
échantillon par board et année.
