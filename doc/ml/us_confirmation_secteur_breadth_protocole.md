# US — Confirmation figée force relative / breadth et régime LONG

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

Protocole enregistré le 4 octobre 2026 avant calcul des résultats de ces
filtres. Recherche seule : pas de fit, pas de changement de modèle, pas
d'écriture SQL, pas de modification de configuration de production.

## Question

1. Les jours où le régime applicatif bloque les LONG évitent-ils les pertes
   de la combinaison MV figée ? Combien de D10 et de gains écartent-ils aussi ?
2. La force relative titre/secteur et la breadth ajoutent-elles de la valeur
   après ce contrôle, sans changer les poids ou remplir les places vacantes ?

## Source et réserves de régime

`service/market/regime_manager.py` : `capital_preservation` fixe
`allowed_long_entries=False`; `close_only/cash_only` fixent aussi
`allow_new_entries=False`. `normal` n'autorise les LONG que si les nouvelles
entrées sont permises. Lire seulement `allow_new_entries` serait incorrect.

On joint les `mode/allow_new_entries` persistés dans
`stock_macro_indicators_daily` à la date exacte J. Mode inconnu, date absente,
permission absente : inconnu, jamais autorisé silencieusement. Un mode
`normal` sans VIX/VXN/VIX3M/MOVE est marqué séparément comme normal avec
macro incomplète : cela n'établit pas que le régime économique est normal.

Il s'agit du replay des modes archivés, pas d'une reconstitution exhaustive
du régime courant (hystérésis, flags CP-V2, blocages individuels, budgets,
earnings et PIT de publication). Le signal utilise la clôture J ; ce test
ne reproduit pas le régime à l'ouverture J+1 ni les positions déjà détenues.
Un blocage d'entrée n'est pas une clôture forcée des positions existantes.

## Données et indicateurs fixés

Sélection d'origine : MV TOP10 du pool ATR20 TOP20 × Oracle H20 TOP20,
2019–2025 et T1 2026. Aucun nouveau rang, aucun remplacement d'un exclu.
Les pairs sectoriels viennent de l'univers actuel des 1 798 titres, pas
seulement des candidats Oracle. Métadonnées secteur actuelles **non PIT**.

Par titre et à J, calculer depuis les cours ajustés : rendement passé sur
20 séances et position au-dessus de la SMA20. Un rendement20 exige 21
clôtures positives et consécutives dans le calendrier SPY ; SMA20 exige
20 clôtures. Pas de remplissage de séances manquantes.

- Secteur de référence : moyenne équipondérée des rendements20 des autres
  titres du secteur, à J (leave-one-out).
- Force relative20 : rendement titre20 moins rendement secteur20.
- Breadth20 : proportion des autres titres au-dessus de leur SMA20.
- Minimum : 20 autres titres avec les deux indicateurs disponibles.
- Secteur absent/UNKNOWN, prix absent, support insuffisant : inéligible
  pour les variantes secteur, sans exclusion de la baseline.

## Variantes — aucun sweep

| Variante | Règle de conservation |
|---|---|
| BASE | Tous les candidats MV initiaux |
| REGIME | Mode normal ET nouvelles entrées autorisées à J |
| RS | Support valide ET force relative20 >0 |
| BREADTH | Support valide ET breadth20 >0,50 |
| RS_BREADTH | RS ET BREADTH |
| REGIME_RS | REGIME ET RS |
| REGIME_BREADTH | REGIME ET BREADTH |
| REGIME_RS_BREADTH | REGIME ET RS_BREADTH |

Les seuils zéro/majorité et la fenêtre20 sont fixés par définition de la
question, pas recherchés sur les pertes déjà connues.

## Lecture et évaluation

Publier année/mois et trois fenêtres : 2019–2022 caractérisation,
2023–2025 contrôle historique, T1 2026 extension déjà consultée. Aucune
fenêtre n'est déclarée prospective intacte puisque les résultats MV étaient
déjà connus. Un résultat favorable demande une confirmation nouvelle.

Mesurer effectifs retenus/exclus/inconnus, D10/D1, rendement H20 brut moyen,
part de D10 conservés et de D1 éliminés. Publier les observations rejetées
par régime séparément. Pour prévenir l'illusion « meilleur rendement en
ne gardant presque rien », rapporter aussi la somme des rendements retenus
divisée par l'effectif initial (abstention=0). C'est une mesure descriptive
à budget d'observations fixe, **pas un PnL ni un rendement de portefeuille**.

Un signal intéressant doit éviter les D1 sans sacrifier disproportionnellement
les D10 et rester utile au-delà de quelques mois/secteurs. Aucun GO production
sur la seule moyenne globale ou sur un mois réparé après coup. Les données
chevauchent et les mêmes symboles se répètent ; pas d'inférence indépendante
à partir de l'effectif brut. Coûts, prix exécutable, sizing et lifecycle
ne sont pas simulés.

## Exécution

Script : `scripts/research/us_sector_breadth_confirmation.py`.
Sortie : `artifacts/research/us_atr_oracle_sentiment/sector-breadth-confirmation-20261004-v1/`.
Suivi : `progress.json`, puis `report.json`; contexte sectoriel et sélection
avec masques dans des Parquet de recherche. La base n'est interrogée que
par SELECT. Le script ne charge ni ne modifie de modèle.
