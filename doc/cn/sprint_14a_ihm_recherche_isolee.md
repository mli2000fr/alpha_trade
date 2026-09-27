# Sprint 14-A — Sélection de marché et vue CN_A de recherche isolée

## Résultat

Les pages **Pipeline**, **Diagnostic ML** et **Backtesting** affichent
désormais un sélecteur de marché en tête de page. Le défaut reste
`US_EQ` : tous les formulaires et commandes US existants demeurent
inchangés. Chaque page garde son propre état de sélection, pour éviter
qu'un changement dans une page modifie silencieusement une autre.

Sous `CN_A`, ces trois pages montrent uniquement une vue de recherche
en lecture seule alimentée par le [rapport Sprint
13-C](../../artifacts/cn/economic/sprint13c/decision/decision-d1745c4c96351267/report.json)
et par `config/univers_cn/canonical_full_2018_2025.txt`. Le rendu
retourne **avant** l'accès à la configuration DB US, aux tables US,
aux sélecteurs de batches US et à tout bouton de lancement. Les
commandes d'entraînement, de prédiction, de backtest opérateur et de
trading live CN ne sont pas disponibles dans 14-A.

La vue rappelle le contexte : marché `CN_A`, base `cn_primary`,
devise `CNY`, calendrier `CN_A`, univers historique de recherche
**non négociable PIT**, cohorte commune 34/40 au coût standard et
33/40 sous stress. Elle affiche le rendement moyen, le drawdown et
l'exposition des quatre politiques sur les mêmes cohortes valides.
Le statut économique reste **NO GO** sur les périodes déjà inspectées ;
la vue ne présente pas ces résultats comme un modèle servable.

## Contrat de sûreté

Le [composant transversal](../../ihm/services/cn_research_market.py)
refuse le rapport s'il n'est pas `COMPLETE_DESCRIPTIVE`, s'il
déclare `serving_enabled`, `live_enabled` ou `economic_go_allowed`,
ou si les quatre politiques attendues ne sont pas présentes. Il
refuse aussi un fichier d'univers vide, dupliqué ou contenant des
codes non CN. Une indisponibilité produit un message explicite, jamais
un fallback vers les données US. Le chemin du rapport 13-C est
volontairement figé à cette première preuve ; un registre CN
versionné sera nécessaire avant de choisir plusieurs campagnes
depuis l'IHM.

| Page | Sélection US_EQ | Sélection CN_A |
| --- | --- | --- |
| Pipeline | Comportement existant | Résultats CN en lecture seule ; aucun entraînement ni predict US réutilisé |
| Diagnostic ML | Tables et batchs US existants | Artefact CN 13-C ; aucune jointure avec `alpha_trade.model_training_batch` |
| Backtesting | Formulaire et historique US existants | Replay CN historique consultable ; aucun appel au lanceur de backtest US |

Les [tests 14-A](../../tests/test_sprint14a_cn_research_ui.py)
vérifient le défaut US, l'isolation des clés de page, la validation
des artefacts et le retour anticipé de chaque page avant les chemins
US. Les tests existants Pipeline/Backtesting restent passants.

## Limites et prochain incrément

14-A est une **porte d'entrée de recherche**, non le Sprint 14 complet.
Il ne propose pas encore de sélecteur de batch CN, d'univers tradable
à la date J, de commandes `--market-code CN_A` ou de replays CN
lancés depuis l'IHM. Leur ajout nécessite un contrat de lancement
spécifique CN, le routage explicite vers `alpha_trade_cn` et des
tests d'incompatibilité batch/univers/marché. Réactiver les anciens
formulaires US sous l'étiquette CN serait incorrect.

Le [Sprint 14-B](./sprint_14b_diagnostic_campagnes_cn.md) a ajouté le
registre et les diagnostics des campagnes CN en lecture seule. Le
[Sprint 14-C](./sprint_14c_replay_recherche_ihm.md) a ensuite ouvert un
replay CN de recherche limité à une cellule du protocole 13-B, sans live
tant que le gate économique reste fermé.
