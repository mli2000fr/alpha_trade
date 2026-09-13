# E8-A2 — Source et coût d’acquisition de l’historique options

## Verdict

E8-A2 est terminé en `GO_ACQUISITION_PILOT`, mais E8-B reste bloqué tant que
les données du pilote n’ont pas franchi les gates de qualité. Aucun abonnement
n’a été acheté et aucune donnée distante n’a été téléchargée.

Artefact reproductible :

```text
artifacts/research/options_acquisition_audit/options-acquisition-audit-20260910183834/report.json
```

Le choix économique recommandé est **ThetaData Options Value pendant un mois,
40 USD**, après un smoke test d’éligibilité. Le repli opérationnel est
**Massive Options Advanced pendant un mois, 199 USD**. Massive est plus cher,
mais son contrat de données ressemble davantage aux endpoints déjà utilisés par
le POC Eroya.

Les prix et droits ci-dessous ont été vérifiés le **10 septembre 2026**. Ils
doivent être revérifiés avant achat.

## Données réellement nécessaires

L’unité causale est `événement Oracle × paire call/put × instant de décision`.
Pour chaque signal Oracle H20 TOP20 à la clôture J :

1. à J+1, récupérer le référentiel historique `as_of` ;
2. choisir sans futur un call et un put de même strike, proches de l’ATM ;
3. conserver expiration, strike, type, multiplicateur et identifiant du contrat ;
4. prendre le premier NBBO exécutable entre 09:35 et 10:00 pour l’entrée ;
5. reprendre le NBBO des mêmes contrats entre 15:30 et 15:55 à H3/H5/H10/H20 ;
6. valoriser l’achat aux asks et la liquidation aux bids ;
7. conserver le spot horodaté, les splits, changements de ticker et ajustements.

Champs minimaux :

```text
underlying, signal_date, entry_date, option_ticker, as_of
expiration, strike, call_put, multiplier
quote_timestamp, bid, ask, bid_size, ask_size
underlying_price, source, ingestion_timestamp
```

L’open interest, le volume et l’IV sont recommandés. Les Greeks du fournisseur
ne sont pas bloquants : IV et Greeks peuvent être recalculés à partir du NBBO,
du spot, du taux sans risque et des dividendes. Une IV courante ne doit jamais
être jointe à une date historique.

Les barres OHLC seules ne conviennent pas. Elles ne permettent ni l’achat à
l’ask, ni la vente au bid, ni la mesure exacte du spread.

## Population Oracle et volume

La source est l’artefact multi-horizon
`multi-horizon-rolling-20260910141708-d5b30f/aligned_predictions.parquet`.
Depuis le début de l’historique NBBO Massive, le 7 mars 2022 :

| Population | Dates | Événements TOP20 | Symboles | Événements/jour |
|---|---:|---:|---:|---:|
| disponible | 588 | 33 524 | 144 | 57,01 |
| minimum Walk-Forward | 504 | 28 736 | 141 | 57,02 |
| pilote réparti dans le temps | 60 | 3 421 | 127 | 57,02 |

Le pilote doit répartir ses 60 dates sur toute la période disponible, et non
prendre 60 jours consécutifs. Ce choix évite de confondre qualité du fournisseur
et régime de marché.

### Stratégie A — une paire 45 DTE, quatre sorties

Par événement : un appel de référentiel, deux quotes d’entrée et huit quotes de
sortie, soit **11 appels**.

| Étape | Appels bruts | Budget avec 15 % de reprises | Stockage brut estimé |
|---|---:|---:|---:|
| pilote 60 dates | 37 631 | 43 276 | 0,48 Gio |
| 504 dates | 316 096 | 363 511 | 4,06 Gio |

### Stratégie B — DTE propre à chaque horizon

Le même snapshot de contrats sert aux quatre horizons. Quatre paires nécessitent
16 quotes entrée/sortie, donc **17 appels** par événement.

| Étape | Appels bruts | Budget avec 15 % de reprises | Stockage brut estimé |
|---|---:|---:|---:|
| pilote 60 dates | 58 157 | 66 881 | 0,52 Gio |
| 504 dates | 488 512 | 561 789 | 4,38 Gio |

Le stockage est une estimation prudente : 128 Kio par réponse de référentiel et
2 Kio par réponse de quote. Il faut conserver le JSON brut compressé et une
table Parquet normalisée afin de rendre l’audit rejouable.

## Comparaison des sources

### ThetaData — choix économique

Le plan retail **Options Value coûte 40 USD/mois**, annonce quatre ans
d’historique, des intervalles d’une minute et un accès aux quotes historiques
et à l’open interest. Cela suffit au premier test ask→bid. Le plan
**Options Standard coûte 80 USD/mois** et ajoute huit ans, le tick NBBO, l’IV
historique et les Greeks de premier ordre.

Sources officielles :

