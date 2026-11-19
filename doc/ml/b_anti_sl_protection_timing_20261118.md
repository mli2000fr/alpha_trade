# B + anti-SL — réexamen des conditions d'activation et de reprise

Complément demandé pendant le test des quatre protections partielles/totales du 18 novembre 2026. **Les quatre replays initiaux restent figés.** Ce complément distingue le calendrier des alertes du coût de la protection ; aucune nouvelle règle n'est activée dans le pipeline PAPER.

## Problèmes constatés

- Le taux gagnant LONG mûr n'est disponible qu'après l'horizon complet. Lui ajouter une fenêtre récente de vingt séances et une référence de 120 séances introduit un retard supplémentaire ; il ne mesure pas immédiatement les pertes que subit le portefeuille.
- L'ancienne sortie exige un rendement positif de plus de 5 % sur vingt séances pendant cinq clôtures. Elle peut manquer une partie de la reprise.
- Dans la première reprise progressive figée, l'ancre fixée au début de PROBE peut aussi retarder le retour au budget complet après un faux rebond. Le compte virtuel peut avoir une bonne tendance récente sans avoir récupéré cette ancienne ancre. Cette limite ne sera pas corrigée discrètement dans les quatre tests déjà lancés.
- L'audit antérieur de 5 581 variables et des sentinelles n'a qualifié aucun contrôleur robuste. Le présent travail ne relance pas ce balayage ni un nouvel entraînement.

## Diagnostic borné, distinct d'un backtest économique

Compte virtuel **B + anti-SL sans protection**, même historique continu 2021–1er octobre 2026. Les règles consultent seulement ses valeurs déjà connues à la clôture ; une décision ne peut être exécutée qu'à l'ouverture suivante. Ce compte reste calculé même lorsque le portefeuille réel protégé investit peu, afin d'éviter un verrouillage en cash sans observation de la reprise.

Deux familles fixes, sans recherche des meilleurs seuils :

1. **Pertes récentes** : drawdown sur vingt séances d'au moins 8 %, avec rendement cinq séances négatif pendant deux clôtures.
2. **Accumulation de pertes normalisées** : rendement journalier divisé par l'écart-type des soixante rendements précédents ; accumulation négative avec tolérance 0,25 et seuil 4. Ce score séquentiel n'est ni une probabilité de baisse ni un modèle entraîné.

Deux familles de reprise : cinq séances positives et valeur supérieure à EMA10 pendant deux clôtures, ou accumulation positive normalisée de seuil 3 avec rendement cinq séances positif. Maintien minimum en protection trois séances, remise à zéro des accumulateurs aux transitions. Le croisement de ces deux activations et deux sorties représente quatre règles, pas une grande grille de seuils.

Le premier audit v1 examine les deux couples directs. Le croisement v2 a été déclaré **après inspection des diagnostics de 2024/25** : c'est une analyse secondaire exploratoire, pas une nouvelle validation indépendante. Les années ont déjà été exploitées dans de nombreux essais.

Les fenêtres futures sont séparées des variables observables et servent seulement à évaluer : présence d'une clôture inférieure de plus de 5 % dans les dix séances suivantes, et reprise dix séances positive sans cette baisse. Les jours se chevauchent fortement ; les pourcentages ne constituent pas autant d'événements indépendants. **Aucun rendement, DD ou coût de portefeuille nouveau n'est déduit de ces masques ON/OFF.**

Sur 2025–2026, l'ancienne règle protège 62,89 % des fenêtres de risque ainsi définies et reste active dans 48,90 % des fenêtres de reprise. La règle DD20/EMA10 ramène ces deux proportions à 15,46 %/18,06 % : moins de temps bloqué, mais beaucoup de fenêtres risquées non couvertes. Les nouveaux signaux ne peuvent donc pas être déclarés meilleurs simplement parce qu'ils sortent plus tôt. Les résultats complets, y compris 2021–2023 et 2024, sont conservés sans inversion du sens ou réglage des seuils après coup.

