# US — Désaccord Oracle × ATR : résultats

4 octobre 2026. [Protocole figé](us_oracle_atr_desaccord_protocole.md).
Statut : **avantage historique d'amplitude ; pas de direction exploitable
démontrée pour le groupe Oracle seul**. Pas de promotion production.

## 1. Périmètre et définitions

Panels déjà disponibles du batch H20 `model-factory-20261003082853-e98332`,
2019–2025 et T1 2026 : 3 196 186 observations symbole–date, 1 821 séances.
Pas de nouvel entraînement ni de nouvelle prédiction de modèle. Les scores
historiques causaux sont ceux utilisés dans les audits précédents.

Les quatre groupes sont établis avant jointure des labels futurs. ATR
désigne ATR20/prix, pas l'ATR en dollars. TOP20 conserve les percentiles
quotidiens moyens >=0,8, comme précédemment. Aucun candidat n'est écarté
pour un mauvais label avant classement ; 214 observations sont ensuite
signalées avec label inconnu/invalide, non utilisées dans les statistiques
réalisées. Aucun panel n'a de ligne exclue pour score/ATR/volatilité non fini.

« Vrai extrême » = `oracle_extreme10` natif, deux queues de 10 % du
rendement ajusté H20 dans l'univers complet. Le rendement absolu mesure
l'amplitude **terminale**, pas le maximum du chemin, MFE/MAE ou la range.
Il ne faut pas confondre ce label et une probabilité LONG.

## 2. Résultats globaux des quatre groupes

Les statistiques sont pondérées par observation symbole–date, non par
trade indépendant. Les deux TOP20 représentent environ 20,03 % chacun
avec les conventions de rang/ex æquo.

| Groupe | Effectif | Part de l'univers | Vrais extrêmes | D10 | D1 | H20 moyen brut | H20 absolu moyen |
|---|---:|---:|---:|---:|---:|---:|---:|
| Oracle ET ATR TOP20 | 496 780 | 15,54 % | 41,76 % | 21,93 % | 19,83 % | +2,54 % | 12,97 % |
| Oracle seul | 143 330 | 4,48 % | 34,37 % | 17,58 % | 16,79 % | +1,46 % | 10,69 % |
| ATR seul | 143 318 | 4,48 % | 25,70 % | 12,94 % | 12,76 % | +1,14 % | 9,28 % |
| Ni Oracle ni ATR | 2 412 758 | 75,49 % | 14,08 % | 6,83 % | 7,25 % | +0,94 % | 6,82 % |

L'intersection reste la plus riche en extrêmes. Oracle seul conserve
néanmoins davantage d'extrêmes que le groupe ni l'un ni l'autre. La
comparaison directe Oracle seul/ATR seul n'est **pas** un contrôle de
volatilité : les gates les placent de part et d'autre du seuil ATR.

Le rendement moyen global légèrement supérieur d'Oracle seul n'établit
pas un avantage LONG robuste : il varie avec les périodes et ne comprend
aucun coût, sizing ou prix d'exécution.

## 3. Contrôle de volatilité fixé avant calcul

Cellules date × décile ATR × tercile volatilité60, avec au moins cinq
labels valides de chaque côté. Chaque cellule est pondérée par le minimum
de ses deux effectifs ; chaque date reçoit ensuite le même poids.
Cela contrôle grossièrement deux dimensions de volatilité, **pas une
égalité exacte de volatilité, ni toutes les expositions de risque**.

| Comparaison | Gain de vrais extrêmes | Gain de D10 | Gain de D1 | Delta H20 brut | Delta H20 absolu |
|---|---:|---:|---:|---:|---:|
| BOTH − ATR seul, parmi ATR TOP20 | +11,82 points | +6,73 pts | +5,09 pts | +0,73 pt | +2,36 pts |
| Oracle seul − NEITHER, hors ATR TOP20 | +10,91 points | +5,94 pts | +4,97 pts | +0,41 pt | +1,79 pt |
| Oracle retenu − non retenu, strates communes | +11,34 points | +6,30 pts | +5,04 pts | +0,55 pt | +2,06 pts |

L'avantage d'amplitude demeure après ce contrôle. Mais l'augmentation
de D10 s'accompagne d'une augmentation de D1 : Oracle détecte les deux
queues et ne résout pas leur sens.

Les supports des trois contrastes sont respectivement 567 394, 517 689
et 1 085 192 observations ; chaque comparaison couvre les 1 821 dates.
Le contraste global porte sur environ 34 % des observations totales,
pas sur tous les titres. Ces effectifs se recouvrent entre comparaisons,
ils ne doivent pas être additionnés comme des échantillons indépendants.

### Incertitude exploratoire

Bootstrap mobile en blocs de 21 séances, 500 répétitions, seed20261004 :

