# Consensus Yahoo — restauration sélective et premier audit directionnel

**État courant au 10 octobre :** l'utilisateur a de nouveau désactivé la
collecte Yahoo (`enabled: false`, `BLOCKED_YAHOO_AUTOMATED_ACCESS`). La
restauration et les résultats ci-dessous sont conservés, sans nouveau
téléchargement ; EODHD reste une alternative envisagée et non activée.

## Restauration effectuée le 10 octobre 2026

Sur GO utilisateur, extraction de la sauvegarde du 4 octobre
`backups/db/alpha_trade_without_news_20261003_230004.sql.gz` et réinjection
des seules six tables analystes. Aucune restauration globale, aucune suppression,
aucun écrasement des observations actuelles. Les dates d'observation, de disponibilité,
d'ingestion et les payloads archivés sont conservés ; les IDs auto-incrémentés
sont régénérés pour ne pas entrer en collision avec les données actuelles.

| Table | Lignes archivées ajoutées |
| --- | ---: |
| analyst_snapshot_collection_run | 57 |
| stock_analyst_estimate_history | 510 916 |
| stock_analyst_eps_trend_history | 142 980 |
| stock_analyst_eps_revision_history | 142 980 |
| stock_analyst_target_history | 71 044 |
| stock_analyst_recommendation_history | 212 190 |
| Total | 1 080 167 |

Les clés métier servent à détecter les doublons. Les valeurs actuelles gagnent
en cas de conflit ; aucune utilisation de REPLACE ou de suppression de table.
Le second contrôle trouve zéro ligne archivée manquante et zéro conflit de hash
sur les cinq tables de données. Il ne réinsère pas les lignes.

Une collecte du 10 octobre était aussi présente : elle n'a été ni arrêtée ni
remplacée. Les compteurs globaux peuvent donc augmenter indépendamment de cette
restauration. Des copies des lignes actuelles avant fusion sont conservées par
table dans `*.before.jsonl.gz` ; ce ne sont pas une sauvegarde transactionnelle
globale ni des dumps SQL directement exécutables.

Les tables restaurées contiennent des univers historiques plus larges que
l'univers actuel. L'analyse ci-dessous est limitée au fichier tradable actuel.
Les premières estimations/objectifs/recommandations remontent au 29 août,
mais les tendances et compteurs de révisions EPS commencent au 13 septembre.
Les réserves sur les droits Yahoo restent inchangées.

## Protocole exploratoire fixé avant le calcul

- Univers : `config/univers_batch/univers_filtred_tradable.txt`, 1 790 titres,
  empreinte enregistrée dans le protocole JSON. Univers actuel, pas un univers
  historique exempt de biais de survivance.
- Aucun entraînement, changement de seuil de modèle ou branchement live.
- Pour chaque observation, contrôle de `available_at` contre la prochaine
  clôture NYSE strictement après `observed_at`. Aucun timestamp recalculé en base.
  Zéro ligne PIT rejetée dans les trois familles testées.
- Décision à cette clôture ; entrée à l'ouverture de la séance suivante ; sortie
  à la clôture de la Hème séance, entrée comprise, à H3/H5/H10/H20.
- Dernières barres utilisées : 9 octobre inclus. Aucune observation immature
  n'est transformée en rendement nul ou en résultat réalisé.
- Chemins canoniques split-adjusted : prix et volumes positifs, OHLC cohérents,
  aucune barre remplie, instrument renseigné et stable sur le chemin. Couverture
  d'au moins 90 % du fichier pour définir les déciles signés. Les prix ne sont
  pas pour autant requalifiés indépendamment titre par titre.
- D1/D10 = déciles des **rendements signés** de l'univers qualifié, et non les
  déciles d'amplitude Oracle. Ce test ne sélectionne pas le TOP20 Oracle.
- Dernière observation par symbole et date de disponibilité, sans remplir
  artificiellement les jours sans snapshot.

Quatre scores, sans optimisation de poids :

1. Révisions EPS du trimestre courant sur 7 jours : `(hausse-baisse)/(hausse+baisse)`.
2. Même score sur 30 jours. Zéro si les deux compteurs valent zéro, valeur absente
   si des compteurs manquent ou sont négatifs.
3. Objectif moyen rapporté au cours canonique à la décision, moins un.
4. Recommandations période `0m` :
   `(2×strong_buy + buy - sell - 2×strong_sell)/nombre total`.

