# E21-B2 — Rôles des fourchettes : protocole de validation

## Contrat

`statement_role` classe chaque fourchette dollar en NEW_FORECAST,
PRIOR_FORECAST, REALIZED_RESULT ou AMBIGUOUS à partir des indices locaux.
Les indices ne traversent pas une phrase achevée. Une comparaison de réalisé
à l'an dernier n'est pas une ancienne prévision. Les cas sans indice,
notamment des cellules de tableau, s'abstiennent. Ces rôles restent des
suggestions, pas des labels validés. Une révision économique n'est pas une
direction boursière. `compare` exige désormais `validated_statement_role`
égal à NEW_FORECAST ou PRIOR_FORECAST ; un réalisé ne peut pas passer.

Périmètre limité : fourchettes USD, pas valeurs ponctuelles, pourcentages,
PDF ni compréhension exhaustive de tableaux. Le taux de réalisé parmi ces
candidats ne représente donc pas le taux de réalisé de l'ensemble du document.

## Validation sur de nouveaux émetteurs

Émetteurs choisis avant lecture de leurs documents : A (Agilent), ADBE.
Fenêtre 2023-01-01 à 2023-12-31, plafond douze dépôts par société et deux
annexes par dépôt. CIK récupérés en lecture seule des dépôts locaux.
Aucun rendement utilisé pour choisir les émetteurs, fenêtres ou exemples.
Un inventaire tronqué ou des annexes manquantes est un problème de couverture,
pas une preuve d'échec du classifieur.

Les règles sont figées avant collecte : ne pas les adapter aux résultats
sans requalifier ce corpus en développement. La revue assistant n'est pas
une annotation humaine indépendante. Pour mesurer la classification,
annoter tous les candidats de ce corpus, les ambiguïtés et faux positifs,
puis confusion par rôle, précision, couverture et abstention. Pour mesurer
le rappel, annoter aussi les prévisions manquées en dehors des candidats.
Une poignée de bons exemples ne permet pas de revendiquer une précision globale.

Run prévu : `artifacts/research/guidance_historical_backfill/e21b-new-issuers-2023-v1`.
Logs : `log/batch/e21b-new-issuers-2023-v1/stdout.log` et `stderr.log`.
Le rapport terminal doit être lu, pas seulement détecté. Aucun batch quotidien,
aucune table production, aucun entraînement ni backtest concernés.

Voir [socle et résultats précédents](guidance_structured_e21b.md).

## Résultat : règles figées sur A et ADBE

Collecte terminée : huit dépôts et huit annexes, zéro erreur. Extraction :
71 candidats. Revue assistant de tous les candidats : 66 prévisions actuelles
annuelles/trimestrielles et cinq faux intervalles. Un faux intervalle joint
une cellule de chiffre d'affaires à une note ; quatre sont des provisions
de créances à deux dates distinctes (`$17 and $23, respectively`, etc.).
Ces valeurs réalisées ne constituent pas une fourchette de résultat réalisé.

Classification : 25 prévisions actuelles classées, 41 prévisions actuelles
laissées ambiguës, cinq faux intervalles laissés ambigus. Les 25 classifications
correspondent à la revue ; cela ne prouve pas une précision de 100% généralisable.
Couverture des prévisions parmi les candidats détectés : 25/66 = 37,9%.
Abstention totale : 46/71 = 64,8%. Les répétitions titre/corps rendent les
candidats dépendants. Pas de rappel global mesuré sur les documents complets.

Agilent bénéficie des phrases explicites ; Adobe présente surtout ses
`targets` dans des tableaux, que les règles figées ne comprennent pas.
Les classes ancienne prévision et réalisé sont couvertes par tests unitaires,
mais **non validées empiriquement sur ce corpus**, qui ne contient pas de
références dans ces classes. Une classe absente n'est pas une classe réussie.

Artefact `artifacts/research/guidance_structured/e21b-new-issuers-2023-v1/` :
queue, rapport d'extraction, `role_reference.json` et `validation_report.json`.
La référence est liée au SHA256 exact de la queue, les résultats reproductibles
par `service.forward_pit.guidance_role_evaluation`. 89 tests ciblés passent.

Conclusion : **INSUFFICIENT_TABLE_COVERAGE_AND_MISSING_CLASS_SUPPORT**.
Toujours DATA_NOT_READY. Aucun entraînement, backtest ou changement des
batchs quotidiens. Aucun run E21 restant après cette analyse.

Suite nécessaire : lecteur de tableaux avec en-têtes de période/mesure et
réjection de valeurs `respectively`, puis nouveau corpus non lu contenant
ancienne prévision, nouvelle prévision et vrai réalisé. Le corpus A/ADBE
devient développement si ses observations servent à adapter les règles.
