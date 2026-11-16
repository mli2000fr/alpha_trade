# Q051 — après un SL5, combien sont positifs à H10 ?

Audit descriptif des deux scénarios Q051 vol20 + régime 2021–1 octobre2026,
sans nouveau backtest ni modification des protections. Les observations se
prolongent jusqu'à leur échéance théorique, même si le trade réel a déjà été
vendu sur stop. Le dénominateur est un nombre de **trades**, pas de sociétés
indépendantes : un titre réacheté à une autre date compte à nouveau.

## Définition et résultat principal

**Positif signifie : cours strictement supérieur au prix d'achat initial**,
variation de prix brute, sans frais/dividendes hypothétiques après la vente.
H10 est la clôture de la dixième séance détenue, entrée incluse. Open11 est
l'ouverture suivante, qui correspond à l'échéance de vente habituelle de Q051.

| Scénario | Trades sortis sur SL | Au-dessus de l'achat à clôture H10 | Au-dessus de l'achat à open11 |
| --- | ---: | ---: | ---: |
| SL5, sans TP | 544 | **139 / 25,55 %** | **148 / 27,21 %** |
| SL5, TP20 | 577 | **156 / 27,04 %** | **168 / 29,12 %** |

Sur TP20, 421/577 (72,96 %) restent au prix d'achat ou en dessous à la clôture
H10. Sur le témoin, 405/544 (74,45 %). Les variations moyennes à H10 sur tous
les trades stoppés sont −4,18 % avec TP20 et −4,33 % sans TP ; médianes
−4,31 % et −4,60 %. Parmi les seuls revenus positifs, hausse moyenne +6,89 %
avec TP20 et +6,46 % sans TP.

Cela ne démontre pas qu'ignorer le stop améliore le portefeuille : l'immobilisation
du capital, les pertes plus lourdes et toutes les entrées suivantes changeraient.
Ce n'est pas une simulation de suppression du SL.

## Hausse à un moment de la période, mesure différente

| Observation depuis l'achat jusqu'à clôture H10 | Sans TP, 544 stops | TP20, 577 stops |
| --- | ---: | ---: |
| A dépassé le prix d'achat, même de très peu | 534 / 98,16 % | 568 / 98,44 % |
| A touché au moins +5 % | 210 / 38,60 % | 228 / 39,51 % |
| A touché au moins +10 % | 78 / 14,34 % | 83 / 14,38 % |
| A touché au moins +20 % | 12 / 2,21 % | 16 / 2,77 % |

Ces pics peuvent survenir **avant ou après le SL**. Ils ne prouvent pas une
récupération après le stop et ne permettent pas d'affirmer qu'un TP aurait
été touché avant le SL, notamment si les niveaux touchent la même bougie.
Le seuil simplement supérieur à zéro est très peu exigeant et n'est pas un
taux de trades gagnants ni un signal de direction exploitable à lui seul.

Contrôle plus strict après vente : au cours d'une **séance postérieure au jour
du stop**, 267/544 (49,08 %) sans TP et302/577 (52,34 %) avecTP20 ont repassé
le prix d'achat avant la clôture H10. C'est une borne inférieure : les rebonds
du jour même du stop sont exclus, faute de chronologie intraday certifiée
pour les séances traitées en repli OHLC journalier. Il ne faut pas lire ces
pourcentages comme un bénéfice réalisable en conservant tous les perdants.

## Couverture et validation

Toutes les échéances H10 et open11 sont observées :544/544 et577/577 ; dix
séances complètes par trade pour les pics. 216/214symboles distincts dans les
deux cohortes. Les données proviennent des mêmes fichiers daily figés que le
replay, sans remplacement des cours déjà archivés, avec continuité des titres
contrôlée. Le prix d'entrée correspond exactement à l'ouverture daily utilisée.

Les tout derniers CRK/KALU dépassent le1octobre pour leur échéance ; les seuls
cours de fin nécessaires sont relus dans les caches **de prix** du batchc59bed,
sans poids, AUC ou prévision de ce modèle. Les cours des deux jeux concordent
exactement sur22ancrages OHLC par titre ; seuls les jours après le1octobre sont
ajoutés localement. ALNY/IONS ont également besoin de l'ouverture open11 pour
la mesure secondaire. Aucun cours antérieur écrasé ni téléchargement.

Validation indépendantePASS sur1 121trades, compteurs, maturité et disponibilité
des prix ; isolation READ ONLY terminée sans violation. Aucun ordre, appel
fournisseur ou SQLwrite, aucune modification de configuration ou du backtest.
Limites historiques de cours révisables et d'univers contemporain maintenues.

Audit : `artifacts/research/us_q051_stop_h10_audit/20261115-v1/`, avec
`report.json`, `summary.csv`, `stopped-trades-followup.csv`, `validation.json`.
Pilote : `scripts/research/us_q051_stop_h10_audit_20261115.py`.
