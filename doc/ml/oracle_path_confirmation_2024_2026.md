# Confirmation Oracle parcours H20 — 2024–2026

## Périmètre autorisé

GO du 13 octobre 2026, après la comparaison chronologique 2016–2023.
Comparer **LightGBM**, **CatBoost** et la branche **champion de validation**
déjà choisie, sans entraînement, recalibration, optimisation ni promotion.
Objectif : concentrer les amplitudes parmi les **10, 20 et 50 premiers titres**,
avec résultats séparés par année. Aucun test directionnel ni PnL ici.

Source immuable :
`artifacts/research/oracle_path_comparison/20261013-v1/models/oracle-path-comparison/oracle_path`.
Résultats isolés : `artifacts/research/oracle_path_confirmation/20261013-v1`.
Univers : les **1 790 titres exacts du protocole d'entraînement**, issu du fichier
`config/univers/univers_filtred_tradable.txt`, sans relire un univers possiblement
modifié après entraînement. Profil exact : **173 features** archivées.

## Dates des modèles : réserve essentielle

Le dernier fold causal disponible est celui du **2023-01-05**. Il est conservé
pour toutes les dates de cette confirmation ; les anciens folds ne sont pas
choisis après observation des résultats.

- Dernière disponibilité des labels train : **2022-07-06**.
- Dernière disponibilité des labels validation : **2023-01-04**.
- Champion figé de ce fold : **CatBoost**, choisi sur l'AUC de validation.
- Les deux poids d'origine restent identiques pour 2024, 2025 et 2026.

La borne demandée de training était 2023-12-31, mais le trainer produit des
folds complets, pas un réentraînement final sur toute l'année. **Ces poids
n'ont donc pas appris toute l'année 2023.** Le test évalue aussi le vieillissement
des modèles. Toute stratégie de refresh annuel exigerait un protocole séparé.
La branche champion sera identique à CatBoost dans ce run ; ce n'est pas un
troisième algorithme ou une adaptation au contexte 2024–2026.

## Calendrier et maturité 2026

Fenêtre de décision : **2024-01-01 → 2026-10-09** ; observation **as-of 2026-10-09**,
dernière date de barres disponible lors du précontrôle. Seules les séances
NYSE existent dans la fenêtre. La séance actuelle non clôturée n'est pas utilisée.

Cible inchangée : TOP20 % de l'amplitude maximale absolue du parcours **J+1 à
J+20**, depuis le close ajusté J. Disponibilité conservatrice **J+21**, même si
le pic s'est produit plus tôt. Avec cet as-of, la dernière date de décision
théoriquement mature est **2026-09-10**. Les décisions ultérieures peuvent être
scorées mais leurs résultats sont marqués **IMMATURE**, jamais imputés.
La date réellement évaluée peut être plus ancienne à cause de barres ou
identités manquantes. La disponibilité calendaire ne certifie pas les prix.

## Construction et qualification

Barres cibles originales archivées, avec `data_source`, `data_adjustment`,
`instrument_id`, `is_filled`, volume et OHLC. Même validation de parcours que
le training : vingt séances exactes, pas de forward fill, prix cohérents,
identité/source/ajustement stables, ruptures connues et sauts inexpliqués exclus.
Le registre d'identités doit correspondre au protocole original.

Features avec warm-up et membership observable à J, indépendamment des
résultats futurs. Rangs transverses sur tout l'univers observable, pas tranche
par tranche. Ordre des 173 features contrôlé contre les deux modèles.
Scores archivés **pour toute la population observable avant exclusion des
résultats futurs**. Aucune ligne manquante dans le futur ne déclenche une
reconstruction favorable du classement prédit.

Le classement réel TOP20 % utilise les chemins qualifiables, selon le même
contrat que la comparaison : minimum vingt titres et 95 % de couverture
quotidienne. Ce n'est pas une connaissance exacte des rangs de titres dont le
chemin futur reste inconnu. Le seuil n'est ni abaissé ni optimisé sur 2026.

## Deux vues complémentaires, sans les confondre

### Métriques conditionnelles : même calcul que le rapport initial

`years.<année>.conditional` calcule AUC, précision/rappel TOP10 %/TOP20 %,
précision et amplitude moyenne des 10/20/50 titres sur les seules lignes dont
le label est qualifié. Cela permet la comparaison technique avec le rapport
2018–2023. **Réserve** : enlever des résultats manquants puis trier peut modifier
la sélection ; cette mesure est conditionnelle, pas une sélection live fidèle.

### Mesures principales : TOP-K original, puis vérification des résultats