Dans la période fin 2024–mi-2025 : ancienne activation 24 décembre, sortie 19 mai ; DD20/EMA10 active 10 décembre mais sort 6 janvier, réactive 12 février, sort 19 mars, puis réactive 4 avril. L'accumulation normalisée était déjà active depuis 6 septembre 2024 et ne sort que 6 juin 2025 : elle aurait aussi bloqué des hausses avant la crise. Un bon repérage visuel de quelques dates ne prouve pas un meilleur rendement/DD.

Archives : `artifacts/research/us_b_protection_timing/20261118-v1` et `20261118-v2-cross` : protocoles, variables, cibles séparées, états, métriques et transitions. Dix-huit contrôles de préfixe vérifient la causalité des états entre les deux analyses.

![Diagnostic ON/OFF, sans performance simulée](../../artifacts/research/us_b_protection_timing/20261118-v1/timing-comparison.png)

## Un cas économique supplémentaire : conditions locales et retour sans ancienne ancre

Une seule nouvelle variante est lancée séparément, avec **la même politique de base permanente et partie pilotée à 50 %**, les mêmes signaux, capital, frais, SL5/open11 et limites natives que le test partiel initial.

- **ON** : drawdown du compte virtuel sur vingt séances ≤−8 % et rendement cinq séances négatif pendant deux clôtures, lorsque le portefeuille n'est pas déjà en phase PROTECTED.
- **PROTECTED** : liquidation de la seule partie pilotée à l'ouverture suivante ; ensuite vol20 + régime sur cette partie, base normale conservée. Pas de nouvelle vente répétée tant que la phase reste PROTECTED.
- **PROBE** : après au moins trois séances de protection et deux clôtures de rendement cinq séances positif avec compte virtuel au-dessus d'EMA10. La moitié du budget piloté normal est autorisée ; pas de filtre SPY/vol20 sur cette fraction.
- **NORMAL** : cinq nouvelles clôtures consécutives avec rendement cinq séances positif, compte virtuel au-dessus d'EMA10 et rendement dix séances positif. **Aucune obligation de retrouver une ancienne ancre ou le sommet historique.**
- Une nouvelle dégradation de deux clôtures peut remettre ON depuis PROBE ou NORMAL. Il n'y a donc pas de pause arbitraire de trois mois, ni de liquidation répétée à chaque bougie.

Les valeurs 8 %/5/10/20 séances et les confirmations sont des valeurs de travail figées, pas des seuils optimaux démontrés. Cette variante secondaire a été formulée après les observations historiques déjà connues. Elle doit être jugée sur son compte complet, frais, réallocations, faux rebonds et années défavorables compris ; aucun bénéfice anticipé n'est revendiqué.

Archives : `artifacts/research/us_b_protection_timing_replay/20261118-v1`. Calcul et contrôles terminés le 19 novembre 2026 ; bilan ci-dessous.

## Correction technique découverte par le nouveau calendrier

Un premier essai a révélé un stop déjà exécuté à l'ouverture alors que le journal de campagne portait encore la quantité de la veille. La réduction partielle calculée sur ce journal tentait alors de revendre une position déjà clôturée. L'exécution utilise désormais **la quantité réellement restante dans le broker simulé**, après les stops/open11 prioritaires. Aucune vente double ni continuation optimiste n'est admise.

Les trois variantes encore en cours ont été arrêtées et archivées, puis relancées après correction ; le cas secondaire échoué est aussi conservé. Les deux contrôles terminés sont inchangés, car le correctif touche uniquement la branche partielle après le retour immédiat de la branche totale. **Douze tests ciblés passent**, dont le cas reproduisant un stop à la même ouverture que la réduction. Empreintes et amendement : `open-stop-fix-amendment.json`, sources antérieures et dossiers `cases-before-open-stop-fix` dans chaque étude. Aucun seuil ou calendrier n'a été changé à cause de cet incident technique.

Aucune écriture SQL, aucun appel fournisseur/LLM, aucun ordre ou changement de production. Les réserves historiques de prix, dividendes et intraday de la référence restent à examiner au bilan final.

## Bilan économique des six cas

