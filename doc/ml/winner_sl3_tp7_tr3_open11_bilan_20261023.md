# Winner SL3 / TP7 / trailing3 / open11 : bilan

23 octobre 2026. **TERMINÉ ET AUDITÉ / EXPLORATOIRE / PAS DE PROMOTION.**
[Protocole figé](winner_sl3_tp7_tr3_open11_protocole_20261023.md).
Canonique : `artifacts/research/us_winner_sl3_tp7_tr3_open11/20261023-v1`.

## Résultat principal

La variante augmente le taux gagnant et réduit le drawdown sur les deux années,
mais ne rend pas 2025 profitable et enlève beaucoup de rendement en 2026.
Elle ne domine donc pas le témoin. Pas de changement automatique en production.

Capital initial 4 000 USD par année/compte, frais 8 bps par jambe inclus.

| Année | Variante | Capital final USD | Rendement net | DD maximal | Gagnants / perdants | Taux gagnant |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | Winner SL7/TR15/open21 | 3 526,84 | −11,83 % | 15,73 % | 9 / 44 | 16,98 % |
| 2025 | SL3/TP7/TR3/open11 | 3 652,94 | −8,68 % | 9,68 % | 56 / 122 | 31,46 % |
| 2026 au 30/09 | Winner SL7/TR15/open21 | **4 798,24** | **+19,96 %** | 10,92 % | 38 / 82 | 31,67 % |
| 2026 au 30/09 | SL3/TP7/TR3/open11 | 4 172,07 | +4,30 % | **3,67 %** | 68 / 105 | **39,31 %** |

Le taux gagnant porte seulement sur les trades fermés. Variante : zéro position
ouverte fin2025, une fin2026 (528,75USD valorisés, cash3643,32USD). Témoin : zéro
et six. Pas de liquidation artificielle au cutoff. Les plus-values latentes
expliquent que rendement annuel et somme des PnL clôturés puissent différer.

Delta variante−témoin : rendement +3,15points en2025, −15,65en2026 ; taux gagnant
+14,48/+7,64points ; DD réduit de6,06/7,26points. Le DD est réalisé, pas garanti.

## Pourquoi davantage de victoires ne fait pas davantage de rendement

| Mesure de la variante | 2025 | 2026 au30/09 |
| --- | ---: | ---: |
| Trades clôturés | 178 | 173 |
| Gains cumulés nets USD | +770,04 | +1 203,63 |
| Pertes cumulées nettes USD | −1 117,10 | −1 051,14 |
| Gain moyen net USD | +13,75 | +17,70 |
| Perte moyenne nette USD | −9,16 | −10,01 |
| Profit factor réalisé | 0,689 | 1,145 |
| Frais USD | 131,78 | 131,60 |
| Capital brut moyen utilisé USD | 206,65 | 241,62 |
| Part moyenne de l'equity engagée | 5,43 % | 5,85 % |
| Capital brut maximal USD | 1 900,02 | 2 338,32 |
| Séances moyennes gagnantes, entrée incluse | 1,95 | 1,82 |
| Séances moyennes perdantes, entrée incluse | 1,46 | 1,44 |
| Durée gagnante moyenne en jours calendaires | 1,45 | 1,09 |
| Durée perdante moyenne en jours calendaires | 0,76 | 0,68 |

Le trailing3 % prend souvent les gains AVANT le TP7 %. Le rendement net médian
d'un gagnant est seulement **+2,02 % / +2,94 %**, celui d'un perdant
**−1,95 % / −2,15 %**. Il ne s'agit pas d'un système gagnant toujours7 % et
perdant toujours3 %. Le seuil théorique de31,6 % avec TP/SL seuls n'est donc
pas le seuil de rentabilité de cet ensemble de sorties.

Le capital utilisé moyen du témoin était340,90/1844,19USD, contre206,65/241,62
pour la variante. Le DD plus faible accompagne aussi une exposition beaucoup
plus faible ; ce n'est pas une comparaison à risque égal, ni une autorisation
de multiplier les tailles pour retrouver son rendement.

