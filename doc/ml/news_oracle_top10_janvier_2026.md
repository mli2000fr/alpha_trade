# TOP10 Oracle et news archivées — janvier 2026

Test terminé et audité le **16 octobre 2026**. Rapport :
`artifacts/research/us_news_oracle_top10_jan2026/20261016-v1/report.json`.

## Conclusion

**Le filtre GPT haussier n'améliore pas le critère TP20 avant SL10 sur ce mois.**
Dans le TOP10 complet, 81 sélections sur 200 atteignent +20 % avant −10 % :
**40,50 %**. Parmi les 26 avis haussiers GPT, neuf réussissent : **34,62 %**,
soit **−5,88 points**. Les stops sont plus fréquents dans ce sous-groupe.

Cela concerne ces réponses GPT déjà archivées et ce mois, pas tous les types
de news/sentiment ni une preuve d'inefficacité universelle. Janvier 2026 n'est
pas un holdout vierge : cette année et ces campagnes ont déjà été examinées.

Pas de nouveau GPT, Web, fournisseur, entraînement, inférence Oracle, écriture
SQL, ordre ou changement de production. Le cache est lu, jamais réexécuté.
**Coût API supplémentaire : 0 USD.**

## 1. Sélection et modèle

- Décisions du 2 au 30 janvier : **20 séances**, dix premiers titres chaque jour,
  **200 sélections**, 28 titres distincts. TOP10 titres, pas TOP10 %.
- Modèle parcours H20 : `model-factory-20261014113232-bc35a7`, backend **CatBoost**,
  fold **2025-12-10**, empreintes poids/profil vérifiées.
- Labels de train/validation de ce fold disponibles au plus tard le 9 décembre
  2025, donc avant 2026. Aucun fold futur du même modèle utilisé.
- Les scores et rangs sont ceux de la campagne figée TOP20 existante, dont nous
  gardons `oracle_rank <= 10`, pas un nouvel entraînement ou classement refait
  après examen des prix. Score décroissant, symbole en cas d'égalité exacte.
- Futurs rendements/labels absents des fichiers de sélection ; jointure de
  lineage, horizon, cible et modèle vérifiée avant extraction des résultats.

La causalité des labels de train ne signifie pas que ces fichiers construits
en octobre existaient en janvier. Univers courant et versions des données
restent des limites historiques documentées.

## 2. News et avis : ce qui est réutilisé

Campagne source : `artifacts/research/us_news_gpt_top20_history/20261015-v1/`,
mois `2026-01`. Paquets originaux, analyses et snapshots SQL sont rapprochés par
empreinte exacte ; réponses valides reparsées et citations revérifiées.
Pas d'appel par `NewsCache.execute`, d'import ou de qualification SQL écrite.

Fenêtre source inchangée : **24 heures strictement avant la clôture NYSE J**,
avec les heures fournisseur admises par cette campagne. Chaque paquet conserve
l'identité courante et les extraits effectivement fournis. Une analyse de lot
titre/date n'est pas découpée en faux avis par article.

| État du lot GPT | Sélections |
| --- | ---: |
| Haussier `BULLISH`, réponse valide | 26 |
| Baissier `BEARISH`, réponse valide | 8 |
| Abstention `ABSTAIN`, réponse valide | 71 |
| Aucun texte admissible `UNKNOWN_NO_QUALIFIED_TEXT` | 90 |
| Réponse invalide `UNKNOWN_INVALID_RESPONSE` | 5 |
| **Total** | **200** |

110 sélections possèdent des articles dans les paquets, soit 418 occurrences
de **409 articles distincts**. Les 90 sans texte admissible ne sont pas des
opinions neutres et ne prouvent pas qu'aucune news n'a été publiée.
Une abstention n'est pas une prédiction de stabilité du cours.

Les 110 lignes de cache concernées sont réutilisées telles quelles, y compris
les cinq invalides, sans retry pour obtenir une autre opinion. Aucun nouveau
seuil de confiance n'est recherché ; tous les avis valides de chaque direction
sont conservés. Ce n'est pas un test du seuil FinBERT >0,9.

## 3. Mesure du parcours : pas un portefeuille

Entrée de référence **open de J+1**, puis **20 séances J+1…J20**, sans utiliser
le high de J. Première entrée le 5 janvier ; dernier chemin terminé le
**2 mars 2026**. Pas de troncature au 31 janvier et pas de label immature.

