# Audit des splits et des cibles D1/D10 Oracle — 30 septembre 2026

Statut initial : **quarantaine de recherche produite**. Un
[replay P0g sur labels corrigés](oracle_split_corrected_p0g_replay_20260930.md)
a ensuite été exécuté à gate Oracle OOF figé. Batch gelé
`model-factory-20260909051302-323684`, horizon H20. Aucun prix, label ou score
n'a été modifié en base ; aucun changement de fournisseur ni de serving.

## Périmètre et sources

Le catalogue historique Alpaca des *forward/reverse splits* a été téléchargé
rétrospectivement en six pages pour la période du 05/07/2018 au 30/06/2026.
Il contient 5 497 événements dans cette fenêtre, dont **391** portent sur les
2 493 symboles présents dans les labels du batch ; un doublon `SNEX` même
date/ratio donne **390 événements distincts**. `oracle_split_events_alpaca.json`
conserve les événements normalisés, les identifiants et empreintes de payload.
Les tables locales de corporate actions ne peuvent pas servir de recensement
historique : elles n'ont aucun split NVIDIA 2024 et quasiment aucun split
avant 2026 (`split_source_inventory.json`). Le téléchargement Alpaca de 2026
n'est pas une preuve de disponibilité PIT en 2018–2025.

Pour chaque événement, `audit_oracle_split_panel.py` compare le dernier vrai
prix local avant sa date au premier vrai prix à partir de celle-ci. Le test
« non ajusté » exige un écart au ratio brut théorique inférieur à 15 % en
échelle logarithmique, et un écart à la continuité supérieur à 30 % ; les
autres cas restent « cohérent avec ajustement » ou « indéterminé ». C'est un
filtre prudent de **candidats**, pas une validation indépendante de toutes les
actions sur titres. Résultat (`oracle_split_price_audit.json`) :

| Classe | Événements |
|---|---:|
| Cohérents avec un prix ajusté | 356 |
| Indéterminés | 31 |
| Ratio observé cohérent avec un split non ajusté | **3** |