## Sorties effectivement déclenchées

| Motif | 2025 | 2026 |
| --- | ---: | ---: |
| STOP intrabar, initial ou remonté | 142 | 129 |
| STOP à l'ouverture, gap | 18 | 13 |
| TP intrabar | 14 | 28 |
| TP sur gap, prix plafonné au TP | 3 | 1 |
| Stop remonté puis cours déjà inférieur | 1 | 2 |
| Vente à l'ouverture de la11e séance | **0** | **0** |

Tous les trades clôturés sortent avant l'échéance. Open11 est raccordé et
vérifié par le calendrier, mais n'est pas le moteur des résultats ici.
Ne pas attribuer la variation à l'horizon seul. SL, TP, trailing et horizon
ont changé ensemble ; aucune attribution causale individuelle démontrée.

## Fidélité de la comparaison

- Mêmes signaux TOP10 Oracle parcours H20 annuels, sans filtre de classement,
  ATR ou direction supplémentaire ; même attente20 et confirmation5m.
- Même cohorte native1428/1027 sur2510/1880signaux, requalification exactement
  identique ; mêmes données SIP raw régulières/nonremplies et daily archivés.
- Même formule de sizing natif et plafonds, mais pas mêmes quantités avecSL3.
  Même demi-position, sans renforcement/réachat d'un titre déjà détenu.
- Risque natif/B4DD15, plafonds secteur/corrélation/concentration hérités,
  exposition effective1x. Le YAML peut autoriser2x mais son plafond de risque
  plus strict n'est pas relevé pour cette expérience.
- B4 garde ici allocation1 dans les deux années. Le témoin2025 était réduit
  dèsavril ; sorties, cash et activité divergent donc après les premiers écarts.
- Références WINNER_ONLY natives déjà auditées réutilisées par leurs empreintes,
  pas un nouveau rejeu des témoins, ni le HALF_CONTROL historique+12,92 %.

## Contrôles et livrables

24tests ciblés passent ; smoke préalable5séances2025 :11achats et11sorties
reconstruits. Smoke séparé, jamais présenté comme rendement annuel.
Calcul complet : **352achats et351sorties** vérifiés ; reconstructeur scalaire
distinct pour SL/TP/trailing/gaps/ratchet/échéance ; cash, frais, positions,
prix/horaires, DD et métriques réconciliés. Audit final PASS ; empreintes des
sources/rapports revérifiées après calcul. Même assistant, pas revue humaine.

La vérification du runtime a aussi corrigé l'audit descriptif des pertes :
STOP intrabar à FIN de5m, pas début. Nouvelle archive descriptiveV2, anciennes
sources intactes, mêmes catégories/chiffres principaux et sondes pré-entrée
exactement identiques. [Amendement](winner_audit_pertes_amendement_horloge_20261023.md).
Cette correction ne change aucun rendement de portefeuille.

Dans le dossier canonique :

- `annual-summary.csv` : témoin et variante, parannée.
- `variant-metrics-audited.csv` : durées en séances et métriques contrôlées.
- `final-audit.json` : bilan des vérifications et empreintes.
- Sous-dossiers annuels : trades, événements, equity5m/daily, B4, refus entiers.

Aucun entraînement, SQL, téléchargement, appel fournisseur/LLM/broker, ordre,
activation, batch, YAML ou moteur de production modifié. Ce n'est pas une
parité broker historique complète : cohorte sélectionnée sur couverture future,
survivants, secteurs actuels, inventaire OST parent vide/non exhaustif,
dailySPYrévisable et absence de quotes/fills certifiés.
Années déjà vues : résultat exploratoire, pas nouveau holdout indépendant.

**Conclusion :** meilleur taux gagnant et DD inférieur, mais pas d'amélioration
transversale du rendement. Conserver les deux résultats, sans promouvoir cette
variante ni lancer une nouvelle grille après lecture.
