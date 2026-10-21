# Étape 11 — correction du contrôle de précision Oracle

## Incident du 17 octobre 2026

L’étape 11 refusait l’analyse `llm-fa604bed142d41a7be61012432c1fc6e`
(séance du 16 octobre) avec :

```text
Classement ou requête LLM incompatible avec le snapshot
```

Le diagnostic en lecture seule a confirmé que les dix rangs et les dix requêtes
archivées correspondaient au snapshot. La différence venait de la colonne
`llm_directional_assessments.oracle_score`, de type MySQL `FLOAT`, comparée avec
une égalité stricte au nombre en pleine précision du JSON signé par SHA-256.
Exemple CCOI : `0.8597901389016575` dans le snapshot, `0.85979` relu en SQL.

## Correction

Dans `service/llm_directional/runner.py`, le contrôle accepte seulement les
représentations connues du même score : valeur exacte, conversion binaire32,
ou rendu à six chiffres significatifs de cette conversion par le protocole
texte MySQL. Il ne s’agit pas d’une tolérance générale autorisant une modification
arbitraire du score.

Le snapshot dont le hash est vérifié reste la référence : son score complet est
transmis à la lineage risque, sans modifier l’archive SQL ni reclasser les titres.
Les rangs, les requêtes complètes, les empreintes des réponses, les évaluations,
la sélection, le protocole, le compte PAPER, la date, la fraîcheur et l’absence
de consommation précédente restent contrôlés. Les messages d’erreur distinguent
désormais rang, score et requête, avec le symbole concerné.

## Validation et reprise

- 294 tests passent, dont les régressions de représentation MySQL, la précision
  transmise au risque et le rejet d’un score/rang/requête réellement différent.
- L’appel réel à `qualified_selection`, en lecture seule, passe tous les contrôles
  pour ce run et restitue **FMC — SHORT — rang Oracle 6**.
- `risk_started_at`, `risk_run_id` et `execution_started_at` restent à `NULL`
  après cette vérification : aucun lancement risque ni ordre n’a été effectué.
- Aucune modification SQL, migration, réécriture de réponse ou nouvel appel
  GPT/DeepSeek n’a été nécessaire.

Reprendre **11. Risk Management avec le même identifiant d’analyse** ; refaire
l’étape 10 n’est pas nécessaire pour cet incident. Les autres contrôles risque
restent applicables : le passage du contrôle d’archive n’est pas une approbation
de FMC par le risque ni une garantie de disponibilité du SHORT chez le courtier.
Si l’analyse a expiré au moment de la reprise, sa limite d’âge doit rester
respectée : ne pas contourner le contrôle de fraîcheur.