2021–1er octobre 2026, 4 000 $ continus, SL5/open11, mêmes signaux et frais natifs. DD maximal intraday ; taux gagnant par campagne entièrement clôturée, fragments de ventes agrégés. La période d'arrêt de fin 2024 n'est pas le seul critère de jugement.

| Cas | Capital final | Rendement | DD maximal | Taux gagnant | Activations |
| --- | ---: | ---: | ---: | ---: | ---: |
| B + anti-SL témoin | 16 140,82 $ | +303,52 % | −34,98 % | 38,13 % | 0 |
| Totale, ancienne sortie | 7 667,96 $ | +91,70 % | −42,19 % | 36,48 % | 15 |
| Partielle, ancienne sortie | 7 006,97 $ | +75,17 % | −39,96 % | 36,74 % | 15 |
| Totale, reprise progressive | 5 819,44 $ | +45,49 % | −36,43 % | 36,20 % | 15 |
| Partielle, reprise progressive | 7 217,88 $ | +80,45 % | −37,38 % | 36,60 % | 15 |
| **Partielle, nouvelles conditions locales** | **8 365,90 $** | **+109,15 %** | **−36,83 %** | **35,19 %** | **25** |

La nouvelle variante est meilleure en rendement que les quatre protections, et réduit le DD par rapport à l'ancienne protection totale. **Elle reste inférieure au témoin sans protection sur les deux critères** : seulement 35,96 % du gain cumulé du témoin conservé, DD dégradé de 1,85 point. Aucune amélioration suffisamment démontrée pour activer la règle en PAPER.

## Activation et reprise : ce qui a changé, ce qui échoue encore

Les dates suivantes sont les décisions de clôture ; ventes et nouvelles tailles seulement à l'ouverture suivante.

| Étape | Ancienne règle | Nouvelle règle locale |
| --- | --- | --- |
| Première alerte fin 2024 | 24 décembre | 10 décembre |
| Première reprise réduite | Pas de phase intermédiaire | 6 janvier 2025 |
| Rechute | Protection continue | Nouvelle alerte le 12 février |
| Nouveau rebond | Protection continue | Reprise réduite le 19 mars |
| Rechute d'avril | Protection continue | Nouvelle alerte le 4 avril |
| Reprise de mai | Retour normal le 19 mai | Reprise réduite le 8 mai, normale le 16 mai |

Le retour complet normal du nouveau cas ne devance l'ancien que d'une séance d'exécution en mai : décision vendredi 16/exécution lundi 19 mai, contre lundi 19/exécution mardi 20 mai. La nouvelle règle réinvestit plus tôt en janvier/mars, mais ce sont des faux départs avant d'autres baisses. Il ne faut donc pas confondre reprise rapide et reprise correcte.

Sur la fenêtre du 6 novembre 2024 au 30 juin 2025, rendement du compte : témoin **−24,27 %**, ancienne protection totale **−23,43 %**, nouvelle protection partielle **−24,21 %**. DD de clôture dans cette fenêtre : respectivement −34,08 %, −31,37 % et −33,84 %. Le nouveau calendrier ne résout presque pas cette période difficile. Du 1er juillet 2025 au 1er octobre 2026, le nouveau cas reprend bien (+87,20 %, contre +63,49 % au témoin), mais à partir d'un capital nettement inférieur : les gains manqués auparavant ne sont pas récupérés mécaniquement.

Le déclenchement reste insuffisamment sélectif. Sur 2021–2023, la nouvelle règle déclenche seize fois ; **une seule alerte** est suivie d'une clôture sous −5 % par rapport au jour d'alerte dans les dix séances suivantes. Sur 2024, une sur quatre ; sur 2025–2026, deux sur cinq alertes évaluables. Cette cible de diagnostic ne mesure ni les pertes déjà subies avant l'alerte, ni tous les drawdowns possibles, et les fenêtres futures sont utilisées seulement pour juger le calendrier. Aucun seuil n'est recalibré à partir de ces résultats.

