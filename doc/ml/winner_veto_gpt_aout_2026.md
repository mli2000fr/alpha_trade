# Winner LONG seul contre veto des scores GPT1–3 — août2026

## Comparaison bornée

Demande utilisateur après le diagnostic des deux excursions : utiliser GPT pour
écarter des achats LONG, pas ouvrir de shorts. Amendement avant le lancement :
**SL fixe7%, sans trailing, sans TP** dans les deux comptes. H20 maintenu,
vingt séances depuis l'entrée puis sortie open21. Pas de recherche de nouveaux
seuils à partir du résultat de ce test.

420 signaux TOP20 Oracle des21 séances d'août2026,37 titres. Même archive annuelle
Oracle et mêmes avis GPT que `gpt_top20_aout_2026_deux_extremes.md`. Aucune nouvelle
prédiction, aucun entraînement ou appel LLM. Les avis furent produits après les
événements : test rétrospectif non PIT, mémoire du LLM non exclue.

Deux comptes indépendants4000USD début août, LONG uniquement, mêmes règles :

- Winner natif, demi-position, sans renforcement, deux confirmations5min au-dessus
  du plus haut de la séance précédente ; attente d'entrée maximale20 séances ;
- jusqu'à8 positions, contraintes risque/corrélation/secteurs natives, plafond
  brut effectif1x, financement natif et frais8pb par jambe ;
- paramétrage risque de la référence native scellée, B4/DD15 d'allocation.
  **Ne pas confondre avec les expériences séparées de liquidation DD25/pause** ;
- overlays factoriels non qualifiés désactivés identiquement comme dans la référence,
  et refus natif des demi-positions ne permettant pas une action entière conservé ;
- signaux du3 au31 août seulement, portefeuille suivi jusqu'au30 septembre.
  Les positions encore ouvertes sont valorisées, pas vendues artificiellement.

Le témoin admet tous les signaux communs qualifiés. Le filtre exclut uniquement
un avis **VALID, score entier1,2 ou3**. Les105 réponses invalides et les avis
indéterminables restent sans veto ; absence de preuve n'est pas un short.
Il existe30 avis admissibles au veto initial, tous notés3. Ce seuil inclusif
est propre à l'expérience : les seuils live YAML ne sont pas modifiés.

Rangs Oracle inchangés ; aucun remplacement TOP21. Le veto précède uniquement
la création d'un nouveau plan. Il ne vend pas une position déjà ouverte et ne
réécrit pas un plan plus ancien encore valide. Ce n'est pas un suivi quotidien
de sortie fondé sur l'avis GPT le plus récent.

## Données, contrôles et limites

Nouveau dossier : `artifacts/research/us_winner_gpt_veto_august_2026/20261025-v1`.
Script : `scripts/research/us_winner_gpt_veto_august_2026.py`.
SQL exclusivement READ ONLY ; bougies SIP5min régulières, historique daily
EODHD prioritaire puis SIP, secteurs actuels et inventaire corporate actions.
Aucun téléchargement fournisseur, écriture SQL ou ordre ; production inchangée.

Les deux comptes partagent une même cohorte de couverture stricte : séances
SIP complètes de J à min(J+40,fin de replay), secteur connu, pas d'événement
corporate action ni rupture d'identité connue traversés. Les exclusions restent
dans les420 lignes et ne sont pas remplacées. **Biais de couverture future**
signalé, jamais présenté comme une règle disponible en live. Le risque valide
aussi ses données journalières avant chaque entrée.

Audits prévus : entrées causales et confirmations, échéance depuis le fill,
sorties SL/gap/horizon recalculées scalairement, cash/frais/positions/PnL et DD
réconciliés. Les trades présents seulement dans un bras sont décrits, sans
assimiler automatiquement toute différence à une perte évitée : capital,
positions et gardes de risque interagissent.

9 tests synthétiques passent avant lancement : veto des seuls scores valides,
avis invalides/null conservés, archives/rangs malformés refusés, cohorte commune,
aucun remplacement, LONG seul. Sources et entrées scellées avant le replay.
Période déjà observée, petit échantillon, versions historiques/secteurs non PIT,
OHLC et non bid/ask/fills : pas de parité live complète ni holdout indépendant.

## Résultat — terminé le25 octobre2026

