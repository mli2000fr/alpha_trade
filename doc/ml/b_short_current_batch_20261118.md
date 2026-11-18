# SHORT seul — batch actuel — 2025–2026

Choix précisé par l'utilisateur le 18 novembre 2026 : utiliser **le batch actuel**, `model-factory-20261118172104-2f6a31`, sur 2025–2026. Ce test est distinct de celui sur 2021–2026 avec de nouveaux modèles annuels de recherche.

## Protocole figé avant le replay

- 4 000 $ continus du 1er janvier 2025 au **1er octobre 2026**, même fin que les comparaisons précédentes. Pas de remise à zéro annuelle.
- Oracle H10 du batch courant, scores recalculés à partir de ses archives de variables, sur les **1 790 titres** avant le classement. Dernier fold causal à chaque date, jamais le dernier modèle appliqué rétroactivement.
- TOP10 % Oracle, soit **179 candidats**, puis probabilités SHORT natives du batch : TOP10, **score >0,50**, **AUC de calibration ≥0,50**, sans remplacement. Pas d'inversion des scores LONG. Pas d'anti-SL, dont la cible est LONG.
- Têtes SHORT 2025 : 1 683 présentes dans le batch ; fit avant 2024, calibration en 2024, labels disponibles au plus tard le 31 décembre 2024. Têtes 2026 : 1 761 présentes ; fit avant 2025, calibration en 2025, disponibilité au plus tard le 31 décembre 2025. Seules les têtes nécessaires au pool Oracle sont chargées pour le test.
- Pas de tête 2024 dans ce batch : aucun remplacement inventé pour le signal du 31 décembre 2024. Cette absence interdit l'entrée issue de ce signal début janvier 2025.
- Modèles et calibrateurs **réutilisés sans entraînement**. Variables B29 recalculées par le générateur natif, depuis la même origine 2019 que l'entraînement. Les fichiers OOS servent ensuite à vérifier les probabilités, jamais à déterminer les observations admissibles avant la décision.
- Positions entières complètes, vente SHORT à l'ouverture J+1, **SL5 % au-dessus du prix exécuté**, sans TP/trailing/confirmation/renforcement ; rachat open11. Risque 1,25 %, poids maximal 20 %, vingt positions SHORT, minimum 50 $, plafond nouvelles entrées 1×, capacité margin 2×.
- Concentration de la référence B : dix entrées sur 90 jours calendaires et pause de 90 jours après trois pertes consécutives sur le même titre/côté. Sans B4/DD, régime SPY, vol20, facteurs, corrélation ou plafond sectoriel.
- Frais **8 points de base par opération**, emprunt **supposé 3 % annuel**, chargé une fois par séance, entrée et sortie comprises. Les emprunts, locates, recalls et taux historiques ne sont pas certifiés.

## Exécution et limites

Les probabilités du nouveau batch sont associées à la même matrice journalière de prix d'exécution et aux événements connus de l'étude B précédente. L'état du compte, les quantités et les historiques de pertes repartent de 4 000 $ début 2025. Il ne s'agit pas de tronquer ou de rebaser le portefeuille 2021–2026 précédent.

Le coordinateur SHORT reste isolé du moteur Winner LONG et de la production. Il utilise le compte simulé SHORT déjà testé, avec dette en titres, frais, emprunt et dividendes connus. Les hauts/bas de la séance ne peuvent pas décider une entrée à son ouverture ; un gap au-delà du stop est racheté à l'ouverture. Une plage manquante pendant une détention fait échouer le calcul.

**DD de clôture journalier**, distinct des anciens DD intraday. Pas de certification d'identité d'exécution avec le live. L'inventaire historique des dividendes/corporate actions n'est pas certifié complet. Les réserves connues DD/Qnity et TOELY sont contrôlées sur les détentions effectives.

Couverture historique des variables Oracle : minimum **92,18 %** des 1 790 titres. Le pool reste fixé à 179 sur les observations disponibles ; aucune donnée absente n'est inventée. Ce diagnostic de recherche ne modifie ni n'annule les contrôles de couverture du pipeline PAPER, dont le périmètre de dénominateur peut différer.

Historique déjà exploré, prix révisés et univers contemporain : **aucun nouveau holdout indépendant**. Aucune modification de configuration, SQL partagé, batch, compte ou ordre.

## Archives et suivi

`artifacts/research/us_b_short_current_batch/20261118-v1` : `progress.json`, protocole, Oracle, pool, classements et probabilités SHORT, empreintes des modèles réutilisés, transactions, courbe et contrôles finaux.

## Résultats définitifs du test

| Période | Capital initial | Capital final valorisé | Rendement | DD maximal de clôture | Trades clôturés | Taux gagnant |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025 | 4 000,00 $ | 2 820,59 $ | −29,49 % | −37,90 % | 304 | 28,95 % |
| 2026, jusqu'au 1er octobre | 2 820,59 $ | 2 027,45 $ | −28,12 % | −39,09 % | 250 | 26,80 % |
| **Continu 2025–2026** | **4 000,00 $** | **2 027,45 $** | **−49,31 %** | **−57,73 %** | **554** | **27,98 %** |

