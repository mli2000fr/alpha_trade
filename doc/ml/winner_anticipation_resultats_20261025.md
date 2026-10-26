# Anticiper les périodes défavorables Winner : audit terminé, aucun veto validé

25octobre2026. [Protocole figé](winner_anticipation_protocole_20261025.md).
Demande : trouver des contextes observables AVANT les entrées pour réduire
le capital engagé dans des épisodes comme2024. Audit local des deux replays
SL5/min70 et SL1/min70, TOP20,4kUSD continu2020–24, pas de nouveau portefeuille.

## Méthode et contrôles

Six règles uniquement : SPY<SMA50, volSPY20>médiane126, breadth20 du TOP20<50%,
momentum20 relatif titre/SPY négatif, ATR20/close≥5%, PF des20derniers trades
clôturés<1. À chaque entrée réelle, dernière clôture NYSE strictement antérieure ;
aucune clôture du jour d'entrée, étiquette future, news ou macro révisée présentée
comme PIT. Le panier courant utilise les20rangs initiaux, pas les titres qualifiés
sur leurs données futures. Les informations manquantes restent inconnues.

Un seul choix sur2020–22, sorties ET maturités communes connues avant2023 ;
support minimal et stabilité sur2ans imposés. Choix figé avant l'agrégation
2023/24. Résultat mesuré : moyenne du rendement NET par dollar du trade accepté,
pas rendement cumulé de portefeuille ni calcul d'un faux capital après veto.
Entrées récentes privées d'open21 exclues même en cas de stop précoce :9clôtures
SL5 et18SL1 réservées. Positions encore ouvertes non transformées en pertes.

Cinq tests passent. Revue supplémentaire : douze égalités EXACTES de features
sur quatre préfixes d'archives (2020/2021/2023/2024),103 états de santé recalculés
depuis les seuls trades déjà clôturés, toutes les dates sources strictement avant
le fill, correspondance exacte des entrées et allocations natives B4.
Même assistant : pas de revue humaine indépendante.

## Résultat primaire : le signal de développement s'inverse

Signal retenu : moins de50% du TOP20 courant ont un rendement20 positif.
Écart défavorable−favorable de rendement net unitaire, moyenne annuelle de
développement :−4,005points. Signal négatif2020/21 mais légèrement positif2022.

| Entrées SL5 | Panier «faible» | Panier non faible | Écart faible−autre |
|---|---:|---:|---:|
| 2023 | +2,348%,128trades | +1,614%,76trades | **+0,734point** |
| 2024 | +1,686%,137trades | −4,499%,49trades | **+6,185points** |

Bootstrap par mois d'entrée,3000tirages : IC95 écart2023[−4,709;+6,573],
2024[+1,706;+12,012]. Le sens attendu n'est pas confirmé. SL1 : écarts également
positifs,+1,189point2023 et+0,240point2024. Cela ne valide PAS après coup un
filtre inversé. Sur2024SL5, couper ce panier aurait ciblé50,25% de la masse
des pertes mais aussi79,05% des gains clôturés de l'échantillon commun.
On ne peut pas soustraire ces PnL pour simuler le portefeuille alternatif.

## Les cinq autres règles ne fournissent pas de secours transversal

Écart rendement net moyen du groupe signalé moins non signalé, points :

| Règle signalée | SL5 entrées2023 | SL5 entrées2024 |
|---|---:|---:|
| SPY sous SMA50 | +0,177 | +5,145 |
| VolSPY20 élevée | −2,551 | +4,167 |
| Momentum20 relatif négatif | +1,940 | +2,456 |
| ATR20≥5% | +0,481 | −0,810 |
| PF des20dernières clôtures<1 | +4,471 | −2,179 |

Ce sont cinq diagnostics SECONDAIRES, pas cinq tests sélectionnés pour promotion.
La volatilité, l'ATR et la santé récente changent de signe selon l'année.
L'ATR manque aussi de deux états suffisamment représentés en développement.
Couper après les pertes récentes paraît protecteur2024, mais cible des rebonds
favorables2023. Les groupes ne sont ni exposés ni composés de titres identiques.

## Le B4 réduisait déjà le risque

Parmi les186entréesSL5 de2024 avec maturité commune,177 ont une allocation
native réduite et9 pleine, contre136réduites/68pleines sur204entrées2023.
Cela concerne le budget des NOUVELLES entrées, pas un plafond de détention totale
ni la preuve qu'un capital identique était exposé dans les deux années.

Stratification sans nouvelle sélection : chez les entrées déjà réduites,
breadth faible écart−1,289point2023 puis+6,038points2024 ; santé PF<1,
+5,423points2023 puis−4,060points2024. L'instabilité demeure. Échantillon
plein2024 trop petit, aucun modèle de sous-régime ou seuil ajouté.

## Conclusion et limites

**NO_ROBUST_EARLY_WARNING_VALIDATED.** Aucun des six avertissements ne donne
ici une justification transversale à une réduction supplémentaire du capital.
Ce n'est pas l'affirmation qu'aucun signal n'existe ; ces règles précises n'ont
pas passé le contrôle chronologique. Pas de nouvelle recherche de seuils ou
combinaisons après observation, ni de retrait des protections existantes.

Années déjà vues, OOF/historiques révisés, sélection par couverture future,
survivants et admission conditionnée au B4. Interdépendances entre titres,
mois et fenêtres ; SL1 non indépendant. Une santé passée faible est réactive,
pas la prédiction prouvée du premier retournement futur. Aucun modèle ajusté,
SQL/API/LLM/replay/ordre ou modification de production.

Rapports et contextes :
`artifacts/research/us_winner_anticipation_audit/20261025-v1`.
`protocol.json`, `frozen-development-choice.json`, `report.json`,
`post-review.json`, `sl5-entry-contexts.parquet`, `sl1-entry-contexts.parquet`,
et leurs copies enrichies des états B4 pour revue. Résultats par ANNÉE D'ENTRÉE,
donc différents du diagnostic précédent par ANNÉE DE SORTIE et du PnL annuel MTM.