Deux comptes audités et **strictement identiques** : mêmes trades, courbes5min
et quotidiennes, pas seulement le même montant final.237 signaux communs
qualifiés sur420 ;183 réservés pour trous dans la fenêtre SIP commune.
30 scores3 d'origine, dont4 dans la cohorte admissible : CCOI18/21/26 août et
MXL20 août. Pas de remplacement des signaux exclus.

| Mesure | Winner seul | Winner + veto GPT1–3 |
|---|---:|---:|
|Capital final, positions ouvertes valorisées|3942,06USD|3942,06USD|
|Rendement net|−1,45%|−1,45%|
|DD maximal5min|−11,55%|−11,55%|
|Achats exécutés|29|29|
|Trades clôturés|24|24|
|Gagnants/perdants clôturés|2/22|2/22|
|Taux gagnant des clôturés|8,33%|8,33%|
|Somme PnL gagnants clôturés|+58,02USD|+58,02USD|
|Somme PnL perdants clôturés|−445,77USD|−445,77USD|
|Capital brut utilisé moyen|1551,74USD|1551,74USD|
|Frais|11,27USD|11,27USD|
|Positions ouvertes au30 septembre|5|5|

Les cinq positions ouvertes sont TTMI, PENG, MXL, MRVL et TXG ; leur valorisation
est incluse dans le capital final, pas dans le taux gagnant des24 trades clos.
Écart du filtre : **0USD /0point**, aucun trade clôturé uniquement présent dans
un bras. Le veto des quatre signaux admissibles n'a modifié aucun achat effectif.
Un achat pouvait rester autorisé par un autre signal/plan encore valide ; la
proposition ne constituait pas un veto permanent au moment du fill et n'annulait
pas les plans antérieurs.31 campagnes natives dans chacun des deux comptes.

Audits :58 achats et48 sorties scalaires au total, cash/frais/positions/PnL et
DD réconciliés ;10 tests synthétiques passent (neuf sur le filtre, un sur la
finalisation). Le runner a ensuite rencontré une erreur purement opérationnelle
en essayant de hasher `run.lock`, exclusif sous Windows. Les deux comptes étaient
déjà terminés/audités. Finalisation locale séparée
`scripts/research/us_winner_gpt_veto_august_2026_finalize.py`, sans rejouer le
portefeuille, lire SQL ou appeler une API ; source originale et comptes inchangés.
`finalization-amendment.json` conserve le motif et l'empreinte du précédent
`failure.json` maintenu comme archive ; `report.json`/`progress.json` attestent
la résolution finale. Un verrou actif n'est pas un fichier économique à hasher.

Conclusion : **aucun bénéfice observé pour ce veto à la création des plans**,
sans conclure qu'un veto exécuté au moment de l'achat aurait le même résultat.
Cette seconde règle nécessiterait une autre expérience explicite, pas un
changement du présent protocole après lecture des résultats. Pas de promotion.

## Extension utilisateur — veto inclusif des scores1–4

Nouvelle demande du25 octobre2026, après résultat1–3 : exclure aussi les scores4.
Protocole séparé, sans remplacer l'expérience précédente ni changer les seuils
de production. Script `scripts/research/us_winner_gpt_veto_1_4_august_2026.py`,
dossier `artifacts/research/us_winner_gpt_veto_august_2026/20261025-score1-4-v1`.

Le compte Winner seul déjà audité est réutilisé comme témoin immuable : mêmes
empreintes moteur, mêmes entrées copiées et vérifiées, même configuration,
même cohorte (comparaison exacte hors indicateur de veto). Un seul nouveau
compte est rejoué. Seule différence : avis VALID de score1,2,3 **ou4**, veto
avant création du plan. Les anciens plans restent valides ; avis invalides/null
conservés ; ni reclassement ni remplacement TOP21. Aucun SQL, réseau ou appel GPT.

172 avis initiaux1–4 (30 scores3 et142 scores4), dont74 dans les237 signaux
communs admissibles (4 scores3 et70 scores4). Ce ne sont pas74 achats exécutés.
SL7, sansTP/sansTR, H20/open21, demi-position sans renforcement, capital4000USD,
plafond1x et coûts/risques inchangés. Mêmes limites rétrospectives et de couverture.
Deux tests supplémentaires vérifient le seuil4 inclusif, les invalides/null,
la cohorte, les rangs et l'absence de remplacement. Sources figées avant calcul.

### Résultat1–4 — terminé et audité

