# Résultat — exclusion GPT1–5 sur Winner LONG, août2026

Terminé et audité le25 octobre2026. Un seul compte nouveau, trois témoins
audités réutilisés ; zéro nouvel appel GPT, fournisseur, SQL ou ordre.
[Protocole scellé](winner_veto_gpt_1_5_aout_2026.md).

Même TOP20 Oracle, signaux du3 au31 août, portefeuille suivi au30 septembre2026,
4000USD, demi-position, sans renforcement, cap1x, SL7 fixe, sans TP/trailing,
H20/open21 depuis le fill, frais8pb/jambe et contraintes natives inchangés.
Pas les règles de liquidation globale/pause des expériences mensuelles.

| Mesure | Winner seul | Veto1–3 | Veto1–4 | Veto1–5 |
| --- | ---: | ---: | ---: | ---: |
| Capital final valorisé USD | 3942,06 | 3942,06 | 4019,44 | 3968,81 |
| Rendement net | −1,45 % | −1,45 % | +0,49 % | −0,78 % |
| DD maximal5m | −11,55 % | −11,55 % | −9,87 % | −10,05 % |
| Achats exécutés | 29 | 29 | 26 | 25 |
| Trades clôturés | 24 | 24 | 21 | 21 |
| Gagnants / perdants clôturés | 2 / 22 | 2 / 22 | 2 / 19 | 2 / 19 |
| Taux gagnant clôturé | 8,33 % | 8,33 % | 9,52 % | 9,52 % |
| PnL gagnants clôturés USD | +58,02 | +58,02 | +58,02 | +58,02 |
| PnL perdants clôturés USD | −445,77 | −445,77 | −374,24 | −371,20 |
| Gain moyen gagnant USD | +29,01 | +29,01 | +29,01 | +29,01 |
| Perte moyenne perdante USD | −20,26 | −20,26 | −19,70 | −19,54 |
| Capital brut utilisé moyen USD | 1551,74 | 1551,74 | 1475,57 | 1318,49 |
| Frais USD | 11,27 | 11,27 | 9,94 | 9,71 |
| Positions encore ouvertes | 5 | 5 | 5 | 4 |

## Lecture

Veto1–5 fait **+26,75USD/+0,67point** contre Winner seul, mais
**−50,64USD/−1,27point** contre veto1–4. Le DD se dégrade légèrement par rapport
à1–4 et le taux gagnant reste inchangé. Le seuil1–4 reste meilleur parmi
ces quatre comptes **sur ce seul mois**, pas comme règle validée hors échantillon.

193 avis1–5 sur420 d'origine ;86 dans les237 signaux admissibles, soit12
scores5 supplémentaires contre le veto1–4. Ces86 couples concernent17 sociétés,
pas86 achats évités.151 signaux restent admissibles, dont77 avis invalides ou
sans score maintenus sans veto. On n'achète donc pas exclusivement les avis
VALID6–10. Aucun reclassement/remplacementTOP21.

Le veto intervient à la création des plans et non comme un blocage permanent
du symbole au moment du fill. Les anciens plans restent valides, les positions
ouvertes ne sont pas vendues à cause d'un avis ultérieur.

## Pourquoi le résultat baisse malgré un PnL clôturé un peu meilleur ?

Le1–4 détient encore une action MRVL entrée le3 septembre à210,36USD,
valorisée264,20USD au30 septembre. Sa contribution latente, frais d'entrée
déduits, vaut **+53,67USD**. Cette position n'existe plus dans le1–5 ; les
quatre autres positions finales ont les mêmes quantités et valorisations.
Le PnL total clôturé s'améliore seulement de **3,04USD** : net final
`+3,04 −53,67 = −50,64USD` contre1–4.

Cela ne prouve pas qu'un avis5 a directement supprimé ce seul achat : le
replay a aussi modifié des achats antérieurs, les liquidités et la trajectoire
des gardes de concentration. Comparaison des clôtures contre1–4 : une ancienne
perte de−21,82USD absente, une nouvelle perte de−16,29USD, plus des différences
sur des trades communs. Pas d'attribution causale naïve à des « pertes évitées ».

## Audit et limites

25 entrées et21 sorties scalaires auditées, cash/frais/PnL/positions/DD
réconciliés. Cohorte strictement identique hors veto. Sources et fichiers
vérifiés après résultat ;15 tests passent avec les tests des extensions
précédentes. Les quatre positions ouvertes sont valorisées et ne sont pas
classées dans le taux gagnant des21 clôtures.

GPT rétrospectif non PIT, petit mois déjà observé, seuil choisi après les essais
précédents, univers/secteurs actuels et filtrage de couverture future : pas de
preuve de robustesse, pas de promotion live. Le capital final peut dépendre
sensiblement de quelques positions non clôturées. Aucun paramètre de production
modifié et aucune nouvelle dépense LLM.

Rapport :
`artifacts/research/us_winner_gpt_veto_august_2026/20261025-score1-5-v1/report.json`.
