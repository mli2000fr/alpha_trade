# Oracle parcours H10 + modèles annuels par titre

Le mode parcours peut désormais entraîner les deux branches LONG et SHORT dans
le même batch que l'Oracle d'amplitude. La sélection opérationnelle reste LONG
uniquement : **TOP20 Oracle → TOP5 selon la probabilité de gain LONG → risque →
Winner**. Le score SHORT n'est ni inversé en LONG ni utilisé pour un ordre SHORT.

## Depuis Pipeline / T1 ML Train

1. Cocher **Oracle Extreme parcours** (coché par défaut), choisir **H10**.
2. Cocher **Bundle Oracle + deux modèles Per-Symbol LONG/SHORT**. Son défaut
   vient de `oracle_path.directional.enabled`, actuellement `true`.
3. Choisir l'univers, les dates et l'algorithme de l'Oracle. Les modèles par titre
   sont des LightGBM indépendants, avec calibration Platt annuelle.
4. Lancer un nouveau batch. Le choix per-symbol est imposé pour ces branches ;
   le mode per-sector ne peut pas le remplacer. Le bundle terminal legacy reste
   disponible quand la case parcours est décochée, avec son ancien contrat H20.

Le CLI ajoute `--oracle-path-model-only --oracle-horizon 10
--oracle-path-directional`. Les trois anciens batches du 4 novembre à 13:19
restent des Oracle seuls : ils ne reçoivent aucun modèle ni nouveau contrat
rétroactivement. Il faut un nouveau batch pour ce bundle.

Les diagnostics ajoutés le 6 novembre sont enregistrés automatiquement aux
prochains entraînements : AUC et mesures de classification par titre, avec
séparation entraînement/calibration/test annuel, prédictions de test et
benchmark figé. Les anciens poids n'ont pas besoin d'être réentraînés pour
compléter leurs diagnostics depuis les archives ; voir
[métriques et périodes per-symbol](diagnostic_oracle_parcours_h20.md).

La taille du pool Oracle et le nombre final retenu règlent la sélection,
pas les modèles à entraîner. Dans le replay, **TOP10 % d'un univers de 1 790
titres → TOP10 LONG** se règle par **Mode du TOP Oracle → Pourcentage de
l’univers**, **TOP Oracle (%)=10**, puis **Top X Long=10**. L'écran calcule
179 candidats et transmet ce nombre au replay. Le dénominateur est l'univers
figé du modèle ; arrondi supérieur, minimum un candidat. Le nombre reste fixe
sur le backtest, sans réduction du pool pour compenser les scores manquants.
Le mode **Nombre de titres** conserve la saisie Top N Oracle et reste le défaut.
Les branches restent entraînées sur les historiques propres de tous les
titres qualifiés. Le pipeline Predict conserve le contrat de sélection gelé
de son batch tant qu'un paramétrage d'inférence distinct n'est pas raccordé.

## Cibles et chronologie

- Oracle : TOP20 % de l'amplitude maximale absolue pendant J+1..J+10, depuis
  la clôture J, sans direction. Son entraînement walk-forward reste inchangé.
- LONG : achat à l'ouverture J+1, SL à 5 %, sans TP/trailing ; dix séances de
  détention, puis sortie open11. Classe positive si le résultat net est positif.
- SHORT : cible symétrique avec stop au-dessus de l'entrée et résultat net d'une
  vente à découvert. Cette branche ne comprend pas emprunt/locate/dividendes :
  elle est archivée et **non utilisée pour le trading**.
- Frais du label : 8 points de base par opération. Gap au-delà du stop : cours
  d'ouverture défavorable. Aucun sommet ultérieur ne répare un stop déjà touché.
- Pour l'année Y : apprentissage avant Y−1, calibration en Y−1 ; les résultats
  des labels doivent être disponibles strictement avant chaque frontière.
  Chaque label est conservativement disponible seulement à la sortie open11.
- Minimum 756 observations d'apprentissage et 126 de calibration, avec minimums
  de classes 40/15. Modèle constant ou historique insuffisant : motif consigné,
  aucun modèle ancien/futur ni score neutre substitué.
- 24 variables prix/tendance/volatilité/volume/SPY, dont trois évolutions sur
  cinq séances ; winsorisation et imputation apprises sur le train seulement.
  Les branches apprennent sur l'historique propre du titre, pas sur le rendement
  futur du TOP Oracle. Pas de news, options ou consensus ajoutés à ces branches.