- https://www.thetadata.net/subscribe
- https://docs.thetadata.us/Articles/Getting-Started/Subscriptions.html

Risques : il faut intégrer le Theta Terminal et vérifier sur un petit
échantillon l’accès aux contrats expirés, le comportement de l’appel « at time »
et l’exactitude des fuseaux horaires. Value est le bon premier achat ; Standard
n’est justifié que si la minute est insuffisante ou si l’IV observée devient
indispensable.

### Massive — choix opérationnel de repli

**Options Advanced coûte 199 USD/mois**, inclut quotes historiques, appels
illimités et plus de cinq ans d’historique. Les flat files de quotes sont
disponibles depuis le 7 mars 2022.

Sources officielles :

- https://massive.com/pricing?product=options
- https://massive.com/docs/rest/options/trades-quotes/quotes
- https://massive.com/docs/flat-files/options/quotes

Les archives OPRA complètes ne doivent pas être téléchargées : les seuls fichiers
2022, 2023 et 2024 représentent environ **65,6 To**. L’API REST ciblée sur les
contrats Oracle est plusieurs ordres de grandeur plus petite. Le prix retail est
réservé à l’usage individuel/non professionnel ; un usage commercial exige une
offre et des droits adaptés.

### Eroya — tarif attractif mais source actuellement non fiable juridiquement

Les prix affichés sont 10 USD/mois pour Pro à 1 000 appels/minute et 59 USD/mois
pour Premium à 5 000 appels/minute. Toutefois, les conditions Eroya datées
d’août 2026 indiquent que la livraison aux clients des données issues de Massive
et Benzinga est suspendue tant que les droits commerciaux et de redistribution
ne sont pas obtenus. L’existence d’un endpoint ou un ancien succès de trial ne
constitue donc pas une garantie d’accès durable.

Sources officielles :

- https://eroya.co/pricing
- https://eroya.co/terms

Décision : ne pas acheter Eroya pour E8 sans confirmation écrite que l’historique
options américain précis est actif et autorisé pour l’usage prévu.

### Cboe DataShop — référence de qualité, pas premier choix économique

Option Quote Intervals fournit du NBBO à la minute depuis janvier 2012, avec IV,
Greeks et open interest en options payantes. Le prix dépend de la sélection et
doit être coté dans le panier DataShop. L’API All Access publique commence à
2 499 USD/mois ; elle est disproportionnée pour ce POC.

Sources officielles :

- https://datashop.cboe.com/option-quote-intervals
- https://datashop.cboe.com/cboe-all-access-api

Cboe reste le contrôle « gold standard » si les résultats du pilote justifient
une validation institutionnelle ou si les autres fournisseurs ont trop de trous.

## Plan d’acquisition préfixé

### A2-0 — Smoke d’éligibilité

Avant la collecte :

- 10 symboles liquides et moins liquides ;
- 5 dates historiques réparties entre 2022 et 2024 ;
- contrats expirés et référentiel à la date ;
- quotes entrée et sortie sur call et put ;
- aucune donnée utilisée après l’instant demandé.

Gate : 100 % des appels autorisés, timestamps cohérents, aucun remplacement par
un snapshot courant et au moins 80 % des événements entièrement valorisables.

### A2-1 — Pilote 60 dates

Collecter 3 421 événements avec checkpoint, reprise idempotente, cache du
référentiel et journal des raisons de rejet. Ne pas écrire de table de production.
Les artefacts bruts et Parquet restent sous `artifacts/research`.

Gates :

- au moins 60 dates et 100 symboles ;
- complétude globale au moins 70 % ;
- aucune moitié d’année sous 50 % ;
- call/put synchronisés à 60 secondes maximum ;
- bid strictement positif, ask supérieur ou égal au bid ;
- taux de trous non corrélé au futur rendement ou au label réel ;
- couverture et spreads rapportés par semestre, symbole et liquidité.

Un taux entre 50 % et 70 % autorise seulement un audit de missingness. Sous
50 %, la source est rejetée pour E8.

### A2-2 — Extension 504 dates

Uniquement si A2-1 passe. La première campagne utilise une paire 45 DTE commune
aux quatre sorties, soit environ 363 511 tentatives avec le budget de reprise.
La version quatre DTE n’est ouverte qu’après preuve qu’une seule paire ne répond
pas à la question.

Une fois la collecte complète et les gates franchis, E8-B pourra comparer
volatilité réalisée et implicite en Walk-Forward. Aucun paramètre de trading,
exit ou serving ne doit être modifié durant E8-A2.

## Reproduction locale

```powershell
python -m modelFactory.options_acquisition_cost_audit --oracle-path artifacts/research/multi_horizon_oracle_rolling/multi-horizon-rolling-20260910141708-d5b30f/aligned_predictions.parquet
```

Le module est purement local : il ne lit aucune clé API, ne contacte aucun
fournisseur et ne lance aucun téléchargement.
