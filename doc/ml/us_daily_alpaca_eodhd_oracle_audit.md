# Audit US — prix journaliers Alpaca/EODHD et sensibilité Oracle au volume

Audit réalisé le 11 octobre 2026. Verdict : **IEX n'est pas un remplacement équivalent démontré ; SIP historique est un candidat beaucoup plus convaincant, accessible lors du test avec le compte gratuit.** Aucun fournisseur de production changé, aucun entraînement, aucune écriture SQL.

Suite réalisée le même jour : [audit de l'univers complet sur 2026](us_sip_daily_universe_2026_audit.md). Les 1 790 titres ont été interrogés ; la majorité concorde, mais la couverture OTC et des divergences d'ajustement/volume interdisent de promouvoir cet échantillon seul en preuve de remplacement complet.

## Question et périmètre

Déterminer si l'abonnement EODHD reste nécessaire pour les barres quotidiennes US utilisées par l'Oracle Extreme. Deux audits distincts : écarts de prix hors volume, puis sensibilité du modèle figé à la substitution du volume et des autres champs.

- Univers de départ : `universe-file:univers_filtred_tradable.txt`, résolu par le chargeur du projet.
- Échantillonnage avant téléchargement : quatre quartiles de liquidité (moyenne close × volume local sur octobre–décembre 2024, au moins 40 observations), six titres par quartile choisis par hash déterministe. Aucun choix en fonction des écarts futurs.
- 24 titres : UHAL, OR, LGND, ALLY, ARMK, BIT, SA, WFC, SPH, UFPI, GLPI, ATEYY, AIZ, CATY, WKC, WGO, KMB, DOCN, LEGN, FTAI, HEI, BJ, SNPS, TROW.
- Histoire téléchargée : 2023-01-01 à 2026-09-30 ; mesures : 2025-01-01 à 2026-09-30.
- 23 titres comparables, 437 séances, **10 051 couples titre/séance**. ATEYY : historique vide sur IEX et SIP ; pas remplacé par un autre titre pour améliorer la couverture.
- EODHD : endpoint EOD et historique des splits, 48 requêtes initiales de ces familles. Alpaca : barres `1Day`, flux explicitement `iex` puis `sip`, `adjustment=raw`, `asof=-`, borne de fin explicite. Les relances utilisent les caches, sans redownload.
- Valeurs brutes OHLC comparées entre fournisseurs ; dates Alpaca normalisées à la journée New York. Aucun remplissage des journées absentes.

## 1. Prix hors volume

Écarts absolus relatifs à EODHD. Le « 95e percentile » est la valeur sous laquelle se situent 95 % des observations, pas une marge de confiance statistique.

| Prix | IEX : écart médian | IEX : 95e percentile | SIP : écart médian | SIP : 95e percentile |
|---|---:|---:|---:|---:|
| Ouverture | 0,2835 % | 1,6608 % | 0 % | 0 % |
| Plus haut | 0,0994 % | 1,1205 % | 0 % | 0,0117 % |
| Plus bas | 0,1061 % | 1,1620 % | 0 % | 0,0108 % |
| Clôture | 0,0364 % | 0,2662 % | 0 % | 0 % |

IEX : 12,14 % des ouvertures s'écartent de plus de 1 % ; 18,07 % des clôtures de plus de 0,1 %. Exemple LGND/2026-05-07 : ouverture EODHD 205,00, IEX 217,235, soit +5,968 %. Cela peut affecter les gaps, ranges, ATR, stops et prix d'entrée, indépendamment du volume. Cet écart n'établit pas une erreur de cotation IEX : un flux mono-place ne mesure pas la même ouverture qu'un flux consolidé.

### Cas BIT : ne pas dissimuler l'écart

Les 156 couples SIP/EODHD avec écart supérieur à 1 % concernent **BIT, du 2 janvier au 18 août 2025**, environ −2,818 % (SIP par rapport à EODHD). Le cache des actions EODHD contient un ratio `1029/1000` au 19 août 2025. Le ratio des prix et cette opération sont cohérents avec un problème de convention d'ajustement ; la source correcte n'est pas arbitrée ici et aucun prix n'a été corrigé.

Analyse complémentaire explicitement séparée, sans BIT : 9 614 observations, maximum des écarts OHLC inférieur à 0,047 %. Le rapport principal **conserve BIT**. Sur 2026, même avec BIT, aucun écart OHLC SIP/EODHD supérieur à 0,1 % dans l'échantillon.

EODHD n'est pas une vérité officielle indépendante. Accord entre fournisseurs ne prouve pas l'exactitude de toutes les barres ni l'indépendance de leurs sources.

## 2. Volume et inférence Oracle figée

Modèle : batch `model-factory-20261003082853-e98332`, dernier champion archivé daté 2024-01-08, 173 features. SHA256 du modèle : `66454360e27c8e16d3a4288ec92423c4bd9fc5871c9d70a20c40fae19203209a`.

Toutes les variantes réutilisent ce même modèle sans entraînement. Le générateur courant du projet reconstruit les features et rangs avec les options du profil archivé. Benchmark SPY et contexte selector local sont fixes. Le benchmark n'est donc pas lui-même substitué par le fournisseur testé.

### Volume observé

- Volume IEX / EODHD : médiane **4,55 %** ; 95e percentile 7,94 %.
- Volume SIP / EODHD : médiane **100,002 %** ; 95e percentile 100,083 %.
- Les features contenant volume/CMF/VWAP/OBV/Amihud représentent **0,731 % du gain LightGBM**. Ce chiffre n'est ni un impact de performance, ni une preuve d'indépendance au volume.

Prix ramenés à une convention split-only commune à partir des splits EODHD. La documentation EODHD indique un volume natif déjà ajusté des splits : il n'est pas multiplié à nouveau. Le volume Alpaca raw est multiplié par le facteur de split pour exprimer les volumes dans la même unité. Une convention erronée d'action sur titre reste une réserve, notamment BIT.

Le VWAP EODHD est ici la convention de l'adaptateur du projet, `(high + low + close)/3`, **un proxy**, pas un vrai VWAP. Alpaca retourne un VWAP de son flux. Sa substitution est isolée dans une variante dédiée.

### Résultats globaux

Les changements de probabilité sont en **points de pourcentage**, pas des changements d'AUC ou de rendement. Les recouvrements concernent uniquement les classements de l'échantillon : TOP20 % = cinq titres parmi 23 ; TOP10 = dix titres parmi 23.

| Variante par rapport à la baseline EODHD | Changement absolu moyen de probabilité | 95e percentile | Recouvrement moyen TOP20 % | Recouvrement moyen TOP10 |
|---|---:|---:|---:|---:|
| Volume × 0,03 constant, contrôle | 0 | 0 | 100 % | 100 % |
| Volume IEX uniquement | 0,6201 point | 1,9530 points | 98,810 % | 98,444 % |
| Prix IEX uniquement | 1,3003 point | 4,0066 points | 95,789 % | 96,865 % |
| VWAP IEX uniquement | 0,0545 point | 0,3100 point | 99,954 % | 99,840 % |
| IEX prix + volume + VWAP | 1,4978 point | 4,3727 points | 95,332 % | 96,247 % |
| Volume SIP uniquement | 0,0047 point | 0 point | 100 % | 100 % |
| Prix SIP uniquement | 0,0735 point | 0,3660 point | 99,954 % | 99,771 % |
| VWAP SIP uniquement | 0,0486 point | 0,2900 point | 100 % | 99,886 % |
| SIP prix + volume + VWAP | 0,1046 point | 0,4499 point | 99,954 % | 99,703 % |

Un volume multiplié par une constante laisse les ratios/z-scores et le modèle inchangés dans ce test. **La part IEX varie quotidiennement** : ce n'est pas une simple constante, d'où les changements de features et de scores. Effet maximum volume IEX : 6,246 points de probabilité ; substitution IEX complète : 14,463 points. Effet maximum SIP complet : 8,431 points, malgré une moyenne basse ; ne pas assimiler « faible en moyenne » à « nul partout ».

Les variantes isolées constituent des perturbations diagnostiques : le couple prix/VWAP peut devenir artificiellement incohérent lorsqu'un seul composant est remplacé. Leurs effets ne s'additionnent pas linéairement.

### Stabilité entre les deux années

| Flux / variante | 2025 : changement moyen / recouvrement TOP20 % | 2026 jusqu'au 30/09 : changement moyen / recouvrement TOP20 % |
|---|---:|---:|
| IEX volume seul | 0,640 point / 99,120 % | 0,594 point / 98,396 % |
| IEX complet | 1,600 point / 95,280 % | 1,361 point / 95,401 % |
| SIP volume seul | 0,0050 point / 100 % | 0,0043 point / 100 % |
| SIP complet | 0,1033 point / 99,920 % | 0,1063 point / 100 % |

## Décision et limites

1. **Non, la différence IEX/EODHD n'est pas uniquement le volume.** Les ouvertures et ranges ne sont pas assez proches pour déclarer une équivalence de backtest/exécution.
2. **L'Oracle dépend peu du volume en moyenne dans cet échantillon, mais pas zéro.** L'effet des prix IEX est plus important. Aucun résultat ne démontre que le rendement futur resterait identique.
3. **Tester le remplacement US par Alpaca SIP historique, plutôt que par IEX**, est la piste la plus pertinente. Le compte gratuit a réellement servi les historiques SIP de 23 titres lors de l'audit. Il faut ensuite qualifier la couverture de tout l'univers, les identités/actions sur titres et la parité des classements complets avant bascule.
4. Pas de preuve de non-infériorité économique : aucun label, PnL ou portefeuille utilisé. Pas d'affirmation de performance prédictive, de gain d'amplitude ou de stabilité D1/D10.
5. Le classement cross-sectionnel est reconstruit sur 23 titres, pas sur l'univers complet. Le TOP10 local est bien moins concentré que le TOP10 de production. L'univers est actuel, donc comporte un biais de survivants. Ne pas interpréter 99,95 % de recouvrement local comme une garantie de production.
6. Les deux années sont calculées avec le dernier champion archivé, pas un rejeu walk-forward des champions successifs. Warm-up limité à 2023 malgré une requête nominale du générateur plus ancienne. Le générateur courant peut différer de sa version d'entraînement.
7. **Ne pas résilier EODHD pour l'application entière sur ce seul audit** : les cours France et l'import de news constituent d'autres dépendances. Le SIP US ne fournit pas leurs équivalents.

## Reproductibilité

- Script : `scripts/research/us_daily_provider_oracle_audit.py`.
- Tests ciblés : `python -m pytest tests/test_us_daily_provider_oracle_audit.py -q --no-cov` : quatre tests passent. Le premier essai sans `--no-cov` a échoué uniquement sur le seuil de couverture global du projet, pas sur ces assertions.
- Commande : `python -u -m scripts.research.us_daily_provider_oracle_audit --output-dir artifacts/research/us_daily_provider_oracle/audit-20261011-v1`.
- Dossier : protocole avant téléchargement, réponses provider en cache sans credentials, CSV des 10 051 paires, scores par variante, importances du modèle, rapport JSON global et par année.
- Connexions SQL déclarées `SET TRANSACTION READ ONLY`. Aucune modification du modèle, de la configuration de production ou d'un batch existant. Les compteurs de quota EODHD habituels et les fichiers de recherche peuvent être mis à jour.

## Sources officielles

- [Alpaca Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) : IEX mono-place versus SIP consolidé ; historique SIP sans abonnement si la borne `end` a plus de 15 minutes ; remapping historique des tickers et accès OTC distinct.
- [Alpaca Historical Stock Bars](https://docs.alpaca.markets/us/reference/stockbars) : sélection explicite du flux, ajustements, pagination et paramètres temporels.
- [EODHD EOD API](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes) : OHLC brut, adjusted close split/dividendes, volume ajusté des splits. Ne pas confondre le champ adjusted close natif avec la convention split-only du projet.
