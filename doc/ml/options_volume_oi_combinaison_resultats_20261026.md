# US : volume call/put + open interest — pas de gain du mélange démontré

26 octobre 2026. **CALCUL ET REVUE TERMINÉS / EXPLORATOIRE / AUCUNE PROMOTION.**

## Conclusion

Le mélange fixe 50/50 ne dépasse pas le meilleur composant individuel dans les
trois horizons étudiés. À H20 primaire, volume0,5396, OI0,4926, mélange0,5244.
Il augmente l'AUC contre l'OI, mais diminue celle du volume. Cela ne démontre
ni un filtre rentable ni une impossibilité de complémentarité sur d'autres
périodes. Ne pas chercher maintenant les meilleurs poids sur ces quelques jours.

[Protocole figé](options_volume_oi_combinaison_protocole_20261026.md),
[amendement technique antérieur aux résultats](options_volume_oi_amendement_20261026.md).

## 1. Périmètre exact et intégrité

- US uniquement, fichier tradable courant :1 790symboles, pas uniquement TOP10.
- Cutoff V2 réel enregistré dans protocol.json le26octobre ; dernière séance
  close23octobre. Données fournisseur déjà en base seulement, READ ONLY /
  REPEATABLE READ / rollback dans alpha_trade. Aucun SQL écrit, appel fournisseur,
  LLM, entraînement, ordre, batch ou configuration de production modifié.
- 314 945snapshots OI indicatifs ;261 004barres options30Min ;63 681prix quotidiens
  EODHD+SIP, exportés sans mélange des sources.
- Source principale EODHD :4 566scores as-of/796titres, dont observations sans
  résultat encore qualifié. Source secondaire SIP :701scores/165titres.
- Deux features disponibles obligatoires, pas d'absence imputée0. Rangs calculés
  AVANT les filtres par qualité du chemin, maturité ou direction future.
- Sur l'intersection :même échéance retenue pour volume et OI dans4 566/4 566cas
  EODHD et701/701casSIP. Aucun conflit de versions simultanées détecté.
- La reprise des anciennes formules est contrôlée contre l'archive10octobre :
 4 150valeurs volume et4 045valeurs OI reproduites avec écart exactement0.

La V1 est un export technique conservé, sans calcul d'issue : son filtre1Day
captait un backfill tardif, pas la collecte prospective30Min. La correction et
la séparation des prix ont été figées AVANT lecture des performances. Aucun
seuil, poids, sens ou modèle n'a été adapté aux résultats ci-dessous.

## 2. Cible différente de l'ancien diagnostic

Comparer l'excursion favorable LONG à l'excursion favorable SHORT pendant H5,
H10 ouH20, chacune arrêtée définitivement à son propre stop adverse10%.
Entrée open de la séance suivant l'observation locale, décision09:25NewYork,
observed_at ET available_at avant décision. Gaps prioritaires ; intraday daily
inconnu conservé comme bornes. Direction retenue seulement si les bornes ne se
recouvrent pas ; sinon ambiguïté/égalité réservée. Maximum et date du maximum,
pas une vente réalisable au pic ni le premier retournement local du prix.

Les anciens0,547 portaient sur les déciles du rendement TERMINAL, à H5 pour le
volume et H3 pour l'OI. Les nombres ci-dessous ne sont pas leur réplication sur
la même cible, ni des taux de trades gagnants, ni une calibration probabiliste.

## 3. Résultats principaux, prix EODHD uniquement

Moyenne équipondérée des AUC par date à deux classes, trois scores sur exactement
les mêmes titres/dates. Une variable constante contribue0,5, pas une date supprimée.

| Horizon | Observations valides | Titres distincts | Dates | Volume seul | OI seul | Mélange50/50 |
|---|---:|---:|---:|---:|---:|---:|
| H5 secondaire |4 137|792|20|0,5286|**0,5507**|0,5482|
| H10 secondaire |3 631|788|15|**0,5452**|0,5262|0,5436|
| **H20 primaire** |406|139|5|**0,5396**|0,4926|0,5244|

Le composant supérieur est indiqué descriptivement, pas sélectionné comme futur
champion. À H5, le mélange bat le volume13/20dates, l'OI10/20 ; H10 :8/15 et10/15 ;
H20 :1/5 et5/5. Aucune affirmation de significativité corrigée n'est faite.
À H20,187LONG-dominants/219SHORT-dominants :ce ne sont PAS187gagnants/219perdants.

Prix EODHD disponibles10septembre–16octobre ; entrées effectivement évaluables :
H5 15septembre–12octobre ;H10 15septembre–5octobre ;H20 15–21septembre.

Les4 566candidats as-of sont conservés dans chaque horizon :

