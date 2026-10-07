# Audit de faiblesse précoce — TOP10 Oracle prédit, 2023–2024

## Objectif et statut

Expérience autorisée le 7 octobre 2026, lancée dans
`artifacts/research/us_concentrated_replay/top10-early-weakness-2023-2024-20261007-v1`.
Identifier si les trajectoires précoces des perdants diffèrent de celles des
gagnants, sans sacrifier les rares grosses hausses qui portent la performance.
Ce premier run réalise le diagnostic et la référence économique, **pas encore
la comparaison d'une règle de vente anticipée ou de réduction partielle**.

## Sélection et référence figées

- Dix scores Oracle prédits les plus élevés, pas les dix mouvements réels.
- Hausses/baisses futures non utilisées pour sélectionner ; toutes les entrées LONG.
- Scores archivés 2023–2024 du batch `model-factory-20261003082853-e98332`.
- Capital 4 000 USD continu, maximum huit positions, sizing canonique inchangé.
- Entrée à l'ouverture suivante ; SL initial fixe 7 % du fill, sans TP ni trailing.
- Échéance vingt séances après la séance d'entrée ; liquidation finale fin 2024.
- Coûts, contraintes d'exécution et régime du moteur de recherche existant.
- Refus complet, sans redimensionnement, des ordres incompatibles avec le budget.
- Prix invalides, volumes nuls, remplissages artificiels et changements d'identité
  restent bloquants pour les positions détenues. Aucun remplacement rétrospectif.

## Mesures de trajectoire

Le fichier `early-paths.parquet` mesure chaque candidat original, même s'il
aurait déjà été stoppé : ces chemins servent à comprendre les récupérations
après une baisse, pas à prétendre qu'un trade arrêté a gagné.

J+1/J+3/J+5 désignent ici le close de la première/troisième/cinquième séance
depuis l'entrée à l'open J+1 du signal. Les rendements sont relatifs à cet open.
La référence terminale est le close vingt séances après la séance d'entrée.
Les excursions favorables et défavorables sont mesurées sur cette fenêtre.
Le rendement relatif à SPY utilise exactement les mêmes dates d'entrée et
d'observation. Les observations absentes restent inconnues ; aucun forward-fill.

`path-summary.json` sépare par année et mois les chemins positifs, non positifs
et les hausses brutes >=50 %. Il indique la fréquence des baisses précoces,
de la faiblesse relative à SPY et des passages au stop initial. Les catégories
futures sont **uniquement descriptives**, jamais des features de décision.
Ces rendements de trajectoire sont bruts, hypothétiques, chevauchants et ne
doivent pas être confondus avec le PnL net du portefeuille dans `baseline/`.
Les trajectoires relatives au secteur restent à compléter : ne pas déclarer
ce volet livré avec les seuls résultats SPY.

## Réserves de validité

Le batch final a été entraîné jusqu'au 31 décembre 2024. Les scores ici portent
des `fold_start` historiques, vérifiés présents et antérieurs ou égaux au signal.
Cela ne suffit pas à certifier à soi seul toute la provenance train/validation,
la calibration et les dates de disponibilité des données. Aucun score du modèle
final n'est substitué à un fold manquant. Ces résultats restent exploratoires
tant que cette chaîne OOF complète n'a pas été qualifiée.

Univers et secteurs actuels : biais de survivance et hypothèse NON-PIT.
Macro historique quotidienne : vintages de publication non certifiés.
Prix locaux : pas de certification indépendante complète. Les contrôles de
qualité peuvent réduire la couverture descriptive, qui est explicitement comptée.
Le portefeuille ne supprime pas préventivement les futurs chemins invalides.

Les années antérieures ne sont pas automatiquement une validation indépendante :
la sélection des expériences et certaines données ont déjà été examinées.
Aucune nouvelle recherche de seuil, aucun entraînement, aucune écriture SQL.
Les extractions et scores sont archivés ; le protocole contient les hashes sources.

## Suivi et suite

```powershell
Get-Content F:\projets\artifacts\research\us_concentrated_replay\top10-early-weakness-2023-2024-20261007-v1\progress.json
Get-Content F:\projets\log\batch\top10-early-weakness-2023-2024-20261007-v1\stderr.log -Tail 20
```

Les phases sont PREPARING, PATH_AUDIT, BASELINE_REPLAY, puis COMPLETED ou FAILED.
Pendant le replay, `baseline/progress.json` donne les séances traitées.
En cas de blocage prix, les fichiers descriptifs déjà produits restent consultables,
mais aucun rendement économique final n'est déclaré valide.