Sur les fenêtres 2025–2026 évaluables, l'ancienne règle laisse 48,90 % des fenêtres de reprise en protection. La nouvelle laisse **41,41 %** en protection ou reprise réduite, tout en couvrant 58,76 % des fenêtres risquées contre 62,89 %. Elle réduit le retard mais conserve beaucoup de restrictions pendant des reprises. La reprise progressive avec ancienne ancre laisse 64,32 % des fenêtres de reprise hors budget normal : son problème d'ancre est confirmé.

## Vérification du rétablissement des achats

La reprise n'est pas restée désactivée par erreur : après le retour normal du 16 mai 2025, exposition moyenne réellement obtenue sur les dix séances suivantes **97,93 %** du capital, 8,3 titres détenus en moyenne. Le compte retrouve son budget ; ses positions, capital et compteurs de concentration diffèrent cependant du témoin. Sa courbe ne peut pas se recoller automatiquement à celle du témoin.

Pendant PROTECTED, le nouveau cas garde en moyenne 58,96 % d'exposition totale, contre 80,59 % en PROBE et 86,04 % en NORMAL. La base est conservée par position ; il ne s'agit pas d'un compte plafonné strictement à 50 %. Les détentions finales, quantités et ventes sont rapprochées, sans survente ni dépassement des vingt positions. Toutes les courbes sont identiques au témoin avant leur propre première activation exécutable ; la première nouvelle alerte survient dès le 4 mars 2021.

## Contrôles et limites du bilan

Deux contrôles exactement reproduits ; douze tests ciblés, six préfixes dans l'étude principale, trois pour le calendrier local, dix-huit dans les diagnostics initiaux/croisés. Flux de frais, positions ouvertes, PnL et équité rapprochés (écart <2e−10 $), liquidations après décision à l'ouverture officielle suivante, covariances antérieures à l'achat. Pas de nouveaux modèles, coûts de fournisseur, appels LLM, écritures SQL, ordres ou modification de production.

Les limites communes restent explicites : univers contemporain, prix révisés, intraday incomplet/repli OHLC, pas de nouveau holdout indépendant. Même divergence de label BIDU connue dans chaque cas. L'audit supplémentaire de détention identifie deux titres avec volume daily nul le 18 juin 2026 (ALNT/QTWO) malgré des échanges intraday : ouvertures et extrêmes corroborés, mais caches incomplets et clôtures légèrement différentes. Réserve conservée sans substitution des données ou suppression rétroactive de trades. Aucun chevauchement de détention avec les anomalies GWRE/LBRDK de l'étude SHORT distincte. Le corpus complet n'est pas certifié.

Décision : **ne pas activer ces nouvelles conditions** et ne pas continuer une recherche de seuils uniquement pour faire coïncider fin 2024/mi-2025. Ces essais montrent le coût des fausses alertes et des faux rebonds ; ils ne démontrent pas qu'aucune protection ne puisse fonctionner. La prochaine proposition éventuelle doit avoir un protocole distinct, une mesure explicite du coût des alertes et une évaluation hors de la période utilisée pour inventer ses seuils.

Archives finales : `completion.json`, `comparison-all.csv`, `annual-comparison-all.csv`, `timing-diagnostics-final.csv`, `timing-events-final.csv`, `windows-all.csv`, `phase-exposure-all.csv`, `off-recovery-all.csv`, `exposure-validation.json`, `volume-screen-review.json`. Les états, transactions, réallocations et sources figées des six comptes restent disponibles dans leurs dossiers respectifs.

![Synthèse des capitaux](../../artifacts/research/us_b_protection_timing_replay/20261118-v1/capital-summary.png)

![Dates d'activation et reprise, exécution à la séance suivante](../../artifacts/research/us_b_protection_timing_replay/20261118-v1/activation-recovery-2024-2025.png)

Les six courbes complètes et SPY figurent aussi dans `capital-comparison-all.png` ; zoom normalisé dans `late2024-mid2025-normalized.png`. SPY : prix seuls, sans dividendes/frais de réplication ; les taux du tableau restent ceux des stratégies, frais inclus.
