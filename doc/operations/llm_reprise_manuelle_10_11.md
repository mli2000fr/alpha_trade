# Reprise entre les boutons indépendants 10, 11 et 12

Mise à jour du 17 octobre 2026 — marché US, filtre GPT/DeepSeek PAPER.

Correctif du 18 octobre : le risque courant peut utiliser un signal J avec un
snapshot PAPER réellement capturé après J, sous contrôles de fraîcheur et avant
l'ouverture suivante. Le cas sans candidats est également corrigé. Voir le
[contrat snapshot et la reprise contrôlée](correctif_risque_llm_snapshot_20261018.md).
Un verrou déjà pris n'est pas remis à zéro automatiquement après erreur.

## Utilisation

1. Dans Pipeline, laisser le champ global **Identifiant analyse LLM** vide.
2. Lancer **10. ML Predict**, puis attendre la fin de tout le traitement Oracle
   et LLM, pas seulement celle des prédictions Oracle.
3. Le bloc **11. Risk Management** affiche automatiquement l’identifiant de cette
   analyse et la date de fin de 10, en heure de Paris. L’aperçu de commande et le
   bouton de lancement utilisent cet identifiant, sans saisie/copie manuelle.
4. Après un 11 réussi, **12. Execution** reprend à son tour l’identifiant LLM
   exact de la commande risque terminée. Il ne confond pas l’identifiant du run
   risque avec celui de l’analyse LLM.

Exemple vérifié sur l’historique local : le lancement IHM
`20261017_202916_df90306c`, terminé le **17 octobre 2026 à 20:36:13 CEST**,
transmet `llm-fa604bed142d41a7be61012432c1fc6e` pour la séance du **16 octobre**.
Cette vérification n’a lancé aucun risque ni ordre.

Un identifiant global renseigné explicitement reste un choix manuel prioritaire.
Pour revenir au préremplissage automatique, vider ce champ. Le champ **Identifiant
analyse à consulter** dans l’Audit reste une consultation, pas un choix de lancement.

## Sécurité et périmètre

- La reprise est déduite du **dernier lancement amont pour le compte**, dans
  l’historique IHM. Elle ne cherche pas une sélection SQL « latest » et ne lance
  aucune nouvelle analyse GPT/DeepSeek.
- Si ce lancement est encore actif, échoué, arrêté, sans filtre LLM ou sans
  résumé LLM complet, aucune ancienne réussite n’est sélectionnée à sa place.
- La séance doit correspondre après résolution du calendrier US. Pour 10 → 11,
  le modèle Oracle et l’univers doivent aussi correspondre. Sinon, un message
  explique le blocage et le bouton est désactivé.
- La reprise ne change pas les paramètres globaux ni les options du workflow.
  Un nouveau workflow incluant 10 garde sa création d’un nouvel identifiant
  partagé ; les lancements manuels n’enregistrent pas un ancien identifiant
  comme défaut permanent pour les futurs 10.
- Le serveur contrôle toujours l’analyse archivée, sa fraîcheur, sa date, le
  compte, ses protections et son éventuelle consommation antérieure. Un
  préremplissage affiché n’est pas une approbation risque ou une autorisation
  d’ordre. Aucun verrou ni garde n’est neutralisé.

## Compatibilité avec les runs déjà terminés

Un reset de couleur ANSI émis par le processus Oracle pouvait précéder le résumé
LLM et empêcher son extraction. Le lecteur des événements structurés ignore
maintenant ces séquences de terminal. Pour les anciens runs concernés, la reprise
peut relire le dernier résumé LLM dans les **64 Kio de fin du stdout de ce même
lancement**, uniquement sous le répertoire des runs IHM. Cela ne modifie ni le log,
ni l’archive SQL, ni les réponses du fournisseur.

Implémentation : `ihm/services/llm_manual_handoff.py`,
`ihm/services/process_registry.py`, `ihm/pages/pipeline.py` et aide du champ dans
`ihm/pages/_execution_center/__init__.py`.

Tests : `tests/test_llm_manual_handoff.py` — passage d’identifiant exact à la
commande, message et date Paris, rafraîchissement après un nouveau 10, refus des
échecs/conflits, choix manuel, abstention complète, reprise 11 → 12, ancien log
coloré et portée de lecture. Transport externe et lancement métier non nécessaires.
