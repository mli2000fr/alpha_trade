# 4 — Artefacts, serving et fallback secteur

## Arborescence

```text
artifacts_dir/
  _sector_<slug>/
    config.json
    h<N>/
      lightgbm/...
      catboost/...
```

Le slug met le secteur en minuscules et remplace espaces et `/` par `_`. Le
`config.json` racine conserve secteur, symboles, features, mode
`per_sector`, target mode et champion.

## Routes

Le registre associe le champion à un `inference_backend` tabulaire et aux chemins
modèle/config/calibrateur. Les signatures SHA256 utilisent le même mécanisme que
le per-symbol. Le serving doit suivre la route persistée plutôt que scanner le
dossier à la recherche du premier modèle.

## Résolution depuis un ticker

Quand `_resolve_artifact_paths` ne trouve pas de champion per-symbol admissible,
`_resolve_sector_run` recherche le modèle du secteur et renvoie sa config/route.
`_classify_prediction_source` marque alors la prédiction `per_sector`. La ligne
reste attachée au ticker demandé, mais le modèle servi est mutualisé.

## Parité features

L’inférence reconstruit les features du ticker et le contexte nécessaires, puis
applique l’ordre de colonnes enregistré. Si `symbol` faisait partie du train, il
doit être fourni avec le type/encodage compatible. Modèle, calibrateur, seuil et
target mode viennent de la route/config du secteur.

## Fallbacks

Le secteur est lui-même un fallback possible du per-symbol. Il ne doit pas être
présenté comme le modèle propre au ticker. Si aucun secteur ou artefact valide
n’existe, la prédiction peut être absente et la cascade supérieure décider d’un
autre mode ; cela doit rester visible dans `source` et les diagnostics.

