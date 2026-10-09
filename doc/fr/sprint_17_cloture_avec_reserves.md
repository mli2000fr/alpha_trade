# Sprint 17 — Clôture administrative avec réserves

## Décision du 9 octobre 2026

L'utilisateur a choisi l'option 2 : suspendre le raccordement d'ordres et
clôturer la tranche livrée, sans continuer indéfiniment les bancs synthétiques.

**Statut : infrastructure de préparation et lecture DEMO livrées ; exécution
FR bloquée.** Ce statut n'est ni une clôture fonctionnelle complète du courtier,
ni un GO PAPER autonome, ni un GO LIVE.

## Livré et conservé

- 17-A : contrat FR et intentions synthétiques, sans route d'exécution.
- 17-B : six lectures Trading212 DEMO accessibles, compte EUR ; historique
  maintenant accessible, contrairement aux premières lectures HTTP 403.
- 17-C : 138 correspondances XPAR/Paris/EUR du périmètre pilote, 95 exclusions.
- 17-D : réconciliation synthétique, cumuls remplis, annulation et timeout.
- 17-E : journal local persistant et reprise, transport factice uniquement.
- 17-F : audit quantitatif des protections et courses ; 124 tests ciblés passaient.
- 17-G : recherche publique bornée et questions support préparées, non envoyées.

Les clés restent dans l'environnement ; les réponses privées ne doivent pas
être publiées. Aucun ordre externe n'a été envoyé dans ces lots.

## Réserves ouvertes

1. OCO/bracket natif et remplacement atomique non qualifiés pour l'API Invest.
2. Réservation des quantités, reduce-only et comportement réel des protections
   non testés ; pas de parité avec le contrat d'exécution du moteur.
3. Aucun adaptateur réseau FR opérationnel raccordé au `BrokerRouter`.
4. MIC réel d'exécution distinct du calendrier de cotation non qualifié.
5. Réserves de données/signal shadow du Sprint 16 non levées.
6. Journal 17-E qualifié en recherche synthétique, pas en production courtier.

Les recherches/lectures hors ordre restent possibles. La clôture ne prouve pas
un fonctionnement shadow complet : les réserves Sprint 16 restent applicables.
Elle n'active aucun job, ne change aucun modèle, base ou règle stop/TP.

## Conditions de réouverture

Réponse technique récente du courtier avec garanties et endpoints vérifiables,
ou décision utilisateur explicite de changer de courtier/contrat de protection.
Puis protocole de tests, autorisation distincte des ordres DEMO, validation de
parité et des données avant tout raccordement. Pas de bascule automatique CFD,
stop seul ou TP local. Aucune ouverture de compte supplémentaire implicite.

Le Sprint 18 LIVE reste bloqué par ses prérequis. Sa
[préparation indépendante](sprint_18_preparation_exploitation.md) a été livrée
le 9 octobre, sans déclarer ces gates verts ni raccorder d'ordres. Voir aussi le
[runbook](runbook_exploitation_fr.md) et le
[TODO de reprise](TODO_reprise_exploitation_sprints_16_18.md).

Voir [planning FR](sprint_planning_integration_marche_francais.md),
[décision courtier 17-G](sprint_17g_decision_capacites_trading212.md) et
[clôture Sprint 16](sprint_16_cloture_bornee.md).
