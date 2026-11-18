# Q051 B / B + anti-SL : audit des signaux d’activation et de reprise

18 novembre 2026. **Audit terminé : aucune des combinaisons examinées n’est suffisamment validée pour remplacer le contrôleur actuel.** Les titres sentinelles ne donnent pas, dans ce protocole, une alerte stable sur les années suivantes. Ce résultat ne démontre pas qu’aucune autre méthode ne peut fonctionner.

## Question et périmètre

Trouver une protection qui intervient avant une baisse importante, puis rend rapidement la main à la stratégie lorsque les conditions s’améliorent. Ne pas sélectionner uniquement des indicateurs qui expliquent après coup novembre2024–juin2025.

Deux stratégies témoins continues, capital4000$, 2021–1er octobre2026 :

- B : Oracle H10, TOP10% de1790titres, puis TOP10 LONG per-symbol B29 ; score>0,50 et AUC≥0,50.
- B + anti-SL : même sélection, puis veto de risque de SL première séance, sans remplacement du candidat exclu. Tête globale44variables, seuil Q90 de calibration antérieure.

Entrée directe ouvertureJ+1, position complète, SL5%, sans TP/trailing/renforcement, sortieopen11. Plafond achats1×, capacitémargin2×, risque1,25%, poids20%,20positions, minimum50$, frais8bps par opération et financement6,5% annuel. Pas de nouvelle simulation économique ici : les comptes témoins déjà calculés servent de trajectoires de référence pour diagnostiquer les signaux. Le présent audit ne leur attribue aucun nouveau rendement.

Archives : `artifacts/research/us_q051_protection_feature_audit/20261118-v1`.

## Données effectivement examinées

1443dates de décision, du31décembre2020 au30septembre2026 ; les résultats futurs non encore connus en fin de période restent inconnus.

| Bloc | Traitement |
| --- | --- |
| 173variables Oracle | Médiane et dispersion dans l’univers entier, TOP179 Oracle, B TOP10 et B+anti-SL TOP10 ; rangs transversaux recalculés sur l’univers complet de la date |
| Variables réellement utilisées par B/anti-SL | B29 et44variables anti-SL, dont trajectoires passées ; distributions dans les cohortes Oracle/B/anti-SL |
| Marché | SPY, rendements, moyennes, volatilités, drawdowns et proportion de titres au-dessus des moyennes |
| Qualité interne | Taux LONG profitables, fréquence de SL première séance, réussite d’amplitude Oracle, scores/AUC per-symbol, risques anti-SL et proportion de veto |
| Comptes témoins virtuels | Rendements passés, drawdowns et profit factor des trades déjà clôturés |
| Titres sentinelles | Prix/force relative/tendance/volatilité de1759titres admissibles ; paniers figés de5et10titres |

Le socle comprend1815mesures quotidiennes. Avec les distributions des scores modèles, variations/moyennes sur5séances et4paniers sentinelles : **5581colonnes** (5055marché/cohortes,438internes,84compte,4sentinelles). Ce sont des mesures fortement corrélées, pas5581sources indépendantes d’avantage.

Les compteurs de couverture, nombres de dossiers et trous d’archives sont conservés pour diagnostiquer la disponibilité. Ils sont exclus de la sélection économique des combinaisons relatives qualifiées. Une première analyse relative avait retenu un compteur de couverture : ses quatre règles sont donc écartées, puis le calcul a été repris sans ces variables. Les règles primaires sur niveaux bruts n’avaient pas retenu ces compteurs.

Les historiques sont issus de caches existants, sans téléchargement ni nouveaux entraînements. Chaque extraction annuelle comporte les empreintes des sources. Les129variables brutes et44rangs transversaux reconstituent les173variables du contrat Oracle.

## Causalité : trois informations différentes