Ces modèles par titre sont des LightGBM peu profonds : 120 arbres, profondeur
maximale 3, sept feuilles et calibration logistique Platt. Les réglages LSTM
du formulaire général ne correspondent pas à l'algorithme de cette branche.
Leur entraînement peut donc être beaucoup plus rapide que celui des modèles
neuronaux historiques ; les dossiers/manifeste font foi pour confirmer ce qui
a réellement été entraîné. Diagnostic ML affiche désormais leur couverture,
dates et motifs d'absence dans un bloc distinct (voir
[le diagnostic parcours](diagnostic_oracle_parcours_h20.md)).

`oracle_path.directional` fige les nombres 20/5, SL, horizon et frais au training.
Changer le YAML n'altère pas un batch existant. Le champ `enabled` règle le défaut
IHM, pas l'activation d'un compte. Les protections effectives de Winner restent
son propre contrat : les garder alignées avec la cible si l'on veut comparer
avec l'expérience SL5/open11. Ce raccordement ne garantit aucun rendement.

## Predict, risque, exécution et replay

Choisir le nouveau batch à l'étape 10, avec **l'univers complet de ce batch**.
Les modèles de l'année de la décision sont chargés, sans substitution par un
autre millésime. Le pool est d'abord figé dans l'ordre Oracle, puis trié par
probabilité LONG décroissante, rang Oracle et symbole en cas d'égalité. Il n'y
a pas de seuil de probabilité : on retient au plus cinq titres du pool de vingt.
Un titre sans modèle/features qualifiés n'est pas remplacé par Oracle rang21.

Le contrôle de couverture à la prédiction se configure séparément dans
`oracle_path.min_prediction_coverage_ratio` : **0.93** depuis le 4 novembre 2026
(30 titres sur 32). Il conserve un minimum de vingt titres et la taille du pool
Oracle configuré. Les dates et titres absents sont journalisés ; aucune donnée
n'est inventée. Ce seuil opérationnel ne modifie ni la cible, ni les poids, ni le
seuil historique de qualification des labels d'entraînement.

Les filtres options et LLM sont écartés pour ce bundle à la construction des
commandes et au lancement du workflow : ils ne doivent pas changer de batch ou
substituer une sélection différente. Cela concerne aussi `us_pipeline` lorsqu'il
est configuré pour utiliser le nouveau batch ; son batch par défaut n'est pas
modifié automatiquement. Les anciens Oracle gardent leurs modes actuels.

Étape 11 vérifie séance, compte, origine, modèle exact, probabilités et classement
archivés. Elle transmet les TOP5 LONG encore tradables aux contrôles de risque
existants. Pas de réallocation vers le sixième en cas de refus, détention ou
manque de cash. Le rang Oracle n'est pas présenté comme probabilité LONG et
aucune espérance de gain n'est fabriquée pour l'optimiseur. Les limites de risque
restent actives selon leur configuration, sans Kelly sur cette stratégie.

Étape 12 utilise le portefeuille cible du compte et le parcours Winner existant,
avec sa vérification de watcher, ses confirmations, ses protections et ses règles
d'idempotence. Le raccordement n'envoie aucun ordre par lui-même.

Le backtest Winner reconnaît ce bundle. La case **per-symbol**, sous le choix du
modèle, est cochée par défaut pour un bundle compatible. Quand elle est cochée :

- **Mode du TOP Oracle** choisit nombre ou pourcentage de l'univers du modèle ;
- **Top N Oracle** fixe le nombre de candidats, ou **TOP Oracle (%)** calcule
  ce nombre depuis le pourcentage (10 % de 1 790 = 179) ;
- **LONG** et **SHORT** activent séparément les classements ;
- **Top X Long** et **Top Y Short** définissent les nombres retenus par branche.
- **Score LONG minimum — strictement supérieur**, défaut IHM **0,60**, filtre
  ensuite les TOP X LONG. Un score égal au seuil est exclu ; aucun remplacement
  depuis les rangs suivants, aucune vente forcée d'une position détenue.

Défaut : N=20, LONG coché, X=5, SHORT décoché, Y=5. Les nombres sont préremplis
depuis le contrat entraîné. X/Y ne peuvent pas dépasser N ; au moins une branche
doit être cochée. Chaque classement reste dans le pool Oracle, sans promouvoir
un titre au-delà de ce pool en cas de score manquant. Si un titre est retenu des
deux côtés, garder la probabilité la plus élevée ; égalité : abstention, sans
remplacement. Ces probabilités portent sur les cibles nettes de chaque branche,
pas sur la seule hausse/baisse à l'échéance.

**Limite actuelle : le classement SHORT est disponible, mais le moteur Winner
ne simule pas les ventes à découvert.** Cocher SHORT désactive le lancement du
replay dans l'IHM ; une commande directe est refusée avant la lecture SQL ou
les appels fournisseurs. Les candidats SHORT ne sont jamais supprimés
silencieusement ni convertis en achats. L'exécution SHORT demande un raccordement
distinct du moteur de campagnes et de sa comptabilité.
Le prototype SHORT isolé et ses tests sont conservés séparément, sans branchement,
conformément à la décision utilisateur du 4 novembre :
[état et travail restant](winner_short_isole_20261104.md).

