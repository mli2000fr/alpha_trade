# TOP10 Oracle parcours — audit de tri selon la tendance pendant vingt séances

## Décision et non-doublon

GO du 22 octobre 2026 : audit borné, **sans entraînement, backtest économique,
SQL, fournisseur, LLM ou changement de production**. Aucun suivi automatique.

Le ranker LightGBM du 11 octobre ciblait le rendement absolu terminal ; le
deux-parties ciblait |R terminal|>=20 %. Ils ne répondent pas à cette question.
Mais E3/E14, le modèle TP-avant-SL, le filtre TP15/SL7 et la séparabilité du
14 octobre ont déjà étudié des chemins et échoué aux gates. Il ne s'agit donc
pas d'une nouvelle famille de données ni d'une garantie de direction retrouvée.

Différence bornée : **ordre transversal de la progression pendant le chemin**,
dans les dix premiers de l'Oracle parcours CatBoost, sans cible TP/SL binaire.
Pas de relance automatique d'un ancien modèle sous un nouveau nom.

## Population et données figées avant les nouveaux labels

- TOP10 = dix titres par décision, avant tout examen des prix futurs. Aucun
  remplacement TOP11, aucune intersection ATR, aucune sélection GPT/consensus.
- Historique causal CatBoost OOF 2018-07-05…2023-07-07 : TOP20 observable gelé
  par la préparation du 15 octobre, puis sous-ensemble oracle_rank<=10.
- Récent : modèles annuels CatBoost `437ed1` (2024), `102eca` (2025), `bc35a7`
  (2026), avec leurs rangs et dates de disponibilité déjà archivés. Pas de fit.
- Prix locaux historiques et récents déjà qualifiés et liés par SHA256 ;
  **anciens caches EODHD split**, pas une nouvelle validation SIP. Aucune
  substitution de fournisseur ni réécriture des ajustements.
- Base des features : adj_close/close du générateur archivé ; base des cibles :
  OHLC split sans ajustement dividende supplémentaire. Réserve de vintage.
- Univers amont survivant de 1 790 titres, pas univers historique PIT certifié.
- Toutes les périodes récentes ont déjà été regardées : pas de holdout vierge.

## Cible sans poids ni seuil optimisés

Entrée de référence open J+1, vingt clôtures J+1…J+20. Pour chaque clôture,
`r_k=100*(close_k/open_J1-1)`. **Cible primaire LONG : moyenne des vingt r_k**,
soit l'aire moyenne signée du chemin. SHORT miroir = son opposé, pas un second
test indépendant. Ce n'est ni le seul rendement H20 ni le maximum futur.

Une moyenne positive peut masquer des revers : on conserve obligatoirement,
sans les combiner avec un poids choisi après résultats :

1. proportion de clôtures au-dessus de l'entrée (persistance LONG) ;
2. excursion contraire sur les clôtures avant le premier maximum de clôture,
   entrée de référence incluse ;
3. maximum favorable de clôture et délai du premier maximum ;
4. excursions intraday et bornes du recul précédant le jour du sommet : ordre
   HIGH/LOW de ce jour inconnu avec des daily, jamais inventé.

SHORT : mêmes mesures inversées. Un classement LONG réussi ne constitue pas
automatiquement un modèle SHORT réussi. Pas d'exécution au sommet futur.
L'aire est une **cible descriptive**, pas un rendement de portefeuille.

Chemin complet obligatoire J…J+20 : OHLCV positifs/cohérents, barres réelles,
source/ajustement/identité stables et renseignés, aucune rupture d'identité
connue ni saut inexpliqué >=20x. Aucun stop/TP, frais ou filtre de gap : il s'agit
du chemin, pas d'un ordre admissible. Disponibilité conservatrice J+21 ; borne
de maturité 2026-10-09 du cache, pas la date courante utilisée pour fabriquer
des prix manquants. Motifs conservés sur les candidats initiaux.

## Audit des informations connues à J

Réutiliser les **23 variables prix/benchmark** de la préparation précédente,
plus rang et score Oracle comme témoins d'amplitude. Historique : lire seulement
ces colonnes et J_qualified du dataset audité, jamais son label TP15/SL7.
Récent : recalcul backward-only, contrôle préfixe sur premier/milieu/dernier
signal par titre. Identité et 121 barres réelles à J ; benchmark 201 séances.
Les cinq variables marché constantes entre titres d'une date ne peuvent trier
les dix titres : diagnostics seulement. Pas de métadonnées secteur actuelles,
macro sans vintage, consensus récent extrapolé dans le passé, texte ou symbole
appris. **Ce n'est pas un audit exhaustif des 173 features amont.**

Famille de tests primaire : seize variables titre et deux forces relatives.
Rang/score Oracle = témoins, pas nouveaux signaux promus. Signe de chaque score
figé sur découverte 2018–2021 exclusivement, selon IC Spearman quotidien moyen.
Purge des labels au 1er janvier 2022 et au 1er janvier 2023 pour la validation
2022 ; contrôle 2023 partiel, puis diagnostics 2024/2025/2026 séparés.

Correction maxT à 999 changements de signes conjoints de blocs fixes de
63 séances, au moins 20 dates par bloc, huit blocs, seed 20261022. Diagnostic
approximatif de dépendance, pas preuve d'alpha ni p-value d'un monde sans tous
nos essais précédents. Pas de choix de feature/sens sur les années récentes.

## Comparaisons et règle d'arrêt

Seulement les dates ayant **les dix candidats complets**, toutes les features
primaires finies et chemins qualifiés. Les exclusions sont quantifiées. Les
sélections de trois/cinq titres sont décidées par score J, puis évaluées ;
égalité départagée symbole croissant. Même calendrier pour tous les témoins.
Comparer à Oracle original et à l'espérance d'un choix uniforme dans les dix.
Une borne de choix sur la cible future est permise **comme plafond clairvoyant
uniquement**, jamais une politique ni une performance réalisable.

Gate d'une sonde avant contrôle : IC quotidien découverte>=0,05 et validation
>=0,03, p maxT<=0,05, >=100 dates découverte/30 validation ; gain d'aire contre
Oracle positif pour TOP3 **et** TOP5 en validation, persistance non dégradée et
excursion contraire moyenne non augmentée. Une sonde doit ensuite conserver
IC>0 et ces trois améliorations pour les deux tailles en 2023, 2024, 2025, 2026,
avec >=30 dates par partition. Pas de seuil assoupli sur échec.

Intervalles descriptifs des deltas appariés par bootstrap de blocs de 63 dates,
999 réplications, seed fixe ; sensibilité sans chevauchement : décisions tous
les 21 jours de bourse sur une grille globale fixée avant qualité, sans choisir
la phase. Effectifs et concentration titre/date explicités. Les fenêtres
répétées ne sont pas des trades indépendants.

Si aucune sonde ne passe : **arrêt de cet audit univarié, pas de ranker entraîné**.
Un éventuel multivarié nécessiterait un autre GO et un protocole distinct.
Les fichiers de préparation et résultats seront immuables, empreintes vérifiées
avant/après calcul, sources/tests liés dans le manifeste, audit technique séparé.
Même assistant ≠ seconde revue humaine indépendante.
