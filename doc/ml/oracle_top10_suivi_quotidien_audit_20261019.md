# TOP10 LONG — audit des états quotidiens avant un modèle de sortie

## Verdict

**AUDIT TERMINÉ / PAS D'ENTRAÎNEMENT / PAS DE NOUVELLE POLITIQUE TESTÉE.**
Le suivi quotidien est techniquement mesurable, mais aucun critère suffisamment
robuste n'est qualifié pour lancer maintenant un nouveau modèle KEEP/EXIT.

Sur vingt features et deux cibles, un seul couple passe le filtre descriptif
initial de stabilité : **faible progression maximale depuis l'entrée**, pour
la comparaison « sortir au prochain open » contre « conserver au plus trois
séances supplémentaires avec les mêmes protections ». Il ne résiste pas aux
réserves supplémentaires : faible effectif2026, intervalles larges et effet
surtout porté par la première clôture après l'entrée. Ce n'est pas une preuve
de détection quotidienne d'un retournement.

Les tests de sortie appris [E7](daily_position_keep_exit.md) et
[challengers TP20/SL10](oracle_challengers_20261013.md) existaient déjà sur
d'autres populations. Le présent audit ne les réentraîne pas ni ne transpose
leurs performances à ce nouveau TOP10 H10.

## Population et protections inchangées

