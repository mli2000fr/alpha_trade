# Winner : lancement Backtest et parcours PAPER/live

Raccordement du 31 octobre 2026. Évolution technique ; aucune nouvelle mesure
de rentabilité, aucun ordre, aucune activation d'un compte en argent réel.

## Depuis l'IHM

Depuis le 1er novembre, les nouveaux replays Winner sont exécutés avec
[isolation des écritures et SQL en lecture seule](backtest_readonly_isolation.md).
Ils peuvent coexister avec le pipeline ; leurs caches et rapports restent
dans leur propre dossier. Les anciens processus gardent leur verrou initial.

Page **Backtesting**, onglet **Backtest**, cocher **Utiliser Winner — Oracle
parcours et replay intraday**. Cette case reprend `winner_pyramiding.enabled`
au premier affichage. Le formulaire dédié remplace les paramètres du moteur
daily classique ; les deux moteurs ne mélangent pas leurs protections.

Sélectionner un modèle Oracle parcours terminé H10/H15/H20 et les dates.
L'univers reprend automatiquement les symboles figés du modèle sélectionné.
Le TOP Oracle, le capital, le type de compte,
les positions maximales et l'exposition 1×/2× restent modifiables. Le 2× n'est proposé que pour
un compte margin et si la configuration de levier l'autorise. Les contraintes
de risque peuvent encore réduire l'exposition effectivement utilisée.

Depuis le 7 novembre, le formulaire Winner utilise **Q088 — risque réduit + B4/DD15** par défaut,
à partir du cas archivé
`artifacts/research/us_winner_risk_tradeoff/20261107-v1/cases/Q088_SIZE125_B4DD15/configuration.json` :

| Paramètre | Défaut Q088 |
| --- | --- |
| Sélection | TOP20 % Oracle → TOP10 LONG per-symbol, sans SHORT |
| Score / AUC LONG | Score strictement > 0,60 ; AUC calibration ≥ 0,60 |
| Entrée | Ouverture journalière J+1, position complète, sans confirmation ni renforcement |
| Sortie | SL5 %, sans TP ni trailing ; dix séances de détention puis open11 |
| Capital / compte / levier | 4 000 $, margin, capacité maximale 2× |
| Risque par entrée / poids par titre | 1,25 % / 20 % |
| Positions / montant minimum | 20 / 50 $ |
| Contrôleur DD/B4 | Actif, DD15 %, perte quotidienne 3 %, liquidation 50 % |
| Facteurs, corrélation, limites sectorielles, cible de volatilité | Désactivés |
| Répétition des entrées | Dix par titre sur 90 jours ; trois pertes consécutives → exclusion 90 jours |
| Coût par achat ou vente / financement | 8 points de base / 6,5 % annuel sur le débit de marge |

Le pourcentage Oracle dépend de l'univers du batch : 358 candidats pour
1 790 titres ; aucun univers ou modèle n'est remplacé automatiquement.
Pour reproduire le parcours Q088, choisir un bundle Oracle H10 + per-symbol.
Un modèle Oracle seul ne contient pas de classement LONG per-symbol.
Le seuil de couverture Oracle conserve son contrôle existant.

Ces valeurs sont appliquées une fois à l'ouverture du formulaire, y compris
dans les anciennes sessions. Les modifications suivantes restent conservées.
La liste **Profil de paramètres du backtest** remplace les trois anciens boutons.
Q088 est sélectionné par défaut. Chaque choix charge les réglages et affiche
immédiatement son explication sous la liste :

- **Q088 — risque réduit + B4/DD15** : profil décrit dans le tableau ci-dessus.
- **Q051 — risque réduit, plafond de risque 1×** : TOP10 % Oracle → TOP5 LONG,
  score >0,60 et AUC ≥0,60 ; risque1,25 %, poids20 %, plafond de risque1×,
  sans B4/DD15 ni liquidation globale. Même SL5/open11, entrée directe,
  capital4 000 $, frais et paramètres communs que Q088. Le compte margin
  conserve sa capacité2× ; les nouvelles entrées sont bornées par le risque1×.
  Cas source `Q051_SIZE125_GROSS1`, résultat exploratoire2025 : +31,67 %,
  DD −18,04 %. Ce profil ne désigne pas le Q051 d'origine à risque2,5 %.
- **Réglages de production — config.yaml** : recharge les réglages Winner et
  les limites du preset de capital ; l'entrée journalière est désactivée.
- **Ancien test de référence** : aucune confirmation/délai, poids20 %, plafond2×,
  DD/B4 et facteurs désactivés ; les autres protections viennent de la config.

**Réappliquer le profil choisi** permet d'annuler ses ajustements manuels.
Les ajustements restent conservés lors des rafraîchissements ordinaires.
Changer de profil conserve le batch et les dates ; les profils Q051/Q088
réinitialisent leur sélection et leurs paramètres financiers.
Les réglages de production et les runs déjà lancés ne sont pas modifiés.
Ce profil exploratoire 2025 avait donné +35,13 % et DD −17,20 %, contre
+58,87 % et DD −40,02 % pour le Q088 d'origine (risque2,5 %, poids40 %, sans B4).
Le seuil DD15 déclenche une réaction et n'est pas un plafond garanti.
Le premier chargement des défauts avait repris le Q088 d'origine : le run
`20261107_222014_0dc532e7` le reproduit exactement. Les défauts et le libellé sont
corrigés pour désigner explicitement `Q088_SIZE125_B4DD15`. Le run existant
conserve ses résultats d'origine ; un nouveau run est nécessaire pour la variante.
La couverture minimale des prédictions reprend le seuil du filtre options (90 %
actuellement) ; disposer de vingt scores ne suffit pas si le reste de
l'univers demandé n'est pas suffisamment couvert. La disponibilité SQL de
chaque fold est recoupée avec les reçus immuables de training/validation.

Dans ce formulaire de backtest, **Appliquer le filtre CALL/PUT + OI du
pipeline** est désormais décoché par défaut, indépendamment de son activation
dans le pipeline de production. Le cocher applique toujours le filtre
historique strict. Le bouton de réinitialisation reprend ce défaut décoché.

