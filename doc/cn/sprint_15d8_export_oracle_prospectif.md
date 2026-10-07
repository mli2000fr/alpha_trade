# Sprint 15-D8 — export Oracle CN H20 prospectif, recherche uniquement

## Statut et objectif

Le code d'export avant ouverture est livré, sans promotion au serving et sans ordre de bourse. Le rattrapage initial du [Sprint 15-D7a](./sprint_15d7a_rattrapage_canonique_2026.md) s'arrêtait au 29 septembre ; la collecte D8 a ensuite couvert la séance du 30 septembre. Le premier score réel a été publié le 30 septembre pour la décision ouverte du **8 octobre 2026**, avant son cutoff. Les rattrapages antérieurs ne sont pas transformés en scores produits à l'époque.

Le modèle H20 LightGBM du fold OOS `2025H2` est figé dans [sprint15d8_oracle_prospective.yaml](../../config/research_cn/sprint15d8_oracle_prospective.yaml) avec les SHA-256 de son fichier et de son rapport. Son entraînement/arrêt anticipé n'a utilisé aucun label postérieur au 30 juin 2025 ; son choix tient compte de l'évaluation OOS 2025H2, jamais des issues 2026. C'est un **modèle de recherche ancien**, pas une validation de qualité en 2026 ou un modèle de production. Les 33 features et le TOP20 (20 %) sont ceux du protocole gelé Sprint 10-B.

## Séquence opérationnelle pour chaque décision K

1. Identifier K à partir du calendrier CN 2026 vérifié. Le programme refuse les jours fermés et toute année sans calendrier validé.
2. Après la clôture de la séance précédente J, collecter le master, calendrier, indices, actions et facteurs J via le chemin incrémental CN. Le moteur historique 2018–2025 n'est pas réexécuté et les lignes existantes ne sont pas écrasées.
3. Avant **09:15 Asia/Shanghai en K**, exécuter `--check`. Le contrôle exige J fermé, la barre CSI 300 et des barres actions connues à cet instant ; il ne crée aucun score ni fichier.
4. Si `READY_TO_SCORE`, exécuter l'exporteur. Il reconstitue l'univers tradable pré-ouverture avec la politique CN Sprint 8, calcule `cn_price_v1` sur au moins 252 séances déjà terminées, refuse les entrées tardives, score la coupe transversale éligible et prend les 20 % les mieux classés. Le rendement antérieur cinq séances est connu avant le cutoff. L'export est atomique, un seul dossier par décision ; aucun écrasement silencieux. Le programme contrôle également l'heure **de publication effective** et met en quarantaine un export qui franchirait 09:15 pendant sa finalisation.
5. Contrôler le rapport, le hash et l'heure réelle de fin du score. Le fichier peut alors être présenté au validateur [Sprint 15-D7](./sprint_15d7_protocole_appariement_dragon_tiger.md), qui vérifie aussi les snapshots Dragon/Tiger et leur heure. Sans snapshot complet avant 09:15, aucun appariement n'est déclaré valide.

Les barres et facteurs rattrapés en septembre ont un `available_at` correspondant à leur observation réelle tardive. Une action d'entreprise observée tardivement mais **connue avant une nouvelle décision** est masquée dans le calcul prospectif en mémoire ; son horodatage d'origine en base n'est pas changé. Le rapport compte ces masques. Les features historiques Sprint 9 et leurs empreintes restent inchangées.

## Commandes à partir de `F:\projets`

Exemple pour la première décision ouverte après les congés d'octobre selon le calendrier local, **2026-10-08**. La dernière séance attendue est le **2026-09-30**. Le rattrapage d'une séance complète peut être long (209 lots pour le manifeste du 30 septembre). Par défaut, le collecteur refuse le jour courant. L'exception explicite `--allow-same-day-after-close` ne l'autorise qu'à partir de **18:00 Asia/Shanghai** ; elle ne permet jamais une date future. Sans cette exception, attendre le 1er octobre en heure de Shanghai.

```powershell
.\.venv\Scripts\python.exe -u -m dataIntegrityEngine.cn_sprint7c_incremental prepare --start-date 2026-09-30 --end-date 2026-09-30 --seed-manifest config/univers_cn/canonical_incremental_2026.txt --manifest config/univers_cn/canonical_incremental_2026-09-30.txt --chunks-root config/univers_cn/sprint7c_chunks_2026-09-30 --output-root artifacts/cn/sprint7c_daily/2026-09-30 --allow-same-day-after-close
.\.venv\Scripts\python.exe -u -m dataIntegrityEngine.cn_sprint7c_incremental run-all --start-date 2026-09-30 --end-date 2026-09-30 --chunks-root config/univers_cn/sprint7c_chunks_2026-09-30 --output-root artifacts/cn/sprint7c_daily/2026-09-30 --allow-same-day-after-close
.\.venv\Scripts\python.exe -m modelFactory.cn_oracle_prospective_15d8 --decision-date 2026-10-08 --check
.\.venv\Scripts\python.exe -u -m modelFactory.cn_oracle_prospective_15d8 --decision-date 2026-10-08
```

