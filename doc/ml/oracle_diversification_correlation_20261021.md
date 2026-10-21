# Oracle TOP10 : éviter les paris corrélés

## Protocole figé avant calcul

GO du 21 octobre 2026 pour le point1 (construction du portefeuille), distinct
du filtre de tendance abandonné. Aucun nouveau modèle directionnel, secteur
actuel assimilé à un historique PIT, ni changement de configuration production.

Une seule règle : refuser une nouvelle entrée si sa corrélation de rendements
daily avec **au moins une position déjà détenue** dépasse strictement **0,90**.
Ce sont les réglages Pearson du profil canonique archivé : **40 rendements**,
au moins **25 observations communes**. Seuil non optimisé après résultats.
Le moteur réutilise `filter_correlated_signed`, paire par paire avec priorité
aux positions détenues. Les comptes LONG et SHORT sont séparés : pas de
conclusion sur les couvertures croisées LONG/SHORT ou la covariance factorielle.

Prix de clôture de l'archive split-adjusted, disponibles avant la séance de
décision uniquement ; aucune donnée du jour, aucune moyenne/complétion des trous.
Variance nulle ou moins de25observations : refus distinct pour données
insuffisantes. Une corrélation qui augmente après l'achat ne force pas la sortie.
Les stops, échéances et sorties B4 sont inchangés. Les positions détenues
restent prioritaires ; les nouveaux candidats simultanés gardent l'ordre Oracle.
Pas de remplacement TOP11, nouvelle tentative, reranking ou sélection sur prix futurs.

### Trois bras, 12 comptes annuels

1. Témoin : reproduction exacte des quatre comptes LONG/SHORT 2025/2026 DD15.
2. Même stratégie + contrôle de corrélation aux positions réellement détenues.
3. Témoin à taille réduite : budgets de risque et de poids cible divisés par deux
   avant arrondis natifs, mêmes limites générales/SL/frais/B4 ; fraction HALF
   d'entrée conservée. Contrôle fixé à l'avance, non calibré sur le résultat.

Ce dernier témoin éclaire l'effet de l'exposition mais **n'est pas exactement
apparié en capital utilisé**. Il ne suffit pas à établir causalement un alpha
de diversification. Les tailles et trajectoires cash/B4 sont réellement rejouées.

SL7 %, trailing15 %, sans TP, expiration historique J+20depuisOracle,
demi-position, plafond1x, 4kUSD indépendants par année, B4DD15, 8bps/jambe,
emprunt SHORT hypothétique0,3%annuel/252 et financement6,5%ACT360 conservés.
Pas le nouveau contrat de vingt séances de détention puis sortie open21.
2026 s'arrête au30septembre. 2024 non qualifié en intraday.

### Mesures et limites

Rendement après coûts, DD5m, gagnants/perdants, gains/pertes et durées moyennes,
capital engagé, refus par motif, concentration des gains et corrélations du
portefeuille chaque soir. Audits scalaires de sorties/cash/coûts et décisions B4.

Même cohorte **213campagnes/72titres**, TOP10 Oracle parcours CatBoost OOS de
recherche (pas LightGBM production), conditionnée à la disponibilité future de
prix complets ; biais de couverture et survivants, pas tout TOP10 historique.
Daily retraité causal par date n'est pas un reçu PIT historique certifié.
Borrow/fills/corporate-actions hypothétiques hérités ; pas paritélivecomplète.
2025/2026 déjà étudiées : pas holdout vierge. Pearson ne couvre pas toutes les
expositions communes ni les changements de corrélation en crise.

Code courant haché ; copies historiques vérifiées pour les évolutions dormantes
du raccordement runtime. Les quatre témoins doivent reproduire exactement les
anciennes transactions et métriques avant interprétation du filtre.

Commande : `python -u -m scripts.research.us_oracle_portfolio_correlation`.
Dossier : `artifacts/research/us_oracle_portfolio_correlation/20261021-v1`.
Suivi `progress.json`, bilan `report.json`/`annual-summary.csv` ; chaque compte
garde décisions de corrélation, concentration quotidienne, transactions et audits.

## Résultats terminés et audités

**12/12 comptes terminés, aucun échec**, environ40secondes hors préparation.
Les quatre témoins reproduisent exactement les transactions et positions de
la référence scellée. Tous les audits de cash/exits/coûts/risque B4 passent.
Audit distinct : reconstruction des rendements directement à partir du daily,
des positions détenues à chaque entrée (y compris ordre simultané et sorties),
des fenêtres antérieures et corrélations par formule scalaire indépendante.
**1 266 évaluations d'entrée**, **1 053 comparaisons de paires** dans le bras
filtré ; erreur corrélation≤4,45e-16, erreur coûts≤5,46e-12USD.
**112 tests réussis**, rapport `artifacts/tmp/portfolio-correlation-tests-final-20261021.xml`.
Même assistant : ce n'est pas une revue humaine indépendante.

### Rendement après frais et DD

Capital initial **4 000USD indépendant pour chaque année/sens/bras**.
2026 jusqu'au30septembre, pas une année complète. DD en amplitude de baisse.

| Sens / année | Témoin : rendement / DD | Corrélation : rendement / DD | Taille réduite : rendement / DD |
| --- | ---: | ---: | ---: |
| LONG2025 | +26,83% /22,36% | +26,83% /22,36% | +6,73% /16,96% |
| LONG2026 | +16,94% /20,32% | +0,07% /21,88% | +30,56% /15,34% |
| SHORT2025 | −24,72% /37,05% | −24,72% /37,05% | −21,30% /27,42% |
| SHORT2026 | −25,61% /27,63% | −25,61% /27,63% | −18,38% /18,67% |

