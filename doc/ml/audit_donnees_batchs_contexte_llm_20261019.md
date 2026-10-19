# Données des batchs US à transmettre au LLM — audit du 19 octobre 2026

**Suite implémentée après cet audit :** le
[paquet frais v7](llm_preuves_fraiches_20261019.md) ajoute calendrier, SEC et
résumés prix/volume/fondamentaux aux prochaines analyses, avec contrôles de
fraîcheur. L'inventaire ci-dessous conserve ses constatations et son périmètre
historiques ; les paragraphes « constructeur actuel » décrivent l'état audité
avant cette livraison, pas le nouveau payload v7. Pas de qualification SQL
automatique ni de réécriture du run v4 existant.

## Conclusion

Oui : en priorité, **calendrier des résultats et documents SEC**, puis un résumé
des fondamentaux SEC, du contexte marché et des opérations sur titres. Il ne faut
pas envoyer toutes les tables ni confondre contexte, preuve directionnelle et
condition d'exécution. Aucun gain D1/D10 ou rendement supplémentaire n'est démontré
par cet inventaire.

L'audit ne change ni les prompts, ni le payload opérationnel, ni les modèles,
ni les batchs. Aucun appel fournisseur/LLM, ordre, entraînement, backtest ou
écriture SQL. Seuls ce document, un outil de recherche et ses rapports locaux
sont ajoutés. Les droits Yahoo/FINRA/FRED ne sont pas réactivés.

## Périmètre et preuves

- Base réelle `alpha_trade`, transaction en lecture seule.
- Univers `config/univers_batch/univers_filtred_tradable.txt` : **1 790 symboles**.
- Inventaire prioritaire des batchs P0/P1 ; contrôles complémentaires P2/P3/P4
  pour options, événements SEC normalisés, macro publique et IPO.
- Fenêtre de réception/mise à jour de 30 jours, bornée au cutoff UTC réel du
  rapport. Dates d'événement, de publication, de collecte et de calcul séparées.
- Rapport de référence : `artifacts/research/us_llm_batch_evidence/20261019-v2/report.json`.
  Zéro erreur de requête. V1 conservé : une requête SEC trop lourde y avait expiré ;
  V2 retire l'agrégation sur les gros textes et couvre le contrôle par formulaire.
- Les couvertures ci-dessous comptent des titres ayant au moins une observation
  récente, **pas** des titres tous à jour à J ni une qualification complète PIT.
  `available_at` est le champ déclaré par chaque collecteur, pas une certification
  indépendante de première disponibilité. `fetched_at/updated_at` sont des dates
  de récupération/mise à jour, pas des preuves de contenu historique immuable.

## Ce que reçoit déjà le LLM

Le constructeur actuel transmet identité locale, score/rang Oracle, horizon et
jusqu'à 21 clôtures jusqu'à J. `local_evidence.py` ajoute dans **les deux modes**
le consensus EODHD et les news archivées recevables, avec un cutoff figé.
Il ne transmet pas automatiquement les calendriers, fondamentaux, documents SEC,
macro, options ou contraintes de borrow.

**Attention à l'historique réellement exécuté :** le dernier run LLM en base,
`llm-fa604bed142d41a7be61012432c1fc6e`, séance du 16 octobre, est encore au
protocole v4. Ses dix contextes archivés ne contiennent ni consensus ni preuves
locales. Le code enrichi concerne les prochaines analyses ; il ne réécrit pas
ce run et n'a pas encore été exécuté en réel lors de cet audit.

## Priorités proposées

