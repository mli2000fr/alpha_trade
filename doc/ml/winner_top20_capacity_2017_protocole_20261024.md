# TOP20 2017 : position complète et capacité assouplie

GO du 24 octobre 2026. Une seule combinaison déjà observée, pas de nouvelle
grille ni de sélection de champion. Période 02/06–31/12/2017, capital 4 000 USD,
LONG, SL 5 %, sans TP, sans trailing, vingt séances de détention puis vente à
l'ouverture de la 21e. Deux confirmations 5 minutes, attente maximale vingt
séances. Aucun renforcement. Frais 8 bps par jambe, réserve de sizing 25 bps,
plafond brut 1x, financement et mark-to-market identiques à la référence.

Modifications demandées : fraction initiale 1.0, maximum vingt positions LONG,
dix entrées par titre sur 180 jours calendaires. Exclusion après trois pertes
consécutives pendant 90 jours inchangée. Budgets de risque, limite par titre,
secteur/corrélation, B4/DD15 et contrôles des cours inchangés. Vingt positions
est un maximum, pas une cible d'investissement imposée.

Comparaison séquentielle dans un nouveau répertoire :

1. Référence archivée : demi-position, huit positions, cinq entrées, données
   complètes Jsignal..Jsignal+40. Rendement observé +10,97 %, non holdout.
2. `FULL_20POS_10ENTRIES_STRICT40` : paramètres demandés, qualification identique.
3. `FULL_20POS_10ENTRIES_ENTRY20` : paramètres demandés, qualification de données
   moins restrictive. Le signal doit avoir une séance SIP complète. À chaque
   tentative d'entrée, couverture jusqu'à la vente maximale (Jentrée..Jentrée+20,
   tronquée au 31 décembre), plutôt que toutes les quarante séances après signal.

**Limite majeure : cette qualification de couverture reste future-dépendante.**
Elle n'utilise ni rendements futurs ni sortie SL effectivement gagnante/perdante
pour choisir une couverture plus courte. Elle ne peut toutefois pas être
présentée comme un filtre causal de production. Les 61 observations daily
passées et les bougies courante/précédente requises restent strictes. Aucun
remplissage synthétique, prix inventé ou saut d'une position tenue.

Les lacunes de candidats non détenus restent listées et donnent un statut
explicite `WITH_CANDIDATE_GAPS`. Une lacune intersectant une détention interdit
la qualification économique. Audit scalaire inchangé sur chaque achat/sortie,
cash/frais/positions et DD. Correctif process-local du premier fill complet
pour conserver le prix moyen broker exact avant arrondi des protections.
Réserve corporate actions héritée, secteurs actuels non PIT, univers survivant,
OHLC et non quotes/fills : aucune parité live complète ou avantage nouveau
hors échantillon revendiqué.

Archives locales parent TOP20 et leurs SHA256 seulement. Aucun SQL, fournisseur,
entraînement, ordre, modification des batchs/configuration de production ou des
sources scellées des runs existants. Un seul worker supplémentaire, priorité
basse. Les deux bras changent plusieurs paramètres à la fois : seul leur écart
mutuel isole la qualification de couverture, pas l'effet individuel du sizing,
des vingt places ou des dix entrées.

Suivi : `artifacts/research/us_winner_top20_capacity_2017/20261024-v1/progress.json`.
Sorties : `comparison.csv`, `report.json`, événements/trades/courbes et rapports
par bras. Script `scripts.research.us_winner_top20_capacity_2017_20261024`.
Les rapports existants sont immuables et vérifiés avant reprise. Une erreur
technique reste un échec explicite, jamais un résultat économique qualifié.
