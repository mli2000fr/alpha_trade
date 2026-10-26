# P02 — bénéfice partiel avec entrée Winner existante : protocole figé

22 octobre 2026. Recherche hors production ; ce protocole est figé avant PnL.

## Entrée : clarification demandée

`config.yaml` → `winner_pyramiding.confirmation_bars: 2`.
Le code partagé exige **deux clôtures régulières de cinq minutes au-dessus du
plus haut brut de la veille**, précédées d'une clôture au niveau/en dessous.
Entrée à l'ouverture contiguë suivante. Ce n'est ni attendre exactement cinq
minutes après l'ouverture, ni simplement constater deux bougies montantes.
Cette règle était déjà présente dans le témoin Winner de P01 ; elle est conservée,
pas ajoutée comme nouveau filtre. Config vérifiée : demi-position, SL7, trailing15,
aucun TP, vingt séances de détention, pas de renforcement. `enabled:false` reste
inchangé en production ; activation uniquement dans les objets de recherche.

## Une seule intervention

Deux bras :

- **WINNER** : entrée existante, SL7 %, trailing15 %, pas de TP en prix.
- **P02** : même entrée et protections ; vendre **une seule fois 50 % à+10 %**,
  garder le solde protégé jusqu'à sa sortie naturelle ou l'open21.

Actions entières : vendre `floor(quantité_initiale/2)` ; pour une seule action,
aucune vente partielle. Stop dur jamais desserré ni déplacé automatiquement au
prix d'entrée. Le sommet, la date d'entrée et l'échéance du solde sont conservés.
Pas de P01 compression, ni nouvelle règle macro/sectorielle, ni grille de seuils.

Limite à+10 % arrondie au cent depuis le prix exécuté. Gap favorable : prix limite,
pas prix d'ouverture avantageux inventé. Gap stop adverse prioritaire. Si le high
et le low d'une même bougie touchent TP partiel et stop, stop d'abord sur toute la
quantité encore détenue ; l'ordre des ticks n'est pas connu. Un nouveau sommet
n'améliore le stop qu'après la fin de sa bougie. Produits d'une vente intrabar
jamais utilisés pour financer un achat à l'ouverture antérieure de cette bougie.

## Comparaison portefeuille

Réutiliser les seules entrées **WINNER** validées dans P01v2, pas ses entrées
compression. La population commune figée comprend200campagnes/69titres, issue
des213campagnes TOP10 CatBoost PATH H20 de recherche. Les13réserves héritées de
P01 s'appliquent identiquement ; pas de remplacement. Cette sélection de chemins
futurs complets et de survivants reste un biais, pas le TOP10 quotidien complet
ni le modèle LightGBM de production.

Années2025 et2026 jusqu'au30septembre, déjà examinées ; pas de holdout vierge.
Pas de2024 simulée sur une archive intraday absente. Comptes annuels4 000USD,
plafond1x, demi-cible et même sizing natif, contraintes et risque B4DD15 avec
régime SPY de la veille. Frais8puis25bps parjambe ; commissions minimales réelles,
NBBO/queue et fills historiques non certifiés. Protection vingt séances depuis
entrée incluse, vente à l'ouverture de la21e. Pas de nouveau levier ni d'emprunt.
Positions ouvertes à la borne annuelle valorisées, non liquidées fictivement.

**Les quatre témoins doivent reproduire exactement les tapes Winner P01v2**,
y compris trades, courbes, décisions, financement et événements B4. Sinon arrêt,
pas comparaison économique d'une sortie partielle contre une autre entrée.

## Comptabilité partielle et vérifications

L'adaptateur de recherche appelle la clôture native pour la quantité partielle,
en répartissant son coût/flux d'entrée au prorata, puis restaure le solde avec
son coût restant. Les frais d'entrée ne sont pas facturés deux fois. Le risque
observe le cash réellement libéré et les actions restantes. Le gain/perte d'une
campagne complète est enregistré une fois dans le suivi de pertes consécutives,
pas à chaque fragment de vente. Un solde perdant après un TP partiel peut donc
appartenir à une campagne globalement gagnante.

Reconstruire séparément : séquence des sorties/quantités, cash et valorisations,
frais parnotionnel, rendement total de campagne, horizon, absence de double achat,
risque B4 avec quantité restante et statut des admissions1x. Les tests couvrent
les collisions/gaps, arrondi demi-cent, quantité impaire, seule action, conservation
du stop/peak/horizon, bilan gagnant malgré solde perdant et coût non doublé.
Même assistant, pas revue humaine indépendante ; pas parité live complète.

## Mesures et critères figés

Huit cas année×bras×frais. Publier capital final/rendement net, DDmax, gagnants et
perdants **par campagne complète**, gains/pertes moyens, durée, capital utilisé,
nombre de ventes partielles et positions encore ouvertes. Ne pas compter une
vente partielle profitable comme un trade gagnant indépendant du solde.

Rendements unitaires sur mêmes entrées, moitiés exactes, puis contrôle non
chevauchant conservateur OracleJ+40. Les quantités entières réellement approuvées
restent dans le portefeuille. Le minimum nécessaire pour une confirmation :
30occasions non chevauchantes et10touches partielles parannée ; surplus de
portefeuille positif en2025/2026 aux deux frictions ; DDnon dégradé aux frais
normaux chaque année ; surplus unitaire positif aux frais stressés chaque année ;
borne basse95 % du bootstrap mensuel >0 (au moins6mois,2 000tirages,graine731).

Sinon NO_GO ou INSUFFICIENT, sans ajuster +10 %/50 % après résultat. Une hausse du
taux gagnant seule ne suffit pas. Si tous passent : seulement confirmation future,
pas promotion automatique, vu le périmètre conditionnel déjà exploré.

## Suivi

`scripts/research/us_oracle_partial_p02.py`, puis vérification séparée
`scripts/research/us_oracle_partial_p02_audit.py`.
Dossier `artifacts/research/us_oracle_partial_p02/20261022-v1` :
`protocol.json`, `progress.json`, `annual-summary.csv`, `report.json`,
`final-audit.json`, sorties unitaires et sous-dossiers bras/frais/année.
Les ventes sont dans `trades.parquet`, campagnes agrégées dans
`campaign-trades.parquet`. Aucun accès SQL, fournisseur, LLM, entraînement,
ordre ou modification de modèle, batch ou configuration de production.
