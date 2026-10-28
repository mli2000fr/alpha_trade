# Sélection options partagée, risque et exécution par compte PAPER

Livraison du 28 octobre 2026. Concerne le filtre actif
`options_directional_filter`, volume CALL/PUT + open interest. Le filtre LLM
reste réservé à `default` : cette évolution ne l'étend pas aux autres comptes.

## Utilisation depuis la page Pipeline

1. Choisir `default`, mode PAPER, puis lancer les étapes 1 à 12 avec le filtre options actif.
2. Choisir `test1`, mode PAPER, conserver la même séance, le même modèle Oracle
   et la même source d'univers, puis lancer seulement 11 et 12.
3. Procéder de même pour `test2`. Il n'est pas nécessaire de refaire 1 à 10.

Un workflow personnalisé 11 → 12 retrouve et fige l'identifiant exact de
sélection au départ. Des lancements manuels séparés retrouvent la dernière
sélection qualifiée du même contexte. Si une nouvelle étape 10 intervient entre
11 et 12, le risque doit être recalculé pour cette nouvelle sélection avant son
exécution ; aucun ancien résultat risque n'est substitué.

La fenêtre de validité reste clôture J ≤ maintenant < ouverture J+1, avec le
contrôle d'âge archivé. Après l'ouverture suivante, une ancienne sélection ne
peut pas servir de nouvelle autorisation d'achat. Un résultat récent échoué,
périmé ou altéré ne permet pas un retour automatique à un ancien succès.

La case **Tous les comptes Alpaca** du bloc watcher est cochée par défaut.
Le bouton démarre un service par compte déclaré, en respectant les services déjà
actifs et leurs verrous. Ce choix ne lance pas automatiquement les étapes 11/12
sur tous les comptes. Le batch `us_pipeline` démarre avec son `account_id`
configuré. Avec `us_pipeline.run_other_paper_accounts: true` (défaut), après
succès de son workflow il enchaîne automatiquement **11 → 12** sur les autres
comptes déclarés PAPER. Il conserve le même identifiant de sélection, la séance,
le modèle et l'univers, sans refaire l'étape 10. Le watcher est vérifié pour
chaque compte avant 12. Le premier échec arrête les comptes suivants ; les
réussites et compteurs déjà acquis restent dans le bilan. `false` conserve le
seul compte configuré. Ce mécanisme exige 11 **et** 12 dans les étapes choisies
et le mode PAPER ; il n'ajoute pas d'étape omise et ignore les comptes LIVE.
Le batch exige toujours 10 avant 11/12 lorsque le filtre options est actif.
Avec le filtre LLM, limité à `default`, désactiver cette répétition ; aucun
contournement par une exécution sans filtre sur les autres comptes.

## Séparation des responsabilités

- **Commun** : classement Oracle, TOP configuré, données options, scores, motifs,
  sélection LONG, cutoff et preuves scellées. L'étape 10 indique son compte
  producteur ; les nouvelles archives portent `selection_scope: SHARED_MARKET`.
- **Par compte** : equity et buying power broker, positions et ordres en cours,
  budgets de risque, concentration, corrélation, décisions et quantités,
  portefeuille cible, tentatives d'exécution et campagnes Winner.
- Le preset de l'univers de la sélection reste celui du rapport archivé. Le
  capital utilisé pour le sizing est celui du compte consommateur ; il n'est
  jamais copié depuis le compte producteur ou remplacé par un capital de secours.
- Un titre retenu par les options peut donc être accepté sur un compte et refusé
  sur un autre. Les limites de risque et les protections Winner restent appliquées.

Les comptes inconnus ou configurés LIVE sont refusés. L'identifiant de compte
du wrapper doit correspondre à celui de la commande imbriquée. Le résumé risque,
les cibles SQL, le binding, le claim et l'enfant d'exécution doivent tous
correspondre au même compte ; un mélange bloque l'exécution.

## Stockage et compatibilité

Sous `artifacts/options_directional/opt-<id>/` :

- `inputs.json`, `report.json`, `seal.json` restent communs et immuables.
- Pour `default`, tous les fichiers de risque/exécution restent à leur ancien
  emplacement à la racine. Un ancien ordre déjà traité reste consommé.
- Pour un autre compte :
  `accounts/account-<id>-<12 premiers caractères SHA256 de l'id>/` contient ses
  `risk.claim.json`, `risk_summary.json`, `risk_binding.json`, verrous,
  `execution.claim.json`, `execution.result.json` et preuves de reprise.

L'empreinte du nom distingue aussi les identifiants différant seulement par la
casse sur Windows. Les identifiants contenant un chemin sont refusés.

Les nouveaux bindings portent `binding_protocol: options-account-binding-v2`
et `account_id`. Les anciens bindings sans compte explicite ne sont acceptés
que pour `default`. Aucune migration SQL n'est nécessaire : les décisions,
portefeuilles cibles et journaux existants ont déjà un compte et un run risque.
Le résumé risque publie désormais aussi `account_id` au premier niveau.

Une exécution terminée ou ambiguë reste bloquante pour le compte concerné.
Les reprises restent limitées aux preuves déjà prévues : échec de chargement
d'univers avant publication, ou échec de l'enfant avant toute possibilité
d'effet financier. Les preuves et les verrous ne sont pas transférables entre
comptes. Aucune suppression de verrou existant n'a été effectuée.

## Vérification

Tests hors ligne : réutilisation d'une sélection pour trois comptes, risque et
exécution distincts, conservation des fichiers du principal, refus des bindings
copiés et des cibles d'un autre compte, erreurs et reprises isolées, contrôles
de fraîcheur et d'univers conservés, capital réel de chaque compte, affichage
de la sélection commune. Courtiers et sous-processus financiers simulés.

Validation ciblée : **514 tests réussis**, dont le vrai point d'entrée du risque
contrôlé avant capture broker. L'empreinte du claim d'exécution existant du
principal a été vérifiée inchangée ; le contrôle de diff passe.

Cette livraison ne lance aucun ordre, aucun calcul de risque opérationnel ni
nouvelle analyse Oracle/options. Un passage PAPER multi-comptes reste à observer
dans la fenêtre de séance autorisée.