| Statut | H5 | H10 | H20 |
|---|---:|---:|---:|
| Label non ambigu |4 137|3 631|406|
| Prix/identité incomplets ou invalides |419|517|1 632|
| Parcours non mature au cutoff réel |0|416|2 528|
| Ambiguïté ou égalité |10|2|0|

Un horizon théoriquement mûr mais privé des derniers prix EODHD reste incomplet,
pas une performance supposée ni une barrière touchée. Aucun fallback SIP ne le remplit.

## 4. Contrôles sans optimisation

Dates d'entrée H-espacées et premières observations par titre choisies sur les
candidats as-of AVANT qualité/maturité des issues. Elles ne créent pas de nouveaux
régimes de marché indépendants.

| Contrôle EODHD | Observations valides | Dates informatives | Volume | OI | Mélange |
|---|---:|---:|---:|---:|---:|
| H5, dates espacées5séances |649|4|0,5096|**0,5617**|0,5435|
| H10, dates espacées10séances |485|2|**0,5546**|0,5096|0,5450|
| H20, dates espacées20séances |84|1|**0,5630**|0,5134|0,5566|

Première observation par titre, AUC GROUPÉE et non moyenne quotidienne :
H5 n790 :volume0,5478/OI0,5456/mélange0,5595 ;H10 n788 :0,5635/0,5633/0,5824 ;
H20 n139 :0,5773/0,4751/0,5384. Les petits gains H5/H10 de ce contrôle secondaire
ne remplacent pas l'échec d'amélioration primaireH20 ni les contrôles H-espacés.
Moitiés et retrait d'une date restent disponibles dans le rapport machine,
sans choisir après coup une fenêtre ou un estimateur plus favorable.

La fenêtre initiale et l'extension sont séparées par DATE D'OBSERVATION :
jusqu'au9octobre→entrée au plus tard12octobre ; depuis10octobre→entrée ensuite.
Pour EODHD, aucun parcours de l'extension n'est entièrement qualifié.
Cette extension n'est donc pas présentée comme une confirmation indépendante.

## 5. Sensibilité SIP séparée, pas de changement silencieux de prix

SIP :une ligne29septembre et presque tout le reste12–23octobre. Pas de parcours
historique SIP completH20 sur les candidats appariés, ni de résultatH10.

| Horizon | Observations valides | Titres | Dates | Volume | OI | Mélange |
|---|---:|---:|---:|---:|---:|---:|
| H5 |415|150|5|0,5227|**0,5671**|0,5594|
| H10/H20 |0|0|0|nonmesurable|nonmesurable|nonmesurable|

Entrées13–19octobre ;ces données récentes ne sont pas le même échantillon que
le tableau EODHD. Pas d'attribution d'une différence d'AUC au seul fournisseur.
À H5, l'OI reste supérieur au mélange sur cette courte extension ; ce n'est pas
une validation du signal OI, vu les cinq dates et les chevauchements.

## 6. Vérifications et conclusion pratique

16tests ciblés passent. Revue arithmétique hors ligne :5 267scores avant issue,
8 602parcours bornés et135AUC quotidiennes recalculés ; sceaux des entrées,
sources et sorties inchangés. Même assistant, pas une revue humaine indépendante.

Conserver l'expérience et collecter sans promotion. Pas de recherche d'un poids
qui gagne ici, pas de veto live, ni de modèle directionnel nouveau sur ce recul.
Pour répondre spécifiquement au TOP10 Oracle, il faudra une expérience distincte
alignant ses scores réellement disponibles et les mêmes dates :le présent test
sur titres couverts par les deux sources ne permet pas de conclure sur le TOP10.

Limites :univers survivant courant, très peu de dates indépendantes, OI/quotes
indicatifs, volume non signé et OPRA non attesté, ajustements/OST et vintages prix
non certifiés indépendamment, absence de neutralisation secteur/taille et de
simulation capital/frais/borrow/exécution. Aucun rendement économique démontré.

## Archives

- Canonique :`artifacts/research/us_options_equal_mix/20261026-v2/`.
- Chaque source :features/asof-scores/protected-paths parquet et report.json.
- Export initial non analysé :`artifacts/research/us_options_equal_mix/20261026-v1/`.
- Revue :`artifacts/research/us_options_equal_mix/20261026-v2-review/report.json`.
- Modules :`scripts.research.us_options_equal_mix_20261026`,
  `scripts.research.us_options_equal_mix_amended_20261026`,
  `scripts.research.us_options_equal_mix_review_20261026`.
- Aucune commande de reprise automatique sur un dossier terminé ; conserver
  ces dossiers immuables et utiliser un nouveau protocole/dossier pour une suite.