Les trois candidats sont `NVDA` 20/07/2021 (4:1), `NVDA` 10/06/2024
(10:1) et `SBS` 07/05/2026 (5:1). [NVIDIA confirme le split 10:1 et le début
de cotation ajustée le 10/06/2024](https://investor.nvidia.com/news/press-release-details/2024/NVIDIA-Announces-Financial-Results-for-First-Quarter-Fiscal-2025/).
Le rapport local prix est respectivement 0,24777, 0,10075 et 0,19210, alors
que les barres sont toutes étiquetées `data_adjustment='split'`. Le cas 2024 a
en plus été contre-vérifié avec Alpaca `split` et `raw` : les cours locaux
précédant le split correspondent au brut, non à l'ajusté. SBS n'a aucun label
du batch traversant sa date de split.

## Élargissement à toutes les barres du batch

`scan_oracle_universe_price_jumps.py` a lu **4 929 382 barres réelles** des
2 493 symboles, sans écrire en base. Le seuil exploratoire ≤0,45× ou ≥2,2×
sur deux séances réelles consécutives trouve **60 sauts**, dont 13 ont un
événement Alpaca proche et 47 n'en ont pas. Ce seuil n'identifie pas une
action sur titres à lui seul : il mélange potentiellement splits manquants,
erreurs de données, fusions, changements d'identité et véritables réactions de
marché. Neuf des 47 sauts sans split proche traversent au moins un label
historiquement marqué valide (`oracle_severe_jump_label_exposure.json`). À titre
de contre-exemple, la chute `MLTX` du 29/09/2025 coïncide avec
[la publication des résultats cliniques VELA](https://ir.moonlaketx.com/news-releases/news-release-details/moonlake-immunotherapeutics-reports-week-16-results-vela-phase-3)
du 28/09 ; elle ne doit pas être effacée au seul motif que son amplitude
ressemble à un split. Les inversions de prix observées sur plusieurs ETF en
2026 restent à examiner séparément. `oracle_universe_severe_price_jumps.json`
conserve la liste entière.

## Quarantaine confirmée et sensibilité

`audit_split_label_exposure_all.py` relève **40 labels H20 NVIDIA** déjà
`target_quality_valid=1` et D1 dont la fenêtre traverse les deux splits non
ajustés : 20 en 2021 et 20 en 2024. Ils sont écartés du scénario principal.
Le contrôle NVIDIA 2024 précédent en comptait 19 car il commençait le
13/05/2024 ; l'audit complet ajoute le label du 10/05, dont la sortie est le
jour du split.
La liste compacte et contrôlable des 40 clés, dates de sortie, rendements et
raisons figure dans `oracle_split_quarantine_20260930.csv` (SHA-256 :
`ba993f773e12a619b7b5cab823953cb8ce055a64d815efbb902bccb177828fb9`).
UCO 21/04/2020 ajoute 16 D1 dans un scénario de sensibilité seulement : son
saut est sévère mais n'a pas le sens du reverse split fourni par Alpaca ; le
mouvement de marché ne peut pas être écarté. Les autres ruptures sans preuve de
split ne sont **pas** supprimées automatiquement.

`evaluate_split_quarantine_labels.py` a reproduit exactement les déciles
stockés (`stored_rank_mismatch=0`) sur les dates touchées, retiré les 40
étiquettes NVIDIA, puis recalculé les rangs transversaux H20 des autres titres.
Le scénario principal est matérialisé dans
`oracle_split_clean_label_overrides.jsonl` : **69 136** lignes auparavant
valides sur 40 dates, dont 40 portent maintenant
`new_target_quality_valid=0` et `unadjusted_split_quarantine`. Les 69 096
survivantes ont leur percentile et décile recalculés ; 175 changent de décile.
L'empreinte SHA-256 du fichier est
`3a0f66d33683096e0a4515da02055c09ee38ab103a12003ab1661b9ba5badeab`.
Ce fichier est un *override* de recherche versionné par son hash, **pas** un
upsert SQL. Les rendements corrigés des titres NVIDIA ne sont pas affirmés :
ils sont exclus jusqu'à une reconstruction complète des prix ajustés.

| Sensibilité sur 56 dates touchées par NVIDIA ou UCO | Principal : 40 NVIDIA écartés | Étendu : +16 UCO écartés |
|---|---:|---:|
| Labels écartés au total | 40 | 56 |
| Parmi eux, membres du TOP20 Oracle OOF | 21 | 37 |
| Déciles modifiés parmi les autres membres TOP20 | 32 | 40 |
| D1 du TOP20, avant → après | 4 435 → **4 429** | 4 435 → **4 414** |
| D10 du TOP20, avant → après | 3 635 → **3 635** | 3 635 → **3 635** |

Le nombre net de D1 baisse moins que le nombre de lignes retirées : certains
titres auparavant D2 deviennent D1 lors du nouveau classement quotidien.
L'écran étendu n'est **pas** une correction affirmée de UCO ; il montre la
sensibilité à ce cas indécidable.

## Portée du verdict directionnel

Le témoin P0g publié avait AUC D10/D1 **0,4904** sur 179 605 lignes OOS et
ne passait pas ses gates. Les prédictions OOS CatBoost et l'artefact du modèle
P0g sont absents du checkout courant : **son AUC exacte après quarantaine
n'a pas été recalculée**. De plus, les scores Oracle sont gelés ici ; un
réentraînement complet exigerait de reconstruire l'Oracle après correction de
ses cibles d'amplitude et de rejouer P0g sur les mêmes folds. Le résultat de
ce rapport est une réévaluation **de la population et des déciles**, pas une
nouvelle validation de performance du classifieur. Le `NO_GO_DIRECTION` P0g
reste en vigueur. Cette phrase décrit l'état avant le replay de sensibilité
ci-dessus ; l'Oracle d'amplitude n'a toujours pas été réentraîné.

Le replay ultérieur a reconstruit les prix NVIDIA et les labels confirmés,
puis réentraîné P0g sur ses folds gelés avec le gate Oracle original. Il reste
à revoir les 31 splits indéterminés et les neuf sauts sans split ayant touché
des labels valides, en séparant mouvements économiques, conventions
d'ajustement et changements de titre. Une validation complète exige ensuite
de réentraîner l'Oracle amplitude et ses 14 folds OOF sur les nouvelles cibles,
puis de rejouer P0g avec ce nouveau gate.
