# Oracle parcours TOP5 — comparaison économique SL5 / ATR20 borné

## Résultat — NO_GO_STABLE_ATR_STOP_ADVANTAGE

La règle ATR n'apporte pas un avantage transversal : amélioration2025, mais
perte plus importante2024 et forte dégradation2026. **Pas d'intégration live**,
pas d'élargissement automatique des stops et aucun nouveau multiplicateur
testé après ces résultats. Cette conclusion porte sur cette règle, pas sur
l'impossibilité universelle d'utiliser l'ATR.

[Protocole figé](oracle_path_atr_stop_20261014.md) : LONG TOP5, stop fixe5 %
contre `clip(ATR20_J/close_J,5 %,10 %)`, TP20/trailing15 dans les deux bras.
Stop choisi à J, fixé sur fillJ+1, jamais desserré ensuite ; budget nominal
2 % equity par entrée identique, taille adaptée au stop, contraintes natives
et coûts inchangés, plafond entrée levier2. Pas de vente forcéeH20 ni terminale.

Même univers/modèles/admissions à J que le sélecteur précédent :

| Année | Oracle CatBoost parcours | Fold retenu |
| --- | --- | --- |
| 2024 | `model-factory-20261014113215-437ed1` | 2023-12-05 |
| 2025 | `model-factory-20261014113226-102eca` | 2024-12-05 |
| 2026 | `model-factory-20261014113232-bc35a7` | 2025-12-10 |

Pas de changement des scores, pas de choix d'un fold entraîné dans l'année
testée, pas de filtre gagnant futur ou de remplacement des TOP5.

## Rendement du portefeuille après coûts et financement

Capital initial4000USD, réinitialisé pour chaque année/bras. Les positions
encore ouvertes sont valorisées MTM, pas inventées comme des ventes.
2026 couvre2 janvier…30 septembre, pas année entière.

| Période | Rendement SL5 | Rendement ATR | Écart ATR−SL5 | Capital final SL5 USD | Capital final ATR USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | −16,74 % | −28,91 % | −12,17 points | 3330,30 | 2843,68 |
| 2025 | +33,12 % | +42,02 % | +8,90 points | 5324,92 | 5680,76 |
| 2026 partiel | +36,14 % | −26,41 % | −62,56 points | 5445,76 | 2943,40 |

Financement hypothétique du débit6,5 % ACT/360 et frais canoniques natifs
inclus. Les gains/pertes ci-dessous sont réalisés, frais de trade inclus,
mais intérêts séparés ; le latent explique aussi l'écart avec le capital final.

| Période | Bras | Gains réalisés USD | Pertes réalisées USD | Latent USD | Intérêts USD |
| --- | --- | ---: | ---: | ---: | ---: |
| 2024 | SL5 | 5807,60 | −6385,68 | −22,81 | 68,81 |
| 2024 | ATR | 3216,90 | −4399,54 | +66,88 | 40,57 |
| 2025 | SL5 | 7758,26 | −6480,69 | +118,24 | 70,89 |
| 2025 | ATR | 7586,36 | −5945,71 | +115,64 | 75,54 |
| 2026 | SL5 | 6399,92 | −5142,77 | +205,56 | 16,95 |
| 2026 | ATR | 2258,56 | −3434,08 | +128,63 | 9,71 |

## Drawdown et fréquence des gains

| Période | DD SL5 | DD ATR | Lots clos SL5 / ATR | Gagnants clos SL5 / ATR |
| --- | ---: | ---: | ---: | ---: |
| 2024 | −32,83 % | −32,03 % | 151 / 140 | 20,53 % / 19,29 % |
| 2025 | −21,79 % | −18,66 % | 140 / 138 | 29,29 % / 34,06 % |
| 2026 partiel | −26,19 % | −35,44 % | 146 / 102 | 26,71 % / 21,57 % |