1. Le taux de réussite d’amplitude Oracle mesure un grand mouvement dans un sens ou l’autre. Il n’est pas un taux de réussite LONG.
2. Le taux LONG profitable n’utilise une cohorte qu’à sa maturité complèteJ+11, même lorsqu’un SL précoce est déjà connu. Sinon les pertes rapides entreraient dans le taux avant les gagnants.
3. La fréquence de SL pendant la première séance est un indicateur distinct, disponibleJ+2. Elle peut être observée plus tôt, mais ne remplace pas le taux LONG mûr.

Les inconnus restent dans les dénominateurs de couverture, sans être transformés en pertes. Les AUC de calibration et têtes anti-SL doivent avoir une disponibilité strictement antérieure au signal. Les rendements futurs utilisés pour évaluer les alertes sont stockés dans un fichier séparé des variables observables.

## Cible de l’audit et découpage chronologique

À chaque clôtureJ, sur le **compte témoin B+anti-SL non protégé** :

- Risque20 : au moins une clôture du compte dans les20séances suivantes est inférieure de plus de5% au capital deJ.
- Reprise20 : le compte finit ces20séances en hausse et ne passe pas sous−5% entre-temps.

Ce sont des diagnostics sur un portefeuille continu, pas des labels LONG/SHORT d’un titre, ni un DD maximal intraday. Une alerte peut sembler pertinente sans que sa liquidation àJ+1 améliore le rendement : il faudrait ensuite le vérifier dans un replay économique.

Protocole primaire : sens du signal découvert en2021, confirmation des variables en2022, seuils fixés en2023, nomination possible d’une combinaison en2024, puis évaluation inchangée2025–2026. Les labels dont l’horizon déborde la frontière annuelle sont purgés pour sélectionner les variables. Une seule variable par famille et corrélation de Spearman absolue≤0,80 entre variables retenues sur la période d’apprentissage.

La direction des variables n’est jamais retournée après lecture de2025/2026. AUC0,50 signifie absence de classement utile ; AUC<0,50 signifie que le sens fixé dans le passé est devenu défavorable. L’AUC n’est pas un taux gagnant.

Toutes ces années ont déjà servi à de nombreuses recherches Alpha Trade. Même avec ce découpage chronologique, il ne s’agit pas d’un nouvel échantillon indépendant.

## Résultat des titres sentinelles

1759titres passent les contrôles de disponibilité2021–2022 : au moins95%de cours, pas de variation journalière absolue>50%, moins de80%de rendements nuls. Huit indicateurs par titre : rendements3/5/10/20, distance moyenne20, drawdown20, force relative20 contreSPY et ratio volatilité5/20. Deux cibles : alerte et reprise. **28144couples titre/indicateur/cible** examinés.

Pour chaque cible, sélectionner uniquement sur2021–2022, au plus un indicateur par symbole ; figer ensuite les paniersTOP5/TOP10 et le sens de chaque composant. Agrégation à poids égaux après classement dans la distribution d’apprentissage ; disponibilité minimale80%du panier. Aucune sélection par connaissance de la crise2025.

| Panier et cible | 2021* | 2022* | 2023 | 2024 | 2025 | 2026 partiel |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5sentinelles, alerte | 0,87 | 0,84 | 0,49 | 0,50 | 0,41 | 0,49 |
| 10sentinelles, alerte | 0,85 | 0,85 | 0,49 | 0,55 | 0,31 | 0,33 |
| 5sentinelles, reprise | 0,85 | 0,84 | 0,64 | 0,34 | 0,48 | 0,50 |
| 10sentinelles, reprise | 0,86 | 0,84 | 0,66 | 0,35 | 0,53 | 0,62 |

*Années ayant servi au choix des titres et indicateurs : chiffres optimistes de sélection, sans valeur de confirmation indépendante.* Les dernières dates2026 sans20séances de recul ne sont pas évaluées.