Après lecture : qualifier la provenance OOF, expliquer les écarts et compléter
le volet secteur. Toute règle de sortie anticipée doit ensuite être explicitée
et figée avant un test distinct ; comparer le rendement net, le drawdown et la
conservation des gros gagnants, pas seulement le taux de trades gagnants.

Validation initiale : 24 tests ciblés passants, incluant calendrier d'entrée,
clôture terminale, volume nul, observation incomplète et récupération après stop.

## Résultats lus le 7 octobre 2026

Run terminé : 502 séances, 5 020 chemins candidats localement valides, référence
économique COMPLETED. Aucune variante de sortie précoce n'a encore été exécutée.

| Référence SL7 sans TP/trailing | Résultat |
|---|---:|
| Rendement net simulé 2023–2024 | +26,92 % |
| Capital final | 5 076,91 USD |
| 2023 | +42,47 % |
| 2024 | −10,92 % |
| Drawdown maximal | −18,97 % |
| Sharpe | 0,68 |
| Positions closes | 318 |
| Taux gagnant | 33,65 % |
| Profit factor | 1,21 |
| Exposition brute moyenne / equity | 49,57 % |

Les cinq meilleurs trades totalisent 1 095,03 USD pour un PnL de 1 076,91 USD :
la concentration reste majeure. Réconciliation cash <1e-12 USD, zéro fill oublié,
zéro refus au commit pour budget incompatible. Le portefeuille est continu entre
les deux années ; 2024 n'est pas un run indépendant avec remise à zéro du capital.

### Trajectoires : signal descriptif mais pertes non évitables avec certitude

Sur les candidats initiaux, sans appliquer le stop au rendement terminal brut :

| Mesure | 2023 | 2024 |
|---|---:|---:|
| Fréquence initiale de rendement terminal <=0 | 40,44 % | 53,77 % |
| Rendement terminal <=0 parmi les candidats négatifs à J+1 | 47,87 % | 59,41 % |
| Même mesure à J+3 | 53,06 % | 62,45 % |
| Même mesure à J+5 | 55,55 % | 67,42 % |
| Rendement terminal <=0 parmi négatifs ET faibles vs SPY à J+5 | 55,64 % | 68,82 % |

La double faiblesse à J+5 signale 1 073 chemins en 2023 et 1 270 en 2024.
Elle signale aussi 31,97 % et 33,99 % des futurs chemins positifs ; parmi les
hausses terminales >=50 %, elle touche 10/88 occurrences en 2023 et 1/10 en 2024.
Les occurrences chevauchent souvent les mêmes titres : 88 et 10 ne sont pas
des nombres d'événements indépendants. Ces comptes ne sont pas les gagnants
du portefeuille, et certains chemins sont déjà stoppés avant J+5.

Autre réserve : 42,31 % des chemins terminaux positifs 2023 et 38,63 % de ceux
de 2024 touchent néanmoins le seuil initial −7 % durant leur trajectoire.
Une hausse terminale ne suffit donc pas à conclure que le trade était gagnant.

Conclusion : la faiblesse précoce est associée à davantage de rendements
terminaux non positifs sur les deux années ; **aucune amélioration nette du
portefeuille n'est démontrée par cette association**. La force relative SPY
apporte peu à la seule baisse à J+5 en 2023, davantage en 2024, sans preuve
de stabilité indépendante. Une prochaine comparaison doit porter uniquement
sur les positions encore ouvertes, décider au close et exécuter à l'open
suivant, avec frais/gaps, puis recalculer tout le portefeuille. Ne pas présenter
les rendements terminaux des chemins exclus comme des pertes effectivement évitées.

## Comparaison économique J+5 — lancée le 7 octobre 2026

Suite autorisée par « continuer », dossier
`artifacts/research/us_concentrated_replay/top10-j5-weakness-comparison-2023-2024-20261007-v1`.
Trois portefeuilles indépendants, chacun démarrant à 4 000 USD en janvier 2023 :

1. BASELINE : aucune intervention précoce ; parité exacte de la courbe journalière
   exigée avec le run précédent, arrêt si divergence.
2. EXIT_ALL : vendre toute la quantité restante si double faiblesse au cinquième close.
3. REDUCE_HALF : vendre la moitié de la quantité observée à ce close ; conserver
   le SL initial et la date d'expiration sur le reliquat.

Double faiblesse : rendement depuis le **fill réel** strictement négatif ET
rendement inférieur à celui de SPY, mesuré depuis l'open de la même séance
d'entrée. Le cinquième close est `entry_idx + 4`. Décision une seule fois par
position, après les protections intraday et les sorties planifiées. Exécution
à l'open suivant, jamais au close qui déclenche le signal.

