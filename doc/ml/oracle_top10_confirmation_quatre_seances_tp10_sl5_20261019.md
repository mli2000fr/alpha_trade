# TOP10 Oracle H10 — confirmation jusqu'à J+2, entrée J+3

## Conclusion

**TERMINÉ / EXPLORATOIRE / PAS DE PROMOTION.** Ajouter la clôture de J+2
améliore le LONG en 2024, mais pas en 2025/2026. Les SHORT et le bras combiné
restent perdants dans les trois années. Le contrôle sans chevauchement ne
renverse pas ce constat. La quatrième clôture ne qualifie pas un filtre de
direction exploitable transversalement.

## Contrat avant calcul

Évolution demandée du [test trois clôtures](oracle_top10_confirmation_trois_seances_tp10_sl5_20261019.md).
Ce dernier, ses sources et ses résultats sont conservés sans modification.

- **TOP10 Oracle amplitude H10 à J**, mêmes scores annuels de recherche
  2024/2025/2026 que précédemment. Aucun nouveau modèle entraîné.
- LONG si les **quatre clôtures ajustées** respectent
  `C(J−1) < C(J) < C(J+1) < C(J+2)` ; SHORT si strictement décroissantes.
  Sinon abstention, sans remplacer le titre par le suivant du classement.
- Signal connu après clôture **J+2**, entrée open **J+3**. Les indices désignent
  des séances boursières, pas des jours calendaires.
- TP10 %, SL5 %, sans trailing ; dix séances maximum **entrée comprise**,
  soit sortie close **J+12** si aucun seuil atteint. Pas une sortie fixe J+10.
- Même qualification des prix, plus la séance supplémentaire : J−1 à J+12.
  OHLC ajustés cohérents, volume positif, barres non remplies artificiellement,
  continuité source/ajustement/identité, réserves DD/Qnity et TOELY inchangées.
- Frais supposés 8 bps par jambe ; emprunt SHORT 0,3 %/an. Gap de stop au prix
  d'ouverture, TP au prix limite ; stop-first lors d'une collision OHLC sauf
  ouverture départageant les seuils. SL5 ne garantit pas une perte limitée à 5 %.
- Référence sans confirmation : mêmes dix titres, **même entrée J+3**, mêmes
  protections et durée. Contrôles tous LONG/SHORT sur les mêmes paires confirmées.
- Répertoire et protocole distincts ; pas de recherche du meilleur nombre de
  jours sur les pertes puis d'annonce d'un résultat prédictif hors échantillon.

Les signaux couvrent 2024/2025 et 2026 jusqu'au **1er septembre** ; prix observés
au plus tard le 30 septembre. Le périmètre 2026 reste volontairement celui de
l'expérience précédente, même si cette règle pourrait mûrir d'autres dates.

## Résultats après frais supposés

**Moyennes par occasion**, pas rendements annuels de capital ni portefeuille
réel avec levier, nombre de positions limité, réentrées ou déduplication live.

| Signaux | LONG : nombre | LONG : gagnants | LONG : moyenne | SHORT : nombre | SHORT : gagnants | SHORT : moyenne | Combiné : moyenne |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 232 | 43,10 % | +0,915 % | 338 | 31,07 % | −1,296 % | −0,396 % |
| 2025 | 255 | 32,16 % | −0,756 % | 304 | 28,29 % | −1,301 % | −1,052 % |
| 2026 | 221 | 32,13 % | −0,415 % | 188 | 23,40 % | −2,034 % | −1,159 % |

Gagnant = résultat net positif après sortie TP/SL/échéance, pas signe du
rendement terminal sans protection ni précision d'une tête directionnelle.

| Signaux | Sans confirmation, tous LONG à J+3 | Sans confirmation, tous SHORT à J+3 | Confirmés, tous LONG en ignorant le sens | Confirmés, tous SHORT en ignorant le sens |
| --- | ---: | ---: | ---: | ---: |
| 2024 | +0,259 % | −0,782 % | +0,618 % | −1,384 % |
| 2025 | +0,358 % | −1,127 % | +0,008 % | −0,853 % |
| 2026 | +0,094 % | −0,524 % | +0,342 % | −1,183 % |

Le supplément LONG de 2024 n'est pas répété. Les intervalles descriptifs à 95 %
par blocs de vingt séances du supplément confirmé face au TOP10 de même sens
incluent zéro dans chaque année, pour LONG et SHORT. Ils utilisent les moyennes
quotidiennes sur les dates confirmées : pondération et calendrier différents
de la moyenne de toutes les occasions du tableau ; ne pas confondre les signes
des deux différences ni les présenter comme une certification statistique.