Les rendements du compte incluent les positions ouvertes, alors que les trades sont regroupés par date de sortie. Les DD annuels repartent du capital et du pic de l'année ; le DD continu conserve le plus haut de toute la période.

- **155 gagnants** : 6 378,52 $ de gains nets ; **399 perdants** : −8 405,38 $ de pertes nettes. Gain moyen **41,15 $ / +9,71 %**, perte moyenne **−21,07 $ / −5,31 %**. Pourcentages moyens arithmétiques par trade, sans pondération par notionnel.
- **375 rachats sur stop**, dont 41 gaps ; 179 sorties open11. Les stops représentent **67,69 %** des clôtures. Cinq positions restent ouvertes à la fin, valorisées.
- Frais de transaction **365,16 $**, emprunt simulé **164,97 $**, inclus dans le compte.
- Notionnel brut moyen à la clôture : **2 646,60 $**, soit **85,82 % du capital courant en moyenne**. Il n'y a pas de levier 2× effectivement autorisé sur les nouvelles entrées : le plafond de risque est bien 1×, malgré la capacité margin 2×.
- 4 004 signaux avant les limites de portefeuille ; première entrée exécutée **3 janvier 2025**.
- AUC SHORT sur les observations du pool Oracle scorées et aux labels mûrs avant la fin du test : **0,5065 en 2025**, **0,5112 en 2026**. Cible native SL5/open11 avant emprunt/dividendes ; ces diagnostics ne déterminent pas la sélection. Le taux gagnant du portefeuille est mesuré séparément après les coûts simulés.

**Conclusion : cette variante SHORT du batch actuel n'est pas retenue pour le trading.** Les deux années sont perdantes et l'avantage directionnel reste proche du hasard. Ce résultat ne démontre pas que toute stratégie SHORT serait impossible. Il ne se compare pas directement au −91,45 % du test précédent : le modèle, la date de départ et la durée diffèrent.

## Contrôles et corrections de données

Les 72 lots d'inférence sont terminés, **sans entraîner de nouveau modèle**. 933 têtes SHORT natives ont été nécessaires. **69 771 probabilités** recoupées avec les archives OOS du batch sont **strictement identiques**, écart maximal 0. Les archives OOS ne servent qu'à cette vérification et au diagnostic des labels mûrs, jamais à sélectionner les observations avant décision.

Empreintes des modèles et sources vérifiées ; disponibilité des folds Oracle et des têtes annuelle antérieure au signal ; seuils, TOP179/TOP10 sans remplissage, entrée J+1, plafonds de poids 20 %/exposition 1× et rachat open11 vérifiés. Réconciliation quotidienne du compte par le coordinateur déjà couvert par les 29 tests SHORT précédents ; chaque PnL est recalculé indépendamment après exécution. Aucun changement apporté à ce moteur commun. Zéro détention dans les réserves DD/Qnity ou TOELY identifiées par l'étude source ; cela ne certifie pas l'inventaire complet des corporate actions.

Deux arrêts explicites ont précédé la simulation complète :

1. **GWRE, 18 juin 2026** : volume journalier zéro, mais OHLC cohérents avec 78 bougies SIP régulières déjà en SQL. Seul le volume a été remplacé par leur somme **2 846 793**, dans la copie de replay. Les OHLC restent inchangés ; clôture 5m 107,83 contre clôture journalière 107,86, écart 0,028 %.
2. **LBRDK, 20 et 21 juillet 2026** : faux reports du cours 30,845 avec volume nul. Les 78 bougies SIP régulières de chaque séance permettent une reconstruction OHLCV locale. Ouverture/clôture corrigées : **31,03/30,36** le 20 et **29,90/30,02** le 21. La base de prix est corroborée sur la séance précédente du 17 juillet : OHL identiques, clôture 30,84 contre 30,845, écart inférieur à 0,05 %. Le problème est antérieur à la suspension d'août indiquée par [l'avis Nasdaq de fusion](https://m.nasdaqtrader.com/TraderNews.aspx?id=ECA2026-577) ; cet événement d'août n'est pas utilisé pour inventer un prix de juillet.

Un inventaire borné des dates candidates à données non positives a également identifié ATEX/DCBO/NOW le 18 juin. Ces dates n'ont pas bloqué une détention effective dans ce replay et n'ont pas été modifiées. Les contrats de sélection, modèles, probabilités et prix ayant servi aux variables d'entrée restent inchangés : les réparations concernent uniquement la matrice d'exécution du replay.

Six requêtes SQL de lecture ont fourni les preuves SIP, aucun téléchargement fournisseur ni écriture SQL. L'original du coordinateur, l'amendement, les preuves et les valeurs avant/après sont conservés : `coordinator-before-volume-recovery.py`, `replay-amendment.json`, `volume-recovery.json`, `price-recovery.json`, `candidate-bad-daily-bars.csv`. Pas de suppression de titre ou de clôture gratuite pour contourner une donnée absente ; pas de seuil réoptimisé après lecture du rendement.

![Capital et DD SHORT du batch actuel](../../artifacts/research/us_b_short_current_batch/20261118-v1/capital-comparison.png)

Rapports finaux : `report.json`, `validation.json`, `final-status.json`, `annual.csv`, `classification.csv`. Le pipeline PAPER LONG, les comptes et les ordres sont inchangés.