Les premières sentinelles d’alerte choisies dans le passé sont ACIC,FWONA,ROL,COTY,FWONK ; les dix comprennent aussi LGRDY,EXPGY,GT,WAT,DGX. **Cette liste documente un essai non confirmé, ce n’est pas une liste à utiliser en exploitation.** L’univers permet différentes classes de titres et n’impose pas un émetteur distinct par symbole ; les paniers n’assurent donc pas une diversification économique indépendante.

![Stabilité annuelle des sentinelles](../../artifacts/research/us_q051_protection_feature_audit/20261118-v1/sentinel-stability.png)

Leur apparente fidélité dans les deux premières années vient en partie du choix parmi un très grand nombre de possibilités. L’échec ultérieur ne se corrige pas honnêtement en inversant le signal après avoir vu2025. La version relative à l’historique récent a également été examinée ; elle ne fournit pas de contrôleur qualifié.

## Variables internes et combinaisons

Exemples de variables retenues uniquement grâce aux premières années, puis examinées sans changer de sens :

| Signal primaire, cible alerte | Plus faible AUC2021/22 | 2023 | 2024 | 2025 | 2026 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dispersion de volatilité inhabituelle120 dans le TOP179 Oracle, moyenne5 | 0,67 | 0,61 | 0,56 | 0,26 | 0,58 |
| Moyenne du score LONG B TOP10, moyenne5, sens inversé | 0,65 | 0,38 | 0,33 | 0,31 | 0,55 |
| Drawdown63 du compte témoin anti-SL, moyenne5 | 0,66 | 0,72 | 0,55 | 0,49 | 0,72 |

Aucun exemple ne conserve un avantage dans toutes les années suivantes. Le niveau absolu des probabilités change aussi lors du remplacement annuel des modèles : un score élevé ne signifie pas automatiquement un marché favorable.

Six règles primaires combinent à poids égaux des familles marché, interne, compte et éventuellement sentinelles. Activation : score de risque>Q90 de2023 pendant deux clôtures, avec deux familles au-dessus de leurQ75 ; sortie : score de reprise≥Q50, deux votes, une ou deux clôtures de confirmation, durée minimale trois séances.

**Les six ne s’activent jamais sur2024–2026.** Leurs seuils de niveaux absolus ne se transportent pas correctement après la calibration. Ce diagnostic de changement de distribution ne prouve pas que toutes les règles combinées sont impossibles.

Analyse secondaire annoncée après ce constat : transformer chaque variable en rang dans ses252observations passées plusJ, minimum64observations ; exiger aussi une AUC2023≥0,53 ; activer auQ85 plutôt queQ90. Ce deuxième protocole est exploratoire et ne devient pas un nouveau test indépendant.

Après exclusion des variables de disponibilité, quatre combinaisons relatives restent : trois familles ou quatre avec sentinelles, sortie après une ou deux confirmations. Critères pour nominer sur2024 : AUC≥0,55, exactitude équilibrée≥0,55, protection≤40%du temps, au moins deux activations et deux sorties. **Aucune des quatre ne passe.**

Contrôle final de la frontière de nomination : exclure aussi les décisions de fin2024 dont le diagnostic à20séances ne devient connu qu’en2025. Les14règles primaires/relatives/macro sont revérifiées sur cette plage purgée ; zéro nomination. Les tableaux annuels descriptifs ci-dessous couvrent, eux, tous les diagnostics de l’année devenus connus ensuite ; ils ne servent pas à contourner cette purge.

| Combinaison relative qualifiée | AUC2024 | AUC2025 | AUC2026 | AUC2025–26 |
| --- | ---: | ---: | ---: | ---: |
| Marché + interne + compte | 0,43 | 0,52 | 0,72 | 0,50 |
| Même ensemble + sentinelles | 0,36 | 0,49 | 0,70 | 0,50 |

Les confirmations de sortie modifient les basculements, pas ces AUC du score continu. Un résultat encourageant en2026 seul ne compense pas les inversions2024/25. Aucun des contrôleurs n’est nommé ni déployé. Les règles de confirmation prévoyaient aussi intervalles par blocs de20séances, au moins dixON/dixOFF et70%de reprises positives ; le filtre de nomination échoue en amont.