La date minimale est calculée depuis les folds du modèle : le premier signal
doit être causal et disponible avant la séance d'entrée. Pour le modèle
`model-factory-20261030213826-eda503`, premier signal le 2 juillet 2021,
première entrée possible le 6 juillet (NYSE fermé le 5 juillet).

Les prédictions causales doivent déjà être en base ; le replay part des
bougies SIP 5m enregistrées.
Générer au besoin les prédictions avec le bouton historique de la page Pipeline,
sur une période comprenant la séance précédente du début du replay. Le
lancement du backtest ne fait pas de prédiction automatique. L'option
d'ignorance des données intraday manquantes active le rattrapage fournisseur
décrit plus bas ; sans cette option, aucun téléchargement de bougies.

Les frais canoniques s'appliquent par défaut ; un coût explicite par achat et
vente peut les remplacer pour ce replay. Le taux de financement est séparé
et porte sur le débit de marge. La réserve de sizing Winner n'est pas une
commission supplémentaire. Le capital reste commun à toutes les positions.

Le profil **« replay prudent disponible, proche du fonctionnement en production »**
est coché par défaut. Ce choix active les hypothèses conservatrices réellement
supportées : bougies SIP 5m, délai de publication configuré, aucun achat
rétroactif, limite d'achat respectée et priorité à la sortie défavorable si
SL et TP sont touchés dans la même bougie. Il n'existe pas de bouton capable
de reconstruire le carnet ou les secteurs historiques absents : les secteurs
actuels restent une approximation et le rapport garde sa qualification
exploratoire. Ce profil ne permet pas d'envoyer un ordre.

Les paramètres utiles du moteur intraday sont accessibles dans des blocs
dédiés : protections/confirmation/renforcement Winner, risque par entrée,
montant minimum, poids par titre et secteur, plafonds de titres, corrélations,
drawdown/perte quotidienne, liquidation au coupe-circuit, volatilité cible,
répétition des entrées/exclusions et plafond bêta. Le capital, les positions
maximales, les frais et le levier restent dans le formulaire principal.
Les valeurs sont préremplies depuis `config.yaml` et le preset du capital.
Un bouton **« Reprendre les réglages de production »** remet les contrôles
de simulation à ces valeurs sans changer les dates, le modèle ni le capital.
Validation du formulaire enrichi : **359 tests réussis**, dont édition des
valeurs, retour aux paramètres de production, transmission JSON au CLI,
replay SQL en lecture seule et vérification que le budget modifie les
quantités. Les paramètres effectifs et les différences locales figurent
dans le rapport.

Les modifications ne concernent que ce replay et sont transmises explicitement
dans `--risk-overrides-json` / `--policy-overrides-json`, contrôlées par liste
de champs raccordés, puis figées dans `protocol.json`. Aucun fichier YAML,
plan existant ou compte courtier n'est modifié. Les paramètres daily non
raccordés à Winner ne sont pas présentés comme des commandes actives.

## Réglages réellement utilisés

Depuis le 1er novembre, le bloc ouvert **Réglages Winner et limites du replay**
contient directement les champs modifiables ; il remplace l'ancien tableau de
lecture seule et le panneau replié séparé. SL, activation/valeur du TP et du
trailing, horizon, position complète/demi-position, renforcement et son seuil,
confirmation 5m, attente d'entrée, retard SIP, marge limite et réserve de sizing
sont modifiables à cet endroit. Les valeurs initiales viennent de
`config.yaml → winner_pyramiding` ; `null` laisse TP/trailing/horizon désactivés.
Le bouton **Reprendre les réglages de production** recharge les valeurs de
configuration. Les modifications restent dans les options de ce run, sont
transmises au moteur et conservées dans son protocole, sans écrire `config.yaml`.

Validation de l'édition dans ce bloc : **41 tests ciblés réussis**, dont lecture
d'un YAML de contrôle, édition des protections et paramètres d'entrée, passage
exact dans la commande et remise aux valeurs de configuration.

Le processus relit `config.yaml` au lancement et fige sa politique dans
`protocol.json` : confirmation, fraction initiale, renforcement, seuil d'ajout,
SL/TP/trailing, durée et expiration du plan, limites de fraîcheur et réserve.
Les modifications de formulaire concernent uniquement ce replay.
La configuration du coupe-circuit reprend désormais explicitement
`risk_management.prod_force_close_on_breaker` / `prod_force_close_pct`
(avec fallback legacy), au lieu d'ignorer ces clés. Le réglage de travail
est actif, liquidation de 50 % des positions lors du déclenchement ; cela
ne garantit pas un drawdown maximal de 15 %. Le capital initial réel du
replay est aussi injecté dans la configuration de risque, et un SL Winner
modifié localement est répercuté dans le sizing. Winner étant LONG-only,
le plafond LONG suit le nombre de positions choisi dans le formulaire.

Au contrôle du 31 octobre : position complète, deux confirmations 5m,
renforcement désactivé, **SL 5 %, aucun TP ni trailing, horizon 10 séances**.
L'entrée compte comme première séance ; sortie à l'ouverture de la **11e**.
L'horizon du modèle d'amplitude et la durée de détention sont deux paramètres
distincts : choisir Oracle H20 ne modifie pas implicitement la durée Winner.

Le replay emploie `BacktestEngine` puis `WinnerCampaignRuntime` et la
revalidation native `reapprove_campaign`, comme le watcher. Il applique
budget de risque, capital disponible, limites configurées, frais, capacité de
marge, financement, protections et échéance. Les dividendes USD documentés
sont comptabilisés ; les actions sur titres non prises en charge lorsqu'une
position est détenue interrompent le replay.

Pour les daily, la ligne entière du fournisseur préféré de
`market_data.daily_bars_preferred_source` est sélectionnée : EODHD par défaut,
SIP complémentaire si le préféré est absent. Une ligne préférée invalide
n'est pas masquée par un autre fournisseur. L'intraday utilise uniquement
Alpaca SIP, US_EQ, séance régulière, 5m raw, non rempli, avec provenance.

## Risque factoriel et données manquantes