Les 200 chemins sont complets et qualifiés : OHLCV split-adjusted du tape local
déjà utilisé, prix/volumes positifs, cohérence OHLC, aucune barre synthétique,
`instrument_id` stable, contrôle des discontinuités d'identité connues. Zéro
exclusion pour données futures manquantes et aucun remplacement hors TOP10.

Les 195/200 sélections ayant des barres **intraday SIP à J** lors du contrôle
préparatoire ne sont pas le dénominateur de cette mesure H20 : celle-ci utilise
les **barres quotidiennes qualifiées, présentes sur 200/200 chemins**. Pas de
substitution ou de mélange des 5m raw et des prix journaliers ajustés.

LONG : TP = open d'entrée × 1,20 ; SL = open d'entrée × 0,90, aucun trailing.
Un open ultérieur dépassant une barrière est examiné avant les extrêmes du jour.
Si le même jour touche TP et SL sans ordre identifiable, résultat `AMBIGUOUS`,
bornes SL-first/TP-first conservées. Ici **zéro ambiguïté journalière**.

`TIMEOUT` signifie aucune barrière atteinte en vingt séances. Les gaps sont
comptés séparément : un stop touché après un gap n'est pas une garantie de perte
limitée à 10 %. Le prix d'exécution réel/slippage n'est pas simulé.

Chaque couple titre/date est une observation, même si le titre figure déjà dans
le classement d'une autre journée. **Pas de capital, sizing, levier, absence de
réachat d'une position détenue, frais, financement ou PnL de portefeuille ici.**
Les valeurs terminales ignorent volontairement les sorties aux barrières pour
décrire aussi le chemin complet ; ce ne sont pas des profits de trades exécutés.

## 4. Résultats LONG : mêmes règles pour tous les groupes

| Groupe | N | TP20 avant SL10 | SL avant TP | Aucune barrière en 20 séances |
| --- | ---: | ---: | ---: | ---: |
| **TOP10 sans filtre** | **200** | **81 — 40,50 %** | **97 — 48,50 %** | **22 — 11,00 %** |
| **GPT haussier** | **26** | **9 — 34,62 %** | **15 — 57,69 %** | **2 — 7,69 %** |
| GPT baissier, mesuré en LONG comme comparaison | 8 | 5 — 62,50 % | 3 — 37,50 % | 0 |
| GPT abstention | 71 | 37 — 52,11 % | 28 — 39,44 % | 6 — 8,45 % |
| Sans texte admissible | 90 | 30 — 33,33 % | 47 — 52,22 % | 13 — 14,44 % |
| Réponse invalide | 5 | 0 | 4 — 80,00 % | 1 — 20,00 % |

Les TP incluent les ouvertures au-delà du TP ; les stops incluent les gaps.
Les groupes partitionnent le même TOP10 ; ils ne sont pas des populations
indépendantes. Les huit avis baissiers ne justifient pas une règle contrariante.
Le meilleur taux des abstentions observé ici n'est pas un filtre validé.

### Excursions et résultat terminal, sans appliquer les sorties

| Mesure | TOP10 complet | GPT haussier |
| --- | ---: | ---: |
| Variation terminale J20 moyenne | +7,33 % | **−4,97 %** |
| Variation terminale médiane | +9,23 % | **−6,17 %** |
| Chemins terminant positifs | 64,50 % | **46,15 %** |
| Hausse maximale moyenne durant le parcours | +22,37 % | +16,96 % |
| Hausse maximale médiane | +20,01 % | +15,87 % |
| Baisse maximale moyenne durant le parcours | −12,54 % | −19,42 % |

Le TOP10 complet peut finir souvent positif à J20 tout en touchant auparavant
un SL : **64,50 % de clôtures finales positives n'est pas 64,50 % de trades
gagnants TP/SL**. Inversement, un TP peut être atteint avant une rechute.

## 5. Concentration et lecture par date

26 avis haussiers, 11 titres, 15 dates. COHR et LMND représentent six avis chacun,
soit **12/26** à eux deux. LMND : un TP pour cinq stops ; COHR : quatre TP pour
deux stops. Des chemins successifs du même titre se recouvrent fortement.

La comparaison équipondérée des quinze dates ayant un avis haussier donne un
écart de taux TP de **−7,78 points** face au TOP10 de ces mêmes dates. Ce n'est
pas un appariement causal marché/secteur/volatilité.

