# Facteurs de risque US : alimentation et qualification

État vérifié le 28 octobre 2026. Cette correction concerne l'étape 7 Alpha
Scanner, l'étape 11 Risk Management et la revalidation des entrées Winner par
le watcher. Les limites du risque dans `config.yaml` restent inchangées.

## Anomalies corrigées

Le scanner calculait les facteurs mais ne persistait les valeurs que pour
les candidats passant ses filtres. Oracle pouvait retenir d'autres titres,
dont les colonnes de `stock_scores_history` restaient alors nulles. Le
collecteur Winner ne raccordait pas de contexte factoriel qualifié et refusait
donc toutes les nouvelles entrées lorsque ce contrôle était activé.

Le précédent montage du risque construisait aussi des séries de facteurs
taille/momentum/valeur nulles et lui transmettait des rendements comme des
prix. Le chemin opérationnel emploie désormais des rendements observés et
des résidus spécifiques. Enfin, les violations factorielles du portefeuille
final ne sont plus de simples avertissements : elles empêchent la publication
de cibles exécutables.

## Stockage et données utilisées

La table dédiée `alpha_trade.stock_risk_factor_inputs` conserve les publications
sans réécrire les anciens scores : `run_id`, `symbol`, `asof_date`,
`observed_at` UTC, empreintes de l'univers/des entrées, `beta_126`,
`trend_score`, `market_cap`, `quality` et `details_json`.

La publication couvre tous les titres de
`config/univers_batch/univers_filtred_tradable.txt`, indépendamment du résultat
du scanner. Les positions et ordres en attente hors fichier sont ajoutés au
périmètre nécessaire à une décision. Les calculs exigent 272 séances NYSE
complètes, sans bougie remplie artificiellement, des OHLCV valides et une
capitalisation USD datée SEC × cours ou Finnhub, âgée de 30 jours au maximum.
La préférence quotidienne configurée EODHD/SIP s'applique à chaque bougie.
Aucune capitalisation de métadonnées non datée ni bêta par défaut ne remplace
une donnée manquante.

Les publications sont immuables et disponibles à leur véritable heure de
production. Un recalcul aujourd'hui ne devient pas une observation connue
hier. La migration additive est `0110_risk_factor_inputs` ; les facteurs sont
stockés en double précision. La version de calcul et le contenu de l'univers
font partie de l'identité du cache.

Le modèle opérationnel utilise trois facteurs observables : marché = rendement
SPY, taille = rendement IWM moins SPY, momentum = rendement MTUM moins SPY.
Les expositions taille/momentum suivent la transformation transversale
existante ; le bêta observé n'est pas écrêté avant le contrôle. Il ne s'agit
pas d'un nouveau prédicteur directionnel. Aucun facteur « valeur » n'est
présenté comme qualifié en l'absence d'entrées exploitables.

SPY/IWM/MTUM sont des dépendances du risque, pas des ajouts à l'univers de
trading. Les imports de séance du pipeline, Alpaca SIP ou EODHD selon le
fournisseur configuré, les collectent lorsque le modèle factoriel est activé.
Ils ont un contrôle distinct de couverture à 100 %, qui ne peut pas être
masqué par les 95 % de couverture de l'univers actions. Les six séances SIP
manquantes du 20 au 27 octobre pour IWM et MTUM ont été rattrapées et conservées
dans les deux tables de bougies.

## Raccordement et règles conservées

L'Alpha Scanner publie les entrées hors filtre après son enregistrement
habituel. L'étape 11 et `NativeWinnerRisk` chargent le même contexte qualifié :
séance exacte, disponibilité réelle, expositions, covariance et variances
résiduelles. Une publication absente peut être calculée depuis les données
locales ; une dépendance non qualifiée bloque la décision.

Le watcher refait le contrôle après sizing sur positions réelles, ordres en
attente et entrée proposée. Son approbation conserve l'empreinte du contexte
et les motifs de refus. Les contrôles de capital réel, liquidité applicables,
concentration, régime, perte quotidienne et drawdown restent en place.

| Limite dans `risk_management` | Valeur actuelle |
| --- | ---: |
| `max_portfolio_beta` | 3,50 (modifié à la demande de l'utilisateur le 29 octobre) |
| `max_factor_concentration_pct` | 0,60 |
| `factor_diversification_check_enabled` | `false` : minimum seul désactivé, données/bêta/concentration conservés |
| `min_factor_diversification` | Si contrôle actif : 2, ramené à 1 sous 100 000 $ d'equity |
| `factor_correlation_threshold` | 0,70 |
| `factor_lookback_days` | 252 |
| `factor_ewma_half_life` | 60 |

Le premier correctif utilisait encore le poids normalisé du portefeuille
investi. L'adaptation ensuite demandée le 28 octobre sélectionne désormais
`beta_exposure_basis: account_equity` : somme des contributions absolues
notionnel × bêta, divisée par le capital total. Le plafond numérique reste
1,20 à cette date, puis a été porté à 3,50 le 29 octobre. Les autres limites
restent actives, avec [la nouvelle règle de diversification des petits comptes](factor_diversification_small_accounts.md). Voir
[le budget bêta rapporté au compte](risk_beta_budget.md).

## Vérification initiale du 28 octobre, avant adaptation de la base bêta

Publication pour la séance du 27 octobre :
`risk-inputs-7392fd1c343141a6b7a1e625c0b0ba9f`, observée le 28 octobre à
14:45:58 UTC. Sur 1 790 titres : **1 521 QUALIFIED, 269 INCOMPLETE**. Les
derniers gardent leurs motifs d'incomplétude ; ils ne sont pas neutralisés.

| Plan existant | Bêta observé | Capitalisation USD datée | Décision native |
| --- | ---: | ---: | --- |
| P | 3,01508 | 41 996 600 000 | Bêta 3,02 > 1,20 |
| OKTA | 1,80303 | 38 462 300 000 | Bêta 1,80 > 1,20 ; diversification 1 < 2 |

Leur refus n'est plus une absence de raccordement des facteurs. Les deux
quantités autorisées par la revalidation sont zéro. Le service PAPER du compte
principal a été rechargé, sans recréer les plans ni libérer leur claim
d'exécution. Le cycle `watch-09c3f2317faa458d` a surveillé les deux plans,
rapporté ces refus et envoyé zéro achat, avec zéro échec technique.

Preuves dans `artifacts/operations/factor_input_remediation_20261028/` :
`native_preview_v2.json` (SQL en lecture seule et requêtes broker GET seulement),
`reload_receipt.json`, réponses SIP du rattrapage et journaux du service
`watcher-95f58bea/`. La prévalidation réutilisable se trouve dans
`scripts/operations/preview_winner_factor_risk.py`.

## Maintenance et validation

Installation additive et publication, si nécessaire :

```powershell
python -u -m risk_management.factor_inputs --asof 2026-10-27 --install-schema
```

`--force` crée une nouvelle publication à l'heure réelle après réparation de
ses sources. Il ne remplace pas les anciennes lignes. Aucun entraînement,
backtest ou ordre n'est lancé par cette commande.

Validation : **269 tests ciblés passent**, couvrant l'alimentation non filtrée,
dates et sources, données manquantes, rendements des facteurs, raccordement
SQL des dates, limites après sizing, risque CLI, comportement Winner,
watcher et couverture quotidienne des trois proxys. La prévalidation réelle
et le cycle du service confirment les refus attendus sans ordre.
