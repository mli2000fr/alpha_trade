# Plafond et attente de deux séances : anti-SL ou vol20 + régime

Protocole fixé le 28 novembre 2026, avant lecture des résultats des variantes.

## Comparaison demandée

1. **Témoin CAP_WAIT2** : archive validée à 18 593,49 USD, +364,84 %, DD maximal
   −46,26 %. L’archive est réutilisée à l’identique après vérification des
   sources, prix, signaux et copies. Ce contrôle ne constitue pas un nouveau
   calcul du rendement témoin.
2. **Même témoin + anti-SL** : seuls les signaux jugés trop risqués par la tête
   annuelle SL10 sont supprimés, sans remplacement par le rang suivant.
3. **Même témoin + vol20 et régime** : mêmes signaux d’origine ; les achats
   sont conditionnés au régime et leur quantité limitée par le budget de
   volatilité. Cette variante n’ajoute pas l’anti-SL.

Il n’y a pas de quatrième cas combinant anti-SL et vol20/régime.

## Socle économique commun

- Du 1er janvier 2021 au 1er octobre 2026, 4 000 USD initiaux, capital continu,
  aucune remise à zéro annuelle.
- Les six modèles annuels **Q051 classiques** et leurs poids LONG par titre
  restent ceux du témoin. Les classements LONG ne sont pas remplacés par B.
- TOP10 % Oracle, soit 179 candidats sur l’univers de 1 790, puis au maximum
  TOP10 LONG per-symbol ; score strictement supérieur à 0,50 et AUC de
  calibration au moins 0,50 ; sans remplissage des places écartées.
- Après clôture J, plafond = clôture J + 0,5 × moyenne simple des vingt true
  ranges. Le plafond est figé ; il n’est pas recalculé avec les prix futurs.
- Attendre une ouverture observée à un prix au plus égal au plafond pendant
  J+1 ou J+2. Les ouvertures régulières de bougies 5 minutes peuvent être
  utilisées ; le simple toucher du plus bas n’est pas un achat simulé.
- Une sélection plus récente du même titre remplace le plan ancien encore
  inexécuté. Un refus du risque n’est pas réessayé pour le même signal.
- Position complète, LONG uniquement, quantités entières, SL5 %, sans TP,
  trailing, renforcement ou confirmation 5 minutes.
- Dix séances détenues à compter de l’entrée effective, puis sortie à
  l’ouverture de la onzième. Une entrée retardée décale donc l’échéance.
- Risque par entrée 1,25 %, poids maximal 20 %, maximum vingt positions,
  minimum 50 USD, plafond d’achat 1×. Le compte margin conserve une capacité
  2×, bornée pour les nouvelles entrées par ce plafond de risque 1×.
- Frais 0,08 % par achat/vente et financement annuel 6,5 % du cash débiteur.
  Réserve de dimensionnement distincte des frais comptables.
- B4/DD15, liquidation globale, contrôles factoriels, corrélation et limites
  sectorielles désactivés, comme le témoin. Les autres règles économiques
  natives conservées sont détaillées dans la configuration archivée.

## Anti-SL : définition et limites du transfert

Les têtes annuelles **SL10**, communes aux titres, ont déjà été entraînées
dans l’expérience B + anti-SL. Elles sont réutilisées sans nouveau fit,
recalibration, changement de seuil ou sélection selon les rendements du test.
Les dates de disponibilité des poids doivent précéder strictement le signal.

Ces têtes utilisent 44 variables : 29 variables instantanées de marché et
quinze descripteurs de trajectoire passée sur dix séances. « Dix séances »
désigne ici les observations passées, pas une prédiction du SL dans les dix
séances futures. La cible apprise est le **SL5 touché pendant J+1**, pour une
entrée à l’ouverture journalière de J+1.

L’[étude anti-SL d’origine](q051_b_early_sl_20261116.md) conserve ses diagnostics
et réserves de prix/labels ; le transfert de ses poids ne les fait pas disparaître.