La commande émet `--per-symbol-long` (flag historique d'activation), puis
`--[no-]per-symbol-longs`, `--[no-]per-symbol-shorts`, `--per-symbol-top-long X`,
`--per-symbol-top-short Y`, `--top-n N` et, depuis l'IHM,
`--per-symbol-min-long-probability 0.6` (valeur modifiable). Les anciennes
commandes sans ce dernier paramètre restent sans seuil. Décocher per-symbol émet
`--no-per-symbol-long` pour un témoin Oracle seul. Les anciennes commandes
conservent l'auto-détection du bundle. L'option reste indisponible sans branches.

Le replay vérifie d'abord les probabilités, empreintes, dates et classements
archivés avec le contrat original. Il recalcule ensuite les classements choisis
**dans son propre dossier** : `per-symbol-ranking.csv`, `signals.csv` et
`protocol.json` (`per_symbol_selection`). Aucun classement SQL, modèle ou choix
du pipeline n'est modifié. Options/GPT ne sont pas rejoués par-dessus. ML Predict
doit avoir calculé les scores historiques nécessaires auparavant. Aucun modèle
ne s'entraîne dans le replay. Les limites OHLC et de couverture restent celles
du moteur. L'utilisation de N/X/Y différents s'applique seulement à ce backtest.

L'univers est sélectionné automatiquement depuis le contrat du batch ; le
champ **Univers Winner** est grisé et le bouton de reprise a été supprimé.
La commande `--symbol-source model-universe` utilise la liste figée, sans lire
un fichier externe mutable. Cela s'applique aussi à Oracle seul. Les anciennes
commandes avec un fichier conservent leurs contrôles ; N/X/Y et le seuil LONG
restent paramétrables. Les dates par défaut prennent l'année
qui suit la fin configurée du training : le batch `model-factory-20261104153014-49a6da`
propose donc **2022**, son univers de **32 titres** et le parcours **TOP20 → TOP5**.
Pour couvrir toute cette année, le signal du **31/12/2021** est nécessaire pour
l'entrée du 03/01/2022 ; il a été préparé séparément le 4 novembre 2026, sans
entraînement, téléchargement ni ordre. Le replay lui-même reste SQL lecture seule.

## Stockage et reprise

Le formulaire Winner applique depuis le 5 novembre les défauts demandés pour
la comparaison au test journalier : confirmation/délai à zéro, poids maximal
20 %, liquidation et facteurs décochés, contrôleur DD/perte quotidienne/B4
décoché. Le moteur reste intraday ; les anciennes commandes conservent leur
contrôleur actif. [Réglages, interrupteur et portée exacte](../backtesting/winner_reference_defaults.md).

- `artifacts/models/<batch>/oracle_path/` : Oracle, protocole et rapport.
- `oracle_path/directional/<symbole>/{long,short}-<année>.joblib` : modèles et
  calibrateurs ; aucun artefact du bundle terminal legacy n'est réutilisé.
- `oracle_path/directional/manifest.json` : bornes réelles, empreintes, modèles
  qualifiés et exclusions par branche/année. Son empreinte est dans le rapport.
- `alpha_trade.oracle_path_directional_predictions` : probabilités LONG/SHORT,
  rangs Oracle/LONG, retenu/motif et empreintes ; créée au premier Predict.
- `model_predictions`, source `oracle_path_long` : projection LONG/FLAT consommée
  par le risque. `proba_short=0` ici ; le score SHORT reste dans la table dédiée.
- L'IHM étape 10 affiche le TOP Oracle, les deux scores et les retenus LONG.
- Training reprend les checkpoints Oracle compatibles ; les modèles annuels
  terminés sont contrôlés par empreinte. Un manifeste incomplet ou corrompu ne
  peut pas être servi. Aucun entraînement de production lancé pour ce changement.

Les univers choisis selon leur AUC de 2026 restent rétrospectifs : les découpages
causaux des modèles ne suppriment pas ce biais de sélection d'univers.

## Vérification du raccordement

Tests ciblés : apprentissage réel sur séries synthétiques et rechargement des
deux branches annuelles, purge des frontières, stop avant retournement, données
manquantes/changement de fournisseur, tri TOP20/TOP5 sans remplacement, empreintes
corrompues, projection SQL LONG/FLAT, contrôle de probabilité dans le risque,
limites natives, commandes IHM/CLI, horloges et compatibilité des anciens modes.
Les tests ne passent aucun ordre et n'entraînent aucun batch de production.
