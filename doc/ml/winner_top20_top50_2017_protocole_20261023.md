# Winner : TOP20 et TOP50 en 2017, comparaison sans levier

GO du 23 octobre 2026. Deux grilles séparées, 300 profils chacune, période
du 2 juin au 31 décembre 2017. Aucun changement aux grilles décennales actives.

## Contrat figé

Même Oracle parcours H20 et mêmes folds causaux que le TOP10 archivé ; rangs
conservés avant contrôle qualité, jamais remplacés par des rangs suivants.
Source TOP100 déjà scellée du sélecteur global, sans utiliser ses labels,
features, poids ni décisions. Identité exacte de tous les TOP10 exigée.
Scores disponibles au plus tôt après clôture, entrée ultérieure confirmée.

Seule variable stratégique : TOP10 de référence contre TOP20 et TOP50.
Même capital initial 4 000 USD, demi-position, sans renforcement, 8 positions
maximum, risque natif B4/DD15 %, frais 8 bps par jambe, réserve de sizing 25 bps.
Plafond d'exposition effective 1x, identique au TOP10 ; pas de taille doublée.
Configuration de marge/règlement identique à la référence (capacité théorique
2x non utilisée pour relever le plafond de risque 1x). Les dérives mark-to-market
et intérêts éventuels sont conservés dans les résultats, pas effacés.

300 profils identiques : SL 3/5/7 %, trailing OFF/3/10/15/20 %, détention
5/10/15/20 séances, TP OFF/7/10/15/20 %. Sortie à l'ouverture suivant l'horizon
de détention, pas suivant le signal. Attente d'entrée 20 séances et deux
clôtures 5 minutes au-dessus du plus haut de la séance précédente après
cassure fraîche. Contrats gaps, frais, lifecycle et audit scalaire inchangés.

## Données et appariement

Les 39 titres TOP10 de 2017 gardent leurs snapshots intraday/daily, secteurs et
opérations sur titres déjà figés. Les 90 titres supplémentaires nécessaires
au TOP50 sont lus dans alpha_trade en transaction READ ONLY et archivés,
sans API fournisseur, entraînement, écriture SQL ni ordre. TOP20 et TOP50
partagent le même snapshot superset ; seuls leurs signaux diffèrent.
Jusqu'à 69 titres pour TOP20, 129 pour TOP50, avant contrôle de couverture.
Pas de relâchement de la qualification : fenêtre commune J..J+40, tronquée
à fin 2017, séances régulières SIP raw 5m complètes et prix/volumes qualifiés.
Opérations sur titres non prises en charge et secteurs manquants restent exclus.

## Exécution, reprise et sorties

Module : `scripts.research.us_winner_topn_2017_comparison_20261023`.
Dossier : `artifacts/research/us_winner_topn_2017/20261023-v1`.
Deux workers de priorité Windows inférieure, threads numériques limités à un ;
les grilles principales ne sont ni arrêtées ni modifiées, mais leur débit peut
diminuer avec la charge partagée. Smoke audité de 20 séances avant chaque grille.
Reprise sur les rapports scellés, vérifiés par SHA256, retries PermissionError
bornés. Ne pas éditer les sources scellées pendant l'exécution.

Suivi global : `progress.json`. Par grille : `top20/year-2017.json`,
`top50/year-2017.json`, rapports individuels dans `cases/`, `annual-2017.csv`,
puis `comparison-vs-top10.csv` avec deltas **à profil identique**. Le classement
des meilleurs 2017 est descriptif, pas une sélection validée de champion.
Mesures additionnelles : fraction du temps sans position, capital moyen investi
conditionnel à une position ouverte, exposition maximale. Métriques originales
inchangées : rendement net, capital final, DD, taux gagnant/perdant, gains/pertes,
durées et capital utilisé. Comparer aussi les couvertures et entrées effectives.

## Limites impératives

2017 partiel et déjà examiné ; petit échantillon, univers survivant actuel,
secteurs non PIT, historique daily révisé, corporate actions non exhaustives,
OHLC et non quotes/fills réels : pas de parité broker complète.
La sélection exige une couverture future et introduit un biais. TOP50 ne répare
pas les trous des titres TOP10. Un gain peut venir d'une meilleure couverture
ou de davantage de positions, pas d'une meilleure prédiction directionnelle.
Le meilleur parmi 300 essais peut être chanceux. Aucune promotion production.