Le seuil d’exclusion reste le percentile 90 du risque calibré dans le passé.
Un risque strictement supérieur au seuil entraîne l’exclusion. Le veto est
appliqué au signal d’origine, après TOP10 LONG et avant expansion J+1/J+2.
Une nouvelle sélection exclue ne crée pas de nouveau plan et ne remplace donc
pas un ancien plan admissible encore dans son attente de deux séances.

Ce test mesure un **transfert de la tête entraînée sur le pool Oracle B vers
les candidats Oracle classiques**. Il ne prétend pas que ces deux pools sont
identiques. Il vérifie aussi si une cible de SL à J+1 reste utile quand l’achat
peut être retardé ; la tête ne prédit pas explicitement le SL après l’heure
effective d’une entrée retardée.

Les scores manquants dans le cache initial ont été inférés avec les mêmes
poids et features historiques. Sur les 160 contrôles titre/année reconstruits,
les 13 044 probabilités déjà archivées sont reproduites sans différence.
Les 9 890 signaux disposent d’un score ; 1 455 sont exclus, 8 435 conservés.
Ces nombres sont des signaux, pas des achats réellement possibles.

| Année d’entrée | Signaux | Exclus par anti-SL |
| --- | ---: | ---: |
| 2021 | 979 | 30 |
| 2022 | 1 626 | 321 |
| 2023 | 779 | 0 |
| 2024 | 2 442 | 93 |
| 2025 | 2 229 | 873 |
| 2026, jusqu’au 1er octobre | 1 835 | 138 |

## Volatilité 20 % + régime

Le régime utilise uniquement les cours connus à la veille de chaque séance
d’achat effective : SPY doit dépasser 98 % de sa moyenne sur 200 séances.
Le contrôle est réévalué à J+2 pour un plan encore en attente. Aucune valeur
future ni clôture de la séance d’entrée n’entre dans cette décision.

Le budget utilise les covariances des soixante rendements passés, annualisées
sur 252 séances, et les positions/pending réellement présentes. La quantité
native est réduite si nécessaire pour respecter une volatilité prévisionnelle
du portefeuille de 20 %, puis repasse par le contrôle natif. Cette couche
ne peut jamais augmenter la quantité native.

Les deux chemins d’entrée sont raccordés : ouverture journalière et ouverture
observée d’une bougie 5 minutes. Dans ce second cas, le budget utilise le prix
effectivement observé à cette heure. Une absence d’historique qualifié reste
un refus de cette entrée, sans substitution de données futures.

Ces protections concernent uniquement les nouvelles entrées. Elles ne vendent
pas le portefeuille existant et ne garantissent aucun plafond de drawdown.

## Exécution, suivi et restitution

Pilote : `scripts/research/us_q051_ceiling_overlays_20261128.py`.
Archives : `artifacts/research/us_q051_ceiling_overlays/20261128-v2`.

Le témoin est conservé en copies vérifiées. Les deux variantes tournent dans
des processus séparés, avec SQL en lecture seule et HTTP interdit. Aucun
modèle, ordre broker ou réglage de production n’est modifié. La préparation
v1, interrompue avant un résultat complet, est marquée `SUPERSEDED` ; seuls
ses caches d’inférence contrôlés sont réutilisés dans v2.

`progress.json` donne l’avancement global ; chaque variante a son propre
`progress.json` et son journal. Après validation : comparaison globale et
annuelle, courbes de capital, trades/frais, capital engagé et import dans
l’historique IHM.

Les résultats restent exploratoires : période déjà étudiée, univers
rétrospectif, prix révisables, couverture 5 minutes partielle et repli OHLC
journalier. Comme dans le témoin, les entrées tardives exigent une séance
5 minutes complète qualifiée ex post. Cette restriction de qualité n’est pas
une certification de disponibilité à l’instant de décision en exploitation.

Pour les modèles et fenêtres exactes :
[guide de reconstruction complet](../backtesting/guide_reconstruction_comparaison_q051.md).