GO pour l'audit sans entraînement, côté LONG, sur la cohorte actuelle :
[TOP10 H10 confirmé jusqu'à J+2](oracle_top10_confirmation_quatre_seances_tp10_sl5_20261019.md).

- Dix rangs Oracle figés à J, quatre clôtures strictement croissantes J−1..J+2.
- Entrée openJ+3, **TP10/SL5**, sans trailing, dix séances entrée comprise,
  expiration closeJ+12 ; pas de remplacement des titres ou nouvelle entrée.
- **708 positions hypothétiques** : 232 en2024, 255 en2025, 221 en2026 ; signaux2026
  jusqu'au1er septembre. Pas un portefeuille avec capital/slots/levier.
- Même copie de prix normalisée, réserves de prix/identité et mêmes coûts
  supposés de8bps par jambe ; aucun prix, modèle ou univers de production modifié.
- Un état ne représente qu'une clôture **après survie aux TP/SL intraday**.
  Aucun état le jour de sortie native ni à l'expiration imposée.
- Décision prise au close, sortie possible au **prochain open** seulement.
  Les protections gap déjà actives à cet open gardent la priorité. Ces états
  deviennent sans avantage de décision, mais restent dans les données : ils
  ne sont pas supprimés a posteriori pour embellir le pouvoir de sortie.

Le choix TP10/SL5 isole la question du suivi ; il ne reprend pas un paramètre
choisi rétrospectivement dans la grille de protections fixe/ATR.

## Ce qui a été construit

**1 835 états de clôture**, provenant de536 positions encore observables à au
moins une clôture. Les172 autres sont sorties dès la séance d'entrée.

| Signaux | Positions | Avec au moins un état | États | Sorties dès la séance d'entrée |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 232 | 200 | 804 | 32, soit13,79 % |
| 2025 | 255 | 199 | 683 | 56, soit21,96 % |
| 2026 | 221 | 137 | 348 | 84, soit38,01 % |

Ces sorties précoces comprennent **TP et SL**, pas seulement des pertes.
Même un suivi du soir parfait ne peut pas annuler un stop déjà exécuté intraday.
Parmi les150 stops2026, seuls68, soit45,33 %, avaient au moins une clôture
précédente dont la sortie au prochain open aurait été meilleure que le stop
natif. C'est une possibilité rétrospective, **pas une précision de prédiction**.

Chaque position reçoit un poids total1 réparti sur ses états : une position
surveillée neuf jours ne devient pas neuf positions indépendantes. Contrôle
supplémentaire earliest-first par symbole, attente de fin de la fenêtre entière :
377 positions au total, dont287 avec946 états. Ce contrôle continue à travers
les frontières annuelles, sans remettre la position à zéro chaque1er janvier.

## Features réellement observables

Vingt features, couverture100 % dans ces états qualifiés. L'historique de calcul
n'est pas tronqué à la date d'achat : une position jeune possède déjà des
rendements et volumes antérieurs observés.

| Famille | Données auditées |
| --- | --- |
| État de la position | Âge, PnL courant, progression maximale observée MFE, baisse maximale observée MAE |
| Restitution et barrières | Recul depuis le plus haut en unités ATR20, distance au SL et au TP en ATR |
| Trajectoire | Rendements1/3/5 séances, variation du momentum3 séances |
| Relatif au marché | Rendements1/3/5 séances du titre moins SPY |
| Prix/volume | Volume relatif à la moyenne des vingt séances précédentes, proxy baisse×volume, position de clôture dans le range du jour, distance au plus bas des trois séances précédentes |
| Volatilité | ATR20/prix et ratio ATR5/ATR20 |

ATR20 = moyenne simple des vingt true ranges, avec vingt et une barres valides,
sources/identités/ajustements cohérents ; aucun remplissage de données manquantes.
Les indicateurs de prix sont sur la même base ajustée de recherche que la référence.
Les rangs Oracle du futur, labels, raison de sortie et succès final ne sont pas
des features. Le proxy de pression baissière n'est pas une mesure réelle de
flux institutionnels ou de volume vendeur.

Pas d'ajout de secteur actuel en prétendant qu'il était historique ; pas de
news ou consensus reconstitués comme disponibles à l'époque. Ces familles
nécessitent des archives PIT qualifiées et ne sont pas indispensables pour cet
audit prix/volume/SPY. Aucun téléchargement ou appel LLM n'a été lancé.

## Deux cibles futures séparées des features

Pour un état donné, on calcule, en pourcentage du notionnel d'entrée :

```text
avantage_sortie = rendement_net_si_sortie_prochain_open
                − rendement_net_si_conservation
```

Conservation jusqu'à la sortie native restante, ou au plus trois séances
supplémentaires, **sans annuler TP, SL ou échéance**. Si un seuil natif intervient
avant ces trois séances, il reste la sortie de conservation. Ce n'est pas le
maximum futur accessible ni une sortie à un close déjà utilisé pour décider.

Un avantage positif signifie que sortir aurait été meilleur **pour cet état**.
Il ne s'agit pas du rendement d'une politique quotidienne : les états suivants
du même trade ne pourraient plus exister après une vraie première sortie.
Aucun cumul de leurs avantages n'est interprété comme un PnL réalisable.

La disponibilité des labels est conservatrice : séance suivant la fin de toute
la fenêtre native de dix séances, même si un stop survient plus tôt. Découverte
sur2024 uniquement, labels **strictement disponibles avant2025-01-01** :
777 états,190 positions. Les positions de fin2024 dont la fenêtre finit2025
ne servent pas à fixer les seuils. Les autres années restent descriptives et
déjà examinées, pas un test prospectif indépendant.

Tertiles pondérés et sens du signal fixés sur cette découverte2024 seulement.
Contrôles par classes d'âge1–2/3–5/6–9 et PnL négatif/non négatif, puis contrôle
supplémentaire d'âge exact ; on ne choisit pas un nouveau sens sur2026.

## Résultat des familles : pas de détection stable de retournement

- Rendements3/5 jours, accélération du momentum et force relative : faibles ou
  variables, pas de critère passant les années et le contrôle sans chevauchement.
- Volume relatif : AUC univariée pour l'avantage restant environ0,57/0,54/0,45
  en2024/2025/2026, sens orienté2024 ; pas de stabilité.
- Recul depuis le sommet en ATR : la queue retenue2024 aurait bénéficié d'une
  sortie en2025 mais perd cet avantage2026, également sans chevauchement.
- PnL et distance aux barrières peuvent distinguer des états, mais leur apport
  supplémentaire après comparaison d'états d'âge/PnL comparables n'est pas
  transversal. Une AUC brute ne suffit pas à justifier un modèle de sortie.

### Candidat descriptif : le trade qui n'a pas démarré

Sur2024, la queue retenue pour MFE est **moins de+2,203 % de progression maximale
déjà atteinte depuis l'entrée**. C'est la borne du premier tertile2024, pas un
seuil optimisé pour2026. Elle concerne souvent la première clôture après achat.

Pour la cible « au plus trois séances supplémentaires », AUC univariée pondérée,
orientée selon2024 : **0,655 /0,653 /0,591** ; sans chevauchement
**0,730 /0,679 /0,548**. Ce ne sont pas des probabilités ni des performances
d'un modèle entraîné. Après examen de40 couples feature/cible, ces valeurs
ne prouvent pas à elles seules un nouveau signal confirmé.

| Signaux | Positions de cette queue, sans chevauchement | Avantage moyen de sortie par état pondéré | Intervalle descriptif95 % par blocs d'entrée |
| --- | ---: | ---: | --- |
| 2024, découverte | 53 | +1,540 point | [+0,709 ; +2,460] |
| 2025 | 50 | +1,084 point | [−0,474 ; +2,647] |
| 2026 | 21 | +0,625 point | [−1,802 ; +4,047] |

**Réserves décisives :**

- Ces avantages sont ceux d'états possibles, pas ceux de la première sortie
  réellement exécutée d'une stratégie.
- Les intervalles2025/2026 incluent zéro ; seulement sept blocs d'entrée et
  treize symboles en2026. Les trois principaux pèsent41,52 % de la queue.
- En écartant uniquement la clôture de la séance d'entrée pour un diagnostic
  supplémentaire, la queue devient **+0,213/−1,028/−2,428 points** sans
  chevauchement, sur15/15/4 positions. L'effectif2026 est minuscule.
- À âge exact et signe du PnL comparables, son supplément devient négatif en2025
  sans chevauchement (−0,373 point). Le filtre descriptif initial, plus grossier
  sur l'âge, n'était donc pas suffisant pour qualifier cette stabilité.

Ces contrôles sont des diagnostics post-screen explicités, pas une recherche
de la meilleure nouvelle règle à promouvoir. L'hypothèse ressemble davantage
à un **départ d'entrée raté** qu'à une inversion de tendance reconnue chaque jour.

## Contrôles et suite bornée

**145 tests passent**, dont douze nouveaux : causalité des prix/volume/SPY,
absence de MFE futur dans l'état, états supprimés après TP/SL mais protections
au prochain open conservées, échéance, cible trois séances et purge des labels.
Audit `PASS_EXPLORATORY_AUDIT_ONLY` :

- 708 issues natives et1 835 labels recalculés ;
- 93 séries avec états vérifiées par recalcul sur préfixe, sans prix futurs ;
- mêmes trades source, poids par position, indépendance et seuils2024 contrôlés ;
- 81 états dont le prochain open impose déjà une protection, conservés sans
  avantage artificiel ; aucune vente fictive avant un stop passé.

**Pas de GO d'entraînement à ce stade.** Un éventuel essai ultérieur devrait
tester une hypothèse distincte et bornée de départ raté, avec première sortie
seulement, gains sacrifiés et prix d'exécution réels dans le replay. Il faudrait
un nouveau GO ; ne pas relancer automatiquement un modèle quotidien générique
ni empiler les critères faibles de cette grille. Les populations/horizons
diffèrent des anciens modèles KEEP/EXIT : leurs résultats ne sont pas réutilisés
comme validation de celui-ci.

Dossier : `artifacts/research/us_top10_daily_exit_state_audit/20261019-v1/`.
`protocol.json`, `baseline-trades.parquet`, `position-states.parquet`,
`2024-feature-contract.json`, `feature-tertiles.csv`, `feature-stability.csv`,
`report.json`, `candidate-robustness.json`, `final-audit.json`, `progress.json`.
Scripts `us_top10_daily_exit_state_audit` et `us_top10_daily_exit_state_verification`.
Aucun entraînement, backtest d'une nouvelle politique de sortie, SQL, API/LLM,
ordre ou changement de modèle/batch/configuration de production.