| Mesure | Winner seul / veto1–3 | Winner + veto1–4 |
|---|---:|---:|
|Capital final, ouverts valorisés|3942,06USD|4019,44USD|
|Rendement net|−1,45%|+0,49%|
|DD maximal5min|−11,55%|−9,87%|
|Achats exécutés|29|26|
|Trades clôturés|24|21|
|Gagnants/perdants clôturés|2/22|2/19|
|Taux gagnant clôturé|8,33%|9,52%|
|PnL gagnants clôturés|+58,02USD|+58,02USD|
|PnL perdants clôturés|−445,77USD|−374,24USD|
|Capital brut utilisé moyen|1551,74USD|1475,57USD|
|Frais|11,27USD|9,94USD|
|Positions ouvertes finales|5|5|

Avantage du compte filtré : **+77,39USD /+1,93point**, DD réduit de1,68point.
Le taux gagnant ne couvre que les21 clôtures ; le capital final inclut les
cinq positions ouvertes (TTMI, PENG, MRVL, TXG, MXL). Les clôtures restent
globalement perdantes : la plus-value latente contribue au résultat final.

Comparaison des couples titre/date d'entrée : six trades clôturés du témoin
absents du filtre, tous perdants (−129,45USD) ; trois trades uniquement dans
le filtre, également perdants (−59,02USD). Certains achats communs peuvent
changer de taille/date ; il ne faut donc pas attribuer mécaniquement77,39USD
à « six pertes évitées ». Capital, taille et positions ouvertes interagissent.

26 entrées et21 sorties scalaires du nouveau compte auditées, cash/frais/DD
réconciliés, aucune lacune d'exécution sur la cohorte retenue ;12 tests passent
au total avec les tests1–3/finalisation. Aucun appel GPT supplémentaire et
aucun changement de production. **Amélioration exploratoire seulement**, pas
de filtre robuste démontré : un seul mois, cohorte stricte avec biais futur,
GPT rétrospectif non PIT et seuil élargi après observation du test précédent.
Le résultat demande une confirmation indépendante, pas une promotion live.

### Que seraient devenus chacun des74 signaux exclus en LONG ?

Question utilisateur distincte du portefeuille : le « aucun gagnant exclu »
précédent portait seulement sur les clôtures effectivement présentes dans le
témoin. Cela ne prouve pas que les74 signaux auraient tous perdu en LONG.

Audit local séparé `signal-outcomes-v1/` sous le dossier1–4, script
`scripts/research/us_winner_gpt_veto_signal_outcomes_august_2026.py`. Chaque
couple titre/date est évalué indépendamment : sans contrainte de capital,
secteur/corrélation ou position déjà détenue, donc **pas un portefeuille**.
SL7 fixe arrondi au cent, gaps pris en compte, aucunTP/trailing, vente open21
depuis l'entrée ; frais8pb par côté sur une action théorique, sans financement.
Deux définitions d'entrée exposées, sans nouvelle collecte ni LLM/SQL :

| Entrée hypothétique | Gagnants nets clôturés | Perdants nets clôturés | Encore ouverts au30septembre |
|---|---:|---:|---:|
|Achat systématique openJ+1|11|63|0|
|Après première confirmation Winner dans les20 séances d'attente|5|51|18|

Pour l'achat direct, **14,86% gagnants /85,14% perdants**. Score3 :1 gain et3
pertes ; score4 :10 gains et60 pertes.63 stops (56 intrabar,7 gaps),11 sorties
horizon ; dernière échéance le30septembre. Tous les74 résultats sont matures.

Avec confirmation Winner : les74 signaux finissent par déclencher une entrée
individuelle, mais18 détentions tardives n'ont ni touchéSL ni atteint open21
à la fin des données ; elles restent **non classées**, même si leur valorisation
latente est observable. Sur les56 clôtures seulement :5 gains/51 pertes,
soit8,93% gagnantes. Score3 :3 pertes et1 ouvert ; score4 :5 gains,48 pertes,
17 ouverts. Ces cinq gains hypothétiques ne contredisent pas les deux gains
réellement conservés dans le portefeuille, qui n'achetait pas les74 cas.

130 sorties comparées entre calcul scalaire et premier-hit vectoriel ;74
confirmations contrôlées contre la fonction native ;2 tests supplémentaires
passent (confirmation causale, priorité horizon/gap/stop). Les74 signaux ne
représentent que15 sociétés, avec répétitions et chevauchements : pas74 paris
indépendants ni preuve prédictive prospective. Même biais GPT rétrospectif et
de couverture que les comptes précédents. Aucun paramètre live modifié.
