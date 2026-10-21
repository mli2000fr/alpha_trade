# Lecture de Wayland Quant Book : pistes pour Alpha Trade

Date : 21 octobre 2026. **Revue documentaire uniquement : aucun nouveau backtest, entraînement, appel LLM, téléchargement de données financières ou changement de production.** La grille B4 v2 déjà lancée n’est pas modifiée.

## Conclusion

Le livre est utile pour organiser et contrôler une stratégie. Je n’y ai pas trouvé de preuve directement transposable d’un signal LONG/SHORT rentable sur notre TOP10 Oracle. Mon choix pour la suite serait **une vérification de robustesse de la grille, puis une expérience bornée de concentration/corrélation du portefeuille**, pas un nouveau grand modèle directionnel.

Source : [Wayland Zhang, AI Quantitative Trading: From Zero to One](https://waylandz.com/quant-book/). Parcours des 22 chapitres principaux, des quatre annexes et de l’index des ressources ; approfondissement des chapitres 5/7/9/12–20. Les 30 articles de contexte et chaque lien externe n’ont pas tous été lus. Les propositions ci-dessous sont mon adaptation au projet, **pas des résultats expérimentaux du livre ou d’Alpha Trade**.

## Lecture des chapitres

| Chapitre | Sujet | Application et avis pour Alpha Trade |
| --- | --- | --- |
| [1](https://waylandz.com/quant-book/%E7%AC%AC01%E8%AF%BE%EF%BC%9A%E9%87%8F%E5%8C%96%E4%BA%A4%E6%98%93%E5%85%A8%E6%99%AF%E5%9B%BE/) | Vue d’ensemble | Séparer amplitude, décision, risque et exécution ; ne pas confondre architecture et alpha. |
| [2](https://waylandz.com/quant-book/%E7%AC%AC02%E8%AF%BE%EF%BC%9A%E9%87%91%E8%9E%8D%E5%B8%82%E5%9C%BA%E4%B8%8E%E4%BA%A4%E6%98%93%E5%9F%BA%E7%A1%80/) | Marchés et ordres | Coûts, liquidité et différences US/CN/FR ; déjà largement structurés. |
| [3](https://waylandz.com/quant-book/%E7%AC%AC03%E8%AF%BE%EF%BC%9A%E6%95%B0%E5%AD%A6%E4%B8%8E%E7%BB%9F%E8%AE%A1%E5%9F%BA%E7%A1%80/) | Statistique | Queues épaisses, dépendance et incertitude ; blocs de dates plutôt que trades IID. |
| [4](https://waylandz.com/quant-book/%E7%AC%AC04%E8%AF%BE%EF%BC%9A%E6%8A%80%E6%9C%AF%E6%8C%87%E6%A0%87%E7%9A%84%E7%9C%9F%E5%AE%9E%E8%A7%92%E8%89%B2/) | Indicateurs | Transformations de prix, pas information magique nouvelle ; éviter une nouvelle grille RSI/MACD. |
| [5](https://waylandz.com/quant-book/%E7%AC%AC05%E8%AF%BE%EF%BC%9A%E7%BB%8F%E5%85%B8%E7%AD%96%E7%95%A5%E8%8C%83%E5%BC%8F/) | Familles de stratégies | Tendance, réversion, portefeuille ; suivi déjà testé, réversion récente non rentable. |
| [6](https://waylandz.com/quant-book/%E7%AC%AC06%E8%AF%BE%EF%BC%9A%E6%95%B0%E6%8D%AE%E5%B7%A5%E7%A8%8B%E7%9A%84%E6%AE%8B%E9%85%B7%E7%8E%B0%E5%AE%9E/) | Données | Identités, ajustements, calendrier, survivants et provenance ; complétude future de la cohorte reste une réserve. |
| [7](https://waylandz.com/quant-book/%E7%AC%AC07%E8%AF%BE%EF%BC%9A%E5%9B%9E%E6%B5%8B%E7%B3%BB%E7%BB%9F%E7%9A%84%E9%99%B7%E9%98%B1/) | Pièges du backtest | Choix parmi de nombreux essais, coûts et validation chronologique : priorité après notre grille. |
| [8](https://waylandz.com/quant-book/%E7%AC%AC08%E8%AF%BE%EF%BC%9ABeta%E3%80%81%E5%AF%B9%E5%86%B2%E4%B8%8E%E5%B8%82%E5%9C%BA%E4%B8%AD%E6%80%A7/) | Bêta et couverture | Attribuer le rendement avant d’envisager une couverture ; celle-ci n’invente pas d’alpha. |
| [9](https://waylandz.com/quant-book/%E7%AC%AC09%E8%AF%BE%EF%BC%9A%E7%9B%91%E7%9D%A3%E5%AD%A6%E4%B9%A0%E5%9C%A8%E9%87%8F%E5%8C%96%E4%B8%AD%E7%9A%84%E5%BA%94%E7%94%A8/) | Apprentissage supervisé | Cible exécutable, faibles signaux complémentaires ; déjà beaucoup de NO_GO directionnels. |
| [10](https://waylandz.com/quant-book/%E7%AC%AC10%E8%AF%BE%EF%BC%9A%E4%BB%8E%E6%A8%A1%E5%9E%8B%E5%88%B0Agent/) | Modèle vers décision | Oracle d’amplitude n’est pas une probabilité LONG ; décision et sizing restent séparés. |
| [11](https://waylandz.com/quant-book/%E7%AC%AC11%E8%AF%BE%EF%BC%9A%E4%B8%BA%E4%BB%80%E4%B9%88%E9%9C%80%E8%A6%81%E5%A4%9A%E6%99%BA%E8%83%BD%E4%BD%93/) | Multi-agents | Frontières et veto risque ; pas raison de multiplier les appels LLM ou les services. |
| [12](https://waylandz.com/quant-book/%E7%AC%AC12%E8%AF%BE%EF%BC%9A%E5%B8%82%E5%9C%BA%E7%8A%B6%E6%80%81%E8%AF%86%E5%88%AB/) | Régimes | Distinguer tendance, range, crise et transition ; intérêt à tester, pas prédiction parfaite. |
| [13](https://waylandz.com/quant-book/%E7%AC%AC13%E8%AF%BE%EF%BC%9ARegime%E8%AF%AF%E5%88%A4%E4%B8%8E%E7%B3%BB%E7%BB%9F%E6%80%A7%E5%B4%A9%E6%BA%83%E6%A8%A1%E5%BC%8F/) | Erreurs de régime | Mesurer retard, faux changements et état incertain ; complément potentiel au B4. |
| [14](https://waylandz.com/quant-book/%E7%AC%AC14%E8%AF%BE%EF%BC%9ALLM%E5%9C%A8%E9%87%8F%E5%8C%96%E4%B8%AD%E7%9A%84%E5%BA%94%E7%94%A8/) | LLM | Extraction factuelle sourcée plutôt que prévision directionnelle générale ; continuité du pilote SEC. |
| [15](https://waylandz.com/quant-book/%E7%AC%AC15%E8%AF%BE%EF%BC%9A%E9%A3%8E%E9%99%A9%E6%8E%A7%E5%88%B6%E4%B8%8E%E8%B5%84%E9%87%91%E7%AE%A1%E7%90%86/) | Gestion du risque | Risque par position/portefeuille/compte ; composantes B4 dans la grille, pas DD garanti. |
| [16](https://waylandz.com/quant-book/%E7%AC%AC16%E8%AF%BE%EF%BC%9A%E7%BB%84%E5%90%88%E6%9E%84%E5%BB%BA%E4%B8%8E%E9%A3%8E%E9%99%A9%E6%9A%B4%E9%9C%B2%E7%AE%A1%E7%90%86/) | Construction du portefeuille | Corrélations, covariance stabilisée, facteurs ; piste la plus directement exploitable. |
| [17](https://waylandz.com/quant-book/%E7%AC%AC17%E8%AF%BE%EF%BC%9A%E5%9C%A8%E7%BA%BF%E5%AD%A6%E4%B9%A0%E4%B8%8E%E7%AD%96%E7%95%A5%E8%BF%9B%E5%8C%96/) | Évolution des modèles | Distinguer dérive des données et perte de validité ; pas réentraînement automatique sur pertes. |
| [18](https://waylandz.com/quant-book/%E7%AC%AC18%E8%AF%BE%EF%BC%9A%E4%BA%A4%E6%98%93%E6%88%90%E6%9C%AC%E5%BB%BA%E6%A8%A1%E4%B8%8E%E5%8F%AF%E4%BA%A4%E6%98%93%E6%80%A7/) | Coûts et tradabilité | Coûts variables et exécutions manquées ; approfondissement des hypothèses de la grille. |
| [19](https://waylandz.com/quant-book/%E7%AC%AC19%E8%AF%BE%EF%BC%9A%E6%89%A7%E8%A1%8C%E7%B3%BB%E7%BB%9F%20-%20%E4%BB%8E%E4%BF%A1%E5%8F%B7%E5%88%B0%E7%9C%9F%E5%AE%9E%E6%88%90%E4%BA%A4/) | Exécution | Chronologie, fills partiels, latence, référentiel ; ni OHLC ni PAPER ne certifient le live. |
| [20](https://waylandz.com/quant-book/%E7%AC%AC20%E8%AF%BE%EF%BC%9A%E7%94%9F%E4%BA%A7%E8%BF%90%E7%BB%B4/) | Exploitation | Reprise, cohérence courtier, identité d’intention ; mesurer ce qui existe avant d’ajouter. |
| [21](https://waylandz.com/quant-book/%E7%AC%AC21%E8%AF%BE%EF%BC%9A%E9%A1%B9%E7%9B%AE%E5%AE%9E%E6%88%98/) | Projet intégrateur | Architecture modulaire pédagogique ; pas un remplacement du moteur existant. |
| [22](https://waylandz.com/quant-book/%E7%AC%AC22%E8%AF%BE%EF%BC%9A%E6%80%BB%E7%BB%93%E4%B8%8E%E8%BF%9B%E9%98%B6%E6%96%B9%E5%90%91/) | Synthèse | Simplicité, séparation des responsabilités et progression ; pas stratégie rentable fournie. |


Les annexes A/B/C/D apportent respectivement le journal ordre/fill, les modes de défaillance, les frontières d’automatisation et une FAQ. L’index des ressources indique lui-même des vérifications anciennes : ses prix, droits et offres de données ne sont pas une référence contractuelle actuelle. Ne réactiver aucune source bloquée sur cette base.

## Priorité 1 — Qualifier la robustesse de la grille avant d’en retenir un profil

Le [chapitre 7](https://waylandz.com/quant-book/%E7%AC%AC07%E8%AF%BE%EF%BC%9A%E5%9B%9E%E6%B5%8B%E7%B3%BB%E7%BB%9F%E7%9A%84%E9%99%B7%E9%98%B1/) insiste sur la sélection parmi de nombreux essais, la sensibilité aux paramètres et la chronologie de validation. Notre grille comprend 288 politiques LONG/SHORT, évaluées sur deux années ; 576 lignes annuelles ne constituent pas 576 observations indépendantes ni 576 stratégies différentes.

Adaptation proposée, après finalisation et audit de la grille en cours :

1. Publier toute la grille et ses voisinages SL/trailing/H/TP, pas seulement le meilleur capital final.
2. Décrire les profils dont les voisins restent raisonnables sur rendement, DD, coûts et durée ; annoncer les critères avant le classement, sans transformer cette description en validation.
3. Mesurer dépendance à chaque symbole et à des blocs de dates. Une suppression de symbole exige un vrai rejeu du cash/sizing/admissions : ne pas simplement soustraire son PnL.
4. Stresser coûts, entrée retardée d’une barre et gaps. Rejouer le portefeuille, car changer un fill change capital disponible et transactions suivantes.
5. Geler un candidat avant des données réellement nouvelles. **2025 et janvier–septembre 2026 déjà inspectés ne redeviennent pas un holdout.** L’intraday 2024 n’est pas qualifié pour cette cohorte ; ne pas inventer sa couverture.

Le projet possède déjà `bootstrap_trades`, `parameter_sensitivity`, `block_bootstrap_sharpe`, `multiple_testing_correction` et une fonction nommée `deflated_sharpe_ratio` dans [statistical_validation](../../backtesting/statistical_validation.py). Présence de fonctions ≠ certification de leurs hypothèses ni raccordement à cette grille. Leur audit précède leur utilisation comme critère de promotion ; ne pas appliquer aveuglément un nombre d’essais standard ou un bootstrap IID de trades chevauchants.

## Priorité 2 — Diversifier les risques réels, pas seulement les noms de titres

Le [chapitre 16](https://waylandz.com/quant-book/%E7%AC%AC16%E8%AF%BE%EF%BC%9A%E7%BB%84%E5%90%88%E6%9E%84%E5%BB%BA%E4%B8%8E%E9%A3%8E%E9%99%A9%E6%9A%B4%E9%9C%B2%E7%AE%A1%E7%90%86/) traite de covariance stabilisée, d’expositions communes et de corrélation. Cela suggère d’examiner si dix valeurs Oracle représentent quelques paris semblables.

**Hypothèse à tester :** à sélection et protections constantes, éviter de cumuler des entrées fortement corrélées pourrait améliorer le compromis rendement/DD. Ce n’est pas une hypothèse de meilleure prédiction LONG/SHORT.

Contrat proposé, à figer avant calcul :

- Même Oracle, ordre de score, confirmation d’entrée, calendrier, coûts et règles de sortie ; pas de remplacement par des titres hors TOP10.
- Corrélations calculées sur des rendements disponibles avant décision ; ni trajectoires futures ni matrice calculée sur toute l’année.
- Un seul contrôle de concentration supplémentaire, déterminé à l’avance. Si une entrée est refusée, laisser le cash ; ne pas ajouter une grille de seuils.
- Comparaison appariée à un témoin de plus petite taille/exposition : un DD inférieur avec beaucoup moins d’argent engagé ne suffit pas à établir une meilleure sélection.
- Mesurer rendement, DD, pertes de queue, capital moyen engagé, occasions refusées et concentration du PnL ; coûts et quantités entières réellement rejoués.
- Pas de secteur historique supposé à partir du secteur actuel. Une première variante price-only évite cette assimilation ; les historiques quotidiens communs et leurs ajustements restent à qualifier.
- Une matrice avec shrinkage peut stabiliser l’estimation ; elle ne rend pas fiables par magie des corrélations de crise inconnues. Commencer par le contrôle existant avant une allocation sophistiquée.

**Ce n’est pas un module entièrement absent.** [PortfolioBuilder](../../risk_management/portfolio_builder.py) contient déjà des filtres de corrélation et des branches d’exposition factorielle ; [correlation_filter](../../risk_management/correlation_filter.py) fournit notamment `filter_correlated_signed`. La grille actuelle documente au contraire qu’elle ne reproduit pas tout PortfolioBuilder ni ses contrôles sectoriels/corrélation. Le travail est donc d’identifier et de comparer un raccordement précis, pas d’annoncer l’invention de cette fonction ou un gain déjà établi.

## Priorité 3 — Diagnostiquer les transitions de régime sans chercher un veto miracle

Les [chapitres 12](https://waylandz.com/quant-book/%E7%AC%AC12%E8%AF%BE%EF%BC%9A%E5%B8%82%E5%9C%BA%E7%8A%B6%E6%80%81%E8%AF%86%E5%88%AB/) et [13](https://waylandz.com/quant-book/%E7%AC%AC13%E8%AF%BE%EF%BC%9ARegime%E8%AF%AF%E5%88%A4%E4%B8%8E%E7%B3%BB%E7%BB%9F%E6%80%A7%E5%B4%A9%E6%BA%83%E6%A8%A1%E5%BC%8F/) examinent l’incertitude et les erreurs de changement de régime.

Notre adaptation serait d’abord descriptive : pertes lors de tendance stable, range et transition, délai du signal SPY, faux changements, persistance de la tendance du titre. Une règle définie uniquement après les plus mauvaises semaines ne démontre aucune anticipation. Un HMM éventuel doit être ajusté sur le passé et produire un état filtré à la décision, pas un historique lissé avec le futur.

Le B4 possède déjà une hystérésis ; les protections dynamiques et le sélecteur de trois profils testés le 14 octobre ont été défavorables. Ce ne serait donc pas une raison suffisante pour relancer les mêmes expériences sous le nom « régime intelligent ». Une nouvelle version demanderait une différence précise et préenregistrée. Aucune réduction d’exposition ni règle live n’est imposée par cette revue.

## Priorité 4 — LLM comme extracteur d’information, pas comme probabilité de marché

Le [chapitre 14](https://waylandz.com/quant-book/%E7%AC%AC14%E8%AF%BE%EF%BC%9ALLM%E5%9C%A8%E9%87%8F%E5%8C%96%E4%B8%AD%E7%9A%84%E5%BA%94%E7%94%A8/) privilégie l’extraction, la comparaison de publications et les résultats structurés, avec séparation du risque et de l’exécution.

Application possible : pour une annonce financière nouvelle, extraire émetteur, métrique, période, unité, valeur actuelle/précédente, guidance, source et heure de disponibilité. Conserver citations, incertitudes et déduplication, puis mesurer l’apport de ces faits au-delà de la réaction du prix.

C’est une continuité de notre travail SEC/news/revenus, **pas une nouvelle preuve de direction**. Une bonne tonalité ou un score de confiance LLM n’est ni une probabilité calibrée de hausse ni un rendement attendu. Aucun nouvel appel payant n’a été fait pour cette lecture.

## Priorité 5 — Suivi de validité et fidélité d’exécution

Le [chapitre 17](https://waylandz.com/quant-book/%E7%AC%AC17%E8%AF%BE%EF%BC%9A%E5%9C%A8%E7%BA%BF%E5%AD%A6%E4%B9%A0%E4%B8%8E%E7%AD%96%E7%95%A5%E8%BF%9B%E5%8C%96/) distingue dérive des entrées, qualité des données et baisse de performance. Pour Oracle, suivre séparément :

- qualité des données et univers effectivement scoré ;
- détection d’amplitude sur labels arrivés à maturité ;
- monétisation de cette amplitude et frais d’exécution.

Une hausse des pertes n’implique pas automatiquement qu’il faut réentraîner Oracle. On peut avoir la bonne amplitude mais une mauvaise entrée ou une exposition concentrée. Les labels H20 ne peuvent pas servir de diagnostic réalisé dès J+1.

Les [chapitres 18](https://waylandz.com/quant-book/%E7%AC%AC18%E8%AF%BE%EF%BC%9A%E4%BA%A4%E6%98%93%E6%88%90%E6%9C%AC%E5%BB%BA%E6%A8%A1%E4%B8%8E%E5%8F%AF%E4%BA%A4%E6%98%93%E6%80%A7/) et [19](https://waylandz.com/quant-book/%E7%AC%AC19%E8%AF%BE%EF%BC%9A%E6%89%A7%E8%A1%8C%E7%B3%BB%E7%BB%9F%20-%20%E4%BB%8E%E4%BF%A1%E5%8F%B7%E5%88%B0%E7%9C%9F%E5%AE%9E%E6%88%90%E4%BA%A4/) rappellent les écarts entre prix observé et fill. À exploiter plus tard : coûts par liquidité, décalages, fills partiels et journal de décision/ordre/fill. Nos barres SIP 5m ne fournissent ni profondeur de carnet, ni file d’attente, ni impact de nos propres ordres ; PAPER ne les prouve pas davantage. Ne pas remplacer les hypothèses manquantes par des données inventées.

Le [chapitre 20](https://waylandz.com/quant-book/%E7%AC%AC20%E8%AF%BE%EF%BC%9A%E7%94%9F%E4%BA%A7%E8%BF%90%E7%BB%B4/) donne aussi un cas concret de course d’exécution : renvoyer une liquidation parce qu’une position en cache paraît encore ouverte peut créer une position inverse. Le projet ayant déjà des protections/reprises, cela appelle un audit ciblé des intentions et de la réconciliation, pas une modification de courtier pendant cette revue.

## Pistes à ne pas relancer simplement parce qu’elles sont dans le livre

Références du projet : [registre des expériences](experiences_done.md).

- Réversion résiduelle SPY/secteur/PCA et réversion intraday : essais récents sans avantage stable.
- Régime → profils SL/trailing/TP, ou apprentissage d’un sélecteur : déjà testés, non promus.
- Complémentarité de faibles signaux sur TOP10 : déjà évaluée ; plusieurs scores corrélés ne créent pas plusieurs informations indépendantes.
- Un modèle plus gros, du RL ou plusieurs agents LLM : pas d’information additionnelle démontrée.
- Acheter options/straddles uniquement parce que l’amplitude est forte : il faudrait comparer volatilité attendue et prix de la protection, avec chaînes/quotes et coûts qualifiés. Les barres d’options seules ne suffisent pas.
- Couverture SPY systématique : le [chapitre 8](https://waylandz.com/quant-book/%E7%AC%AC08%E8%AF%BE%EF%BC%9ABeta%E3%80%81%E5%AF%B9%E5%86%B2%E4%B8%8E%E5%B8%82%E5%9C%BA%E4%B8%AD%E6%80%A7/) est utile pour attribuer bêta/alpha, pas une garantie que la couverture améliore le rendement net.
- Renforcement d’un gagnant : testé récemment ; pas d’avantage stable contre la demi-position témoin.

## Réserves sur le livre : lire de façon critique

Ce sont des supports pédagogiques, souvent avec cas synthétiques et chiffres illustratifs, pas des performances de stratégies transposables.

Deux points techniques méritent correction lors d’une implémentation :

1. Le chapitre 7 formule un contrôle disant que les labels ne doivent utiliser que le passé. Pour un apprentissage supervisé, **la cible utilise justement un futur réalisé** ; l’exigence correcte est que les features soient disponibles à la décision et que tous les labels utilisés pour entraîner aient mûri avant le cutoff, avec purge des chevauchements. Ne pas en déduire que la cible Oracle parcours est interdite.
2. L’inverse de volatilité n’assure pas, en général, des contributions au risque égales lorsque corrélations et structures de covariance diffèrent. Il faut distinguer cette approximation du vrai calcul des contributions de portefeuille.

Ne pas recopier des pourcentages universels de dégradation live ou des seuils ADX/PSI/Kelly comme s’ils avaient été validés sur Alpha Trade. Le score d’amplitude Oracle ne peut pas entrer directement dans Kelly comme probabilité de succès directionnel.

## Décision proposée

**D’abord terminer la grille B4 v2 et vérifier la robustesse des résultats existants ; ensuite, si nouveau GO, une seule expérience de concentration/corrélation sur la même stratégie.** Cette piste exploite le portefeuille et les prix déjà disponibles sans promettre de résoudre D1/D10 et sans changer Oracle. L’analyse des régimes et la collecte événementielle restent complémentaires, pas des raisons de rouvrir simultanément toutes les expériences rejetées.

