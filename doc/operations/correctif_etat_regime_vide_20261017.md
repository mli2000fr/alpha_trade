# Étape 11 LLM PAPER — état de régime vide

## Cause confirmée

Le run IHM `20261017_211818_a962643e` du 17 octobre 2026 à 21:18 Paris
transmettait correctement l’analyse `llm-fa604bed142d41a7be61012432c1fc6e`
pour la séance du 16 octobre. Il ne s’agissait plus du problème `run-id auto`
du run précédent de 20:56.

Son échec suivait cette chaîne :

1. `artifacts/market_regime/state/latest.json` contenait `{}`.
2. `load_regime_state()` envoyait ce dictionnaire à `MarketRegimeState.from_dict()`.
3. Le champ requis `trade_date` était absent : `KeyError`.
4. Aucun snapshot de régime n’était produit ; le garde LLM PAPER bloquait
   correctement le risque avec « régime du jour non qualifié ».

Le dictionnaire vide est pourtant une représentation prévue par
`save_regime_state(None)` : c’était une incohérence lecture/écriture.

## Correctif appliqué

Dans `service/market/state_store.py` :

- fichier absent ou objet JSON exactement vide : aucun état précédent ;
- objet non vide sans date, JSON malformé ou type de document incorrect : erreur,
  pas de substitution silencieuse ;
- état valide, y compris défensif : conservation des valeurs et compteurs.

Ce correctif **ne crée pas un régime normal**. Le moteur doit toujours calculer
un snapshot du jour avec les fournisseurs configurés. Les gardes de qualité,
de fraîcheur, de compte et d’autorisation d’entrée ne sont pas désactivés.
Les avertissements d’absence de snapshots de compte ne sont pas la cause de
ce `KeyError`. La branche LLM lit ensuite un snapshot PAPER frais au courtier ;
il ne faut pas lancer l’étape 12 uniquement pour faire disparaître ces warnings.

## Validation et limite de la remise

307 tests passent : lecteur d’état, moteur de régime, CLI risque, archives LLM et
reprise entre boutons. Les nouveaux tests couvrent le retour `save(None)` / `load`,
la conservation d’un état défensif, le recalcul après `{}` et le maintien du
blocage si le calcul du régime échoue. Les tests CLI sont explicitement isolés
du cache réel et des fournisseurs macro.

La lecture du cache réel ne déclenche plus le `KeyError`. **Aucun risque complet,
appel LLM ni ordre n’a été relancé pour cette validation.** Cela ne prouve pas
encore que toutes les données nécessaires au calcul du régime du jour sont
qualifiées : un autre contrôle peut légitimement bloquer la reprise.

La tentative de 21:18 avait réservé `risk_started_at` avant le lancement du
sous-processus. Ce verrou n’avait pas été réinitialisé par le correctif. Avant une
nouvelle tentative, une reprise contrôlée doit vérifier son échec terminal,
l’absence de cibles/liaison risque et d’exécution, puis réarmer uniquement cette
tentative avec autorisation explicite. Ne pas supprimer le run d’analyse,
réécrire sa réponse ni relancer l’étape 10 pour contourner ce verrou.

## Réarmement explicitement autorisé — 17 octobre à 21:28 Paris

Après GO utilisateur, une seule ligne de `llm_directional_runs` a été modifiée :
`risk_started_at` de `llm-fa604bed142d41a7be61012432c1fc6e`, auparavant
`2026-10-17 19:18:19` UTC, est remis à `NULL`. L’ancien échec reste dans
l’historique IHM ; son statut et ses logs ne sont pas maquillés en réussite.

Contrôles préalables :

- analyse `COMPLETED` toujours qualifiée, compte `default`, séance du 16 octobre ;
- aucun processus Python associé à cette analyse encore actif ;
- run IHM exact `20261017_211818_a962643e` terminal `failed`, code 1, signature
  d’échec régime confirmée dans ses logs ;
- aucun fichier `risk_summary.json` ni temporaire ;
- aucune cible ni décision pour ce compte et cette séance ;
- aucun `execution_order_requests` ni `execution_runs` du compte depuis la réservation ;
- aucune liaison `risk_run_id` ni réservation `execution_started_at`.

Le changement est réalisé en transaction, avec verrou de la ligne et comparaison
de l’ancienne réservation exacte. Le nombre de lignes modifiées est **1**.
Toutes les autres valeurs de la ligne et toutes les archives des dix réponses
LLM ont été comparées avant/après et sont inchangées.

Empreintes de contrôle SHA-256 :

- archives évaluations/requêtes/réponses/sources/sélection :
  `ed338880e232893b495a0b1c4e3a40ba73633a5077e3b1cad3ac7cf42157701f` ;
- stdout source :
  `fc76bcfe2bd9403987b54db43690660b1651f1fd3f346ed74e09c0e69cbd62b2` ;
- stderr source :
  `1221a7b8ae5b52b8d8835d71a40b6871cff3baaa0be67fbf24c5ef6c320c5e7a`.

Vérification après commit à **21:28:57 CEST** : réservation risque vide, aucune
liaison risque/exécution, analyse toujours valide, sélection inchangée
**FMC — SHORT**. L’étape 11 n’a pas été relancée ; aucun appel GPT/DeepSeek,
aucune exécution et aucun ordre n’ont été lancés par ce réarmement.
L’utilisateur peut reprendre uniquement l’étape 11 tant que l’analyse reste
dans sa durée de validité ; ses contrôles de régime et de risque restent actifs.
