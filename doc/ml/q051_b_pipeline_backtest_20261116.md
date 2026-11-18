# Option B — entraînement par titre et profil de backtest

## Pipeline — T1 ML Train

Sous **Bundle Oracle + deux modèles Per-Symbol LONG/SHORT**, la case
**Volatilité inhabituelle — per-symbol (B)** est cochée par défaut. Elle
concerne les branches par titre du bundle Oracle parcours H10/H15/H20.
Lorsque le bundle est inactif, cette case est désactivée et n’ajoute aucun
paramètre au modèle historique.

Cocher entraîne LONG et SHORT sur les24 variables compactes existantes plus :

- `rolling_volatility_60` ;
- `rolling_volatility_120` ;
- `rolling_volatility_20_zscore` ;
- `rolling_volatility_60_zscore` ;
- `rolling_volatility_120_zscore`.

Soit29 variables, dans cet ordre. Décocher conserve les24 variables historiques.
Les variables de l’Oracle d’amplitude restent indépendantes. Le mode CLI
`--oracle-path-directional-features compact_volatility` est archivé dans le
contrat et le manifeste du batch ; `compact` et `oracle` restent supportés.
La CLI sans ce paramètre conserve son défaut historique compact24.

Les nouvelles branches utilisent les mêmes arbres légers, bornes1/99,
imputation, calibration Platt et découpages annuels causaux que le bundle.
La qualification des lignes B reprend celle du test contrôlé :60 barres
récentes qualifiées, au moins80% des24 variables compactes disponibles et
contexte prix/marché/volatilité fini. Les quatre facteurs marché de contexte
du test commun T0/A/B qualifient les lignes mais ne sont pas des entrées
ajoutées au modèle B. Le test compare les panels natifs aux panels de recherche.

Les z-scores s’appuient sur une fenêtre allant jusqu’à1260 séances, avec
minimum252 observations. Pour B, Predict recharge depuis l’origine de données
figée dans le contrat d’entraînement : la fenêtre compacte historique de650
jours calendaires serait trop courte et modifierait les scores. Train,
Predict et le diagnostic relisent le même ordre des29 variables. Les anciens
contrats compact24 et Oracle complet gardent leur mode existant.

## Backtest — profil B seul

La liste **Profil de paramètres du backtest** contient maintenant
**Q051 — B seul, volatilité inhabituelle per-symbol, TOP10**. Le défaut de la
liste reste Q051 témoin TOP10 ; les autres profils sont conservés.

Le profil B applique TOP10% Oracle → TOP10 LONG, score>0,50, AUC de calibration
≥0,50, position complète, entrée à l’ouverture J+1 sans confirmation, SL5%,
sans TP/trailing/renforcement, sortie open11. Risque par entrée1,25%, poids20%,
20 positions, minimum50$, plafond achats1×, compte margin de capacité2×,
frais8 points de base par opération et financement6,5% annuel. Sans budget
vol20, filtre de régime, B4/DD15, facteurs, corrélation, limites sectorielles
ni pause100. Les réglages restent modifiables.

**Réappliquer le profil choisi** restaure ces valeurs et la sélection TOP10% /
TOP10 / seuils0,50, après des changements manuels, comme pour les autres profils.
Le modèle et les dates choisis restent conservés.

Un profil ne peut pas transformer les variables d’un modèle déjà entraîné :
pour lancer B, sélectionner un nouveau batch dont le manifeste indique
`compact_volatility` avec les29 colonnes attendues et laisser per-symbol actif.
Un modèle24 ou173 variables affiche une explication et ne lance pas un faux
backtest B. Aucun batch existant n’est réentraîné ou modifié automatiquement.

## Comparaison archivée

La fenêtre **Voir les courbes et leur comparaison** affiche sept courbes :
les quatre références Q051 TOP5/TOP10 simples/protégées, le témoin apparié
T0/24 variables du lot1, B/29 variables du même lot et SPY. Courbes, tableau,
réglages et Oracle annuels de B sont visibles. Les capitaux finaux, périodes,
contrôles arithmétiques et qualifications de prix archivées sont vérifiés.

B seul :15894,14$, +297,35%, DD−40,99%, 37,63% gagnants ; témoin apparié :
9162,34$, +129,06%, DD−39,12%. Période2021–1er octobre2026, départ4000$ continu.
Ces deux courbes ont les mêmes Oracle entre elles ; les anciennes références
Q051 utilisent une autre série de modèles annuels. Pour mesurer l’ajout des
variables B, comparer B à son témoin apparié, pas uniquement à une ancienne
courbe Q051. Les chiffres archivés ne garantissent pas le résultat d’un nouveau
batch ou d’une autre période. Intraday partiel/repli OHLC, univers contemporain,
prix révisés, sans certification PIT complète ni parité live.

## Vérification

80 tests ciblés couvrent les panels B et leur causalité, les vrais entraînements
LONG/SHORT, la relecture, les prédictions, le diagnostic, le défaut/opt-out de la
case, la commande émise, H10/H15/H20, la compatibilité24/173 variables, le profil,
sa réapplication et les courbes. Une image de contrôle du graphique est dans
`artifacts/ui_checks/q051_b_profiles_20261116.png`.

Les tests n’envoient aucun ordre et n’appellent aucun fournisseur. Aucun réglage
de compte ou de risque de production n’est changé par le profil de backtest.

## Extension du 18 novembre 2026 : anti-SL optionnel

T1 propose désormais **Ajouter le filtre anti-SL — trajectoire dix séances**,
après activation du bundle H10 et des variables B. Un batch ainsi entraîné applique
automatiquement son veto après le TOP LONG, sans remplacement. Les batchs B sans
cette tête gardent leur comportement. ML Predict doit enregistrer les scores avant
le backtest. Cette extension ne change pas le profil PAPER quotidien actuel.
Protocole, stockage, abstentions et limites :
`doc/ml/oracle_path_anti_sl_pipeline_20261118.md`.