| Priorité d'ajout | Collecte / tables | Constat réel sur l'univers | Utilité et réserves |
|---|---|---|---|
| 1 | Étape 5 de `us_pipeline` / `stock_earnings_calendar` | **1 297 titres** avec au moins une date dans les 35 prochains jours ; **les 10 titres du dernier run LLM** ont une prochaine date | Date prochaine, jours/séances restants, EPS/revenus estimés disponibles. Catalyseur et incertitude, pas direction garantie. Pas d'heure d'annonce dans cette table : ne pas inventer avant/après séance. |
| 1 | `sec_edgar_incremental` P0 / `sec_filing_raw`, `sec_filing_documents` | **1 028 dépôts / 577 titres** reçus sur 30 jours ; **333 pièces EX-99* / 208 titres** | Source primaire pour résultats, perspectives, financement, risques matériels, acquisitions et dirigeants. Sélectionner des extraits récents, attribués au bon émetteur, avec accession, URL et citations. Toutes les pièces EX-99 ne sont pas des guidances. |
| Déjà raccordé au code, qualification prioritaire | `eodhd_consensus_snapshot` P1 / `stock_analyst_consensus_eodhd_history` | **1 778 titres**, huit jours d'observations ; EPS, revenus, analystes, références J−7/30/60/90 et compteurs de révisions présents | Déjà transmis aux nouvelles analyses. Comparer mêmes exercices/périodes, variation du consensus, dispersion et nombre d'analystes. Toute la population récente inspectée est encore `RESEARCH_ONLY`, unités et identité fiscale non qualifiées. |
| 2 | `market_cap_sync` P0 + collecte des fondamentaux de l'étape 2 / `stock_market_cap_daily`, `stock_fundamentals_daily` | Capitalisation calculée : **1 784 titres**. Fondamentaux SEC récupérés récemment : **141 titres**, dont 130 avec revenus, 125 avec EPS, 66 avec dette/fonds propres | Taille, dilution potentielle, croissance, marges, endettement, valorisation si calcul qualifié. Contextualiser sans confondre un petit PER avec un LONG. Les 141 titres ne sont pas toute la couverture historique : des rapports trimestriels plus anciens restent en base. |
| 2 | `corporate_actions_sync` P0 / `corporate_action_source_events` | **719 observations / 456 titres** sur 30 jours | Splits, regroupements, dividendes, fusions et changements d'identité : expliquer les mouvements mécaniques et les risques d'interprétation. Un split n'est pas un signal haussier. |
| 2 | `security_master_snapshot` P0 / `security_master_snapshots`, `security_master_changes` | **1 674 titres** observés sur 30 jours | Désambiguïsation symbole/émetteur/type d'instrument ; contexte pour éviter d'analyser une société homonyme ou une classe de titre différente. Pas un signal directionnel autonome. |
| 2 | Étape 1 de `us_pipeline` P0 / `stock_bars_daily` | Le constructeur actuel ne joint que les clôtures de 21 séances au plus ; cet audit ne recompte pas la couverture OHLCV canonique | Ajouter un résumé calculé jusqu'à J : gap, performance 1/5/10/20 séances, volume relatif qualifié, amplitude/range et force relative à SPY. Utile pour juger si une nouvelle a déjà été intégrée au prix. Préciser le flux, les ajustements et les valeurs manquantes ; le volume IEX/indicatif ne doit pas être assimilé au consolidé. |
| 2, après contrôle de fraîcheur | `stock_macro_indicators_daily` et `public_macro_snapshot_sync` P4 / `macro_public_observation_versions` | Macro publique : inflation/emploi BLS jusqu'à septembre ; taux H15 jusqu'au **15 octobre** | Petit bloc partagé : niveau/tendance des taux, courbe, inflation/emploi et stress volatilité si source qualifiée. Pas un veto LONG réajusté sur les pertes. Les périodes macro ne sont pas leurs dates de publication. |
| Différer jusqu'au rafraîchissement et à la liaison de versions | Étape 8 / `ticker_daily_sentiment_features`, `news_ticker_sentiment` | Dernière séance agrégée trouvée : **9 octobre**, mise à jour le 10. J−1/J−2/J−5 possibles seulement quand réellement disponibles | Résumé de dynamique, volume de news, polarité, contradiction et antériorité. Un score positif est une tonalité, pas une probabilité de hausse. Les scores courants ne prouvent pas une correspondance immuable au texte archivé transmis. |
| Optionnel, recherche d'abord | `oracle_options_indicative_snapshot` P2 / `stock_option_snapshots` | **1 635 titres**, 240 484 lignes reçues sur 30 jours | Résumé IV/skew/asymétrie call-put éventuellement utile avec liquidité, date et provenance. Flux **indicatif, pas OPRA/NBBO** ; ne pas présenter les prix/volumes comme consolidés ni un ratio put/call comme direction certaine. |
| Risque/exécution, pas preuve directionnelle | `borrow_status_snapshot` P1 / `stock_borrow_status_snapshots` | **1 750 titres** observés sur 30 jours | Shortable/easy-to-borrow : admissibilité et faisabilité du SHORT. Cela ne démontre ni baisse future ni coût d'emprunt. Vérification fraîche conservée dans le moteur de risque. |
| Risque/exécution, pas preuve directionnelle | Étape 4 / `stock_quote_snapshots` | **1 651 titres** avec réception récente dans le champ `collected_at` | Spread/liquidité et fraîcheur SIP utiles au contrôle d'entrée, pas pour convaincre le LLM d'un sens de marché. Snapshot de clôture ancien ≠ quote exécutable actuelle. |
| Qualité des prix, pas nouvelle information directionnelle | `daily_bars_sync` P0 / `stock_bars_daily_versions` | **1 654 titres** sur 30 jours ; dernière réception versionnée trouvée le 12 octobre | Provenance/corrections, écart éventuel avec les barres canoniques. Ne pas confondre cette table avec l'alimentation de `stock_bars_daily` par l'étape 1. |