À cet open, les stops en gap ont priorité, puis les actions de régime déjà
programmées, puis l'ordre de faiblesse. Une position déjà fermée n'est pas
vendue à nouveau. Le motif et le statut sont archivés dans
`early_weakness_orders.json`. La réduction ne réinitialise ni l'entrée, ni
le SL, ni les vingt séances. Les frais natifs sont appliqués sur chaque jambe.
La taille restante est bornée à celle effectivement détenue après les actions
de régime ; pas de vente à découvert. Toute fermeture reste comptabilisée
dans le même ledger ; le capital libéré modifie les décisions futures.

Le TOP10 prédit, sizing, coûts, contraintes et macro restent inchangés.
Les fichiers bars/scores/macro sont réutilisés hors ligne, sans lecture SQL,
écriture SQL, nouvel entraînement ou modification du live. La configuration
marché/risque et le hash des secteurs doivent rester identiques au contrat.
Le code de recherche possède une option désactivée par défaut : les anciens
scénarios ne reçoivent pas la règle J+5.

Cette règle a été choisie après l'audit descriptif 2023–2024 : comparaison
**exploratoire**, pas nouvelle validation indépendante. Les réserves OOF,
survivance, secteurs et prix restent intégralement applicables.
Validation initiale : 51 tests ciblés passants (réduction moitié, sortie totale,
chronologie next-open, absence d'intervention sans faiblesse, cash et ledger).

```powershell
Get-Content F:\projets\artifacts\research\us_concentrated_replay\top10-j5-weakness-comparison-2023-2024-20261007-v1\progress.json
```

Chaque sous-dossier BASELINE/EXIT_ALL/REDUCE_HALF contient son avancement par
séance. Le rapport racine est écrit à la fin des trois scénarios seulement.

### Résultats de la comparaison économique

Les trois scénarios sont COMPLETED. Parité **exacte** de la courbe journalière
BASELINE avec le run précédent (`baseline_daily_parity: true`).

| Scénario | Net 2023–2024 | Capital final USD | Drawdown max | Sharpe | Positions closes | Gagnantes |
|---|---:|---:|---:|---:|---:|---:|
| BASELINE | +26,92 % | 5 076,91 | −18,97 % | 0,68 | 318 | 33,65 % |
| EXIT_ALL | +18,10 % | 4 724,08 | −16,66 % | 0,51 | 361 | 27,98 % |
| REDUCE_HALF | +21,85 % | 4 874,09 | −17,30 % | 0,62 | 311 | 30,87 % |

| Scénario | 2023 | 2024 | Exposition moyenne / equity | Profit factor |
|---|---:|---:|---:|---:|
| BASELINE | +42,47 % | −10,92 % | 49,57 % | 1,21 |
| EXIT_ALL | +38,73 % | −14,87 % | 45,30 % | 1,14 |
| REDUCE_HALF | +39,60 % | −12,71 % | 43,44 % | 1,20 |

EXIT_ALL réalise 60 ventes J+5, REDUCE_HALF 55 réductions. Dans chaque variante,
deux ordres programmés ne sont plus exécutables car la position a déjà fermé
à l'ouverture (priorité stop/régime). REDUCE_HALF compte 366 jambes mais 311
positions : le taux gagnant agrège toutes les jambes d'une même entrée.
Zéro fill oublié, zéro refus de budget au commit, réconciliation cash <5e-12 USD.

Verdict : **NO_GO pour améliorer le rendement ou le Sharpe avec cette règle**.
La vente totale perd 8,82 points de rendement par rapport à la référence,
la moitié 5,07 points ; le drawdown est respectivement réduit de 2,31 et
1,67 points. Les deux variantes font moins bien sur chacune des deux années,
et n'évitent pas l'année négative 2024. La faible amélioration du drawdown
ne suffit pas à revendiquer une amélioration générale : l'exposition baisse aussi.

La concentration reste élevée : cinq meilleurs trades = 1 244,72 USD pour
724,08 USD nets en EXIT_ALL, et 1 092,07 USD pour 874,09 USD en REDUCE_HALF.
Ces portefeuilles suivent des parcours et tailles différents ; les écarts ne
prouvent pas à eux seuls quels gagnants ont été coupés. Une attribution par
position appariée serait nécessaire pour cette explication causale.
Ne pas ajuster maintenant J+3/J+4/J+6 pour rechercher a posteriori le meilleur
jour. Conserver la référence pour la recherche et ne pas activer ce veto J+5
en production sur la base de ces résultats exploratoires.
