# Batchs et marchés — guide opérateur

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

État du 10 octobre 2026, rapproché de `ihm/pages/batches.py`,
`ihm/services/batch_management.py`, des YAML et des launchers.

## 1. Où aller et quoi sélectionner

Ouvrir **Workflow & Orchestration → Batch**, puis choisir États-Unis, Chine ou
France dans « Périmètre des batchs ». Même présentation, catalogues et historiques
séparés. Le choix ne change pas les droits d'exécution d'un marché ni ses données.
Pipeline, Diagnostic ML et Backtesting ont aussi des parcours multi-marchés ;
toutes les autres pages ne basculent pas automatiquement sur un broker FR/CN.

| Vue | Configuration du catalogue | Base métier |
| --- | --- | --- |
| US | batch.yaml, sections US | alpha_trade |
| CN | batch_cn.yaml + quatre sections CN legacy de batch.yaml | alpha_trade_cn |
| FR | batch_fr.yaml | alpha_trade_fr |

Les trois bases peuvent partager les credentials, pas les lignes. Le router
contrôle les alias et le marché. Ne pas réparer une connexion FR en la pointant
sur alpha_trade. [Configuration](../18_reference_configuration.md).

## 2. Comprendre les cartes et compteurs

Chaque carte présente finalité, priorité P0–P4, source/tables, univers,
horaires/fuseau, couverture J−N/J ou second passage, statut, raisons de blocage,
commandes, dernière exécution et logs. Le compteur « actif » signifie enabled
dans la configuration ; il ne signifie ni installé, ni sain, ni GO ML.

- Rouge/gras : dernier échec opérationnel, à diagnostiquer dans son résumé/log.
- Noir avec ⛔ ⚖️ : droits/prudence ; ne pas chercher un contournement technique.
- Désactivé/remplacé : famille volontairement non lancée ou intégrée ailleurs.
- Fournisseur/qualification manquant : lire « Comment le débloquer » ; avoir un
  secret ou un connecteur ne suffit pas à lever le besoin complet.

La date Windows et le dernier run métier sont deux informations différentes.
Une ancienne valeur Windows sentinelle (année <2000) ne représente pas une
collecte. CN/FR lisent leurs rapports propres, pas pit_collection_runs US.

## 3. Installer, lancer et désinstaller

Relire d'abord la commande, le marché, le compte Windows et le statut.
Installer/réinstaller une tâche ne déclenche pas automatiquement une collecte.
« Lancer maintenant » contourne le planning, jamais enabled=false, les droits
ou les gates de marché/données. Les traitements restent asynchrones.

Actions globales :

1. Installer/réinstaller tous : uniquement les activés compatibles du marché
   sélectionné ; les tâches en cours sont ignorées.
2. Désinstaller tous : ses tâches installées, hors tâches en cours, y compris
   celles devenues dormantes ; les autres marchés ne sont pas touchés.

Désinstaller supprime la tâche Windows, pas YAML, tables, fichiers ou logs.
Les filtres de recherche/affichage n'en font pas une action sur « seulement les
cartes affichées ». Le mode Interactive nécessite une session Windows ouverte.
Les launchers cachés utilisent un wrapper Windows ; un trigger horaire vérifie
le calendrier configuré avant de réellement appeler le fournisseur.

## 4. Reprise et notifications

J−N/J : le job relit une fenêtre, déduplique/upsert selon son contrat et conserve
la provenance/version. RAW et runs peuvent croître sans doublon métier.
Un snapshot du jour ne peut pas être refabriqué comme s'il avait été observé
hier. Pour les secours US déclarés, succès récent COMPLETED ou
COMPLETED_WITH_WARNINGS → SKIP ; sinon rattrapage. Aucun second passage n'est
actuellement déclaré pour les batchs FR/CN actifs.

Les launchers envoient email/Telegram avec demandés, reçus, persistés, échecs,
alertes et erreur ; principal/secours est précisé lorsque ce contrat existe.
Un problème de transport peut empêcher la notification : les logs et le run
restent à vérifier. Un script de recherche hors launcher ne bénéficie pas
automatiquement de ce dispositif. Les compteurs us_pipeline mesurent des
étapes, pas des titres.

## 5. Ce que les trois marchés font actuellement

US : us_pipeline planifié à 22:45 Paris, listes semaine/vendredi dans config.yaml,
PAPER/default, import ciblé J et watcher avant 12. Le filtre GPT IHM n'est pas
activé implicitement par le scheduler. Quotes/earnings autonomes désactivés
car intégrés aux étapes 4/5. Business Quant daily_bars_sync reste versionné,
pas un remplacement de l'import canonique EODHD.

CN : backup et recherche D10/17-C visibles, mais D9 BaoStock et D6 SSE/SZSE sont
bloqués ; leurs dépendants activés ne prouvent pas une chaîne saine. Pas d'ordres
broker autorisés. Ne pas créer un second propriétaire canonique pour les contourner.

FR : collectes de recherche actives et sauvegardes propres ; EODHD quotidien
alimente fichiers et staging SQL, pas automatiquement les barres canoniques.
Les autres familles sont principalement archivées en fichiers. INPI/consensus
Yahoo sont bloqués ; borrow/options complets manquent encore. MiFIR partiel reste
en quarantaine. Shadow local et Trading212 DEMO ne sont pas un canary autonome.

Horaires de collecte hors absence 07:30–20:00 Paris, avec conversion NY/Shanghai
et marges de durée : [FR/CN](../operations/horaires_fr_cn_presence_pc.md),
[US](../operations/forward_pit_batches.md). Le PC doit rester allumé pendant
le run ; ces horaires ne maintiennent pas le watcher lorsque le PC est éteint.

## 6. Pour prendre la main

Lire [l'état actuel](../ETAT_ACTUEL_IMPLEMENTATION.md) et le
[catalogue complet actif/bloqué](../operations/catalogue_batchs_actuel.md), puis
le [contrat us_pipeline](../operations/us_pipeline.md),
l'[index FR](../fr/README.md) ou l'[index CN](../cn/README.md).
Les anciennes valeurs dans les comptes rendus de sprints sont des constats
datés ; elles ne prévalent pas sur ces contrats et la configuration effective.