| Sens / année | Trades clos témoin / corrélation / taille réduite | Gagnants témoin / corrélation / taille réduite | Capital brut moyen témoin / corrélation / taille réduite |
| --- | ---: | ---: | ---: |
| LONG2025 | 100 /100 /98 | 37,00% /37,00% /35,71% | 2483,21 /2483,21 /1403,12USD |
| LONG2026 | 73 /70 /81 | 34,25% /30,00% /39,51% | 1961,11 /1724,47 /1864,55USD |
| SHORT2025 | 94 /94 /91 | 27,66% /27,66% /26,37% | 1161,73 /1161,73 /685,64USD |
| SHORT2026 | 61 /61 /51 | 19,67% /19,67% /15,69% | 714,00 /714,00 /347,10USD |

Le témoin taille réduite n'engage pas mécaniquement la moitié du capital moyen :
arrondis, admissions, niveaux de portefeuille, B4 et sorties changent le chemin.
En2026LONG, il ne déclenche aucun B4, contre deux pour les deux autres bras.
Cela ne suffit pas à promouvoir la demi-taille : résultat favorable2026 mais
forte réduction des gains2025, années déjà étudiées, pas de validation neuve.

Les gains/pertes moyens enUSD et%, durées moyennes gagnant/perdant,
valorisations ouvertes et capital final de chacun des12comptes sont conservés
dans `annual-summary.csv` et `report.json`. Positions ouvertes2025 :
7LONG et8SHORT dans les trois bras ; aucune fin de période2026.

### Un seul refus de corrélation

Le18février2026 à15:55UTC, entrée LONG **STX** refusée car **WDC** déjà détenu :
corrélation **0,910321**, **40 observations**, dernière séance17février2026.
Les autres positions détenues étaient AMKR (rho0,288891) et LMND (rho0,353533).
**Aucun refus pour historique manquant**, aucune autre entrée refusée au seuil0,90.

Le STX écarté **aurait perdu61,56USD après frais dans le témoin** : ce n'est
donc PAS l'exclusion directe d'un grand gagnant qui explique la baisse finale.
Le portefeuille est un système dépendant de son chemin : avoir évité cette
perte modifie ensuite cash, equity, pic B4, reprises, quantités et sorties.

Exemples observés, à ne pas convertir en règles rétrospectives :

- Premier déclenchement B4 LONG2026 :19mars dans le témoin,31mars dans le filtre.
- DOCN16avril :6actions et+417,03USD dans le témoin,1action et+69,50USD filtré,
  même entrée et échéance. Différence−347,52USD due à la quantité.
- MU17avril : présent dans le témoin,+294,89USD, absent du bras filtré à cause
  des décisions ultérieures de portefeuille, pas d'un autre veto corrélation.
- Trades communs identifiés par paire/symbole/heure d'entrée :68 ; PnL
  +401,59USD témoin contre−3,20USD filtré. Cinq trades seulement du témoin
  totalisent+276,18USD ; deux seulement du filtre,+6,18USD.
- Différence finale LONG2026 : **−674,79USD** pour le filtre, malgré le refus
  initial d'un perdant. Pas un calcul «ancien PnL moins STX».

### Les positions représentaient-elles presque toutes le même pari ?

Dans cette cohorte et selon cette mesure Pearson : pas de corrélation>0,90
entre positions en clôture en2025LONG/SHORT ni2026SHORT ; deux séances pour
2026LONG témoin, zéro avec filtre. Au-delà des seules paires>0,90, la
corrélation pondérée moyenne reste modérée :2026LONG **0,3267→0,3361** avec
le filtre. Ce dernier retire la paire très corrélée sans réduire la moyenne
globale mesurée. Ce calcul est conditionnel aux séances avec au moins deux
positions et une paire observable, pas un risque global prouvé faible.

Les plus mauvais trades sont inchangés sur trois comptes. LONG2026, pire trade
−90,37→−82,95USD et moyenne des cinq pires−88,43→−79,64USD, mais DD global
plus élevé : les pertes individuelles et le risque portefeuille ne se confondent pas.

La concentration des gains demeure : les trois meilleurs symboles représentent
**64,70%** de la somme des PnL positifs par symbole LONG2026 témoin, **55,25%**
avec filtre. Ce dénominateur ignore les symboles perdants et n'est pas la part
du bénéfice net. Les mesures détaillées sont dans `concentration-summary.csv`.

## Conclusion bornée

**Pas d'amélioration démontrée par ce contrôle Pearson à0,90 ; aucune promotion.**
Il est presque inactif et ne corrige pas les pertes SHORT. Le seul refus
modifie fortement le chemin LONG2026 sans améliorer rendement ou DD.
Ne pas diminuer le seuil après observation pour essayer de sauver le résultat.

Ce n'est ni une preuve que la diversification est inutile, ni un test complet
des facteurs communs, du bêta, des corrélations de crise ou du risque sectoriel.
Le compte qualifié détient en moyenne seulement1,3à3,5titres selon année/sens,
pas dix titres simultanés en permanence. La forte sensibilité à une entrée
appelle surtout une validation de robustesse (point2), pas un nouveau modèle
directionnel ou un seuil «optimal» choisi sur2026.

Aucun modèle, donnée SQL, fournisseur, ordre ou configuration de production
modifié. Résultats et anciennes grilles conservés. Contrôles finaux :
`final-review.json` et `post-review.json` ; refus explicite dans `refusals.json`.