### Comparaison au test précédent et contrôle de l'heure d'entrée

| Signaux | Trois clôtures, entrée J+2 : combiné | Quatre clôtures, entrée J+3 : combiné |
| --- | ---: | ---: |
| 2024 | −0,669 % | −0,396 % |
| 2025 | −0,904 % | −1,052 % |
| 2026 | −0,500 % | −1,159 % |

Cette comparaison change **deux choses**, le filtre et l'entrée. Contrôle
descriptif supplémentaire ajouté à l'audit, non utilisé pour choisir la règle :
conserver la confirmation sur trois clôtures mais attendre également J+3, sur
les mêmes candidats et prix qualifiés que le nouveau test. Le combiné vaut alors
**−0,404 / −0,752 / −0,537 %** (2024/2025/2026). La quatrième clôture améliore
à peine 2024 et dégrade 2025/2026 même lorsque l'heure d'entrée est identique.
Résultats LONG de ce contrôle : +0,295/−0,208/−0,190 %, contre
+0,915/−0,756/−0,415 % avec quatre clôtures. Pas de promotion de ce contrôle
ajouté au reporting ni de nouveau test de stratégie sélectionné après observation.

### Contrôle sans chevauchement

Earliest-first par symbole/sens ; entrée suivante seulement après fin de toute
la fenêtre précédente de dix séances. Ce n'est pas un portefeuille agrégé et
les deux sens d'un même titre restent traités séparément.

| Signaux | LONG : épisodes / moyenne | SHORT : épisodes / moyenne | Combiné : épisodes / moyenne |
| --- | ---: | ---: | ---: |
| 2024 | 128 / +0,700 % | 172 / −0,626 % | 300 / −0,061 % |
| 2025 | 143 / −0,405 % | 151 / −0,960 % | 294 / −0,690 % |
| 2026 | 108 / −0,732 % | 94 / −1,662 % | 202 / −1,165 % |

## Couverture et limites

Mêmes **6 690 couples titre/date**, 669 dates, 161 symboles distincts, dix rangs
figés avant examen du futur. Tous les parcours de cette sous-population sont
qualifiés avec la séance supplémentaire ; aucun remplacement ou rendement nul
attribué à une donnée inconnue.

| Signaux | TOP10 total | Confirmations | Abstentions | Part confirmée |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 2 520 | 570 | 1 950 | 22,62 % |
| 2025 | 2 500 | 559 | 1 941 | 22,36 % |
| 2026 | 1 670 | 409 | 1 261 | 24,49 % |

Soit environ un quart des occasions, contre la moitié pour trois clôtures.
Les gaps de stop affectent 5,26/8,05/8,31 % du combiné ; pire perte nette
simulée −9,26/−23,93/−19,25 % selon l'année. Aucune amélioration fictive de fill
ne plafonne ces pertes au SL5. Les réserves de prix ajustés/OST, univers courant
survivant, années déjà examinées et absence de certification PIT complète des
features historiques restent celles de l'étude source. Pas de certification
de fills, locates, dividendes, marge ou coûts d'emprunt réels.

## Tests, audit et traçabilité

**118 tests passent**, dont treize spécifiques : quatre clôtures strictes,
J+2 indispensable, absence de dépendance à J+3 pour le sens, entrée J+3,
expiration J+12, gaps, contrôle des deux extrémités de la fenêtre, identités et
invariance du sens aux données futures manquantes.
Audit `PASS_EXPLORATORY_ONLY` : TOP10 identique au test précédent, 6 690
confirmations recalculées en scalaire, **13 380 sorties LONG/SHORT** vérifiées
par une boucle séparée, frais, moyennes, épisodes et contrats de dates contrôlés.
Chaque signal quatre clôtures est bien un sous-ensemble de même sens du signal
trois clôtures ; aucun reclassement ou nouvelle sélection par résultat futur.

Dossier : `artifacts/research/us_top10_four_session_confirmation/20261019-v1/`.
`protocol.json`, `selected-at-j.parquet`, `qualification.parquet`,
`evaluations.parquet`, `comparison.csv`, `report.json`, `final-audit.json`,
`three-vs-four-closes.json`, `same-entry-three-vs-four-control.json`,
`progress.json` et checkpoints `parts/`.

Scripts `us_top10_four_session_confirmation` et
`us_top10_four_session_confirmation_audit` sous `scripts/research/`.
Aucun entraînement, appel fournisseur/LLM, écriture SQL, modèle/batch/configuration
de production ou ordre modifié. **Fin de cette expérience ; pas d'enchaînement
automatique sur d'autres délais ou paramètres.**