- BOTH − ATR seul : delta extrêmes +11,82 pts, intervalle95 % [10,97 ; 12,82].
- Oracle seul − NEITHER : +10,91 pts, intervalle [9,89 ; 11,89].
- Oracle retenu − non retenu : +11,34 pts, intervalle [10,50 ; 12,22].

Les trois avantages d'amplitude sont positifs dans chacune des sept années
et au T1 2026. Ils ne constituent toutefois pas une preuve prospective,
causale ou nette de coûts. Les blocs opèrent sur les dates avec support,
les vintages d'origine et l'univers historique complet ne sont pas certifiés.

## 4. Direction : le groupe Oracle seul ne résout pas le problème

| Période | D10 Oracle seul | D1 Oracle seul | H20 moyen Oracle seul |
|---|---:|---:|---:|
| 2023 | 16,94 % | 16,27 % | +1,45 % |
| 2024 | 18,23 % | 17,18 % | +1,66 % |
| 2025 | 17,80 % | 18,21 % | +1,04 % |
| T1 2026 | 15,73 % | 19,35 % | −0,59 % |

Au T1 2026, Oracle seul atteint encore **35,08 % de vrais extrêmes**,
mais D1 dépasse D10. Son rendement est −2,90 % en janvier, −5,67 % en
février, +5,55 % en mars. Détection de mouvement et choix LONG restent
deux missions différentes.

À volatilité comparable, Oracle seul − NEITHER donne :

- 2023–2025 : amplitude +11,74 points, rendement +0,19 point ; l'intervalle
  exploratoire du rendement [−0,25 ; +0,77] inclut zéro.
- T1 2026 : amplitude +9,19 points ; D10 +2,40 points mais D1 +6,79 points,
  rendement −1,29 point, intervalle [−4,07 ; +1,81].

Ces données ne permettent pas de transformer la cohorte Oracle seul en
une stratégie SHORT non plus : elle contient des gagnants, le rendement
varie et aucun borrow/coût/exécution n'est simulé.

## 5. Régime archivé

Tous les jours ont un mode reconnu et des champs macro renseignés dans
l'instantané actuel. LONG autorisé = mode normal ET permission générale,
sinon blocage conformément aux modes du code. Il s'agit du mode à J, pas
d'un rejeu complet des sorties, de l'état d'un compte ou de l'ouverture J+1.

| Groupe | H20 moyen, LONG autorisé | H20 moyen, LONG bloqué |
|---|---:|---:|
| BOTH | +1,51 % | +5,08 % |
| Oracle seul | +0,80 % | +3,40 % |
| ATR seul | +0,52 % | +2,96 % |
| NEITHER | +0,43 % | +2,23 % |

Le régime écarte également des cohortes de rebond favorables. Ces moyennes
ne sont pas une justification pour désactiver les protections ; elles ne
mesurent ni drawdown, ni perte intrapériode, ni risque d'exécution. Les
contrastes appariés ci-dessus ne sont pas conditionnés au régime : les
tableaux de régime sont les distributions brutes des groupes.

## 6. Conclusion et suite

**Oracle n'est pas seulement une copie de l'ATR** : son classement repère
des extrêmes supplémentaires à niveau ATR/volatilité grossièrement comparable.
En revanche, **le désaccord Oracle seul ne fournit pas une direction LONG
stable**, notamment en 2025 et au T1 2026.

L'intersection n'élimine donc pas un sous-univers clairement supérieur pour
le LONG ; elle concentre davantage l'amplitude. Garder Oracle pour détecter
les mouvements est compatible avec ces résultats, mais ni Oracle seul ni
ATR seul ne doit être promu en règle directionnelle sur cet audit.

Une exploitation future de l'amplitude exigerait soit une information
directionnelle nouvelle, soit une stratégie adaptée à l'amplitude avec
ses propres données et coûts. Ce rapport ne propose pas automatiquement
une stratégie options, ni une modification du modèle existant.

## 7. Traçabilité

Script : `scripts/research/us_oracle_atr_disagreement.py`.
Sortie : `artifacts/research/us_atr_oracle_sentiment/oracle-atr-disagreement-20261004-v1/`.
Rapport annuel/mensuel/semestriel, mode, contrastes par année et fenêtre,
hashes protocole/panels/labels dans `report.json`; cohortes annuelles,
`daily_groups.parquet`, `daily_matched.parquet`, macro_snapshot.parquet.
progress.json COMPLETED. Deux tests passent : partition exhaustive,
indépendance des gates aux labels, contraste attendu et support minimal.

Réserves : univers actuel survivant, périodes déjà examinées, prix ajustés
reconstitués, disponibilité macro/vintages non certifiée, rendements
chevauchants et répétés, absence de coûts ou de portefeuille. Aucun fit,
aucune écriture SQL ni modification d'un batch existant.