Les sauvegardes P0 `ml_artifacts_backup`, `db_core_backup`, `db_news_raw_backup`
n'apportent aucune information de direction : ne pas transmettre leurs données
d'exploitation, accès ou inventaires de fichiers au LLM.

## Réserves observées

### 1. Mode local : les preuves admises ne sont pas encore qualifiées

Les **1 170 331 lignes** de consensus récentes inspectées sont toutes
`RESEARCH_ONLY`, `units_qualified=0`, `fiscal_identity_qualified=0`.
Sur **28 655 mappings de news** récents inspectés globalement, aucun n'a
`mapping_context.identity_qualified=true`.

Avec `analysis_mode: local_data_only` actuellement configuré,
`min_local_sources: 1` et le constructeur limité à ces deux familles,
ces observations n'offrent pas de preuve locale qualifiée autorisant une
nouvelle sélection. Le LLM peut les commenter ; un avis LONG/SHORT ne serait pas
admissible en l'état. Le mode Web peut satisfaire sa propre exigence de sources
Web qualifiables, sans promouvoir les données locales.

Ne pas résoudre cela en mettant arbitrairement tous les flags à vrai, en
supprimant le minimum de preuves ou en assimilant le mapping fournisseur à une
vérification indépendante. Qualifier le sous-ensemble réellement transmis.

### 2. SEC : le contenu brut est plus riche que la normalisation actuelle

Le corpus récent contient notamment 658 dépôts 8-K, 300 6-K, 31 10-Q et 12 10-K
dans l'univers. Mais `sec_corporate_events` ne contient que **8 événements pour
6 titres** sur la même fenêtre. Le normaliseur cherche des en-têtes `ITEM`
au moyen d'une expression régulière ; il ne constitue pas une extraction
sémantique exhaustive des événements, notamment dans le HTML.

Il faut donc partir des dépôts/pièces pertinents plutôt que conclure « aucun
événement » à partir de cette seule table. Les pièces EX-99* disponibles dans
le sous-ensemble inspecté ne dépassent pas le 3 octobre : ne pas promettre un
corpus de communiqués frais pour tous les titres.

Raccordement requis : identité CIK/émetteur, formulaire, vraie date d'acceptation,
réception réelle, amendements, références et extraits attribuables. Les upserts
SEC peuvent modifier `available_at`, et les événements normalisés héritent de
la date du brut : ce n'est pas une garantie de première disponibilité de la
version/normalisation. Vérifier aussi la fin du run producteur/normaliseur avant
cutoff et figer le paquet réellement envoyé ; aucune reconstruction PIT ancienne
ne doit être prétendue à partir de ces seuls champs.

### 3. Fondamentaux : provenance à filtrer

La fenêtre récente contient aussi **2 583 lignes étiquetées `Yahoo Finance` pour
310 titres**, et 207 lignes Finnhub pour 23 titres. Ces lignes Yahoo sont un
constat historique en base, pas la preuve d'un appel Yahoo encore actif après
son retrait du code. Ne pas les envoyer via un fallback implicite. Le petit
sous-ensemble Finnhub inspecté n'a pas de revenus/EPS/dette/marges non NULL :
il ne remplace pas les comptes SEC pour ces données.

Pour la capitalisation calculée, respecter `available_date` et la date du cours,
la base du nombre d'actions, les événements sur titres, les classes/ADR et la
mention `ESTIMATE_NOT_OFFICIAL`. Réception/computation seule ne suffit pas si
le contrat rend l'observation disponible au jour suivant.

### 4. Macro : quelques champs ne doivent pas être présentés comme frais

La dernière ligne `stock_macro_indicators_daily`, au 16 octobre, a `mode=NULL`
et `sentiment_score=NULL`. VIX, VIX9D, VXN, VIX3M, MOVE et ten_y y sont exactement
identiques aux valeurs de la ligne du 2 octobre. Ce constat demande une
vérification de source/fraîcheur ; il **ne prouve pas** à lui seul un bug ou un
report automatique. Ne pas présenter un régime calculé manquant ou un cache
non qualifié comme information de séance fiable. Préférer les observations
producteurs publics versionnées pour les séries qu'elles couvrent, avec
période et date de réception distinctes. Ne pas réutiliser l'archive FRED bloquée.

