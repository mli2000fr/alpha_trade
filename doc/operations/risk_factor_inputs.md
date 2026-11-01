# Facteurs de risque US : alimentation et qualification

État complété le 1er novembre 2026. Cette correction concerne l'étape 7 Alpha
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

### Ligne prioritaire invalide : secours qualifié pour les facteurs

Depuis le 1er novembre, le calcul factoriel conserve la ligne prioritaire si
elle est valide. Si ses OHLCV ou son marqueur de remplissage sont invalides,
une autre ligne **complète**, déjà en base, EODHD/SIP peut être utilisée pour
le même symbole, la même séance et le même ajustement `split`. Elle doit
passer tous les contrôles de prix, volume positif et `is_filled=0`. Les
doublons ambigus, deux lignes invalides ou des ajustements différents restent
refusés. Aucun mélange cours EODHD/volume SIP, aucune interpolation.

Cette règle est propre aux entrées factorielles : elle ne change pas la
préférence quotidienne générale ni les autres contrôles d'admission. Les
tables de bougies ne sont pas modifiées. Chaque substitution figure dans
`details_json.daily_bar_fallbacks` avec sa séance, les deux sources et son
motif. Le protocole `daily-risk-inputs-qualified-provider-fallback-v3` crée
une nouvelle identité de cache ; les publications antérieures sont conservées.

Incident corrigé : étape 11 du compte `default`, signal du 30/10/2026,
sélection `opt-1593e7178d7d4cc3bd74a6792cc0eab5`. Pour **BAND le 18/06/2026**,
la ligne EODHD avait un volume nul ; la ligne Alpaca SIP avait les mêmes
OHLC et un volume de **1 997 939**. Le recalcul du 01/11 à **09:49:07 UTC**
publie `risk-inputs-08c533e44cd7411b825c5ad5fc18bc68` : 1 522 titres
qualifiés et un contexte valide pour BAND/ICHR/SIMO/SITM/FN. Il s'agit d'une
qualification des données, pas d'une approbation d'achat ou de sizing.

Le diagnostic d'erreur sépare désormais les titres manquants, l'effectif
qualifié et le minimum requis : il n'affiche plus une fausse inégalité
`1521<20` lorsque seul un titre nécessaire manque.

Une erreur au chargement des facteurs, avant création des décisions/cibles,
peut sceller une preuve de reprise de la tentative options. Une sortie risque,
un lien d'exécution ou un claim d'exécution existant interdit toujours cette
reprise. Pour l'ancien échec exact `bace6fe9689b4e9fa922bf6230a0e2ab`, l'état
terminal, la trace, le compte, les empreintes et l'absence de sorties ont été
vérifiés avant de créer cette preuve ; le claim original reste conservé et
sera archivé par la prochaine tentative. Aucun ordre ni étape 12 lancé.

Reçus : `artifacts/operations/factor_band_remediation_20261101/qualification.json`
et `retry-qualification.json`. **66 tests ciblés réussis**, dont secours par
ligne complète, priorité valide conservée, échecs sans secours, doublons,
ajustements, historique causal, covariance et reprise des tentatives.

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

### Reconstruction automatique dans le backtest Winner

Depuis le 31 octobre 2026, le replay Winner essaie d'abord un snapshot
archivé qualifié, puis calcule les entrées historiques manquantes à partir
des sources locales. Cette reconstruction est isolée de `refresh_inputs` :
elle ne publie rien dans `stock_risk_factor_inputs` et n'antidate aucune
observation. Son heure de calcul réelle et la borne historique d'utilisation
des sources restent séparées.

Les capitalisations peuvent être des observations datées déjà enregistrées
avant la décision ou des reconstructions depuis des faits SEC bruts publics
à l'époque et un close intraday raw de la séance. Les faits conservent leur
accession, mesure et publication ; la date de collecte actuelle n'est pas
transformée en réception historique. Les ADR/classes ambiguës, sources
incomplètes et splits connus depuis la mesure restent refusés. Les prix sont
l'historique canonique actuel (révisions possibles), sur le fichier d'univers
figé : cela reste un replay de recherche, pas une archive complète des
données reçues à l'époque. Un manque de capitalisations/prix/proxys qualifiés
bloque toujours l'entrée et marque la couverture incomplète.

Le formulaire Winner propose également **Contrôler la capitalisation
historique — facteur taille**, coché par défaut. Décoché, le replay n'utilise
plus le facteur taille ni les capitalisations : marché et momentum restent
calculés et contrôlés, avec une covariance réduite à ces deux facteurs.
Cette option ne change ni les protections Winner ni la configuration de
production. Le protocole signale explicitement le facteur retiré. Un tel
contexte est refusé en exploitation et ne peut être autorisé que par
l'adaptateur de replay.

Les fichiers comprimés et les reçus sont stockés dans le dossier du run.
Le risque natif conserve ses limites ; l'autorisation explicite de données
reconstruites appartient au seul adaptateur de backtest. Le watcher et les
étapes de risque/exécution opérationnelles continuent à exiger leurs
observations réellement publiées. Voir le
[contrat du replay Winner](winner_backtest_live_20261031.md).

### Publication opérationnelle

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
