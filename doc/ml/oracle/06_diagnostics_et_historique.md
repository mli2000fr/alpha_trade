# Oracle Extreme — diagnostics, expériences et statut actuel

Retour : [dossier Oracle](README.md)

Synthèse transversale des campagnes : [expériences Oracle](../../experiences/oracle_extreme.md).

## Évolution synthétique

La spécification initiale proposait Oracle TOP/BOTTOM au-dessus de B25. Les diagnostics ont montré une forte proximité des deux scores et une difficulté à distinguer le signe. Le contrat a évolué vers un modèle unique de magnitude `oracle_extreme10`, puis vers O0 sans Global Rank et un gate percentile quotidien.

Cette chronologie explique le code ; elle ne prouve pas une promotion actuelle.

## Diagnostics disponibles

| Module | Question |
|---|---|
| `audit.py` | capture, déciles, golden |
| `hard_negatives.py` | faux extrêmes difficiles |
| `error_severity.py` | sévérité/rang continu |
| `feature_diagnostic.py` | séparabilité des features |
| `directional_features.py` | signal signé |
| `fundamental_diagnostic.py` | fondamentaux/sentiment |
| `catastrophic_detector.py` | rejet des cas sévères |
| `confound_validation.py` | couverture et faux signaux |

Ces scripts contiennent parfois dates/defaults expérimentaux et ne sont pas des gates live.

## Enseignements durables

- capture ML améliorée ne garantit pas PnL ;
- un filtre libère parfois une capacité remplie par de moins bons candidats ;
- un score cascade peut être ignoré si l’aval retrie sur `p_side` ;
- TOP/BOTTOM peuvent apprendre la magnitude commune ;
- une feature rare peut créer un faux signal ;
- les recherches per-symbol souffrent fortement du multiple testing ;
- le lifecycle doit être identique pour attribuer une amélioration.

## Statut effectif

La présence du code ne signifie pas activation. Vérifier commande, config, batch, champions, prédictions, mode cascade/risk et metadata du run.

Les anciens verdicts concernent leurs données et protocoles. Réouvrir exige une information nouvelle, une hypothèse préfixée et un holdout non consulté.

## Protocole de réouverture

1. Définir l’information nouvelle.
2. Geler baseline, univers, folds, lifecycle et coûts.
3. Déclarer métriques ML et trading.
4. Réserver le holdout.
5. Vérifier PIT/couverture avant le modèle.
6. Tester O0 avant les combinaisons.
7. Mesurer seeds, folds et concentrations.
8. Rejouer production parity.
9. Conserver artefacts et verdict synthétique.

## Non repris

Les tableaux complets de campagnes, ids de runs, listes de seeds, prompts et trades individuels restent des archives. Leur conclusion durable est conservée ici sans présenter leurs chiffres comme état actuel.
