# FR P0/P1 : pas de validation directionnelle H20 possible à ce stade

Audit achevé le26octobre2026, archives locales et SQL FR en lecture seule.
Aucun batch changé, téléchargement, appel LLM, entraînement ou ordre.
Treize tests passent : stops/gaps, ordre intraday inconnu, maturité, identité
fournisseur datée, absence sous seuil AMF, contrôle de disponibilité pré-entrée.

## Périmètre

Six collectes de marché P0/P1 et deux sauvegardes dans `batch_fr.yaml`.
Univers courant actif vérifié de collecte :293codes fournisseur, après exclusion
Lhyfe et migration PERR→ALPER. Pas seulement TOP10/20 Oracle. Ce référentiel
courant n'est pas un univers historique tradable/PIT validé.

Le snapshot initial contient294codes, car son warmup commence le1erseptembre
et couvre les deux côtés de la migration du7septembre. La revue hors ligne
exclut PERR pour les décisions d'octobre : ALPER seul, aucun collage de prix.
Archives initiales conservées intactes ; cette correction de périmètre retire
uniquement des cas manquants/nonmatures, sans changer les AUC ni labels valides.

## Ce que chaque batch apporte réellement

| Batch | Données constatées | Qualification directionnelle actuelle |
| --- | --- | --- |
| `fr_calendar_snapshot` P0 | 4 observations de calendrier | Support des séances ; aucun score LONG/SHORT autonome |
| `fr_security_master_sync` P0 | 17 observations, continuité courante au25octobre, zéro anomalie au checkpoint | Identité/MIC et intégrité du panel, pas direction ; canonical_go=false |
| `fr_daily_bars_sync` P0 | Prix versionnés en staging jusqu'au23octobre, observations opérationnelles sur15jours | Features prix testables seulement si version disponible avant entrée ; indice momentum préliminaire, non validé |
| `fr_corporate_actions_sync` P0 | 8 251 observations,15jours | Contrôle des dividendes/splits, pas une prédiction autonome ; preuves fournisseur non indépendantes |
| `fr_amf_short_sync` P1 | 15 snapshots depuis5octobre ; export reconstruit14 238lignes historiques/106ISIN ;47ISIN avec position publique courante dans le périmètre | Variations de mêmes détenteurs faiblement favorables dans quelques fenêtres, non confirmées indépendamment |
| `fr_dila_disclosures_sync` P1 | 18observations/15jours ;860documents logiques sur214ISIN du périmètre courant | Métadonnées et titres seulement ; aucun texte PDF collecté par ce batch, aucune guidance/surprise qualifiée |
| `fr_db_backup`, `fr_artifacts_backup` P0 | Copies de sécurité, pas nouvelles données de marché | Hors signaux ; l'audit n'est pas un contrôle de restauration/succès des sauvegardes |

