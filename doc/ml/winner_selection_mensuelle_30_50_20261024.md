# Winner TOP20 : sélection mensuelle sur 30 ou 50 séances, 2020–2024

GO du 24 octobre 2026. Deux portefeuilles distincts, capital initial 4 000 USD
au premier jour de 2020, continus jusqu'au 31 décembre 2024. Pas de remise à
zéro annuelle, liquidation mensuelle ou collage de rendements annuels.
Fenêtres de sélection figées : 30 et 50 **rendements** de séance (N+1 clôtures).

Six profils candidats fixés avant ce run, pas une nouvelle grille de 300 :

| Nom | SL | Trailing | TP | Détention |
| --- | --- | --- | --- | --- |
| REFERENCE | 5 % | aucun | aucun | 20 séances |
| TRAILING15 | 5 % | 15 % | aucun | 20 séances |
| TP20 | 5 % | aucun | 20 % | 20 séances |
| COURT | 3 % | 10 % | 7 % | 10 séances |
| H15 | 5 % | 15 % | aucun | 15 séances |
| LARGE | 7 % | aucun | aucun | 20 séances |

Sortie à l'ouverture suivant la dernière séance de détention ; le jour du fill
compte comme première séance. Confirmation par deux clôtures 5m après cassure
du plus haut de la séance régulière précédente. Attente maximale vingt séances,
position complète sans renforcement. Vingt places LONG, dix entrées par titre
sur 180 jours ; trois pertes consécutives donnent 90 jours d'exclusion. Risque
B4/DD15, secteur/corrélation, budget par trade, frais 8 bps/jambe, réserve de
sizing 25 bps et plafond brut 1x inchangés. Pas d'objectif d'investissement forcé.

## Classement mensuel et temporalité

Six comptes fictifs indépendants simulent les six profils fixes en continu
depuis le 1er juillet 2019. Cette phase fournit les cinquante rendements passés
nécessaires dès janvier 2020. Leurs valorisations de clôture incluent les
positions ouvertes, les pertes latentes et les frais. Ce ne sont pas des gains
unitaires ni seulement les trades vendus, et ces six capitaux ne sont jamais
additionnés au portefeuille réel simulé.

Au premier jour de chaque mois, choisir le rendement net de portefeuille le
plus élevé sur les N séances se terminant à la clôture précédente. Tous les
profils utilisent les mêmes dates. Aucun champ de prix futur, durée effective
de sortie ou résultat du mois à venir ne sert au classement. Égalité numérique :
garder le profil précédent s'il est ex aequo, sinon l'ordre fixe du catalogue.
Si tous sont perdants, retenir tout de même le meilleur : pas de veto cash ajouté.
Historique insuffisant/dates non comparables : échec explicite, pas zéro inventé.

Le profil du **mois de l'entrée réelle** est figé dans chaque campagne. Une
position déjà détenue ne change jamais de policy. Un plan non tenté et non
financé peut être annulé/réarmé au changement de mois, avec son signal et son
expiration d'origine, sa taille recalculée et un nouvel identifiant. Aucun reset
du délai d'attente, double achat, nouvelle tentative IOC ambiguë ou stop desserré
sur une position ouverte. Revalidation native du risque à l'entrée conservée.

Deux témoins fixes (REFERENCE et TRAILING15) repartent eux aussi de 4 000 USD
début 2020 et traversent les cinq années sans reset. Les comptes shadow ayant
démarré en 2019 servent au classement seulement, pas de témoins au même capital
initial. Au total : six shadows, deux adaptatifs, deux témoins, séquentiellement.

## Données, exécution et limites

Rangs TOP20 originaux du corpus TOP100 déjà scellé, disponibilité du modèle
antérieure à chaque signal, aucune substitution TOP21 après exclusion. SIP raw
5m et daily canoniques qualifiés. Réutilisation des archives locales déjà
collectées lorsqu'elles couvrent la période, sinon nouvelles lectures SQL
**READ ONLY** de `alpha_trade`, par symbole, avec reprise locale. Aucun appel
Alpaca/EODHD/LLM, écriture SQL, entraînement ou ordre. Partitions mensuelles,
lectures bornées et worker unique à priorité basse ; les grilles en cours ne
sont ni stoppées ni éditées.

Même couverture commune Jsignal..Jsignal+40 pour les six profils, OST réservées,
aucune bougie synthétique. **Cette exclusion suivant la couverture future est
un biais déclaré**, même si les scores mensuels ne lisent que les valorisations
passées. Secteurs actuels non PIT, univers survivant, daily révisés, hypothèses
OHLC et données déjà observées : aucune affirmation de parité live complète,
de holdout neuf ou d'avantage garanti. Le choix des six candidats après les
études antérieures rend cette comparaison exploratoire.

Contrôles : N rendements/N+1 clôtures, cutoff strict avant première ouverture,
changements de données futures sans effet sur les choix antérieurs, mois/années
continus, plans en attente réarmés sans prolongation, protections financées
inchangées, sizing selon SL choisi, audit scalaire de chaque sortie, contrôle
cash/frais/positions, confirmations d'entrée et lacunes pendant détention.
Le correctif process-local du prix moyen du premier fill est conservé.

## Suivi et résultats

Commande : `python -u -m scripts.research.us_winner_monthly_selector_20261024`.
Dossier : `artifacts/research/us_winner_monthly_selector/20261024-v1`.
`progress.json` suit les snapshots puis les dix replays ; `cases/*/report.json`
marque les comptes terminés. Reprise : même commande **après arrêt du processus**,
jamais un second lancement simultané. SHA256 contrôlés, comptes finis conservés.

Décisions : `decisions-30.json`, `decisions-50.json`, avec chaque score passé,
cutoff et profil choisi. Résultats : `annual-summary.csv`,
`cumulative-summary.csv`, `report.json`, courbes, trades, événements et policies.
DD annuel calculé sur les valorisations de l'année avec capital de départ
réel, DD global dans le bilan cumulatif. Les trades gagnants/perdants annuels
sont classés par année de sortie ; leur PnL peut donc chevaucher deux années,
contrairement au rendement annuel valorisé. Aucune estimation de durée garantie.
