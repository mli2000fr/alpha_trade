# Résultats SHORT — août2026, SL7 sans TP/trailing

Huit comptes terminés et audités le25 octobre2026 : six SHORT et deux témoins
LONG. [Protocole figé](gpt_short_aout_2026.md). Signaux TOP20 du3 au31 août,
suivi jusqu'au30 septembre,4000USD,demi-position,cap1x,frais8pb/jambe,
sortie open21. Confirmation SHORT = cassure fraîche du plus bas précédent
puis deux clôtures5m sous ce seuil, exécution à l'open suivant. Pas de renfort.

## Pourquoi les taux LONG étaient faibles

La même cohorte exploitable contient237 couples titre/date :130 ont une
excursion négative absolue supérieure à la positive,106 l'inverse,1 égalité.
Soit54,85% de dominantes négatives, pas une écrasante majorité baissière.
141/237 finissent H20 sous l'openJ+1,96 au-dessus. Ces mesures ne sont PAS les
gains d'une stratégie avec stop : une hausse adverse peut précéder la baisse.
Les couples répétés ne sont pas237 observations indépendantes.

Winner LONG sans veto :24 clôtures,2 gagnantes à échéance,22 pertes via16
touches SL et6 gaps. Les5 positions encore ouvertes sont valorisées dans le
capital mais pas dans le taux gagnant clôturé8,33%. Amplitude Oracle n'est
ni direction ni probabilité d'éviter un stop7% pendant20 séances.

## Six comptes SHORT

| Entrée | Veto GPT | Capital final USD | Rendement net | DD5m | Clôtures | Gains/pertes | Taux gagnant | PnL gains USD | PnL pertes USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Directe openJ+1 | Aucun |3982,14|−0,45%|−7,41%|18|5/13|27,78%|246,28|−264,14|
| Directe openJ+1 |7–9|3989,82|−0,25%|−6,03%|16|5/11|31,25%|206,08|−216,25|
| Directe openJ+1 |6–9|4003,57|+0,09%|−6,84%|16|5/11|31,25%|222,10|−218,52|
| Confirmée baissière |Aucun|3795,47|−5,11%|−6,60%|20|3/17|15,00%|122,08|−329,47|
| Confirmée baissière |7–9|3812,87|−4,68%|−6,38%|20|3/17|15,00%|130,79|−320,77|
| Confirmée baissière |6–9|3816,71|−4,58%|−6,38%|20|3/17|15,00%|130,79|−316,93|

Les trois confirmés ont21 entrées et1 position REZI restante valorisée.
Les trois directs sont totalement clôturés. PnL gagnants/perdants inclut frais
et emprunt ; ne pas soustraire les frais à nouveau. Les confirmés ont environ
2,85USD de contribution nette de la position restante, d'où différence entre
somme des PnL clôturés et variation du capital final.

Veto7–9 :32/237 signaux exclus,205 restants. Veto6–9 :74 exclus,163 restants.
Les77 avis invalides restent sans veto. Aucun score8,9,10 dans la cohorte
valide : ici7–9 revient à retirer les7 ;6–9 à retirer6 et7. Pas de reclassement.
Caps d'origine conservés :8 positions totales mais5 SHORT maximum ; exposition
moyenne754,99/789,43/778,39USD en direct,856,61/859,12/850,21USD en confirmé.
La différence de rendement n'est pas uniquement une comparaison de direction
à exposition identique. Emprunt supposé0,3%/an : coûts totaux observés0,47–0,53USD,
pas un prix historique garanti ni un accès à l'emprunt démontré.

## Contrôles

**14 tests passent**. Les deux nouveaux témoins LONG reproduisent tous les
achats, toutes les sorties et toutes les courbes5m des comparateurs natifs
précédents (tolérance numérique1e−8USD), pas seulement le capital final.
Contrôles indépendants des6 SHORT : signaux retenus, absence de doublon, maximum5
positions, gross1x à l'entrée, comptabilité du collatéral, frais/emprunt,
sorties scalaires, stops de la bougie d'entrée, échéance21 et DD.
Tous les fichiers scellés et sources vérifiés après exécution.

## Conclusion et limites

Le SHORT direct fait moins mal que les anciens LONG directs sur ce mois,
mais aucun avantage exploitable démontré : le meilleur résultat est seulement
**+3,57USD**, sensible à l'emprunt réel et aux frictions. La confirmation
baissière ne résout pas le problème et dégrade les trois rendements observés.
Un faible taux LONG ne signifie pas qu'inverser tous les paris sera rentable.

GPT rétrospectif nonPIT, couverture future, secteurs actuels, répétitions de
titres, seuils choisis après observations et un seul mois : pas de holdout
indépendant ni preuve de performance live. Aucun appelGPT/fournisseur, SQL,
entraînement, ordre ou changement production.

Rapport :`artifacts/research/us_winner_gpt_veto_august_2026/20261025-short-v1/report.json`.
