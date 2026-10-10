# Maintenir la documentation à partir des sources

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Organisation et ordre de lecture

Le point d'entrée est [README](README.md). Les guides 01–22 et
[l'état actuel](ETAT_ACTUEL_IMPLEMENTATION.md) expliquent le comportement courant.
Les références de `data`, `database`, `signals`, `risk`, `execution`,
`operations` et `guide_utilisateur` détaillent ces contrats. FR/CN ont leurs
propres README et plans ; les bases, catalogues et capacités restent séparés.

Les dossiers `ml`, `fr`, `cn` mélangent volontairement contrats et comptes
rendus datés : lire leur statut en tête. `experiences` et
`sources_historiques` sont des archives, pas des runbooks. Les plans/TODO ne
valent pas preuve de livraison. Chaque fichier est classé dans le
[registre](audit/registre_documentaire.md) ; l'[index](INDEX.md) permet la recherche.

Les inventaires de `api` et `reference` sont générés : éditer leur générateur,
pas leurs tableaux. Ils localisent le code, sans certifier toutes ses sémantiques.
Les CSV, JSON, TXT et YML documentaires restent dans le registre ; ne pas modifier
des résultats expérimentaux ou règles de monitoring pour uniformiser le texte.

## Source de vérité par contrat

| Contrat | Sources à lire ensemble |
| --- | --- |
| Orchestration | pipeline_runner, page pipeline, service/forward_pit/us_pipeline, tests de commandes |
| Signal US | common/us_signal_date, service/llm_directional/pipeline et runner, CLI Oracle-only |
| Collectes | trois catalogues YAML, batch_management, runner du marché, launchers/installers Windows |
| Configuration | config_loader, résolveur/dataclass du consommateur, CLI, builder IHM, YAML effectif |
| Bases | router, config/databases, contextes de marché, DDL et graphe Alembic du marché |
| ML | profil de l'artefact, trainer, prédicteur, tables de sortie, gouvernance et tests |
| Exécution | risque, ledger, broker/account/mode, protections/watcher, réconciliation, coûts |
| Données PIT | horodatages source/observation/disponibilité, joins et qualité ; jamais seules dates économiques |

Ne pas transformer une capacité du code en instruction d'activation. Un statut
droits/prudence demeure un verrou, même si la clé fonctionne. Ni les signatures
générées ni cette revue locale ne constituent un nouvel audit juridique.

## Procédure reproductible locale

Depuis la racine du dépôt, avec Python et PyYAML installés :

```powershell
python scripts/refresh_documentation.py
python scripts/refresh_documentation.py --apply --date 2026-10-10
python scripts/generate_doc_index.py
python scripts/refresh_documentation.py --apply --date 2026-10-10
python scripts/refresh_documentation.py --audit-links
python scripts/generate_doc_index.py --check
python -m pytest tests/test_documentation_refresh.py -q --no-cov
git diff --check
```

Adapter la date au jour réel de révision. `--no-cov` concerne seulement cette
suite ciblée ; elle ne mesure pas la couverture globale de l'application.
Le premier appel ne modifie rien.
`--apply` écrit seulement sous `doc` : inventaires AST, noms/types de clés YAML
(sans valeurs/secrets), planning déclaré, références DDL, statuts et liens
déplacés. Aucun import métier, connexion SQL, installation Windows ou appel
fournisseur. Le second passage met le registre et son contrôle de liens à jour
après l'index ; un passage suivant doit ne rien changer.

Le contrôle de liens vérifie **l'existence des fichiers locaux**, pas les
ancres Markdown ni la validité des URLs externes. Les liens d'archives dont la
preuve manque deviennent un identifiant textuel explicitement absent ; aucun
résultat n'est inventé. Une référence déplacée est raccordée au fichier actuel
et son ancienne ancre est retirée.

## Mise à jour sémantique obligatoire

Le générateur ne remplace pas la revue du comportement. Pour toute évolution :

1. Lire les consommateurs et les tests du contrat ; distinguer défaut Python,
   valeur YAML et option IHM/CLI effectivement transmise.
2. Corriger le guide courant propriétaire, l'état actuel et les index impactés.
3. Conserver résultats, dates et réserves historiques ; ajouter un avertissement
   de remplacement, pas un nouveau verdict rétrospectif.
4. Régénérer les références, tester liens/index/idempotence et examiner le diff.
5. Documenter les limites : état déployé non vérifié, preuve absente, capacité
   bloquée ou validation nécessitant une autre revue.

Éviter les déplacements massifs sans nécessité : IHM/config/scripts peuvent
citer les chemins documentaires. Fusionner les consignes dans un propriétaire
canonique et garder un lien de compatibilité avant de supprimer un doublon.
