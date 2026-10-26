# FR P0/P1 : petit gain exploratoire du mélange prix/AMF

26 octobre 2026. Comparaison terminée, sans entraînement, optimisation de poids,
seuils, retournement de signe, nouvel accès SQL/API/LLM, ordre ou changement batch.
Huit tests passent. Sources figées et sceaux vérifiés avant/après calcul.

## Règle unique fixée

Prix seuls = moyenne des rangs momentum5 et20. AMF seule = rang de la variation
des positions publiées chez les mêmes détenteurs (diminution orientée LONG).
Mélange =50%prix/50%AMF, donc25%momentum5/25%momentum20/50%AMF.
Rangs calculés sur les candidats aux features complètes disponibles avant open,
AVANT toute sélection par maturité ou résultat futur. Aucun remplissage à zéro.
Score constant =rang0,5. Score de classement, pas probabilité LONG calibrée.

Les trois comparateurs portent sur exactement les mêmes titres/dates et labels :
plus grande excursion favorable avant SL10 propre à LONG/SHORT, pas clôture
terminale ni performance économique. L'absence de textes DILA qualifiés empêche
d'en faire une direction. ConsensusP3 et sources bloquées restent hors périmètre.

## Résultats comparables

| Horizon | Observations évaluées | Titres distincts | Dates | AUC prix seuls | AUC AMF seule | AUC mélange | Écart mélange−prix |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| H5 | 287 | 50 | 6 | 0,5769 | 0,5292 | 0,5885 | +0,0116 |
| H10 | 47 | 47 | 1 | 0,6118 | 0,5736 | 0,6609 | +0,0491 |
| H20 | 0 | 0 | 0 | indisponible | indisponible | indisponible | nonmesurable |

AUC =moyenne des AUC par date contenant les deux classes. Les scores constants
comptent0,5 : les dates ne sont pas supprimées différemment selon la méthode.
Ces valeurs ne sont PAS comparables directement aux AUC sur les274titres du
premier audit : l'intersection avec AMF réduit le périmètre à50titres.
Les50titres ne représentent pas l'ensemble des293codes FR de collecte.

À H5 :159labels de parcours LONGdominant et128SHORTdominant. À H10 :25/22.
Ce ne sont pas des trades gagnants/perdants, ni des opérations réalisables au pic.
477scores titre/date sont archivés sur50titres/10dates, y compris ceux dont
les chemins futurs sont encore nonmûrs. Tous les labelsH20 restent nonmûrs.

## Détail par date H5

| Entrée | Titres évalués | Prix | AMF | Mélange | Écart mélange−prix |
| --- | ---: | ---: | ---: | ---: | ---: |
| 12octobre | 47 | 0,6753 | 0,5552 | 0,6970 | +0,0216 |
| 13octobre | 48 | 0,5684 | 0,5586 | 0,5850 | +0,0166 |
| 14octobre | 49 | 0,5726 | 0,5285 | 0,6057 | +0,0331 |
| 15octobre | 48 | 0,4528 | 0,5333 | 0,4880 | +0,0352 |
| 16octobre | 47 | 0,6784 | 0,4536 | 0,6220 | −0,0565 |
| 19octobre | 48 | 0,5137 | 0,5459 | 0,5332 | +0,0195 |

Le mélange dépasse les prix sur5/6dates, mais le16octobre il les dégrade nettement.
Le15octobre il améliore le comparateur tout en restant sous0,5 : amélioration
relative ne veut pas dire bon signal directionnel ce jour-là.

## Contrôles descriptifs, sans réapprentissage

- Cohortes H5 sans chevauchement des fenêtres :12et19octobre,95observations
  sur50titres. Prix0,5945, AMF0,5505, mélange0,6151, écart+0,0206. Seulement
  DEUX dates, pas une validation indépendante ni95événements indépendants.
- Première observation par titre à H5 :50titres, AUC poolée prix0,6705,
  AMF0,5571, mélange0,6933. La plupart sont issus de la même date de marché.
- En retirant successivement une des six dates de la moyenneH5, l'écart
  mélange−prix reste positif, entre+0,0069et+0,0252. Il s'agit d'une sensibilité
  de la métrique, pas de folds entraînés/testés, test de significativité ou preuve OOS.
- H10 : une seule date,12octobre ; les contrôles redonnent le même échantillon,
  pas des confirmations supplémentaires.

## Conclusion bornée

**Petit indice de complémentarité prix/variationsAMF**, pas preuve d'un avantage
exploitable. Aucun poids à retoucher après ce résultat. Garder cette règle exacte
comme candidate de recherche et l'évaluer ultérieurement sur plusieurs nouvelles
cohortes mûres. Ne pas promouvoir le score en filtre/live ou déduire un rendement.
Le H20 demandé reste nonmesurable sur le snapshot au23octobre ; première fin
théorique2novembre pour l'entrée6octobre, sous réserve de cours complets.
Les premières observations du H20 ne suffiront pas à elles seules à valider
un signal stable. Les diagnostics individuels de cette période avaient déjà
été consultés avant la définition du mélange ; pas de holdout vierge revendiqué.

Réserves héritées : échantillon court, mêmes titres/fenêtres répétés, univers
courant survivant, données fournisseurs/révisions et corporate actions non
qualifiées indépendamment, daily ne permettant pas toujours l'ordre intraday,
aucune qualification borrow SHORT ni PnL après frais/risque/exécution.

Artefacts : `artifacts/fr/research/p0_p1_equal_mix/20261026-v1` :
`protocol.json`, `asof-scores.parquet`, `scored-diagnostics.parquet`, `report.json`,
`seal.json`. Le protocole et les sources précédents sont laissés intacts.