La base `alpha_trade_fr` contient2 124 452versions de staging,1452codes,
de2016au23octobre2026, tous périmètres de backfill confondus. Cela n'est pas
2millions d'observations prospectives ni1452titres tradables. Les deux tables
`fr_provider_bars_daily` et `stock_bars_daily` canoniques sont vides : les prix
existent bien, mais ne sont pas promus. Le snapshot récent utilisé compte
30 069versions du staging (y compris l'ancien alias de warmup).

Consensus EODHD =P3, options MiFIR=P3, INPI=P2 : hors demande P0/P1.
Les sources bloquées droits/prudence, notamment INPI/Yahoo, ne sont pas utilisées.

## Cible et maturité

Preuves reçues strictement AVANT ouverture, référence prix=open J+1,
excursion favorable maximale avant stop fixe10%, calculée séparément LONG
et SHORT ; comparer ces deux excursions, pas le rendement de clôture H20.
La première séance du maximum favorable et l'ordre des deux pics sont conservés
quand déterminables. Cela n'est pas un premier maximum local ni une sortie
exécutable au sommet. Deux pics le même jour restent sans ordre intraday.
Si stop et nouveau pic touchent la même bougie daily, utiliser des bornes et
réserver les directions indécidables. Gaps traités avant tout rebond ultérieur.

Les premiers snapshots AMF/DILA sont réellement reçus le5octobre après clôture,
donc première entrée admissible le6octobre. Prix disponibles jusqu'au23octobre :
**14séances seulement** pour cette première entrée. H20 se termine le2novembre
(entrée incluse), sous réserve de collecte/qualité complète des prix.
Au cutoff :**zéro label H20 mûr**,4 102couples titre/date nonmatures.
Aucune AUC H20 ni preuve de séparation LONG/SHORT ne peut être produite.
Les lignes AMF datées2017 et DILA datéesseptembre reçues enoctobre ne sont pas
antidatées : leur date économique n'est pas leur disponibilité dans l'application.

## Diagnostics secondaires H5/H10 — pas une validation

| Feature, orientation figée | AUC moyenne par date H5 | Dates informatives H5 | AUC H10 | Dates informatives H10 |
| --- | ---: | ---: | ---: | ---: |
| Niveau public AMF plus bas → LONG | 0,473 | 10 | 0,503 | 5 |
| Diminution chez mêmes détenteurs AMF → LONG | 0,526 | 8 | 0,529 | 3 |
| Momentum5séances plus élevé → LONG | 0,556 | 6 | 0,594 | 1 |
| Momentum20séances plus élevé → LONG | 0,524 | 6 | 0,588 | 1 |

Une AUC0,53 n'est pas53% de trades gagnants. C'est un diagnostic de classement
des labels de parcours protégés. Pas de seuil optimisé ni inversion d'un score
après observation. Les dates sans variation ou sans les deux classes ne peuvent
pas contribuer à l'AUC quotidienne ; ne pas gonfler leur nombre.

Les variations AMF donnent0,478(H5)/0,477(H10) en ne retenant que la première
observation admissible de chaque titre, sur50/47titres. Ce contrôle ne confirme
pas l'avantage et n'apporte toujours pas d'indépendance des régimes de marché.
Le niveau AMF seul ne montre pas non plus d'avantage robuste.

H5 :2 506labels décidables sur274titres/10dates (1 102LONGdominants,
1 404SHORTdominants),107chemins ambigus,300prix incomplets/invalides,
17fenêtres réservées pour actions fournisseur connues,1 172nonmatures.
H10 :1 228labels sur257titres/5dates (534LONG,694SHORT),30ambigus,
190prix incomplets/invalides,17actions réservées,2 637nonmatures.
Ces classes ne sont ni des recommandations ni des taux de trades gagnants.
Les fenêtres se chevauchent et répètent les mêmes titres : ne pas compter
2 506lignes comme2 506expériences indépendantes. Aucun test hors échantillon.

## Conclusion et prochaine reprise bornée

**NO_H20_DIRECTIONAL_VALIDATION_POSSIBLE_YET**. Ce n'est pas la preuve que toutes
ces données sont inutiles : l'expérience demandée n'a pas encore ses labels.
AMF : piste de variation observée à conserver, mais pas d'avantage confirmé.
DILA : il manque le contenu et la qualification du fait nouveau pour tester
une hypothèse directionnelle ; compter toutes les annonces ne donne pas leur sens.
Prix/momentum : indice exploratoire à surveiller, pas de modèle ou filtre promu.
Ne pas prolonger automatiquement le travail documentaire ni déclencher de collecte.

Après le2novembre, une première fenêtre H20 pourrait être auditée si les prix
sont complets ; une seule date ne suffira pas à qualifier un signal stable.
Conserver les vrais snapshots quotidiens et attendre plusieurs cohortes mûres,
puis reprendre le protocole figé, sans entraîner ni choisir la règle sur les
mêmes résultats de confirmation. L'emprunt et les coûts SHORT FR restent hors
de ce diagnostic : distinguer direction et possibilité réelle de vendre à découvert.

Résultats faisant foi :
`artifacts/fr/research/p0_p1_directional/20261026-v1-reviewed/report.json`.
Prix/observations figés et reçus initiaux :
`artifacts/fr/research/p0_p1_directional/20261026-v1`.
Chaque dossier possède son sceau ; aucune table SQL ou source collecteur modifiée.
