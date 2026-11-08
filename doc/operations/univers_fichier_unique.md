# Univers texte US — fichier unique dans config/univers

Mise à jour du 3 novembre 2026, à la demande utilisateur.

`config/univers/` ne contient plus que `univers_filtred_tradable.txt` : **1 790
symboles**, avec les mêmes octets et le même ordre qu'avant la consolidation.
Le choix court est `universe-file:univers_filtred_tradable.txt`.

## Références de lancement

Le screener, les configurations de régime, le canary et les valeurs par défaut
des outils de recherche qui citaient un ancien univers utilisent désormais ce
fichier. Les configurations E17B/E18A changent de chemin, mais leur ancien fichier
equities avait déjà exactement le même contenu que le fichier conservé.

Les anciens petits univers de 12/15/47/300/400 titres et l'ancienne liste de 2 688
titres ne sont plus des sources de lancement courantes. Relancer un ancien outil
avec ses nouveaux paramètres par défaut ne reproduit donc pas automatiquement
son ancien protocole : les dates, cohortes et paramètres doivent être qualifiés
pour toute nouvelle expérience.

Les défauts génériques et l'alias `ticket-recherche` préfèrent explicitement
`univers_filtred_tradable.txt`, même si un autre fichier vient à être ajouté avant
lui dans l'ordre alphabétique. Les anciens choix ML Train/ML Predict conservés
dans une session IHM sont migrés vers ce fichier. Les choix natifs valides, comme
`stock-bars-daily`, restent disponibles.

Les neuf noms retirés ne sont **pas** des alias de chargement vers le nouvel
univers : cela réinterpréterait silencieusement d'anciennes sélections et leurs
empreintes. Ils sont reconnus seulement pour migrer les choix de l'IHM.

## Exports de recherche

Les outils qui construisent un sous-univers lisent le fichier conservé mais
écrivent désormais leurs sorties sous `artifacts/research/universe_exports/` :

- `scripts.build_equity_universe` : `equities.txt` ;
- `modelFactory.oracle_balanced_universe` : `balanced_400.txt`.

Ils refusent une destination qui écraserait leur entrée ou le fichier partagé.
Ces exports sont des résultats de recherche, pas de nouveaux fichiers proposés
automatiquement dans les choix courants de `config/univers`.

Le plan de recherche d'identité des news utilise aussi le chemin conservé, mais
ne propose plus de commande de collecte si le sous-ensemble relu diffère de
l'univers complet : une substitution de 15 à 1 790 titres ne doit pas contourner
son contrôle de périmètre. Aucun téléchargement n'a été lancé.

## Archives et périmètre de la consolidation

Les neuf anciennes listes, leurs comptes et SHA-256 sont conservés dans
`artifacts/archives/univers/20261103-v1/manifest.json` avec les fichiers eux-mêmes.
Les configurations modifiées mécaniquement ont aussi leurs copies antérieures
sous `reference-configs-before/`. Le rapport initial reste
[consultable](audit_univers_20261103.md).

Les rapports historiques, contrats de modèles, analyses scellées et commandes
de runs terminés restent inchangés. Pour une reproduction historique, utiliser
une copie explicite du bon ancien fichier avec le contrat historique approprié ;
ne pas remplacer son contenu par celui de l'univers courant.

Cette demande concernait **config/univers**. Les fichiers de collecte de
`config/univers_batch/`, dont `stock_bars_daily.txt` et `action_ordinaire.txt`,
restent distincts. Sa copie `univers_filtred_tradable.txt` conserve actuellement
les mêmes 1 790 symboles ; les batchs qui l'utilisent gardent leur chemin explicite.
Aucun modèle, contenu d'univers, seuil de risque, batch lancé ou ordre n'a été modifié.
