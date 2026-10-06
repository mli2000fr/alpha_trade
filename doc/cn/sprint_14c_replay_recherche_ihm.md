# Sprint 14-C — Lancement d'un replay CN_A de recherche depuis Backtesting

## Capacité livrée

Dans **Backtesting → Marché : CN_A**, le panneau Sprint 14-C permet de
lancer en arrière-plan **une cellule du protocole économique 13-B** :
un semestre OOS, une politique, une seed de départage, un scénario de fill
et un profil de coûts. Le moteur utilisé est
[`modelFactory.cn_economic_replay_13b`](../../modelFactory/cn_economic_replay_13b.py),
appelé par un worker IHM de suivi qui n'en modifie pas le calcul,
pas `python -m backtesting run` du marché US. Le sélecteur US et ses
formulaires ne changent pas. Aucun replay n'est lancé par défaut ou au
simple affichage de la page.

Cette capacité sert à reproduire et inspecter la recherche existante.
Les périodes 2022H1–2025H2 sont **déjà inspectées**, donc ne sont pas un
nouveau holdout indépendant. Le [verdict 13-C](./sprint_13c_decision_economique.md)
est **NO GO économique** ; ni une exécution réussie ni un rendement positif
isolé ne l'annulent. Aucun ordre live, prédiction servable ou politique
de production CN n'est activé. `config/markets/market_cn.yaml` conserve
son gate général `enabled: false` ; seul ce replay de recherche utilise
explicitement la route CN isolée.

## Paramètres réellement modifiables

Les listes proviennent du [protocole gelé 13-A](../../config/research_cn/sprint13a_economic_preflight.yaml),
validé par le code :

| Contrôle IHM | Valeurs |
| --- | --- |
| Semestre OOS | 2022H1 à 2025H2, par semestres entiers |
| Politique | `oracle_all`, `reversal_veto_bottom20`, `lightgbm_veto_bottom20`, `lightgbm_long_top20`, `momentum_top20_same_universe` |
| Seed | 0, 1, 2, 3 ou 4 |
| Fill | `base` ou `conservative` |
| Coûts | `cn_a_research` ou `cn_a_research_stress` |

Le marché `CN_A`, l'alias `cn_primary`, la base `alpha_trade_cn`, la devise
CNY, la source Ranking OOS LightGBM H20, le pool et l'univers correspondant,
le capital initial 100 000 CNY, le ticket 10 000 CNY, huit positions LONG
au maximum, les règles lot/T+1, l'entrée J+1 et la sortie après 20 séances
complètes ne sont **pas modifiables dans ce panneau**. Une plage de dates
arbitraire ou un fichier d'univers US ne peut donc pas être injecté.
Les deux profils de coûts et les fills sont des hypothèses de recherche,
pas des transactions observées.

L'aperçu de commande affiche `--market-code CN_A` et
`--database-alias cn_primary`. Le chemin `preview` est illustratif : au
clic, un ID de run unique est créé et le véritable répertoire de sortie
se situe sous `artifacts/ihm_backtesting_runs/cn-research-replay/<run_id>/artifacts`.
La cellule produit un `sprint13b-<empreinte>/report.json` et son journal.
L'historique CN n'affiche que les runs de type `cn-research-replay`, jamais
les runs US. Il permet de suivre l'état, les logs et d'arrêter un run.
Le panneau se rafraîchit toutes les 5 secondes et le worker émet un message
au démarrage puis un signal de vie environ toutes les 30 secondes. La barre
de progression indique uniquement les jalons réellement observés
(démarrage, replay, cellule écrite, rapport écrit, fin) : elle ne prédit pas
la durée restante. Les anciens runs conservent leurs journaux originaux ;
leur statut terminé est affiché sans nécessiter de nouveau replay.

## Préflight bloquant avant tout processus

Le [contrat de lancement](../../ihm/services/cn_replay_launch.py) vérifie
au clic, avant toute écriture de run ou création de sous-processus :

1. les cinq choix appartiennent strictement au protocole pré-enregistré ;
2. le marché est `CN_A`, l'alias `cn_primary` et la route cible est
   exactement `alpha_trade_cn`, même si une variable d'environnement tente
   de rediriger le schéma ;
3. le rapport 13-C déclare toujours NO GO production et interdit serving/live ;
4. les prédictions Ranking OOS H20 LightGBM du semestre sont présentes et
   vérifiées par empreintes ;
5. les preuves A2 d'actions d'entreprise sont complètes et hashées ;
6. une vraie connexion à la base CN répond `SELECT DATABASE()` avec
   `alpha_trade_cn`.

Le CLI CN vérifie aussi les indicateurs explicites `--market-code` et
`--database-alias` et répète les contrôles métier durant le replay. Le
gestionnaire de jobs existant fournit historique, logs et arrêt, mais la
commande construite est uniquement celle du module CN. La sortie est
restreinte au répertoire de runs CN de l'IHM. Les anciens chemins de
backtest US n'acceptent pas ces options.

## Lire le résultat

Le panneau indique le statut du processus et, si un rapport existe,
son statut métier, la validité économique, le rendement et le drawdown
**proxy**, le capital final CNY, les commissions, autres coûts et nombres
d'achats/ventes **hypothétiques**. Si `economic_result_valid=false`, le
rendement n'est pas affiché comme interprétable. Un processus `completed`
signifie seulement que le programme s'est terminé sans erreur technique.
Une cellule isolée n'est pas la campagne complète multi-semestres et le
rapport peut donc porter `COMPLETE_RESEARCH_BLOCKED_OR_PARTIAL` même si
la cellule calculée est valide. Les [règles de censure du 13-B](./sprint_13b_validation_economique.md)
et le verdict 13-C restent la référence.

## Vérification et suite

Les [tests Sprint 14-C](../../tests/test_sprint14c_cn_replay_ui.py) couvrent
la commande dédiée, l'absence de lancement avant clic, le rejet du marché
US, de la mauvaise base, d'un semestre/politique/seed hors protocole et
d'une sortie hors espace CN. Un préflight réel en lecture seule sur 2024H1
a confirmé sources OOS, preuves A2 et route `alpha_trade_cn` ; **aucun
replay lourd n'a été démarré pendant la mise en place**.

Le Sprint 14 n'est pas un GO de déploiement CN. Les prochaines recherches
directionnelles devront disposer de nouvelles périodes et données PIT ;
les résultats 2022–2025 déjà inspectés ne doivent pas servir à optimiser
une politique puis à annoncer une validation indépendante.