`years.<année>.strict_original_top` choisit chaque TOP10/20/50 dans les scores
complets, **avant** de vérifier les résultats. Les trois branches sont comparées
sur les **mêmes dates**, uniquement si leurs sélections originales de cette taille
sont toutes qualifiées. Un résultat absent ne fait jamais remonter le titre suivant.

Pour chaque année/candidat/taille : dates complètes, dates matures, couverture,
précision, amplitude moyenne et nombre de résultats sélectionnés manquants.
Les métriques restent `null` s'il n'y a pas de date complète. La couverture est
indispensable : une comparaison restreinte aux dates complètes peut elle-même
être biaisée par la disponibilité des résultats ; elle ne représente pas les
dates exclues. Les séances entièrement sans scores sont comptées séparément.

Le fichier quotidien fournit également des bornes de précision pour les
sélections partiellement connues sur une journée dont les labels sont qualifiés,
en supposant tous les résultats absents faux ou tous vrais. Ce ne sont pas des
intervalles de confiance, ni des bornes pour les journées complètement non qualifiées.

Précision = appartenance au vrai TOP20 % d'amplitude **qualifiable** de la journée.
Ce n'est ni le taux de trades gagnants, ni LONG/SHORT, ni l'atteinte d'un TP
exécutable. Les maxima haut/bas sont a posteriori, sans coûts, sizing ou sorties.
Une amplitude moyenne de 35 % ne veut pas dire un portefeuille gagnant de 35 %.

## Isolation, checkpoints et suivi

Le script `scripts/research/oracle_path_confirmation.py` utilise uniquement des
lectures SQL sur `alpha_trade` ; chaque nouvelle connexion MySQL est configurée
en transaction read-only. **Aucun modèle actuel, table, compte, batch, ordre ou
journal SQL de training/prédiction n'est modifié.** Modèles originaux lus, jamais
écrasés. Une seule instance par dossier grâce à un verrou OS, libéré à l'arrêt.

Les 72 tranches de 25 titres archivent barres/features/membership/chemins avec
SHA-256. Reprise uniquement avec le même plan, mêmes dates, mêmes poids et
checkpoints valides. Changer source, date ou code nécessite un nouveau dossier.
L'écriture JSON est atomique, avec retries bornés pour les verrous Windows.

| Fichier | Usage |
| --- | --- |
| `plan.json` | Dates figées, modèles, hashes, univers, protocole métrique, pas de secrets |
| `run.json` | RUNNING/COMPLETED/FAILED et PID/erreur |
| `progress.json` | Dataset par tranche, puis scoring et métriques |
| `chunks/NNNN/` | Entrées archivées et empreintes du checkpoint |
| `scores.parquet` | Scores des deux candidats et du champion, tous titres observables |
| `labels.parquet` | Chemins, maturité et réserves, y compris résultats non qualifiés |
| `evaluated.parquet` | Jointure des scores et labels, sans perte silencieuse de résultat |
| `daily_coverage.parquet` | Couverture, maturité et dates comparables |
| `daily_original_top_metrics.parquet` | Métriques quotidiennes des sélections originales, manquants et bornes |
| `report.json` / `report.md` | Résultats par année, conditionnels et TOP-K stricts distingués |
| `stdout.log` / `stderr.log` | Sortie du lancement local, sans indicateur d'erreur fondé sur le seul canal stderr |

Commande reproductible (ne pas relancer si le processus est déjà actif) :

```powershell
python -u -m scripts.research.oracle_path_confirmation --output artifacts/research/oracle_path_confirmation/20261013-v1 --start 2024-01-01 --end 2026-10-09 --as-of 2026-10-09
```

## Interprétation et statut

Même réserve que le training : univers actuel statique, survivance possible,
prix ajustés actuels et disponibilité PIT des familles optionnelles non entièrement
certifiée. Les années 2024–2026 ont déjà été vues dans d'autres expériences :
confirmation temporelle après gel de cette comparaison, pas holdout vierge.
Séances/fenêtres H20 chevauchantes : observations non indépendantes ; les nombres
de lignes ne constituent pas autant d'essais indépendants.

Ne pas changer le champion, les features ou les seuils sur les pertes de cette
confirmation. Aucun avantage ni besoin de LSTM n'est présumé. Aucun backtest
économique ne sera lancé automatiquement après ce run.

Lancement vérifié le **13 octobre 2026 à 20:50 Paris**, processus de calcul
**1752** (launcher venv 21516). Le premier suivi avancé confirme RUNNING/dataset,
18 tranches terminées sur 72. Validation élargie : **280 tests ciblés passent**,
dont six tests spécifiques calendrier/maturité, sélections originales, verrou,
serving et reprise locale. Consulter `run.json` / `report.json` pour l'état réel ;
ce document ne constitue pas un résultat empirique terminé.