Ne lancer la dernière commande que si le préflight dit `READY_TO_SCORE` **et** avant 09:15 Shanghai le 8 octobre. Une exécution après ce cutoff échoue avant lecture de la base ou écriture d'export. La commande refuse également d'écraser un export déjà présent ; l'exemple ci-dessus décrit la reproduction du protocole, pas une invitation à relancer la décision désormais publiée. La collecte et le score ne sont **pas planifiés automatiquement** par D8.

Résultat attendu : `artifacts/research/cn_oracle_prospective_15d8/2026-10-08/oracle_top20.parquet` et `report.json`. Aucun label futur, décile réalisé, rendement futur, résultat de backtest ou colonne cible n'est inclus. La ligne porte `model_trained_through`, `score_available_at_utc`, `prior_return_available_at_utc` et `oracle_oos=true`, contrôlés par D7. Le fichier n'est pas une décision de trading : les droits sur Dragon/Tiger, la stabilité Oracle sur 2026 et le gate économique CN restent ouverts.

## Vérifications effectuées et résultat réel

- Le SHA-256 du modèle et du rapport figés passe ; l'ordre des 33 features du fichier LightGBM correspond exactement au protocole.
- Le test synthétique de bout en bout produit un fichier accepté par le validateur D7. Tests de refus : jour fermé, score trop tardif, empreinte modifiée, couverture insuffisante, doublon de publication.
- Le préflight initial pour K = 2026-10-08 retournait `BLOCKED` : les barres et la séance du 30 septembre ainsi que CSI 300 manquaient en base. Ce n'était pas une panne du modèle : le rattrapage initial s'arrêtait au 29 septembre.
- Le 30 septembre après 18:00 Shanghai, BaoStock a répondu pour deux actions de contrôle et CSI 300. La préparation incrémentale a produit un manifeste de **5 224 actions** et **209 lots**. Les **209/209 lots sont terminés**, sans avertissement ni échec, dans `artifacts/cn/sprint7c_daily/2026-09-30/state.json` ; le dernier journal est `log/batch/cn-sprint7c-20260930-d8-retry3/`.
- Incident de collecte : après 56 lots validés, Windows a refusé transitoirement le remplacement atomique de `state.json` (`WinError 5`). L'écriture de l'état retente désormais cette opération avec attente progressive et un fichier temporaire unique. Les 56 lots restent enregistrés ; une reprise avec le même `output-root` les ignore et commence au lot 57. Le journal de cette reprise est `log/batch/cn-sprint7c-20260930-d8-retry1/`.
- Second incident après 96 lots : BaoStock a refusé une connexion sur `adj_factor`; son SDK a tenté d'imprimer un message chinois dans une sortie Windows `cp1252`, enveloppant l'erreur réseau dans `BaoStockError`/`UnicodeEncodeError`. Le collecteur reconnaît maintenant cette chaîne d'exceptions pour la relance réseau ; la reprise est démarrée avec `PYTHONIOENCODING=utf-8`. Le lot 97 a été vérifié `COMPLETED` avant de lancer la suite. Journal courant : `log/batch/cn-sprint7c-20260930-d8-retry3/`.
- Le préflight réel a répondu `READY_TO_SCORE` : **5 228 barres connues** et CSI 300 présent. L'export [Oracle TOP20 du 8 octobre](../../artifacts/research/cn_oracle_prospective_15d8/2026-10-08/oracle_top20.parquet) est publié à `2026-09-30T16:27:50.095021+00:00`, bien avant le cutoff `2026-10-08T01:15:00+00:00`. Son [rapport](../../artifacts/research/cn_oracle_prospective_15d8/2026-10-08/report.json) compte **5 166 titres éligibles et 1 034 candidats** ; les 1 034 identités sont uniques, le SHA-256 du parquet correspond au rapport et aucune colonne d'issue future n'est exportée. Le modèle est figé jusqu'au `2025-06-30`. Il s'agit d'une prédiction prospective de recherche, **pas** d'une preuve de performance directionnelle ni d'une autorisation de trading.
- La [prévalidation D7](../../artifacts/research/cn_dragon_tiger_15d7/oracle-export-readiness-20260930-d8-preview.json) contrôle dès maintenant les **1 034 lignes**, les timestamps et le snapshot officiel connu ; elle retourne `WAITING_FOR_DECISION_CUTOFF` sans erreur de contrat. Le moteur d'appariement, lui, conserve sa règle stricte : il ne considère pas la décision avant 09:15 Shanghai le 8 octobre. Le passage D6 avant ouverture peut encore réviser le snapshot ; il devra être vérifié après le cutoff avant tout appariement.

Le dossier par date et le rapport sont la trace de recherche. Le job reste manuel jusqu'à mesure de son temps réel d'exécution et qualification de la fraîcheur après clôture ; l'activation d'une tâche planifiée fera l'objet d'un gate séparé.
