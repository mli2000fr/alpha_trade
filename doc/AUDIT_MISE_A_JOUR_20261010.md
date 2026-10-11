# Audit documentaire ciblé — 10 octobre 2026

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Archive conservée pour traçabilité : les commandes, paramètres et promotions ci-dessous décrivent leur époque, pas une consigne actuelle. Ne pas réactiver un batch sur la base de ce texte. [Référence actuelle](ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Objet et limites

Rapprocher les guides d'entrée/exploitation des sources actuelles, après les
évolutions multi-marchés, collectes et filtres US. Révision documentaire seulement :
aucun code métier, configuration, modèle, batch Windows, ordre ou ligne SQL modifié.
Pas d'appel fournisseur ni de contrôle de santé des bases/tâches dans cet audit.

Le dépôt contenait 660 Markdown avant cette mise à jour. Ce travail **n'est pas
une certification ligne par ligne des 660 documents**, ni une régénération de
tous les inventaires API. Les performances et preuves de recherche restent datées.

## Sources examinées et contrats réconciliés

| Domaine | Sources rapprochées | Corrections principales |
| --- | --- | --- |
| Marchés et bases | common/market_context.py, common/config_loader.py, database/router.py, config/databases.yaml, profils marché | trois bases, alias/capacités, credentials partagés sans données communes, serving CN/FR fermé |
| IHM et pipeline | ihm/services/navigation.py, pipeline_runner.py, batch_management.py, pages Pipeline/Batch | page Batch manquante des anciens index, choix de marché non global, 10 manuel sans dépendance visuelle obligatoire à 9 |
| Batch US | service/forward_pit/us_pipeline.py, launchers Windows, recovery_gate.py, YAML | 1–14, semaine/vendredi, date US figée, univers commun, attente cours J, watcher avant 12, 13/14 ledger PAPER |
| Collectes | runners Forward PIT et FR/CN, batch.yaml/batch_cn.yaml/batch_fr.yaml | actifs/bloqués/retirés, sources exactes, staging FR distinct du canonique, dépendances CN |
| GPT prospectif | service/llm_directional/{config,runner,validation,pipeline,risk_adapter,protections,repository}.py | N=20/K=3 configurés, SHORT/ETB, confidence non calibrée, run exact, SL7/trailing15/séance21, défauts Python différents |
| Données d'entrée | service/market/new_entry_data_guard.py | nouvelles entrées contrôlées indépendamment des futures listes partielles ; rejets par symbole vs panne globale |
| Étude Oracle × ATR | service/market/oracle_atr_study.py et contrat de table | résultats futurs réalisés, ordre score vs ordre amplitude, politique partial ≠ statut incomplet |
| FR broker/shadow | qualifications Trading212 et préparation 18, clôtures/TODO | lectures DEMO/bancs synthétiques distincts d'un canary autonome autorisé |
| Sauvegardes | catalogues et guide des scripts | keep US ML=5 actuel, US DB core=5/news=3, FR/CN isolés ; restauration marché à qualifier |

## Documents d'entrée à utiliser désormais

- [État actuel de l'implémentation](ETAT_ACTUEL_IMPLEMENTATION.md).
- [Catalogue des 48 batchs visibles](operations/catalogue_batchs_actuel.md).
- [Guide Batch et marchés](guide_utilisateur/19_batchs_et_marches.md).
- [Index général actualisé](README.md), [ML](ml/README.md), [CN](cn/README.md), [FR](fr/README.md).

Les guides fonctionnels, architecture, pipeline, configuration, données,
risque, régime, exécution, backtest, IHM, runbook et sauvegardes ont été corrigés
ou complétés. Les chapitres opérateur concernés et la matrice de navigation
pointent vers ces contrats. Les comptes rendus historiques ne sont pas remplacés
par des valeurs de déploiement contemporaines.

## Vérifications effectuées

Bilan : **37 documents existants actualisés et 5 documents créés** ;
**762 liens locaux contrôlés, aucun lien cassé**, couverture des **23 pages**
de navigation et des **48 entrées** du catalogue. `git diff --check` réussi.
Les chemins modifiés sont exclusivement sous doc.

Contrôle local en lecture seule des catalogues avec le même résolveur que l'IHM :
US 25 entrées/16 activées, CN 10/3, FR 13/9 ; aucun batch visible absent du
nouveau catalogue. Rapprochement des paramètres GPT/protections, listes des
étapes US et rétention ML avec les YAML réels. Vérification des liens locaux
dans les documents modifiés, y compris les chemins percent-encodés.

Les tests métier historiques cités dans les rapports n'ont pas été rejoués
pour cette modification de documentation. Aucun entraînement, appel API ou
backtest lancé. Une réussite de contrôle documentaire ne démontre pas la
couverture effective en base ni les droits commerciaux des fournisseurs.

## Entretien à poursuivre

Pour une évolution : identifier le consommateur réel de la clé, le builder de
commande et le runner, vérifier leurs tests, corriger le contrat opérateur et
son index, puis conserver le résultat expérimental distinct. Si une ancienne
page est ambiguë, dater une réserve et lier le contrat courant plutôt que
réécrire le protocole/les métriques d'origine.

Les inventaires API automatiques et les autres archives restent à relire à la
demande du domaine concerné ; ils ne sont pas certifiés complets par cet audit.
