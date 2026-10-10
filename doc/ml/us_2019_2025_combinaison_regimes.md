# US 2019–2025 — Confirmation descriptive M+V et audit des mois défavorables

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## Protocole fixé avant calcul, 4 octobre 2026

Demande : tester la combinaison momentum120 + volatilité60/ATR20 entre
2019 et2025, et rechercher des caractéristiques des mois défavorables.
2025 a déjà servi à choisir les features : aucune validation indépendante
ne sera revendiquée. 2019–2024 constituent une extension temporelle, sur
un univers actuel qui conserve une réserve de biais de survivance.

### Contrat figé

- Univers actuel `univers_filtred_tradable.txt`,1 798titres ; ne pas inventer
  leur présence avant introduction et ne pas considérer ce fichier comme
  univers tradable PIT complet de chaque année.
- OracleH20 batch `model-factory-20261003082853-e98332`, champions par fold.
  À chaque date : dernier champion avec `t_start <= date`. Aucun modèle
  futur. L'entraînement natif purge les labels non disponibles, le test ne
  pilote pas l'early stopping. Manifeste sans bornes train détaillées :
  vérification du contrat code, pas certification indépendante du fit.
- Reconstruction des features avec **les options exactes du batch** et
  les cours locaux ; sauvegarde des folds/hashes. 2025 réutilise le pool
  et scores de l'expérience initiale pour garantir la comparabilité.
- GateOracleTOP20 et ATR20TOP20 dans le même univers quotidien observé,
  puis intersection. Rangs des blocs à J avant jointure des rendements.
- M=rank(momentum120) ;V=(rank(volatilité60)+rank(ATR20))/2 ;MV=(M+V)/2.
  TOP10 etTOP20 du pool,ceil etexaequo symbole. Contrôles M,V,Oracleseul
  etpoolintersection. Pas de sentiment dans la confirmation principale :
  il dégradait M+V et son PIT n'était pas certifié.
- LabelsH20natifs en `dry_run=True` pour2019–2024,labels2025existants.
  Aucune écriture SQL. Labels invalides/manquants restent comptés, pas
  utilisés pour changer les gates. PrixH20ajusté et qualité natifs.

### Résultats et diagnostic prévus

Parannée,semestre etmois : effectifs, D10/D1, rendementbrutmoyen/médian,
proportiondehausse. Retours closeJ→closeJ+20 : descriptifs, non fills.
Dates de signal mensuelles, H20 peut déborder sur le mois suivant.
ComparerMVauxblocs seuls à même TOP, sans rechercher un nouveau seuil.

Audit des mois mauvais : mouvements SPY, distanceSMA200, volatilité,
drawdown marché observé àJ ; rendementSPYfutur explicatif seulement ;
momentum/volatilité et concentration de la sélection, attribution symbole
et secteurs actuels en contexte nonPIT. Données macro disponibles àJ
à examiner séparément : manque de donnée ne signifie pas régime neutre.
Ne pas fabriquer un switch de régime d'après les pertes constatées.

Un mois est signalé si rendement moyenMVTOP10<0. Classement des pires
mois pour diagnostic, pas sélection d'un sous-ensemble pour améliorer le
résultat global. Aucun lien causal automatique : un marché défavorable peut
expliquer une perte LONG sans fournir une règle prédictive d'abstention.

### Exécution / surveillance

Script : `python -m scripts.research.us_combination_history_regimes`.
Sortie : `artifacts/research/us_atr_oracle_sentiment/combination-history-2019-2025-20261004-v1/`.
`progress.json` donne année/phase ; un dossier parannée stocke features,
scoresOracle,labels etévaluations. `report.json` final n'est créé qu'après
les sept années. Reprise permise des panels/labels complets, pas d'écrasement
d'artefacts incohérents. Logs dans
`log/batch/us-combination-history-2019-2025-20261004/`.

Aucun entraînement, tuning des poids, coût, portefeuille, SQLwrite ni
modification de batch en cours. Réserves : survivance, PIT contexte,
rendements chevauchants, sélection exploratoire, absence de statistiques
groupées et de confirmation réellement intacte.

## Extension explicite au premier trimestre 2026

**Calcul et audit terminés le 4 octobre 2026.** Voir le
[rapport détaillé 2019–2026 T1](us_2019_2026_audit_regimes_combinaison.md)
pour les résultats annuels, mensuels, secteurs, concentration, couverture
macro et réserves PIT. Aucun veto prédictif n'est validé.

L'utilisateur demande aussi janvier,février,mars2026 : ne pas limiter le
diagnostic à février2025 ni supposer cesmois forcément mauvais avant calcul.
Run séparé sans interrompre2019–2025 :

`python -m scripts.research.us_combination_history_regimes --start-year 2026 --end-year 2026 --end-date 2026-03-31 --output artifacts/research/us_atr_oracle_sentiment/combination-history-2026q1-20261004-v1`

Mêmebatch,dernierchampioncausal etpoidsM+Vfigés. Rapportdescriptive2026,
sans entraînement àfin2025, ni ajustementa posteriori. H20desdernières
datesdemars nécessite lescoursenavril disponibles enbase.

**Question d'anticipation :** expliquer les pertes ne prouve pas qu'on
pouvait les prévoir. Chercher changements de SPY/momentum/volatilité,
compositionsecteur,bêta etconcentration observablesàJ. Toute règle de veto
future doit être définie surune période distincte, purgée des labelsH20,
puis mesurée sur confirmation sans ajustement. Ne pas calibrer un veto sur
janvier–mars2026 pour annoncer qu'il anticipe ces mêmesmois.
