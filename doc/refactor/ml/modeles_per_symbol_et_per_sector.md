# Modèles per-symbol, per-sector et modèle global

## Trois granularités

- global : mutualise les observations et généralise aux symboles couverts ;
- sectoriel : spécialise sur une population économique plus homogène ;
- per-symbol : capture une dynamique propre, au prix d’un échantillon réduit.

Le code et les artefacts peuvent conserver plusieurs familles. Leur simple
présence ne signifie pas qu’elles participent toutes au serving courant.

## Trade-offs

| Granularité | Atout | Risque principal |
|---|---|---|
| global | volume, robustesse, couverture | hétérogénéité masquée |
| secteur | compromis spécialisation/volume | classification secteur et petits groupes |
| symbole | comportement local | variance, historique insuffisant, maintenance |

## Sélection et fallback

Le mode de sélection doit être persisté. Lorsqu’un artefact spécifique manque ou
échoue un gate, la cascade peut descendre vers une granularité plus générale.
Il faut distinguer « modèle non disponible », « modèle rejeté » et « modèle
disponible mais moins prioritaire ».

## Données et validation

Les splits restent temporels. Une validation par symbole/secteur doit montrer
le nombre d’observations et la distribution des performances. Comparer à un
modèle global sur exactement les mêmes lignes. Les secteurs doivent être
normalisés avec une convention stable et disponible PIT.

## Exploitation

Surveiller couverture d’artefacts, fréquence de fallback, métriques par symbole,
coût d’entraînement et désynchronisation serving/gouvernance. Une famille peu
utilisée mais coûteuse doit justifier sa complexité par un gain OOS stable.

Les campagnes historiques B0–B44 ont testé de nombreuses combinaisons ; leurs
enseignements sont synthétisés dans
[Global Ranking et per-sector](../experiences/global_ranking_et_per_sector.md).
Le modèle courant doit être déduit des manifests et chemins de serving.

