# Q051 TOP10 — plafond de prix après Oracle et per-symbol

## Demande et statut

GO du 27 novembre 2026 pour la première expérience de timing, issue de la
lecture des pages FM Studio / UpToGo. **TERMINÉ / CONTRÔLES PASS ; attente plus
rentable mais drawdown plus profond, aucune promotion en production.** Cette expérience ne teste pas encore le
repli sur moyenne mobile ; ce serait un protocole distinct.

Sources d'inspiration, sans preuve d'efficacité sur notre stratégie :
https://fmstudio.blog/stock-buying-points-guide/
https://uptogo.com.tw/財經/如何判斷股票買賣點？/
La seconde page a été consultée via son texte indexé.

Archives : `artifacts/research/us_q051_entry_ceiling/20261127-v1`.
Pilote : `scripts/research/us_q051_entry_ceiling_20261127.py`.
Coordinateur et rapport : `scripts/research/report_q051_entry_ceiling_20261127.py`.

## Témoin commun

Q051 témoin TOP10, 2021–1er octobre 2026, dépôt initial de 4 000 USD,
sans remise à zéro annuelle : TOP10 % Oracle H10 → TOP10 LONG per-symbol,
score strictement >0,50 et AUC de calibration ≥0,50. Modèles annuels déjà
archivés, signaux inchangés ; pas de nouvel entraînement ou de nouvelle inférence.

Position complète entière, entrée standard à l'ouverture J+1, SL5 %, sans
TP/trailing/renforcement, dix séances détenues puis vente open11. Risque par
entrée 1,25 %, poids maximal 20 %, plafond achats 1× et capacité margin 2×,
20 positions, ligne minimale 50 USD. Frais 8 pb par opération et financement
inchangés. B4, vol20, régime, facteurs, corrélation, limites sectorielles,
options et GPT désactivés comme dans le témoin figé.

Le témoin complet scellé et validé le 26 novembre donne **15 237,79 USD,
+280,94 %, DD intraday −40,45 %, 1 471 clôtures, 35,62 % gagnantes**.
Une nouvelle vérification a confirmé les **96 sources économiques Python
inchangées**, la configuration effective identique et les mêmes signaux/prix.
Le contrôleur complet validé est réutilisé : `baseline-reuse.json` conserve
la provenance et les empreintes ; `baseline-reproduction.json` confirme
l'identité numérique des 1 443 clôtures avec la référence du 15 novembre.

Un recalcul redondant avait commencé avant cette vérification. Seuls ses
deux processus Python précisément identifiés ont été terminés ; son passage
partiel reste sous `cases/REFERENCE-partial-check`. Il n'est pas présenté comme
un nouveau replay complet. Aucun autre run ni service n'a été arrêté.

## Trois cas, règle figée avant résultats

1. **REFERENCE** : témoin inchangé.
2. **CAP_OPEN** : achat à l'ouverture J+1 seulement si son prix est inférieur
   ou égal au plafond ; sinon abstention, aucun remplacement.
3. **CAP_WAIT2**, cas principal : même contrôle à J+1, puis possibilité d'entrée
   aux ouvertures 5m réellement observées et à l'ouverture J+2, jusqu'à la
   clôture J+2. Au-delà, le signal expire.

Le plafond est fixé après la clôture J :

`plafond = clôture(J) + 0,5 × ATR20(J)`

Ici ATR20 signifie **moyenne simple des vingt true ranges**, et non lissage
Wilder. `TR=max(high-low, abs(high-close_précédent), abs(low-close_précédent))`.
Vingt et une séances valides sont nécessaires. Les données manquantes ne sont
pas remplies et ne deviennent jamais un prix d'achat fictif. Le coefficient
0,5 et l'attente de deux séances ne sont pas optimisés après résultat.

Une entrée n'est pas simulée parce que le plus bas de la journée aurait touché
le plafond : seule une **ouverture observée ≤ plafond** est admissible. Le niveau
est connu dès J ; il ne dépend ni du futur plus bas ni d'une confirmation
calculée avec une bougie cinq minutes pas encore reçue. C'est une hypothèse
d'exécution historique, pas une garantie de remplissage d'un ordre réel.

Le risque est revalidé et le capital redimensionné par les fonctions natives
au prix d'entrée. Un refus natif n'est pas retenté. Un signal répété pour un
même titre remplace son ancien plan non exécuté ; les anciens rangs/scores
sont conservés et aucun titre extérieur aux TOP10 archivés n'est ajouté.
Les plans en attente peuvent coexister avec les nouveaux candidats. Une entrée
J+2 reste liée au signal original dans les événements et les contrôles.

La détention de dix séances commence à l'entrée effective. Elle n'est pas
confondue avec les dix séances de prévision d'Oracle : attendre consomme une
partie de la fenêtre du signal, ce qui constitue un coût potentiel du timing.

## Faisabilité avant calcul des rendements

Sur les **9 890 sélections** originales : aucun ATR manquant ; **9 287**
ouvertures J+1 sous le plafond et **603** au-dessus, soit **6,10 %** filtrées
avant le risque. Ce ne sont pas des nombres de trades ni de gagnants.
`opening-audit.csv` documente les dates et les prix. L'expansion en fenêtres de
deux séances détecte 6 703 anciens plans remplacés par un nouveau signal du
même titre ; ce compteur n'est pas un nombre d'achats évités.

## Isolation et limites

Les simulations utilisent exclusivement les prix et scores archivés, des
répertoires propres aux runs et un garde SQL/réseau en lecture seule. Aucun
téléchargement, appel GPT, ordre broker ou changement de configuration de
production. Les deux variantes tournent avec deux workers de recherche.