Le bénéfice2025 ne résiste donc pas aux deux autres périodes. Moins de PnL
perdant réalisé en dollars ne signifie pas automatiquement un meilleur
portefeuille : les gains et les occasions de réinvestissement changent aussi.
Il n'est pas valide d'appliquer a posteriori l'ATR seulement à2025.

## Stops et exposition réellement exécutés

| Période | SL ATR médian au fill | Min/max SL ATR | Fills à la borne10 % | Levier brut moyen SL5 / ATR |
| --- | ---: | --- | ---: | ---: |
| 2024 | 5,87 % | 5 / 10 % | 1 / 143 | 1,03 / 0,90 |
| 2025 | 7,30 % | 5 / 10 % | 17 / 143 | 0,83 / 0,85 |
| 2026 partiel | 7,85 % | 5 / 10 % | 22 / 107 | 0,48 / 0,41 |

Le risque nominal autorisé à J reste2 % avant les multiplicateurs natifs.
Le risque au fill peut varier avec le gap : borne budget effectifJ×1,03
vérifiée, pas hausse cachée du budget proportionnelle à la largeur du stop.
Les portefeuilles n'ont pas exactement les mêmes trades/capital à tout moment,
car sorties, réinvestissements et garde-fous dépendent de leur propre état.
Le trailing reste15 %, mais son seuil d'activation dépend mécaniquement du
SL initial ; il ne desserre jamais ce dernier.

## Artefacts et contrôles

Dossier final : `artifacts/research/us_oracle_path_atr_stop/20261014-v2`.
Commande finale (les cas déjà complets sont vérifiés et repris, pas doublés) :

```powershell
python -u -m scripts.research.us_oracle_path_atr_stop --output artifacts/research/us_oracle_path_atr_stop/20261014-v2 --workers 3
```

Six cas complets, zéro échec. Le premier calculv1 est conservé : il portait un
libellé générique hérité `sizing_unchanged=true` dans le brasATR, alors que la
distance de risque et les quantités étaient réellement adaptées. La correction
porte uniquement sur ces métadonnées, pas les protections, données ou paramètres.
Le calcul a été répété à l'identique dansv2 : trades et courbes quotidiennes
strictement identiques dans les six cas ; ne pas interpréterv1/v2 comme
deux hypothèses financières différentes. La copie du runner originalv1 est
conservée dans `runner-at-freeze.py` avec son empreinte originale.

Le rapport de campagne/cas et le rapport natifv2 distinguent désormais :
`sizing_unchanged=false` pourATR, `risk_budget_unchanged=true`, pas de resize
caché, trailing15 inchangé mais activation dépendante du SL.

**41 tests ciblés réussis** (12 propres à cette comparaison,29 contrats
réutilisés du sélecteur, règles et diagnostic). Budget partagé, tranches/bornes, ATR absent rejeté, préservation
de la sous-classe dans les overrides/régimes, stop gelé malgré changement des
HIGH/LOW futurs, gap d'entrée, TP20/trailing15 et parité native sur fixtures.
La revue technique vérifie les préfixes ATR de toutes les décisions, le risque
des fills committés, les protections des lots clos, les dates, la réconciliation
cash/latent/intérêts, DD et la parité exacte des trois témoins natifs archivés.
Cette seconde vérification est faite par le même assistant, pas une revue
humaine indépendante.

Réserves inchangées : univers actuel de survivants, secteurs actuels nonPIT,
prix split-adjusted actuels, dividendes incomplets, macro sans vintages de
publication certifiés, hypothèses de financement/marge et fillsOHLC. Pas une
certification brokerLIVE. Les périodes déjà observées restent exploratoires.
Ni modèle réentraîné, SQL, batch, YAML de production ou ordre courtier modifié.

Le SL5 reste seulement le **témoin de recherche**, pas une stratégie prouvée
rentable en toutes circonstances :2024 négative et DD importants. Ce GO
s'arrête à la comparaison ; aucun balayage de coefficients ni nouvel algorithme
lancé automatiquement pour corriger les pertes observées.