### 5. Ownership : pas de signal prêt à transmettre

`sec_ownership_snapshots` ne couvre que **4 symboles de l'univers** récemment.
Le normaliseur affecte `issuer_symbol` à partir du symbole du dépôt, alors que
pour un 13F le déclarant et l'émetteur détenu sont différents. Lier d'abord
CUSIP/émetteur et distinguer la date du portefeuille de la date du dépôt.
Ne pas annoncer « les institutionnels achètent ce titre » sur ce raccordement
non qualifié ni assimiler des positions trimestrielles retardées à un flux du jour.

## Cas concret : dix titres du dernier run LLM

Toutes les dix lignes ont un snapshot de consensus du 18 octobre et une
prochaine date de résultats en base. Ces dates sont des estimations calendaires
non certifiées, sans heure d'annonce.

| Symbole | Prochaine date en base | Dépôts SEC reçus sur 30 jours | Dernière séance de sentiment agrégée |
|---|---|---:|---|
| CCOI | 2026-11-05 | 0 | 2026-10-08 |
| ICHR | 2026-11-02 | 0 | 2026-10-01 |
| BAND | 2026-10-29 | 0 | 2026-10-08 |
| FUN | 2026-11-05 | 0 | 2026-10-02 |
| UCTT | 2026-10-26 | 1 | 2026-09-28 |
| FMC | 2026-10-27 | 2 | 2026-10-08 |
| MXL | 2026-10-21 | 0 | 2026-10-09 |
| COHR | 2026-11-03 | 0 | 2026-10-09 |
| TXG | 2026-11-04 | 0 | 2026-10-09 |
| DOCN | 2026-11-03 | 0 | 2026-10-06 |

Zéro dépôt dans cette requête n'est pas une preuve d'absence de nouvelles
publiques : collecte limitée, formulaire, rattachement et fenêtre sont en jeu.
Les comptes SEC de ces dix symboles ont leur dernier `fetched_at` au 13 septembre :
ne pas les annoncer comme fraîchement collectés en octobre ; ils peuvent rester
pertinents comme derniers comptes connus si la période et la disponibilité sont qualifiées.

## Paquet recommandé pour une évolution ultérieure

1. **Qualité avant volume** : qualifier identités/périodes/unités des éléments
   réellement utilisés ; expliciter donnée absente/périmée, sans faux zéro.
2. Par candidat : calendrier des résultats, consensus déjà raccordé, quelques
   extraits SEC/news significatifs, résumé fondamental et technique jusqu'à J.
   Résumer les changements à 1/5/10/20 séances et la force relative au marché,
   sans envoyer cent features brutes ni créer une règle directionnelle non testée.
3. Petit bloc global commun : macro publique et volatilité qualifiées, avec
   dates des données et contradictions, sans override des garde-fous de risque.
4. Archiver exact contexte, cutoff, sources, versions, qualifications et champs
   manquants ; nouvelle version de protocole, anciennes réponses inchangées.
5. Étendre explicitement les types de preuves et leurs contrôles : le validateur
   actuel ne connaît que consensus/news ; ne pas déguiser un compte ou une série
   macro en article pour contourner ses règles.
6. Après GO distinct, comparer les mêmes candidats avec/sans enrichissement,
   en conservant coût et taux d'abstention. Mesurer ensuite les résultats arrivés
   à maturité ; aucune hausse de confiance ne vaut preuve d'efficacité.

Ne jamais transmettre des rendements futurs H20, listes d'extrêmes réels,
labels D1/D10, PnL futurs ou sorties réalisées de l'étude
`oracle_atr_market_regime_daily`. Ni secrets, holdings, informations de compte
ou ordres. Le LLM reste un filtre de tendance, pas le moteur d'exécution.

## Reproduction et code contrôlé

```powershell
python -m scripts.research.us_llm_batch_evidence_audit --output-dir artifacts/research/us_llm_batch_evidence/NOUVEAU_DOSSIER
```

Le dossier doit être neuf. Requêtes bornées à 15 secondes ; erreurs explicites
dans le rapport, jamais transformées en « table vide ». Dates et compteurs peuvent
évoluer avec les collectes concurrentes ; cet inventaire n'est pas un snapshot
global atomique de toute la base.

Code : `service/llm_directional/runner.py`, `local_evidence.py`, `validation.py`,
`service/forward_pit/batch.py` (collectes SEC, normalisation et corporate actions),
`service/forward_pit/market_cap_calculations.py`, `service/eodhd/consensus_snapshot.py`,
`service/forward_pit/public_macro.py`, `event_sentiment/db_io.py`.