Le contrôle factoriel reprend la configuration de production par défaut.
Il cherche d'abord les observations qualifiées réellement archivées dans
`stock_risk_factor_inputs` et connues avant la décision. À défaut d'archive
qualifiée, il reconstruit automatiquement les entrées depuis l'historique
local, sur l'univers complet figé du backtest, indépendamment du classement
Oracle. Les prix SPY/IWM/MTUM restent nécessaires au modèle factoriel complet.

La reconstruction partage le calcul de production : 272 séances complètes,
préférence des fournisseurs daily, bêta/tendance et capitalisation datée.
Les lignes de `stock_market_cap_daily` doivent avoir une observation vieille
de 30 jours au maximum, une devise USD et une source SEC × cours ou Finnhub.
Leur date de disponibilité et leur heure réelle de calcul doivent précéder
le cutoff historique des sources. Ce cutoff est fixé à l'ouverture de la
séance officielle suivante : les publications de la nuit sont admises,
et les cours de clôture ont dépassé leur délai SIP de 30 minutes. Il ne
se déplace pas vers une décision intraday ultérieure. Moins de vingt capitalisations qualifiées
empêchent la reconstruction transversale. À défaut d'observations de l'époque,
le replay peut maintenant calculer une capitalisation depuis les faits SEC
bruts locaux et un prix brut contemporain, selon le contrat détaillé plus bas.
Aucune capitalisation actuelle ni valeur neutre ne remplace une source manquante.

### Option sans dépendance à la capitalisation

Sous le formulaire Winner, **Contrôler la capitalisation historique — facteur
taille** est décoché par défaut. Ce choix transmet
`--no-factor-market-cap-check` au vrai moteur de replay. La réinitialisation
du formulaire restaure ce défaut décoché. Le réglage concerne ce backtest et
ne modifie pas `config.yaml`, l'étape 11 ni le watcher.

Dans ce mode, le contexte de risque est reconstruit depuis les facteurs
**marché et momentum**, sans lecture de capitalisation ni des fichiers SEC.
Le facteur taille est absent de la covariance, des résidus et de la
décomposition ; aucune série de taille factice à zéro n'est présentée comme
un facteur observé. IWM n'est plus requis. Le minimum transversal de vingt
titres porte alors sur les facteurs techniques qualifiés. Les contrôles
natifs de bêta, concentration/diversification des facteurs restants,
capital, sizing, drawdown, frais et protections Winner restent actifs.

Le protocole et `report.json.factor_inputs` consignent
`market_cap_check=false` et `disabled_factors=['size']`. Le modèle réduit
peut prendre des décisions différentes du modèle complet ; le comparer ne
revient pas à tester une simple absence de données avec les mêmes facteurs.
Un contexte sans taille est refusé en exploitation ; son utilisation exige
l'autorisation explicite propre à l'adaptateur de replay.

### Reconstruction SEC des capitalisations

`backtesting/historical_sec_capitalization.py` utilise uniquement les fichiers
déjà présents sous `artifacts/sec_cache/companyfacts`, avec le mapping CIK
local. Il ne réutilise pas aveuglément `stock_fundamentals_daily` : le mapper
agrégé a parfois associé une date de dépôt à une période comparative plus
ancienne, et de nombreuses lignes n'ont pas de référence de dépôt.

Les faits instantanés `dei:EntityCommonStockSharesOutstanding` et
`us-gaap:CommonStockSharesOutstanding`, unité `shares`, sont conservés
individuellement avec leur accession, date de mesure et date de dépôt.
Les moyennes pondérées d'actions ne sont pas substituées. Le fait admissible
est la mesure la plus récente, puis sa publication/révision la plus récente
connue au cutoff ; des valeurs contradictoires équivalentes sont refusées.
Un dépôt sans heure est disponible après la fin de sa journée civile à
New York : cette borne prudente n'est pas une heure d'acceptation inventée.
Les mesures plus âgées que `market_cap.max_age_days` sont rejetées.

Le nombre d'actions est multiplié par le **dernier close régulier 5m raw
Alpaca SIP de la séance**, avec ses horodatages et son hash de payload.
L'absence de cette bougie bloque le calcul ; un daily ajusté des splits
futurs ne la remplace pas. Cette valeur reste un proxy du prix de clôture,
pas le fixing officiel. Les prix raw évitent notamment de multiplier un
nombre d'actions antérieur à un split par le prix ajusté après ce split.

Les ADR/classes ambiguës, instruments non-actions/non-USD, CIK absents ou
incohérents, ruptures d'identité connues et splits connus depuis la mesure
des actions sont refusés. Le mapping CIK actuel et le registre des ruptures
ne sont pas un référentiel exhaustif des identités historiques ; les
événements de split conservés ne constituent pas une couverture certifiée.
Les capitalisations sont des estimations à partir du dernier nombre public
d'actions, pas des nombres d'actions exacts pour chaque journée.

Les nouvelles lignes portent `evidence_kind=RECONSTRUCTED_SEC_FACT`, l'heure
réelle de calcul et une disponibilité historique distincte. Elles restent
des fichiers de recherche dans le run et ne sont pas publiées en SQL.
`sec-capitalization-receipts.json` explique la couverture et les refus ; les
preuves complètes sont incluses dans les fichiers comprimés de reconstruction.