Une valeur plus forte est supposée favorable à D10. La sélection descriptive
prend les 20 % de scores les plus hauts parmi les titres couverts, avec un
départage fixe par symbole. Comparaison à la baseline **des mêmes titres couverts**.
Les taux ci-dessous sont des moyennes par séance, pas un rendement de portefeuille.

Les horizons fiscaux relatifs restent imparfaitement identifiés : aucun delta
temporel de consensus EPS/revenus n'est construit en reliant des trimestres qui
pourraient être différents. Les tendances et les estimations sont restaurées,
mais pas encore exploitées comme features de changement de niveau.

## Premier résultat

### Compteur net de révisions EPS à 30 jours

| Horizon | Dates d'entrée | AUC D1/D10 globale | AUC première / seconde moitié | D10 sélection / baseline | D1 sélection / baseline |
| --- | ---: | ---: | --- | --- | --- |
| H3 | 16 | 0,596 | 0,634 / 0,558 | 13,49 % / 10,30 % | 8,75 % / 10,33 % |
| H5 | 15 | 0,616 | 0,643 / 0,593 | 14,54 % / 10,36 % | 8,43 % / 10,23 % |
| H10 | 10 | 0,679 | 0,711 / 0,647 | 16,53 % / 10,47 % | 6,59 % / 10,23 % |
| H20 | 0 | Non mesurable | Non mesurable | Non mesurable | Non mesurable |

H10 : 16 067 observations symbole-date, dont 3 326 dans D1 ou D10, sur les
entrées du 15 au 28 septembre. Le score à 7 jours présente aussi une séparation
H10 : AUC 0,648, sélection D10 14,54 % et D1 7,67 %.

**Signal exploratoire intéressant, pas une validation de profitabilité.** Les
moitiés chronologiques ne sont pas indépendantes : les rendements se chevauchent,
les mêmes symboles et scores reviennent et un régime court peut expliquer une
partie de l'effet. Aucun intervalle de confiance indépendant, contrôle secteur/
taille/momentum ou confirmation dans une autre période n'est établi.

### Objectifs et recommandations à H20

Neuf dates d'entrée sont matures pour ces familles plus anciennes :

- Objectifs : AUC 0,548 globale, mais 0,628 puis 0,489 dans les deux moitiés.
  Le TOP20 augmente D10 à 19,57 %, **mais aussi D1 à 13,49 %**, contre environ
  9,9 % chacun dans la baseline. Une concentration d'amplitude/risque n'est donc
  pas à confondre avec une séparation directionnelle robuste.
- Recommandations : AUC 0,567 globale, mais le TOP20 donne D10 9,22 % et
  D1 10,46 %, sans amélioration des taux de sélection.

Les révisions EPS n'ont aucune entrée déjà mature H20 : leurs premières
observations disponibles sont le 14 septembre, pour une entrée au 15 septembre.
Les données du 10 octobre sont exclues des décisions historiques, leur
disponibilité se situant après la période évaluée.

## Suite exécutée : contrôles de secteur et momentum

Diagnostic distinct dans `artifacts/research/analyst_archive_restore/20261010/controls/`.
Le momentum20 est calculé sur les 21 clôtures qualifiées précédant et incluant
la décision, sans utiliser le futur. Les secteurs viennent du mapping actuel
archivé le 7 octobre : **métadonnées non PIT**, uniquement pour un contrôle
rétrospectif, pas une stratégie sectorielle historiquement validée.

Neutralisation descriptive : percentile du score de révisions dans chaque
groupe date × secteur × quintile de momentum, au moins 20 titres couverts
par groupe. Aucun modèle, régression entraînée ou seuil optimisé. Cette
transformation change le classement : elle n'est pas une preuve causale.

Comparaison H10 sur la même couverture après exclusion des groupes trop petits :

| Score | AUC D1/D10 | D10 TOP20 | D1 TOP20 |
| --- | ---: | ---: | ---: |
| Révisions30 brutes | 0,695 | 17,30 % | 6,39 % |
| Révisions30 neutralisées secteur/momentum | 0,595 | 7,16 % | 8,27 % |
| Baseline sur les titres couverts | — | 11,26 % | 9,34 % |

L'AUC neutralisée reste 0,623 puis 0,572 dans les deux moitiés, **mais le
TOP20 neutralisé n'enrichit pas D10**. La séparation parmi les seuls extrêmes
ne garantit donc pas que les scores les plus élevés identifient les futurs
gagnants parmi tous les titres. Le momentum20 seul sur les titres ayant des
révisions a une AUC H10 de 0,535 ; la relation n'est pas simplement une copie
du momentum, mais son apport exploitable reste non confirmé.