Une sensibilité supplémentaire conserve les variables/sens primaires figés et mesure leurs cibles à5et10séances, sans choisir de nouveaux seuils. Elle est archivée dans `frozen-feature-horizon-sensitivity.csv` ; elle ne révèle pas une correction évidente par le simple passage àH10. Par exemple, l’alerte des dix sentinelles reste àAUC0,30 sur2025 à10séances.

## Calendrier : pourquoi la nouvelle combinaison n’est pas une solution à fin2024

L’ancien signal de taux s’active le24décembre2024 ; sortie le16mai2025 par le taux ou le19mai par le témoin anti-SL+5%. Il a déjà laissé passer une partie de la baisse. Sa première activation historique était le10août2021, avec application le11août ; avant cela les simulations protégées et témoins sont identiques.

La nouvelle combinaison relative marché/interne/compte avec sortie une confirmation s’active le17janvier2024 et ne sort que le19juillet. Elle reste ensuite OFF pendant la baisse de fin2024–avril2025 et se réactive le9juillet2025, jusqu’au15août. Les versions avec sentinelles manquent également cette baisse. **Elles ne résolvent ni le retard initial ni les réactivations après reprise.**

![Calendrier des décisions et capital témoin](../../artifacts/research/us_q051_protection_feature_audit/20261118-v1/warning-timing-diagnostic.png)

Le graphique montre un témoin non protégé et deux états d’alerte, pas une courbe de performance des nouvelles règles. Leurs états débutent OFF en2024, contrairement au contrôleur ancien continu depuis2021 ; ne pas en déduire une comparaison économique directe. Les décisions à la clôture ne peuvent être exécutées qu’à l’ouverture suivante.

L’ancien contrôleur RATE est protégé53,35%des jours évaluables2025–2026. Ses trois sorties évaluables sont suivies d’un rendement témoin positif à20séances, mais cet échantillon minuscule et ces sorties parfois tardives ne démontrent pas une bonne capture de la reprise. Une forte proportion de sorties positives ne garantit ni un bon calendrier ni un meilleur rendement/DD.

## Inventaire SQL et compléments réellement disponibles

38tables pertinentes inventoriées en lecture seule. Les dates d’événements, périodes fiscales, dates d’observation et dates de chargement ne sont pas interchangeables.

| Données | Constat et utilisation |
| --- | --- |
| VIX,VIX9D,VIX3M,VXN,MOVE,taux10ans | 1696dates de2020à1er octobre2026 enSQL. L’ancien cache local de163dates était partiel : il ne représentait pas toute la base. RVX absent. |
| Sensibilité macro | 40mesures, plus moyennes/variations5 =120colonnes supplémentaires. Historique chargé plus tard en2026, absence d’archive de versions certifiée ; indice de marché rétrospectif, pas disponibilité historique inventée. Quatre règles relatives examinées ; aucune nomination2024, les variables macro ne remplacent pas les variables déjà retenues selon le critère de sélection passé. |
| FondamentauxSEC | 106836lignes,5720symboles avec `available_date` entre2020et1er octobre2026 ; nombreuses valeurs non nulles, dont capitalisation86376, EPS90535, revenu79650. Ils ne sont donc pas absents de la base. Un signal fondamental dédié n’est pas construit dans cet audit : vérifier accession, versions/restatements, devises/unités, identité fiscale et prix servant aux ratios avant de reconstruire leurs variations historiques. Leurs seuls compteurs ne prouvent pas un pouvoir prédictif. |
| Autres fondamentaux | Finnhub/FMP/Yahoo commencent en septembre2026 dans cette table ; pas de série comparable2021–25 substituée. |
| Options volume/OI | Observations des tables pertinentes à partir de septembre2026 ; pas rétroprojetées sur2021–25. |
| Consensus | Dates d’observation/PIT à qualifier ; la requête bornée10secondes de plage globale a échoué. Pas de plage exacte revendiquée ici et pas de période fiscale utilisée à sa place. |
| News/sentiment | Des features portent des dates depuis2015, mais le chargement est ultérieur ; les archives de première connaissance sont beaucoup plus récentes. Pas de recalculLLM ni de sentiment historique présenté comme certifié sans première disponibilité. |
| DocumentsSEC, earnings, borrow | Historiques observés récents et/ou date de publication originale non qualifiée pour ce test long ; inventoriés, pas injectés dans les règles2021–25. |

