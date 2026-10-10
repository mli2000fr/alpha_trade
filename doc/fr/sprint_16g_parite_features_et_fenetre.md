# Suite Sprint 16-G — Parité arithmétique et fenêtre d'identité

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## État au 8 octobre 2026

**Parité arithmétique vérifiée sur 233 candidats ; pas de libération du modèle.**
Cette étape poursuit la contre-revue technique demandée à l'assistant. Aucun
réentraînement, chargement du modèle sérialisé, inférence, accès réseau, ordre,
activation de batch ou écriture SQL n'a été réalisé.

Rapport exécuté :
`artifacts/fr/research/feature_parity_16g/opening-20261008-v1/report.json`.
Service : `service/fr/feature_parity_16g.py`.
Tests dédiés : `tests/test_fr_feature_parity_16g.py`.

## Résultats

| Contrôle | Résultat |
|---|---:|
| Candidats du dossier figé | 233 |
| Features ordonnées par candidat | 14 |
| Comparaisons brutes | 3 262 |
| Comparaisons après transformation d'entraînement | 3 262 |
| Candidats concordants pour les deux étages | **233 / 233** |
| Différences au-delà des tolérances | 0 |
| Séances XPAR nécessaires par candidat | 21 |
| Séances compatibles selon les versions déclarées du master | 21 / 21 pour 233 titres |
| Séances précédant l'ancrage du 26 septembre | 13 par candidat |
| Qualification indépendante de la fenêtre complète | Non |

Statut : `FEATURE_ARITHMETIC_PARITY_PASSED_NOT_RELEASED`.
Les tolérances relative et absolue sont chacune `1e-10`. Il ne s'agit donc pas
d'une comparaison d'égalité binaire stricte entre deux implémentations numériques.

## Sources et disponibilité

Le contrôle est lié par empreinte au dossier 16-G3 v2 et à sa confirmation
du **8 octobre à 09:00 Paris**. Il revérifie les dépendances via le contrôle de
remise 16-G, exige le même lineage modèle et les mêmes observations de barres
que la confirmation figée. Une observation nouvelle ou altérée ne peut pas
être silencieusement substituée au dossier audité.

Les barres proviennent des archives opérationnelles `eodhd_daily` et du
bootstrap de remédiation du 7 octobre. Les corrections connues avant la décision
sont sélectionnées suivant leur disponibilité réelle. Les observations reçues
après la décision restent exclues. La fenêtre est recalculée à partir de XPAR
et doit être exactement celle de la confirmation : **9 septembre–7 octobre**.
Aucune séance manquante n'est imputée.

## Méthode de parité

Le premier résultat est celui de `compute_symbol_features`, fonction effectivement
réutilisée par l'adaptateur quotidien et le panel d'entraînement. Un second
calcul explicite, utilisant les listes de barres, `statistics` et `math`, vérifie
séparément les 14 valeurs :

- rendements à 1, 3, 5, 10 et 20 séances ;
- distance à SMA20 ;
- ATR20 relatif à la clôture, incluant les écarts à la clôture précédente ;
- écart-type échantillon de 20 rendements, annualisé par `sqrt(252)` ;
- position dans la plage high/low des 20 dernières séances ;
- volume relatif et moyenne de `close × volume` sur 20 séances ;
- gap overnight, rendement intraday et range intraday relatif.

La première des 21 barres fournit la clôture précédente au premier true range
et au premier rendement. Elle est aussi nécessaire à `return_20`. Elle n'entre
pas dans la moyenne de volumes/valeurs échangées des 20 dernières séances.
Les tests vérifient explicitement cette distinction.

Le résultat est ensuite passé à la fonction réelle `feature_matrix` du pilote
Oracle H5, **pas au modèle**. Cette fonction sélectionne l'ordre des 14 colonnes
et applique une fois `log1p` à `traded_value_mean20_eur`. Le calcul séparé vérifie
les valeurs transformées. Les tests injectant un ATR multiplié par deux et un
double logarithme détectent bien ces défauts.

