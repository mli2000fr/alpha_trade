# Sensibilité des titres aux news : protocole d'audit borné

Protocole fixé le 22 octobre 2026, avant le nouveau calcul par titre.
Ce travail ne reprend pas le précédent filtre fondé uniquement sur les gains
passés : il étudie la relation **titre × ton de news × horizon**.

## Périmètre et limites préalables

- Univers courant `config/univers_batch/univers_filtred_tradable.txt`, intersecté
  explicitement avec les archives du premier audit news ; différences publiées.
- Archives figées `artifacts/research/us_news_same_day/audit-202510-20261011-v1` :
  publications 2025–septembre 2026, prix quotidiens jusqu'au 9 octobre 2026.
- Pas de téléchargement fournisseur, appel LLM, entraînement, ordre ou SQL écrit.
  Enrichissement SQL **SELECT-only** des titres d'articles et secteurs actuels.
- Les années ont déjà été explorées : 2026 est une vérification chronologique
  séparée, pas un nouvel échantillon vierge de recherche.
- Les `updated_at` archivés ne sont pas des reçus immuables. Aucun remplacement
  de date par une heure inventée. Un résultat rétrospectif ne sera pas promu live.
- Familles par mots-clés dans les titres : résultats/guidance, analystes,
  financement, acquisitions, multiple/autre. **Routage non validé**, pas preuve
  d'une nouvelle annonce ni de l'identité de son émetteur. Pas d'entraînement
  ou de sélection par famille sans qualification des documents.
- Métadonnées sectorielles actuelles, non PIT. Comparaison secondaire à la
  moyenne du secteur courant, hors titre étudié, au moins cinq autres titres.

## Horloge, déduplication et observations

Un même hash non vide par titre n'est compté qu'à sa première publication ;
hash absent : article ID. Scores valides, inférence réussie dans l'archive.
UTC exactement minuit est réservé (précision inconnue). Les articles sont
regroupés par titre et **première ouverture NYSE strictement postérieure à
leur publication**, avec une marge opérationnelle fixe de cinq minutes.
Une publication cinq minutes avant l'open n'est donc utilisable qu'à l'open
suivant. Les nouvelles en séance entrent au prochain open, pas à un prix
journalier supposé juste après la publication.

Ton fort : au moins un score strictement >0,9 ; positif seul, négatif seul,
mixte, aucun score fort. Mixte et aucun restent descriptifs, jamais neutres
imputés à une absence de news. Tous les articles du groupe interviennent dans
les réserves de disponibilité ; pas de choix du meilleur article après coup.

Association déjà potentiellement consommée : clôture précédant la publication
→ ouverture de décision. Ce pont comprend aussi l'attente après publication :
il ne mesure **pas** exactement le mouvement avant la news.

Réaction restante : open de décision → close de la 1re/5e/10e/20e séance,
entrée incluse. Retours bruts, excès SPY simple, excès secteur non PIT, fréquence
d'alignement avec le ton. Ce ne sont ni TP/SL ni rendements de portefeuille.
Une friction illustrative de 16 bps aller-retour est soustraite au retour
signé ; pas d'emprunt, de bid/ask ou d'exécution certifiés, donc pas de PnL.
Prix split non remplis, OHLCV positifs/cohérents, toutes les séances du chemin
présentes, ruptures d'identité connues réservées. Pas de remplissage des trous,
pas d'écrêtage des rendements extrêmes. Réserve OST/prix héritée maintenue.

## Sélection figée et vérification

**Primaire H5** ; H1/H10/H20 secondaires, pas recherche du meilleur horizon.
Par titre, premiers événements chronologiques non chevauchants, **tous tons
confondus**, avant consultation des rendements ; un événement au chemin
incomplet consomme quand même son créneau. Aucune indépendance inter-titres
ou inter-secteurs n'est supposée.

2025 sert uniquement à construire une liste titre/ton, figée pour 2026.
Labels de 2025 entièrement terminés avant 2026 ; aucune admissibilité ne peut
dépendre d'un prix ou d'un score de 2026. Conditions H5 préfixées :

1. au moins 20 événements indépendants, huit dans chaque semestre et six mois ;
2. borne basse Wilson90 de l'alignement excès SPY > max(50 %, taux global
   passé du même ton), retour signé après friction positif et supérieur au global ;
3. retour signé après friction et excès SPY moyens positifs dans les deux semestres.

H1/H10/H20 : mêmes conditions avec minimum total 30/12/8, par semestre
10/4/3, mois 6/5/4. Faibles effectifs secondaires ne prouvent pas une stabilité.
Toutes les cellules titre/ton testées restent dans le dénominateur de correction
Benjamini–Hochberg à 5 % (test binomial descriptif, dépendances résiduelles).
Les listes avant et après correction sont conservées, sans abaisser les seuils.

Vérification 2026 : au moins 10 observations et quatre mois, alignement
excès SPY >50 %, moyennes retour signé après friction et excès SPY positives.
Comparaison supplémentaire aux autres titres **du même ton et aux mêmes dates** ;
contrôle marché/secteur, concentrations et blocs mensuels descriptifs.
Un gain de taux de succès sans gain net n'est pas qualifié de profitabilité.

Pas de listes production. L'absence d'archives PIT ou d'effectif termine
l'audit sur un statut limité, pas sur un réentraînement automatique.
Le croisement TOP10 n'est envisageable qu'après qualification ; il n'est pas
nécessaire pour répondre à la question principale sur tout l'univers.
