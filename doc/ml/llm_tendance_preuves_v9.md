# LLM v9 — tendance estimée, qualité des preuves et sélection séparées

Livraison du 24 octobre 2026. Protocole `oracle-direction-evidence-v9` pour les
nouvelles analyses GPT/DeepSeek, en données locales seules ou avec Web. Modèles,
fournisseurs, budgets, horizons et protections ne sont pas changés.

## Configuration et activation

```yaml
llm_directional_filter:
  scoring_mode: direction_1_10
  separate_trend_evidence: true
```

Cette option est activée dans le YAML courant. Les seuils et `allow_long` /
`allow_short` restent indépendants et inchangés. Relancer une **nouvelle étape
10** pour obtenir ce format ; les étapes 11/12 relisent la configuration exacte
du run, pas le YAML actuel. Une archive sans la nouvelle option reste v4–v8.
`false` avec le mode score conserve v8. Aucun ancien résultat n'est réécrit.

## Trois informations distinctes

| Information | Définition |
| --- | --- |
| `trend_status` | `ASSESSED` ou `UNDETERMINABLE`. |
| `direction_score` | Entier 1–10 si estimée ; `null` si indéterminable. Jamais un 5 automatique pour masquer un manque de données. |
| `evidence_quality` brut | Appréciation du LLM : `SUFFICIENT`, `PARTIAL`, `INSUFFICIENT`, accompagnée de `evidence_explanation`. |
| Qualité effective | Recalculée par l'application, conservée dans `assessment_json.evidence_quality`. Elle peut être dégradée, jamais promue au-delà du LLM ou des contrôles existants. |
| `selected` | Publication seulement après seuil strict, sens autorisé, preuves suffisantes, plafond et succès global du run ; ce n'est pas une approbation du risque ni un ordre. |

Barème : 1–2 fortement baissier, 3–4 plutôt baissier, 5–6 informations utilisables
mixtes/équilibrées, 7–8 plutôt haussier, 9–10 fortement haussier. Le score reste
subjectif, pas une probabilité de gain. Il évalue une tendance **pendant** les
séances de l'horizon, pas seulement leur dernière clôture ni un TP avant un SL.
Les seuils de sélection n'altèrent pas cette lecture qualitative : un 7 peut
être plutôt haussier sans dépasser le seuil LONG configuré.

Un contexte utilisable mais incomplet peut conduire à une tendance **provisoire**,
sans autoriser sa sélection. Une identité incertaine ou l'absence de base
exploitable appelle une tendance indéterminable. Le LLM n'est jamais obligé de
répartir les notes ni de fournir un nombre minimal de LONG/SHORT. Oracle prédit
l'amplitude, pas la direction ; une bonne couverture des extrêmes ne justifie
pas de forcer une note haussière ou baissière.

## Vérification indépendante et limites

L'application conserve les contrôles de fraîcheur, source_id et citation exacte,
identité, unités/périodes du consensus, provenance des news, SEC et intégrité.
Elle conserve les motifs existants et ajoute `evidence_partial`,
`evidence_insufficient` ou `trend_undeterminable` selon le cas. Une qualité
`SUFFICIENT` revendiquée par le LLM ne contourne jamais une preuve manquante,
une citation exclue ou un consensus non qualifié. Une qualité `PARTIAL` ou
`INSUFFICIENT` revendiquée reste bloquante même si les contrôles techniques
trouvent une source qualifiée. Les refus de sens et la neutralité n'abaissent
pas à eux seuls la qualité des preuves.

La qualité effective est une **qualification opérationnelle**, pas une mesure
statistique de vérité ni de performance prédictive. Les sources de contexte
ne deviennent pas directionnelles par ce changement. Le modèle reçoit aussi
une consigne de citation contiguë exacte : pas de clés JSON réordonnées ou de
fragments assemblés. Le validateur reste strict, sans « réparation » de citation.

Cette livraison ne répare ni ne qualifie automatiquement les 82 articles, les
identités SEC ou les consensus du run v8 du 23 octobre
`llm-5c606e08250a4a4389b12301a54ad25e`. Elle ne rallonge pas son historique prix
limité par provenance. Il est donc possible qu'un nouveau run conserve zéro
sélection, avec désormais un diagnostic séparé et plus informatif.

## Stockage, affichage et compatibilité

Pas de migration SQL nécessaire : `llm_directional_runs.config_json` archive
l'option ; `protocol_version` identifie v9. `llm_directional_assessments.response_json`
conserve la réponse brute (avec `null` éventuel), tandis que `assessment_json`
archive le score, `trend_status`, `reported_evidence_quality` (déclaration LLM),
`evidence_quality` (effective), `evidence_explanation`, `evidence_quality_reasons`,
`retention_evidence_verified`, décision dérivée, motifs et admissibilité.

Les tableaux 10/11 affichent la tendance, le score ou un tiret, la qualité
effective, la qualité déclarée et son explication. « Indéterminable » n'est ni
« Neutre » ni une erreur technique. Le tableau 11 conserve seulement la
sélection publiée en 10. Rapport, logs et Telegram distinguent aussi les cas.
Le résumé fournit les compteurs de tendances estimées/indéterminables et de
qualités, en plus des compteurs historiques d'admissibilité.

Les schémas/prompts v4–v8 restent inchangés, notamment le score v8 entier
obligatoire et ses anciennes notes de 5. Relecture exacte avec configuration
archivée aux étapes risque/exécution ; pas de conversion rétroactive.

Les champs requis mais nullables sont pris en charge par le schéma structuré
OpenAI ; DeepSeek est validé localement avec le même contrat.
[Documentation officielle Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

Validation hors ligne : schémas et incohérences score/état, quatre parcours
fournisseur/mode, transports DeepSeek simulés, preuves provisoires non promues,
citations inventées bloquées, permissions, stockage SQLite et relecture risque,
rapports, tableaux 10/11 et Telegram. Aucun appel LLM payant, entraînement,
écriture SQL de production ou ordre lancé pour cette livraison.

Résultat : **645 tests ciblés passent**. Contrôle complémentaire READ ONLY de
l'archive v8 `llm-5c606e08250a4a4389b12301a54ad25e` : les vingt requêtes se
reconstruisent à l'identique, les hashes de réponse et assessments se vérifient,
et la sélection reste inchangée. Aucun appel GPT n'a été nécessaire pour ce
contrôle. La documentation officielle OpenAI a guidé le contrat de champs
obligatoires mais nullables ; elle ne valide pas l'efficacité financière des notes.