Un adaptateur en mémoire effectue deux substitutions vérifiées du point
d'entrée du moteur : le contrôle journalier peut coexister avec son mécanisme
existant d'entrée programmée. **Aucun fichier du moteur natif n'est modifié** ;
dimensionnement, frais, protections et comptabilité restent ceux du moteur.

La protection reprend le même mélange de journées 5m complètes et de repli
OHLC journalier que le témoin. Pour les entrées tardives seulement, une séance
5m complète et compatible avec l'ouverture journalière est requise. Cette
qualification de couverture est connue ex post dans l'archive : **pas de
certification PIT stricte ou de disponibilité historique live**. Les jours
incomplets ne fournissent jamais de faux prix intraday ; J+2 peut néanmoins
encore fournir sa vraie ouverture journalière. Univers rétrospectif et période
déjà étudiée conservés ; pas de preuve indépendante hors échantillon vierge.

## Suivi et validation prévue

`progress.json` est terminal `COMPLETED_EXPLORATORY`, `validation=PASS`, 3/3.
Les deux variantes ont terminé leurs 1 443 séances. Finalisation le
28 novembre 2026 à 00:51:28 Europe/Paris (27 novembre 23:51:28 UTC).

Contrôles : ATR recalculé scalairement pour les 9 890 signaux, prix d'entrée
et fenêtre d'attente, absence de double entrée sur un même signal, durée H10,
sorties open11, coûts/PnL/cash/DD et capitalisation des rendements annuels.
Publication : `comparison.csv`, `annual-comparison.csv`, `capital-comparison.png`,
`validation.json` et import de trois résultats dans l'historique IHM.
Le bilan distingue gagnants/perdants, capital engagé moyen/maximal, stops
précoces et trades du témoin non achetés. Le PnL de ces trades manqués est un
diagnostic à taille figée, pas le rendement du portefeuille contrefactuel.
Quatre tests unitaires de causalité, seuil, attente et adaptateur passent au
lancement. Vérification par le même assistant ; pas une revue humaine indépendante.

## Résultats complets après frais et financement

| Cas | Capital final USD | Rendement | DD max intraday | Trades clôturés | Gagnants | Capital engagé moyen USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Témoin | 15 237,79 | +280,94 % | −40,45 % | 1 471 | 35,62 % | 7 187,51 |
| Plafond à J+1 seulement | 9 673,96 | +141,85 % | −43,20 % | 1 447 | 34,55 % | 5 511,72 |
| Plafond avec attente deux séances | 18 593,49 | +364,84 % | −46,26 % | 1 444 | 34,63 % | 6 842,92 |

L'attente gagne **83,89 points** de rendement cumulé face au témoin, avec
**5,81 points de DD supplémentaires** et environ 1 point de taux gagnant
en moins. Ce n'est pas un progrès simultané rendement/risque, ni une preuve
de filtrage plus fiable des perdants. Le plafond à l'ouverture seule est
défavorable sur ces deux métriques. Aucune configuration de production modifiée.

L'exposition moyenne rapportée au capital courant est respectivement
88,72 %, 88,20 % et 88,61 %. Les nombres de gagnants/perdants clôturés sont
524/947, 500/947 et 500/944. Profit factors : 1,183 / 1,121 / 1,277.
Stops initiaux/same-day : 876/167, 869/170 et 866/159. Les capitaux absolus
et les quantités divergent à mesure que le chemin du portefeuille change.

Le cas avec attente n'a pas acheté 560 trades clôturés du témoin : 196 gagnants
et 364 perdants, PnL de référence à taille figée −4,12 USD. Ce n'est pas le seul
effet du timing : d'autres entrées/prix/quantités et le capital disponible
diffèrent. Il serait incorrect d'attribuer tout le surplus aux seuls exclus.

Sur les 1 451 achats du cas avec attente, 1 423 ont lieu à l'ouverture J+1,
25 plus tard durant J+1, un à l'ouverture J+2 et deux plus tard durant J+2.
Il n'y a donc que **28 achats différés**, dont **trois durant J+2**. La plupart
des entrées restent immédiates ; les effets de capitalisation et d'admission
interdisent d'assimiler le surplus final au gain brut de ces seuls 28 achats.

| Année | Témoin | Plafond J+1 | Plafond attente deux séances |
| --- | ---: | ---: | ---: |
| 2021 | +8,45 % | +4,25 % | +4,26 % |
| 2022 | −2,13 % | −22,52 % | −21,75 % |
| 2023 | +83,23 % | +82,82 % | +85,26 % |
| 2024 | +34,14 % | +30,85 % | +50,32 % |
| 2025 | +35,38 % | +21,22 % | +46,92 % |
| 2026 au 1er octobre | +7,87 % | +3,25 % | +39,26 % |

Le gain de l'attente n'est pas transversal : 2021 et surtout 2022 se dégradent,
avec une amélioration concentrée dans les années suivantes.

Les fichiers `comparison.csv`, `annual-comparison.csv`, `capital-comparison.png`,
`results.md` et `validation.json` sont publiés dans les archives. Les trois runs
IHM portent les identifiants `20261127_q051_ceiling_reference`,
`20261127_q051_ceiling_cap_open` et `20261127_q051_ceiling_cap_wait2`.

![Comparaison du capital et du DD de clôture](../../artifacts/research/us_q051_entry_ceiling/20261127-v1/capital-comparison.png)