La [documentation officielle SEC](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
décrit CompanyFacts comme l'agrégation des concepts standards applicables à
l'entité entière. Les règles ci-dessus de sélection, délai prudent et
qualification de prix sont celles du replay Alpha Trade.

Audit local READ ONLY dans
`artifacts/research/historical_sec_capitalization_20261031-v2/report.json` :

| Séance de référence | Capitalisations reconstruites / 1 790 | TOP20 Oracle couverts |
| --- | ---: | ---: |
| 02/07/2021 | 1 151 | 11/20 |
| 30/06/2022 | 1 165 | 6/20 |
| 30/06/2023 | 1 199 | 11/20 |
| 28/06/2024 | 1 218 | 10/20 |
| 27/06/2025 | 1 237 | 16/20 |
| 30/09/2026 | 1 256 | 14/20 |

La base comptait 39 232 observations de capitalisation, du 18 au 31 octobre
2026 ; les dépôts bruts SQL commencent le 3 septembre 2026. L'historique
`stock_fundamentals_daily` contient 154 175 lignes SEC avec des actions
positives, mais les fichiers CompanyFacts bruts sont nécessaires pour
qualifier individuellement les faits et périodes. Le cache local compte
5 774 fichiers ; aucun téléchargement n'a été fait pour cet audit.

Validation sur la séance du 30/06/2025, Oracle TOP20, 4 000 $, cash 1×,
SL5, H10, sans TP/trailing, confirmation 2 et SIP retardé 930 s : cinq
achats simulés avec modèle factoriel complet, et cinq dans le mode sans
taille (sélections différentes). Les deux bilans restent incomplets à
cause des lacunes de prix, ainsi que des preuves factorielles manquantes
pour certains titres dans le mode complet. Cela valide le raccordement,
pas la rentabilité de l'un des deux modèles. Artefacts sous
`artifacts/research/winner_sec_cap_20261031/` ; aucune reprise des cinq
années, aucun ordre broker et aucune écriture SQL.
Validation finale du mode sans taille et de la reconstruction SEC : 362 tests
de la suite Winner/qualification réussis, complétés par 17 tests ciblés du
flux factoriel de production, des sources SEC et de l'option. Les versions
opérationnelles du calcul et du risque conservent leurs défauts stricts.

Les bougies sont l'historique canonique disponible aujourd'hui, susceptible
d'avoir été révisé : cette reconstruction ne prétend pas disposer des
versions de prix effectivement reçues à l'époque. L'univers de fichier
reste aussi un univers courant figé, sans certification de survie historique.
Ces limites de recherche restent enregistrées ; `full_live_parity=false`.

Un calcul est mutualisé entre les candidats d'une même séance. Les
reconstructions et leurs raisons d'incomplétude sont conservées dans le
dossier du run : `factor-reconstruction-receipts.json` et
`factor-reconstructions/YYYY-MM-DD.json.gz` lorsque le calcul des entrées
a abouti. Les dates `observed_at` et `reconstructed_at` restent les dates
réelles d'aujourd'hui ; `input_available_at` identifie séparément la borne
historique modélisée. Les reçus de contexte indiquent
`ARCHIVED_OBSERVATIONS` ou `RECONSTRUCTED_HISTORICAL_INPUTS`, et le rapport
compte les contextes archivés, reconstruits et refusés.

Cette branche est propre au replay : aucun rafraîchissement live, appel
fournisseur ou écriture SQL. Les snapshots opérationnels ne sont pas
antidatés ni enrichis par ces fichiers. La réapprobation de production
refuse une reconstruction historique ; seul l'adaptateur du replay
l'autorise explicitement, en conservant les limites natives sur les
quantités finales, le bêta, la concentration et la diversification actifs.

Validation du raccordement : 348 tests Winner/qualification factorielle
réussis lors de la passe élargie. Les tests de reconstruction passent par
le vrai calcul, une base SQLite surveillée en SELECT-only et le moteur
intraday jusqu'à un achat simulé. Ils couvrent aussi l'archive prioritaire,
les sources futures/manquantes, la mutualisation par séance, l'export des
preuves et le maintien des refus de risque. Aucun replay économique sur
cinq ans ni ordre n'a été lancé par ce changement.

Sans contexte qualifié, la nouvelle entrée est bloquée et le bilan est
`INCOMPLETE_COVERAGE`, avec motifs et reçus. Le traitement des positions
déjà ouvertes conserve ses protections. Une bougie manquante nécessaire à
la valorisation d'une position détenue provoque un échec explicite.

Le formulaire permet de désactiver **explicitement pour ce replay** le
contrôle factoriel. Cette différence avec la production est affichée et
figée dans le protocole ; le fichier de configuration n'est pas modifié.

## Rapports et périmètre exact

Le launcher conserve les résultats dans son dossier neuf
`artifacts/ihm_backtesting_runs/run/<run-id>/artifacts` (chemin exact visible
dans la commande et le registre). Rapport et graphique sont lisibles dans
la page : `report.json`, `equity_curve.csv`, `equity_curve.png`, `trades.csv`,
`annual-summary.csv`, événements, risque 5m, reçus intraday et factoriels.
Le rapport conserve également les anciens indicateurs de recherche à plat.
Les empreintes des signaux, des daily, des secteurs et des actions sur titres
sont consignées. Un dossier existant n'est jamais écrasé.

Ce formulaire sélectionne les TOP-N Oracle dans leur ordre de score,
**LONG uniquement**, puis applique par défaut le filtre CALL/PUT + OI du
pipeline. Le même lecteur SQL, les mêmes features et la même fonction de
sélection sont utilisés. Le filtre GPT n'est pas rejoué.
Les secteurs sont actuels, les historiques daily peuvent être
révisés et les décisions de régime ne constituent pas une bande macro PIT
complète. Prix OHLC, priorité conservatrice des touches et glissement simulé
ne reproduisent pas le carnet réel. `full_live_parity` reste donc **false**.
Un résultat incomplet est signalé dans la page même si le calcul est arrivé
à la dernière séance. Les positions finales restent valorisées, sans vente
terminale artificielle.

Le mode daily classique reste accessible en décochant Winner dans l'IHM.
Sa commande porte `--no-winner-pyramiding`, override local qui évite
d'activer accidentellement Winner via le YAML global. Le CLI dédié complet
est `python -m backtesting.winner_campaign_replay --help`.
Cet override retire aussi les trois adaptations Winner du risque daily :
stop fixe, suppression du TP en prix et obligation de quantités entières.
Les autres contraintes restent intactes.

## En exploitation

Le chemin existant reste : prédiction/sélection → risque 11 → exécution 12
→ campagnes persistées → watcher du **même compte et du même mode**.
Avec confirmation positive, le watcher vérifie les clôtures 5m puis le
risque courant avant achat. Avec confirmation zéro, le chemin standard
applique le réglage dédié des cotations. Les protections sont attachées
aux fills réels et la date de sortie est calculée depuis le premier fill,
selon le calendrier officiel ; un ajout ne redémarre pas le compteur.

Chaque compte garde son propre capital, ses contraintes, ses ordres et
ses verrous. Les campagnes déjà ouvertes gardent leur politique figée :
modifier le YAML ne change pas rétroactivement leur trailing ou leur durée.
Le watcher doit rester en fonctionnement pour la sortie temporelle et les
protections locales. Les ordres stop déjà déposés restent chez le broker.

La configuration accepte désormais le SIP retardé :
`winner_pyramiding.market_data_delay_seconds: 900` et
`delayed_entry_limit_buffer_pct: 0.01`. Les confirmations utilisent les
bougies closes connues à l'heure réelle moins quinze minutes. L'ordre IOC
est limité au dernier close retardé majoré de 1 %, avec les plafonds de
risque et le plafond d'écart à la référence approuvée lorsqu'il est configuré.
Le sizing se fonde sur ce plafond, et le fill réel peut être plus bas.
Il n'y a pas de bid/ask temps réel inventé ni d'appel SIP latest pour ce chemin.
Au-dessus de la limite, aucun achat n'est garanti. `market_data_delay_seconds: 0`
conserve le chemin temps réel et ses contrôles. Aucun fallback IEX n'est ajouté.

Le délai accepte **tout entier entre 900 et 3 600 secondes**, sans obligation
de multiple de cinq minutes : `930` représente quinze minutes et trente
secondes et conserve une marge de publication. Le fichier de travail est
actuellement réglé à `930`. La grille temporelle des bougies reste cinq minutes.
Une valeur invalide est signalée dans la page Backtest, sans lancement ni
remplacement silencieux de la politique par une valeur par défaut.

Le délai est aussi reproduit dans le backtest : disponibilité après le délai,
achat à une ouverture 5m observée à partir de cette disponibilité, jamais
au cours historique de la bougie de confirmation. La sortie temporelle
compte depuis le fill réel. Le contrôle de fraîcheur résiduel reste 60 secondes
au-delà du délai, et les confirmations doivent appartenir à la séance courante.

Le cutoff options du replay est fixé une seconde avant l'ouverture de la
séance d'entrée. Cela inclut les reçus de la nuit connus à cette date, sans
lire les données options de la nouvelle séance. `options-receipts.json` et
`options-selection.csv` tracent les décisions, exclusions et empreintes des
inputs. Un historique d'OI absent ne peut pas être reconstitué avec du
volume seul ou avec les snapshots d'aujourd'hui : bilan incomplet et aucune
entrée pour les cohortes insuffisantes. L'option peut être décochée pour un
témoin Oracle brut, différence explicitement consignée dans le protocole.

### Diagnostic du premier semestre 2025, run 20261031_125841_66dcce61

La commande demande le 01/01/2025–30/06/2025, modèle parcours H10
`model-factory-20261030213826-eda503`, TOP20, 4 000 $, sans levier,
confirmation de deux bougies, filtre options et contrôle factoriel activés.
Les artefacts du run établissent :

- 122 séances, 2 440 lignes dans `signals.csv` ;
- 2 440 lignes dans `options-selection.csv`, toutes refusées avec
  `MISSING_OR_STALE_OPTIONS` ;
- 122 cohortes `covered: 0`, `incomplete: true` dans `options-receipts.json` ;
- 122 lacunes `OPTIONS_COHORT_INCOMPLETE`, aucune campagne et aucun achat ;
- reçus intraday et facteurs vides : ces contrôles n'ont pas été atteints ;
- rapport `INCOMPLETE_COVERAGE`, capital inchangé 4 000 $ ; le rendement 0 %
  ne constitue pas une performance économique mesurée.

Ce constat provient des artefacts enregistrés, pas d'une nouvelle lecture SQL
de toute la couverture options. L'accès direct MySQL était indisponible pour
ce diagnostic ; aucune borne globale d'historique en base n'est affirmée.
Les reçus postérieurs au cutoff ne peuvent pas être antidatés pour débloquer
le test. Un témoin sans options est une autre expérience explicite ; le
contrôle factoriel requiert également ses propres archives qualifiées.

L'historique IHM lit désormais les flags complets `--start-date`/`--end-date`
et les anciens `--start`/`--end`, sans confondre `-date` avec une valeur. Pour
les runs Winner terminés, le badge consulte le statut du rapport/progress :
`INCOMPLETE_COVERAGE` devient **orange, couverture incomplète**, même lorsque
le processus est sorti normalement avec le code zéro. Le journal d'exécution
et les résultats historiques ne sont pas réécrits. L'avertissement apparaît
avant le chargement facultatif du rapport détaillé ; le résumé explique aussi
le cas où le filtre options a bloqué toutes les entrées.

Régressions ciblées : 59 tests réussis (dates/labels, page Backtesting et
sélection options historique). Aucun ordre, appel fournisseur, modification
SQL ni nouveau replay n'a été exécuté pour ce correctif d'affichage.

### Run 20261031_151056_45eba031 : anomalie d'horloge SIP retardée

Période demandée 06/07/2021–29/10/2026, 1 337 séances, même Oracle H10,
TOP20, 4 000 $, confirmation 2, délai 930 s, fraîcheur résiduelle 60 s,
filtre options désactivé, contrôle factoriel activé. Les artefacts indiquent
26 740 sélections et 2 409 campagnes/plans créés, sans aucun fill d'achat.

`events.csv` contient 3 204 761 refus `DELAYED_SIP_UNQUALIFIED`, 479 001
refus de référence de séance précédente, 60 022 absences de bougie candidate
et 44 budgets de signal insuffisants. Les lacunes distinctes du rapport se
répartissent en 5 619 `SIGNAL_RAW_5M_INCOMPLETE`, 7 192
`CANDIDATE_RAW_5M_INCOMPLETE` et 6 802 `PRIOR_RAW_5M_INCOMPLETE`.
Les reçus factoriels sont vides : la réapprobation factorielle n'a pas été
atteinte, ce qui ne qualifie pas sa disponibilité historique.

L'ancien replay ne testait les campagnes qu'aux ouvertures 5m. Avec
930 secondes de délai, le cutoff tombe 30 secondes avant une borne 5m : la
dernière bougie achevée a donc 270 secondes d'ancienneté résiduelle, contre
60 autorisées. Cela bloque même une série de données parfaitement complète.
Reproduction synthétique sur la séance officielle du 06/07/2021 : 74/78
instants qualifiés avec un délai 900 s, **0/78 avec 930 s** ; le même jeu
de bougies devient frais à l'instant de disponibilité décalé de 30 secondes.

Le paramètre 930 s est valide en exploitation avec un watcher au bon instant.
Le défaut venait du raccordement à l'horloge du replay ; ce résultat ne
prouvait pas une absence d'occasions de trading.

### Correctif du replay SIP décalé, 31 octobre 2026

`backtesting/winner_clock.py` sépare l'horloge de disponibilité des preuves
de celle des prix observés. Avec un délai de 930 secondes, les confirmations
sont évaluées aux bornes 5m décalées de 30 secondes. Le délai figé, la
fraîcheur résiduelle de 60 secondes et les cutoffs historiques sont conservés.

Les bougies 5m ne donnent pas le prix exact trente secondes après leur
ouverture. Pour un signal entre deux bornes, le replay réserve le capital,
fige la quantité et la limite approuvées, puis tente une seule exécution à
l'ouverture 5m suivante de la même séance. Une ouverture absente, un cours
au-dessus de la limite ou une capacité insuffisante annulent cet ordre.
Une nouvelle décision ultérieure reste possible, mais cet ordre précis ne
peut attendre une ouverture plus favorable, exploiter un low futur ou être
reporté au lendemain. C'est un **proxy d'exécution IOC pour la recherche**,
pas la reproduction d'un véritable IOC envoyé au moment du signal.

Les décisions et exécutions ont leurs horodatages distincts dans `events.csv`
(`DELAYED_ENTRY_DECISION`, `BUY_FILL`, `DELAYED_ENTRY_CANCELED`). Le contrat
`replay_clock` est conservé dans le protocole et le rapport ; la page IHM
explique cette approximation. `full_live_parity` reste faux. Les ajustements
de stop décidés entre deux bornes prennent effet à l'ouverture suivante ;
l'ancien stop reste actif jusque-là, sans appliquer le nouveau seuil au low
déjà passé. À la fin de séance, le dernier ajustement ne peut affecter la
bougie qui le précède ; son seuil est applicable à l'ouverture suivante.

Le coordinateur traite séparément la réconciliation, la protection des lots,
l'expiration et l'échéance sur l'horloge des prix. L'entrée standard sans
confirmation conserve son exécution à l'ouverture. Les fills différés sont
réconciliés avant le contrôle de liquidation globale ; une coupure déjà
connue annule l'achat en attente avant son exécution. Le budget partagé,
les frais, les limites de levier et les contrôles natifs restent appliqués.

Validation hors ligne sur un échantillon synthétique : signal qualifié à
14:00:30 UTC, achat au prix de **103 $ à 14:05 UTC**, sans utiliser ni le cours
de 102 $ de la preuve retardée, ni l'ouverture de 101 $ à 14:00. Les cas
de limite dépassée, ouverture manquante, réservation de capital, absence de
facteurs historiques, liquidation, clôture anticipée et échéances H10/H20
sont couverts dans `tests/test_winner_replay_clock.py`.
Suite Winner : 326 tests réussis lors de la passe élargie ; après le dernier
raccordement de réconciliation avant liquidation, 69 tests ciblés réussis
(horloge, replay intraday, SIP retardé et liquidation globale).

Les archives d'origine restent inchangées. Le prochain processus de
backtest chargera le correctif. Aucun replay économique sur cinq ans, ordre,
appel fournisseur ou changement des services en fonctionnement n'a été lancé.
Les lacunes de bougies du run d'origine restent à qualifier. Le contrôle
factoriel peut désormais être atteint : son absence éventuelle doit encore
produire un refus et un bilan incomplet, jamais un facteur antidaté ou un
contrôle désactivé implicitement.

### Run 20261031_173004_6b225c2c : risque factoriel sans archives historiques

Le run suivant, terminé en `INCOMPLETE_COVERAGE`, utilise bien la nouvelle
horloge (décalage de 30 secondes). Son protocole indique `options_filter=false`,
`factor_model=true`, 4 000 $, TOP20 et la période du 06/07/2021 au 29/10/2026.
Il a créé 2 409 campagnes, sans achat ni frais ; capital final 4 000 $.

Les 22 722 événements `NATIVE_RISK_REJECTED` portent tous le motif
`Aucun snapshot factoriel reçu avant décision`. Le fichier
`factor-receipts.json` contient 12 038 contrôles distincts jour/périmètre,
tous non qualifiés. Ces nombres sont des tentatives/contrôles, pas des
trades indépendants. Les requêtes de `HistoricalFactorSource` cherchent dans
`stock_risk_factor_inputs` un snapshot à la date de référence, avec
`observed_at <= cutoff` : un snapshot collecté ultérieurement ne peut servir
de preuve historique. Le correctif d'horloge permet désormais d'atteindre
ce contrôle ; aucune approbation d'entrée n'a pu le franchir.

Les autres lacunes subsistent : 5 619 `SIGNAL_RAW_5M_INCOMPLETE`, 7 192
`CANDIDATE_RAW_5M_INCOMPLETE` et 6 802 `PRIOR_RAW_5M_INCOMPLETE`. Le statut
incomplet et les zéro achat ne constituent pas une mesure de performance
économique de la stratégie.

Pour un témoin historique sans ces archives factorielles, l'utilisateur peut
décocher **Appliquer le contrôle factoriel de production** dans le formulaire.
Cette différence de protocole est explicite ; elle ne désactive ni SL,
budget de risque, capital partagé, frais ni autres contrôles actifs. Le
défaut factoriel de production reste inchangé. Aucun nouveau replay ni
changement de configuration de production n'a été lancé pour ce diagnostic.
L'évolution suivante ajoute le calcul automatique décrit ci-dessus. Elle
ne garantit pas de débloquer ce run : une capitalisation historique absente
reste absente même lorsque les facteurs techniques sont recalculables.

### Incident SDGR : une bougie détenue absente le 31/01/2025

Le run `20261031_211630_0f9ddba2`, du 01/01 au 30/06/2025, a atteint une
position SDGR puis s'est arrêté sur l'intervalle 17:00–17:05 UTC du
31/01/2025 (18:00–18:05 Paris). La base contient 77 des 78 bougies régulières
attendues ce jour-là. La ligne n'existe dans aucun autre flux local à cet
instant ; elle n'est pas simplement exclue par le filtre qualité du replay.

Deux vérifications GET auprès d'Alpaca SIP, en raw, ont confirmé zéro bougie
5m et zéro bougie 1m à l'intérieur de cet intervalle. Le serveur retourne
aussi la borne de fin de requête : une ligne à 17:05 ne répare pas la
période manquante 17:00–17:05. Cette absence ne démontre à elle seule ni
un arrêt de cotation, ni l'absence de transactions éligibles, ni une panne
de fournisseur.

Le moteur reste strict : pas de cours inventé, de remplissage au cours
précédent, de suppression rétrospective de SDGR du classement ni de SL
ignoré pendant le trou. Un simple relancement sur ces mêmes données peut
donc rencontrer le même arrêt. Les vérifications n'ont écrit aucune ligne
SQL et n'ont pas relancé le backtest. Preuves :
`artifacts/operations/sdgr_intraday_gap_20261031/report.json`, avec les deux
réponses fournisseur locales.

Dans ce run, `factor_market_cap_check=false` : « 0 capitalisations datées »
est donc attendu et ne constitue pas un refus d'entrée. La réduction de
CLMT à zéro est un refus de sizing au minimum de position de 50 $, distinct
du défaut de couverture SDGR.

### Ignorer automatiquement les titres aux données intraday manquantes

Le formulaire Winner propose **Ignorer automatiquement les titres aux données
intraday manquantes**, **coché par défaut**. Il remplace la saisie manuelle
des titres exclus. La commande équivalente est `--ignore-missing-intraday`.
Le bouton de reprise des réglages de production rétablit cette option cochée ; aucun
fichier d'univers ni paramètre live n'est modifié. Sans cette option, le
moteur conserve son arrêt strict sur une bougie détenue absente.

Avant la simulation, le contrôle compte les bougies SIP raw régulières 5m
qualifiées sur le calendrier officiel, y compris les séances raccourcies.
Pour chaque signal Oracle, il examine la fenêtre potentielle allant du signal
à la dernière sortie possible selon l'attente d'entrée et l'horizon de
détention, bornée par la fin du replay. Sans horizon, la fenêtre va jusqu'à
la fin du replay. Les fenêtres qui se chevauchent sont regroupées. Il ne
contrôle pas les années antérieures au premier signal d'un titre.

**Évolution du 1er novembre 2026 :** les nouveaux runs tentent un rattrapage
**Alpaca SIP → Yahoo → EODHD**, uniquement sur les séances incomplètes. Les
réponses sont requalifiées : grille 5m, séance officielle, OHLCV positifs,
absence de doublons, durée et provenance. Les cours SIP existants sont
prioritaires ; seuls leurs timestamps manquants peuvent être ajoutés.

Yahoo/EODHD ne sont pas renommés SIP. Avant un complément, il faut au moins
trois bougies communes de la même séance avec le SIP brut, et tous les OHLC
communs doivent être à moins de 1 %. Sinon la base de prix est jugée
incompatible ou non vérifiable et le complément est refusé. Une séance
entièrement absente sans ancrage SIP ne peut donc pas être réparée par un
autre fournisseur sur la seule foi de sa réponse.

Un échec fournisseur passe au suivant ; aucun achat d'abonnement, contournement
de refus d'accès ou remplacement par IEX/daily. Un 401/403/429 ou circuit/quota
épuisé suspend ce fournisseur pour le run ; les autres restent essayés.
Yahoo est interrogé avec une pause aléatoire de 1 à 5 secondes. Lorsqu'il
annonce explicitement sa limite glissante de 60 jours, les dates plus anciennes
ne provoquent plus d'appels Yahoo répétés. Ses bougies 5m ne constituent pas un
historique sur plusieurs années.

Si une lacune subsiste, **le titre n'est plus exclu de tout le run**. Le replay
bloque une entrée à une date donnée si la séance précédente (référence), la
séance d'entrée ou sa détention possible jusqu'à l'ouverture de sortie contient
cette lacune. Un même trou peut donc bloquer plusieurs dates d'entrée voisines,
mais pas toutes les années. Le plan non exécuté peut retenter plus tard dans
sa validité initiale. Sans horizon, le contrôle porte jusqu'à la fin du replay.

La validation des scores, leur traçabilité et la couverture Oracle portent
toujours sur l'univers demandé. Le blocage intervient après le classement
TOP-N et le filtre options éventuel, à l'admission d'entrée par le replay.
Elle conserve les rangs d'origine, **sans reprendre le rang N+1**. Une liste
qui retire tous les candidats laisse le portefeuille en liquidités.

Le protocole et le rapport conservent les lacunes restantes, le hash de la
sélection d'origine et le reçu du contrôle de couverture.
`entry-exclusions.csv` donne **symbole, date d'entrée interdite, dates des
lacunes et motif** ; le même tableau est écrit intégralement dans le journal
final, y compris après un échec. Il recense les plans bloqués, sans prétendre
qu'ils auraient tous donné un trade. `excluded-signals.csv` reste réservé aux
exclusions manuelles sur toute la période ;
`missing-intraday.json` et `missing-intraday.csv` détaillent les titres,
dates et nombres de bougies absentes/non qualifiées. Le journal final liste
les dates d'entrée écartées. Le suivi affiche d'abord le contrôle, puis le
rattrapage (`RECOVER_INTRADAY`), puis la simulation.

`intraday-recovery.json` détaille essais, erreurs, fournisseurs suspendus et
compléments utilisés. Les réponses natives sont conservées avec SHA256 et
heure réelle de téléchargement sous `artifacts/winner_intraday_recovery`,
avec objets immuables par contenu. Le cache d'une requête est réutilisé 24 h,
puis rafraîchissable sans supprimer les anciens objets cités par les reçus.
Les compléments constituent une surcouche du replay, **aucune écriture SQL
ni modification des tables canoniques**. Un backtest ultérieur réutilise le
cache sans confondre ces réponses avec des archives connues à l'époque.

Avec au moins une exclusion automatique, le résultat reste
`INCOMPLETE_COVERAGE` (orange), avec les résultats du sous-ensemble retenu.
Ce mode utilise **la disponibilité future des données**, connue après coup :
il introduit un biais de sélection possible et n'est pas une règle live
causale. Le résultat ne prouve pas ce qu'aurait donné le protocole initial
complet.

Le moteur ne fait jamais disparaître une position déjà ouverte quand un
trou survient et ne remplit pas une bougie absente. Les contrôles de prix
daily, d'identité, d'actions sur titres et de risque restent actifs : cette
option concerne uniquement la couverture intraday. Elle nécessite un
nouveau run ; elle ne reprend pas automatiquement le run échoué.

**Constat antérieur au changement de politique** : vérification locale
SELECT-only sur les signaux de janvier, jusqu'au
31/01/2025 : **43 titres contrôlés, 21 exclus, 202 séances incomplètes**,
dont la lacune SDGR du 31 janvier. Ce constat de couverture n'est pas une
mesure de performance. Preuves :
`artifacts/operations/winner_ignore_missing_intraday_20261031/january-screen.json`
et `january-missing-intraday.csv` dans le même dossier. Aucun fournisseur
n'a été appelé et aucune ligne SQL n'a été écrite pour ce contrôle.

La commande manuelle `--exclude-symbols SDGR` reste disponible pour les
anciens scripts ; elle n'est plus proposée dans le formulaire. Un symbole
manuel invalide ou absent de l'univers demandé est refusé explicitement.

Validation initiale de l'ancienne politique : **52 tests distincts réussis**, couvrant le
formulaire et sa remise à zéro, le défaut strict, le contrôle SELECT-only,
les demi-séances, la conservation des rangs, le replay avec les autres titres
et les exports complets lorsque tous les candidats sont exclus.

Validation du raccordement du 1er novembre : **101 tests réussis** (rattrapage,
cache/provenance, erreurs et limites fournisseurs, TLS vérifié EODHD,
reprise du même titre à une date ultérieure, positions/protections conservées,
options, horloge retardée, formulaire et export complet en SQL lecture seule).

Essai fournisseur borné réel : **SDGR, 31/01/2025**. Alpaca SIP renvoie
toujours 77/78 bougies ; Yahoo refuse la plage (HTTP 422). Après correction
de la session TLS du nouvel appel, EODHD répond `EodhdPermissionError` :
la bougie reste non récupérée. Reçus initiaux dans
`artifacts/operations/winner_recovery_probe_20261101/intraday-recovery.json`,
et vérification EODHD finale dans le sous-dossier `verified-output`.
Cet essai porte sur la récupération, sans replay économique ni écriture SQL.
Les précédents résultats de backtest ne sont pas modifiés ni recalculés.

### Contrat SIP du watcher en exploitation (rappel)

Redémarrer le watcher pour charger ce nouveau contrat avant une nouvelle
étape 12. Le contrôle d'ancienneté du code refuse l'ancien processus.
Les anciennes campagnes gardent leurs paramètres figés, y compris le délai
zéro lorsqu'il n'était pas renseigné : cette mise à jour ne réécrit ni plans
existants ni positions. Les nouveaux paramètres concernent les nouvelles admissions.

**Le moteur Winner comporte les chemins PAPER et live, mais les filtres
options/LLM actuels conservent leur restriction PAPER.** Ce raccordement ne
les autorise pas en argent réel, ne bascule aucun compte et ne démarre
aucun watcher. Les tests d'exécution restent simulés.

## Validation technique

Suite Winner/exécution/registre/commandes : 309 tests réussis. Vérifications
ciblées supplémentaires après durcissement des folds et du mode daily :
65 tests réussis, avec contrats H10/H15/H20. Les scénarios comprennent le
vrai formulaire Streamlit, parsing de la commande produite, replay complet
sur base SQLite surveillée SELECT-only, rapports réutilisables par l'IHM,
blocage des données factorielles futures/manquantes, passage du contexte au
contrôle natif, confirmations, protections, échéance et reprise idempotente.
La base de production, les ordres et les services en fonctionnement n'ont
pas été modifiés par ces tests.

Complément SIP retardé/options : tests de parité de sélection avec le pipeline,
cutoffs et refus des reçus futurs, absence de substitution du rang suivant,
achat au prix ultérieur et refus au-dessus du plafond, revalidation native,
preuve retardée sans faux marqueur temps réel et idempotence du premier achat.
Suite élargie après raccordement : **364 tests réussis** (Winner, options,
commandes, formulaire et registre), complétée par les régressions du mode
zéro confirmation et du plafond d'écart approuvé. Aucun test n'a envoyé
d'ordre ni appelé de fournisseur.

Voir aussi [entrée standard](winner_standard_entry.md),
[cotations standard](winner_standard_entry_quotes.md),
[alignement SL/sizing](winner_sl_sizing_alignment_20261030.md) et
[risque factoriel](risk_factor_inputs.md).

### Cible trop petite pour une action entière — 1er novembre 2026

Le budget Winner inclut le SL et la réserve de frais configurée :
`prix × (stop_loss_pct + 2,05 × cost_reserve_bps_per_leg / 10 000)` par action.
Une cible de l'étape 11 peut donc être entière mais non finançable après cette
réserve. L'admission écarte alors uniquement cette cible avec le motif
`INSUFFICIENT_CAMPAIGN_BUDGET`, son budget et le minimum nécessaire. Elle ne
crée aucun plan pour ce titre et ne le transmet pas au circuit d'achat standard.
Les autres plans restent admissibles. Les quantités ne sont jamais arrondies
à la hausse et les budgets ne sont jamais augmentés.

Le bilan d'exécution expose `winner_plans_insufficient_budget`, la liste
`winner_plans` et le compteur `skipped`. Un contrat malformé (budget absent,
fractions interdites, date invalide) continue de faire échouer la validation
complète avant toute création de plan. Ce correctif ne modifie pas les
protections ni les paramètres des campagnes existantes.
