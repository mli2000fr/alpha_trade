# Reprise ciblée après timeout GPT — VICR, 25 octobre 2026

Parent : `llm-26f584e35725425c903a5c5b1342b2eb`, signal2026-10-23,
protocole `oracle-direction-evidence-v9`, GPT `gpt-6-luna`, données locales seules.
Dix-neuf réponses valides et un `ReadTimeout` pour VICR, rang13. Le délai
du parent était120 secondes, la limite de sortie20000 tokens : ce n'était
ni un JSON malformé reçu, ni un défaut Triton, ni une limite6000 tokens.

L'utilisateur autorise explicitement une reprise de l'appel GPT. Les tables
historiques du parent restent inchangées. Un enfant distinct est enregistré :
`llm-resume-26f584e35725425c903a5c5b1342b2eb-v1`.

## Contrat

- Réutiliser19 réponses sans appel fournisseur : requêtes, réponses brutes,
  dates d'observation, assessments et sources identiques à l'archive parent.
- Vérifier les empreintes, rangs et scores à partir du snapshot hashé, pas
  d'un classement refait ou des résultats de prix futurs.
- Actualiser les seules données locales de VICR avant l'appel : le paquet
  initial vieux de six heures ne passe plus la fraîcheur30 minutes.
- Même modèle, même mode sans Web, même schéma/prompt/seuils/autorisations.
  Seul le délai transport passe à300 secondes **pour cette reprise**, sans
  modification du YAML global. Au plus un appel pour VICR, aucun retry caché.
- Archiver la réponse brute avant parsing et appliquer le validateur normal.
  En cas de nouvel échec : enfant FAILED, aucune sélection publiée.
- En cas de succès : nouvelle sélection sur les20 candidats, conservant
  strictement les19 jugements d'origine. Aucun risque, ordre ou prédiction
  Oracle relancé automatiquement ; l'utilisateur reçoit le nouvel ID.

La limite de validité est **héritée du parent**, pas renouvelée de24 heures
par la copie. Ici, elle est le2026-10-25 à16:57:05 UTC, soit17:57:05 Paris
après le changement d'heure. La fenêtre avant la prochaine ouverture US est
également vérifiée. Le garde aval `qualified_selection` vérifie cette filiation,
les copies exactes et la limite héritée avant tout usage risque/exécution.
Une reprise n'autorise donc pas à conserver ces mêmes avis jusqu'à lundi.

## Données externes et contrôle

Le premier lancement a été bloqué par le contrôle de sécurité avant tout appel
payant faute d'un descriptif suffisant du payload. Une prévisualisation en
lecture seule a établi : identité Vicor/NASDAQ, rang/score Oracle demandés,
quatre lignes de consensus, huit articles et un résumé prix/volume.
Pas de portefeuille, montant de compte, position ou secret ; aucun outil Web.
Le code refuse les champs inconnus, données de courtage et clés ressemblant
à des secrets avant tout envoi. Le lancement motivé après ce contrôle a été
accepté. Aucun autre mécanisme ni fournisseur de contournement n'est utilisé.

## Outils et validation

Module `service.llm_directional.resume_failed`, avec `--preview` pour un
contrôle sans appel API ni écriture SQL. L'ID enfant explicite et unique interdit
de rejouer automatiquement un appel dont l'issue reste inconnue.
Les archives sont dans `llm_directional_runs` / `llm_directional_assessments`,
sans évolution de schéma. Rapport local sous `artifacts/llm_directional/<ID>`.

332 tests de non-régression et reprise passent avant le lancement réel :
appel unique, original inchangé, fraîcheur du paquet réessayé, conservation
de l'échéance, échec technique et falsification de la copie/deadline rejetés.
Les scores restent subjectifs et non calibrés ; réussite technique ne signifie
ni direction correcte ni efficacité économique.

## Résultat effectif

L'unique nouvel appel pour VICR a réussi : enfant **COMPLETED**, **20 réponses
VALID**, dont19 copiées sans changement et une réponse nouvelle. VICR obtient
**6/10**, `ABSTAIN`, preuves `PARTIAL` : sources locales qualifiées insuffisantes
et score dans la zone neutre. La sélection finale des20 reste vide ; aucun
risque ni ordre lancé. Parent toujours FAILED et inchangé.

Le contrôle aval a révélé un écart d'ordre des clés JSON dans le champ `input`
de la seule requête fraîche. Les données décodées et tous les autres champs
de requête sont identiques. Compatibilité limitée aux symboles réessayés d'une
reprise dont la filiation est d'abord vérifiée, en OpenAI local uniquement.
Doublons de clés, constantes non finies, changement de données, prompt, modèle,
schéma ou limite de sortie restent refusés. Les19 archives copiées gardent leur
comparaison exacte. Aucun octet de requête/réponse SQL n'a été réécrit et aucun
appel supplémentaire n'a été nécessaire. Les futures reprises sérialisent le
contexte dans le même ordre canonique que le chemin normal.

Contrôle réel SQL en lecture seule : `qualified_selection` passe,20 VALID,
sélection vide, `risk_started_at=null`, `execution_started_at=null`.

Validation finale : **348 tests passent**, sans couverture globale, sur la
reprise, le filtre, les preuves fraîches, le protocole tendance/preuves et les
données locales. Le test de compatibilité accepte le seul réordonnancement
JSON du symbole réessayé ; il refuse toute modification des19 copies.