La sensibilité macro ne confirme pas davantage les indicateurs : par exemple VXN/VIX lissé donne une AUC de reprise0,61 en2024,0,53 en2025,0,49 en2026. Le taux10ans donne une AUC d’alerte0,48/0,59/0,45. Des fenêtres favorables isolées ne constituent pas une règle stable.

L’expression « audit complet » couvre ici **les variables numériques existantes décrites ci-dessus, leurs agrégats, les signaux internes et l’inventaire des autres sources**, pas tous les facteurs imaginables à dériver de toutes les tables brutes. Les fondamentauxSEC et le consensus gardent leurs réserves explicites de qualification.

## Conclusion et suite justifiée

Ne pas brancher les sentinelles ni une nouvelle combinaison de seuils dans le pipeline. Pas de petite liste de titres « fidèles » confirmée pour cet usage, et pas de preuve d’une activation/désactivation robuste par les combinaisons retenues.

Les signaux utiles pour expliquer une baisse ne sont pas forcément utiles pour la prévoir. Les taux mûrs observent une dégradation avec retard ; le compte témoin reflète déjà les pertes ; les niveaux des scores changent avec les modèles annuels ; les sentinelles choisies parmi des milliers de tests capturent facilement une coïncidence de période.

Si l’objectif prioritaire devient de limiter la perte acceptable plutôt que de prévoir la reprise, une protection mécanique avec taille réduite et réengagement progressif répond à une autre question. Elle doit être préspécifiée et comparée économiquement, sans promettre de conserver tous les gains. Ne pas conclure de cet audit qu’une telle règle a déjà été validée. Pour chercher encore un signal économique nouveau, le complément concret est la qualification des fondamentauxSEC historiques ; pas un nouveau balayage de seuils sur2024/25.

Limites : univers contemporain, prix historiques révisés, années déjà exploitées, cohortes/jours fortement dépendants, labels20séances chevauchants, peu d’épisodes indépendants. Les comptes sources héritent d’intraday partiel/repliOHLC et d’une réserve connue BIDU26février2021. Les décisions ne sont jamais certifiées avant leur source observable ; une validation prospective reste nécessaire.

## Vérifications et reproductibilité

15tests ciblés passent : échéances des labels, inconnus, agrégats journaliers, distributions d’apprentissage seules, sélection indépendante des colonnesAUC futures, règles à hystérésis, rangs passés et features macro. Des contrôles par préfixe figurent aussi dans les extractions/analyses. Aucun entraînementOracle/per-symbol, appel fournisseur/LLM, écritureSQL, ordre ou modification de production.

Principaux fichiers : `analysis-protocol.json`, `data-ready.json`, `complete-feature-inventory.csv`, `feature-screen-all-years.csv`, `frozen-selected-features.csv`, `sentinel-single-stock-audit.csv`, `sentinel-frozen-baskets.csv`, `rule-contracts.json`, `rule-metrics.csv`, `nomination-2024-purged.csv`, `adaptive-qualified-v2/`, `macro-sensitivity-v1/`, `sql-feature-availability.json`, `availability-supplement.json`, `old-policy-diagnostic-metrics.csv`, `late2024-mid2025-event-comparison.csv`, `final-audit-status.json`.

Les sources, seuils, orientations et tableaux complets sont conservés ; les diagnostics originaux non qualifiés sont archivés et identifiés, sans être promus en conclusions économiques.
