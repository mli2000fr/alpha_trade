# Page ML / Prédictions — gouvernance, serving et audit

## Modèle conceptuel

La page rapproche quatre plans qui peuvent diverger temporairement :

```text
run d'entraînement → métriques et artefact → gouvernance champion/challenger
                                      ↘ modèle effectivement servi → prédictions DB
```

Une campagne terminée n’est pas automatiquement promue. Un champion déclaré
n’est pas une preuve que son fichier est chargé. Une prédiction persistée doit
être reliée à son batch, son modèle, son symbole et sa date.

## Gouvernance et artefacts de serving

Le premier bloc inventorie les artefacts et leur cohérence avec la gouvernance.
Il peut permettre une promotion de batch et une inspection par symbole. Avant
toute promotion, vérifier : statut du run, métriques OOS, couverture, manifests,
compatibilité des features, politique de gate et possibilité de rollback.

Les manifestes bruts exposent configuration et métriques sérialisées. Ils sont
utiles pour l’audit mais ne remplacent pas la vérification du code de chargement.
Un champ historique présent dans un manifeste peut ne plus gouverner le runtime.

## Drift et gate ML

Le drift mesure une divergence selon les statistiques implémentées ; il ne
signifie pas à lui seul que le modèle est faux. Le gate traduit cette observation
et d’autres conditions en une règle de service : autorisation, blocage ou mode
dégradé selon le module.

Pour un gate fermé, documenter : métrique déclenchante, seuil effectivement
chargé, fenêtre, population, date et conséquence. Ne pas contourner un gate en
promouvant un autre artefact sans comprendre si le problème vient des données.

## Filtres d’audit DB

Les filtres réduisent les runs et lignes affichés. Ils permettent de suivre un
batch, un symbole ou une période, mais peuvent masquer la portée d’une anomalie.
Revenir à une vue non filtrée pour mesurer la couverture globale.

## Runs d’entraînement et métriques par symbole

Le run porte le contexte de campagne. Les métriques par symbole montrent
l’hétérogénéité cachée par une moyenne globale. Pour juger un modèle : distinguer
train/validation/OOS, contrôler le nombre d’observations et comparer aux
baselines avec le même protocole. Une excellente métrique sur peu de cas ne
justifie pas une promotion.

## Challengers, champion et audit serving ↔ gouvernance

Le tableau de gouvernance décrit la sélection institutionnelle. L’audit de
serving vérifie ce qui est réellement consommé. Les statuts importants sont :

| Situation | Risque |
|---|---|
| champion = served et artefact valide | état attendu, sous réserve du gate |
| champion différent du served | promotion incomplète, rollback ou désynchronisation |
| artefact absent/invalide | prédiction impossible ou fallback |
| ligne DB sans lien gouvernance clair | traçabilité insuffisante |
| symbole DB différent de l’artefact ciblé | vérifier modèle global, fallback ou mapping |

La navigation d’audit peut cibler un artefact et recentrer les lignes du run ;
conserver le `run_id`, le symbole DB, le symbole d’artefact, le modèle servi et
le mode de sélection.

## Prédictions récentes

Une prédiction doit être lue avec horizon, date de disponibilité, valeur,
éventuelle calibration et identité du modèle. Dans le cas Oracle Extreme,
`proba_extreme` représente la magnitude/probabilité d’appartenir à une extrémité
et non la direction haussière ou baissière. Voir la
[documentation Oracle détaillée](../ml/oracle/README.md).

## Procédure d’anomalie

1. mesurer l’étendue : symbole, batch, modèle ou toutes les prédictions ;
2. vérifier features et dates disponibles ;
3. rapprocher gouvernance et serving ;
4. inspecter manifeste et chargement de l’artefact ;
5. lire drift/gate ;
6. vérifier écritures DB et couverture ;
7. décider entre réparation de données, réentraînement, rollback ou maintien du
   gate ;
8. valider OOS avant promotion.

Références : [Model Factory](../06_ml_vue_ensemble.md),
[validation ML](../ml/validation_et_gouvernance.md) et
[Global Ranking](../07_ml_global_ranking.md).