### Ce que ce succès ne prouve pas

Il ne certifie pas les prix du fournisseur, la devise de cotation ou les actions
sur titres. Il ne teste pas les scores d'un modèle désérialisé et ne compare pas
sa performance future à celle de la campagne historique. La parité arithmétique
est une partie de la gate `MODEL_FEATURE_PARITY_AND_RELEASE_REVIEW`, pas sa clôture.

## Fenêtre d'identité : compatibilité n'est pas qualification

Le master exact connu à la décision est interrogé pour chacune des 21 séances,
et non seulement au 7 octobre. Ses versions déclarées décrivent un état compatible
pour les 233 candidats à chaque séance. Cela ne comble pas les publications
historiques manquantes : on ne peut pas supposer qu'une archive manquante ne
contenait aucun changement parce que le dernier état paraît stable.

La lacune héritée la plus récente est le **9 septembre 2026**, début de la
fenêtre. Treize séances précèdent le nouvel ancrage. La recherche locale ciblée
des Full août/septembre et des Delta du 9 septembre, dans les répertoires ESMA et
master opérationnel examinés, n'a retrouvé que les deux fragments Full du
26 septembre. Ce constat n'est pas une recherche exhaustive sur Internet.

L'identité de fenêtre reste donc `identity_full_window_independently_qualified:false`.
Ni `historical_continuity_confirmed` ni une autre capacité active n'a été modifiée.

## Modèle effectivement référencé

Le candidat reste Oracle amplitude H5, champion du fold 7 de la campagne réparée :

| Phase du fold candidat | Période enregistrée |
|---|---|
| Entraînement | 31 janvier 2019 – 27 juin 2024 |
| Validation | 29 juillet 2024 – 23 janvier 2025 |
| Test | 24 janvier 2025 – 23 juillet 2025 |

Ces dates proviennent du manifeste vérifié, non d'un nouvel entraînement.
Le bloc de plan de dates conserve son statut historique
`PLAN_ONLY_SUPPORT_NOT_YET_VALIDATED` ; le présent audit ne le requalifie pas.
Le candidat ne doit pas être décrit comme réentraîné jusqu'en octobre 2026.
L'âge du modèle est une réserve de revue de release, pas une preuve à lui seul
que ses performances sont mauvaises. Aucun gain directionnel D1/D10 n'est testé
par ce contrôle d'un Oracle d'amplitude.

## Tests et reproduction

**146 tests ciblés passent**, dont 13 nouveaux tests de parité ; cette suite
inclut désormais aussi le contrat 16-A. Ce n'est pas la suite globale de l'application.
Les nouveaux cas couvrent calcul séparé, transformation, ATR erroné, double log,
fenêtre courte/dupliquée/désordonnée, OHLCV invalide, mauvais calendrier fourni,
ordre des colonnes et rôle de la première barre.

```powershell
python -u -m service.fr.feature_parity_16g --packet artifacts/fr/research/release_review_16g3/anchor-20261008-v2/report.json --output-dir artifacts/fr/research/feature_parity_16g/nouvel-audit
```

La sortie doit être un nouveau répertoire. Le statut de succès porte sur le
calcul ; `serving_allowed`, `orders_allowed`, `sql_writes` restent false.

## Suite utile

Ne pas répéter la contre-revue des mêmes XML ou ce calcul arithmétique sans
nouvelle preuve ou nouveau code. Il reste à qualifier les intervalles d'actions
et de devise de cotation, fournir une couverture de fenêtre utilisable, puis
traiter la release du modèle et les réserves opérationnelles Sprint 15.
La contre-revue du même assistant est conservée comme telle ; elle n'est pas
transformée en attestation humaine indépendante.

Références : [dossier 16-G3](sprint_16g3_revue_liberation_actions_devises.md),
[ancrage 16-G2](sprint_16g2_rejeu_ancre_et_contrat_prospectif.md),
[contrat 16-A](sprint_16a_contrat_prediction_et_preflight.md).