Sensibilité figée « retirer un titre à la fois » : écart de taux TP haussier
moins témoin entre **−13,89 et +1,11 points**. Il devient positif dans un seul
des 28 retraits, en retirant LMND. On conserve LMND : **aucune exclusion après
coup** et aucune nouvelle règle ou seuil de confiance promu sur ces pertes.

Ces variations ne constituent ni des tests indépendants ni des intervalles de
confiance. Un mois avec des labels H20 fortement chevauchants ne suffit pas à
démontrer une stabilité annuelle.

## 6. Lecture SHORT secondaire

Même référence d'entrée, TP à −20 % et stop à +10 %, sans emprunt ni exécution
simulés. Sur les **huit avis baissiers** : un TP (**12,50 %**), six stops
(75,00 %), un timeout (12,50 %). Le TOP10 entier dans cette géométrie SHORT
atteint le TP dans 13,50 % des cas.

Donc pas d'amélioration de ce critère SHORT non plus dans ce petit groupe.
Ce panneau est une mesure de chemin, pas un backtest SHORT : disponibilité
historique, borrow, marge, quotes et frais ne sont pas qualifiés ici.

## 7. Limites et décision

- Importations/révisions historiques des news, métadonnées courantes et absence
  d'archives immuables de disponibilité/scoring de janvier : **non PIT strict**.
- Le LLM a été interrogé rétrospectivement. « Pas de futur dans le prompt » ne
  démontre pas l'absence de connaissances futures dans ses poids.
- L'avis porte sur un lot d'articles avant clôture, pas nécessairement sur une
  nouvelle information encore exploitable le lendemain. Pas de Web ajouté.
- Les réponses sont réutilisées sans réinterprétation après résultats.
- Un modèle amplitude Oracle n'annonce pas lui-même une direction ; le résultat
  de cette comparaison concerne le filtre GPT ajouté, pas sa qualité d'amplitude.
- Pas de sélection de seuil, de mois favorable, de titre à exclure ou de direction
  à inverser pour transformer ce mois en succès.

**Décision : ne pas promouvoir ce filtre haussier à partir de janvier 2026.**
Ce test historique répond à la question sur un périmètre réellement Oracle
TOP10, contrairement au petit descriptif d'octobre. Il ne démontre aucun gain
stable et n'établit pas que toute information textuelle est inutile. Une
éventuelle confirmation sur un autre mois doit garder le protocole figé ;
elle n'est pas lancée automatiquement.

## 8. Traçabilité et reproduction

Racine : `artifacts/research/us_news_oracle_top10_jan2026/20261016-v1/`.

- `protocol.json`, `cohort.parquet` : sélection et méthode figées avant résultats.
- `sql_cache_snapshot.json` : réponses et requêtes exactes réutilisées, snapshots
  source vérifiés ; SQL en lecture seule, aucune nouvelle utilisation enregistrée
  dans les tables du cache.
- `outcomes.parquet`, `prices_snapshot.parquet` : 200 couples × deux directions
  et leurs entrées de calcul locales.
- `daily_comparison.json`, `leave_one_symbol_out.json` : diagnostics prévus.
- `report.json`, `audit.json` : bilan et contrôle offline des 400 chemins,
  dates, barrières/gaps et agrégats. Tous contrôles réussis.

11 tests unitaires dédiés passent : TOP10 sans labels futurs, TP puis SL et
inverse, ordre ambigu, gaps, miroir SHORT, fenêtre exacte et qualité des prix.
Un audit offline supplémentaire a revérifié les **400 chemins** effectivement
calculés. Les anciens dossiers et les configurations restent inchangés.

```powershell
python -u -m scripts.research.us_news_oracle_top10_jan2026 --phase prepare --output artifacts/research/us_news_oracle_top10_jan2026/NOUVEAU-DOSSIER
python -u -m scripts.research.us_news_oracle_top10_jan2026 --phase run --output artifacts/research/us_news_oracle_top10_jan2026/NOUVEAU-DOSSIER
python -u -m scripts.research.us_news_oracle_top10_jan2026_audit --output artifacts/research/us_news_oracle_top10_jan2026/NOUVEAU-DOSSIER
```

L'étape prepare relit seulement le cache SQL et fige les sources. Aucune fonction
de transport GPT n'est appelée. Dossier neuf requis ; pas d'écrasement des résultats.