Décalage des observations pour ne pas chevaucher les chemins : H3 donne six
dates, H5 trois, et **H10 une seule**. Ces dates ne suffisent toujours pas à
une confirmation temporelle indépendante. Le TOP10 des symboles les plus
répétés pèse environ 3,1 % des sélections brutes ; la concentration sectorielle
et la période peuvent néanmoins peser. Conclusion : piste à conserver et à
confirmer sur des données futures, aucun GO portefeuille.

Script `scripts/research/analyst_revision_controls.py`, protocole enregistré
avant calcul, un test supplémentaire de rangs/ties/petits groupes réussi.
Aucune nouvelle écriture SQL depuis la restauration.

## Quels champs ont réellement fourni le premier résultat ?

| Famille | Résultat de ce test |
| --- | --- |
| Compteurs de révisions EPS hausse/baisse à 30 jours | Meilleur signal brut H10 ; stabilité économique non confirmée après contrôles |
| Compteurs de révisions EPS hausse/baisse à 7 jours | Signal brut plus faible, AUC H10 0,648 |
| Niveau du consensus EPS | Restauré, pas testé isolément |
| Niveau du consensus revenus | Restauré, pas testé isolément |
| Nombre d'analystes | Restauré, pas testé comme signal isolé ni utilisé pour normaliser les scores |
| Valeurs EPS actuelles et références J−7/30/60/90 | Restaurées, pas à l'origine des AUC annoncées ; fiscalité des horizons à qualifier |
| Objectifs de cours | Testés ; H20 instable et concentration simultanée D10/D1 |
| Recommandations achat/conserver/vendre | Testées ; pas d'amélioration de sélection TOP20 démontrée |

Ne pas confondre le compteur net des révisions sur 30 jours avec la variation
du consensus EPS entre aujourd'hui et J−30 : ce sont deux variables différentes.
Les objectifs et recommandations ne semblent pas indispensables **au signal
brut actuellement observé**, mais cela ne prouve pas leur inutilité générale.
Il n'y a pas encore de comparaison directe Yahoo/EODHD sur les mêmes titres.

## Trente jours de collecte ne donnent pas 120 jours de backtest PIT

Trente snapshots quotidiens contenant des références jusqu'à J−90 peuvent
porter sur une étendue calendaire d'environ 120 jours. Cela dépend des valeurs
présentes, de la convention de jours, des changements d'exercice et des
corrections du fournisseur : ce n'est pas automatiquement une série quotidienne
complète ou comparable.

Surtout, la première récupération du jour J n'a été **observée qu'à J**, y
compris ses champs « 90 jours auparavant ». Ne pas antidater `observed_at` ou
`available_at` à J−90. Ces références peuvent former des features de tendance
utilisables après la collecte J ; elles ne permettent pas de prendre une
décision PIT simulée à J−90 sans preuve indépendante de disponibilité à l'époque.
Le support EODHD a explicitement exclu un vrai historique as-known/PIT pour
ces données. Avec un mois de collecte, on a un mois de snapshots prospectifs
qualifiables, enrichi de références rétrospectives, pas quatre mois de décisions.

## Suite proposée, pas encore exécutée

Conserver ce protocole pour confirmer les révisions sur les nouvelles dates et
H20 à maturité ; compléter le contrôle de taille et des événements de résultats.
Ensuite seulement, tester leur apport dans les
candidats Oracle et une simulation économique avec coûts. Aucune promotion
de modèle ou d'exécution n'est autorisée par ce seul audit.

## Preuves et reproduction

- Dossier : `artifacts/research/analyst_archive_restore/20261010/`.
- `extraction.json` : colonnes archivées, empreintes des extraits.
- `restore.json` : lignes effectivement ajoutées ; `preview.json` : dernier
  contrôle idempotent après restauration.
- `directional/protocol.json`, `report.json`, `features.parquet`, `panel_h*.parquet` :
  protocole, inventaire, métriques et observations évaluées.
- Scripts : `scripts/research/restore_analyst_archive.py` et
  `scripts/research/analyst_restored_directional_audit.py`.
- Quatre tests ciblés passent : extraction sur allowlist, intégrité des extraits,
  refus d'un schéma absent, score de révision et disponibilité après clôture.

Commande de l'analyse seule (SELECT uniquement) :

```powershell
python -u -m scripts.research.analyst_restored_directional_audit
```

Attention : les dates de fin sont volontairement figées dans cette version.
Une confirmation ultérieure doit garder une trace distincte du protocole et
de son cutoff, sans écraser les résultats de cette première étude.
