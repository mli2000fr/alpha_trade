# TOP20 — sélection mensuelle sur 100 séances, DD15 et pause trois mois

Nouvelle expérience demandée le 25 octobre 2026. La formulation mentionne
DD20 puis précise « chaque fois DD15 ». Le contrat retenu, annoncé avant
lancement, est **DD15**, comme la série 30/50 en cours : seule la fenêtre de
sélection mensuelle passe à **100 séances**. Aucun plafond global DD25.

## Règle et comparabilité

TOP20 d'origine, LONG, 4 000USD initiaux, 1x, positions complètes, pas de
renforcement, frais8pb/jambe et risque hérité. Évaluation du 2 janvier2020
au 31 décembre2024, sans reset annuel. Les six profils SL/TP/trailing/horizon
sont identiques à ceux des variantes30/50.

À DD15 depuis le sommet du cycle : liquidation totale, annulation des plans,
pause trois mois calendaires depuis la date NY de vente effective. Reprise à
la première ouverture officielle éligible, sur le **capital restant** et non
4 000USD, avec DD/B4 de cycle remis à zéro. Nouvelles entrées soumises aux
confirmations5m et au risque ; aucun ancien plan pré-pause ressuscité. Le DD
historique reste mesuré mais n'empêche pas les reprises. Plusieurs pertes
de cycle peuvent cumuler bien plus que 15 % ou 25 % ; gaps et frais ne sont
pas écrêtés. Pas de liquidation partielle supplémentaire.

Au début de chaque mois, comparer les **100 derniers rendements journaliers
observables des comptes de référence**, donc **101 clôtures**. Inclure les
positions ouvertes valorisées et frais, garder le calendrier officiel commun
complet et un cutoff à la clôture précédant l'ouverture du mois. En cas
d'égalité exacte, garder le profil précédent, sinon ordre du catalogue.
Le profil des positions déjà financées reste figé.

## Réutilisation sans doublon

Les six comptes de référence DD15/pause3m/sans plafond sont déjà en calcul :
`artifacts/research/us_winner_monthly_selector/20261025-cycle15-pause3m-no-global-cap-v1`.
Ils débutent en juillet2019 et donnent plus de 101 clôtures avant janvier2020.
**Aucun second calcul de ces références n'est lancé.**

Un worker léger attend leurs six rapports finaux. Il n'alloue pas encore le
tape intraday. Chaque référence doit avoir le bon contrat, calendrier complet,
statut et audit réussis, puis toutes ses empreintes doivent être vérifiées et
consignées dans `shadow-receipts.json`. Si une référence manque et le parent
échoue, arrêt explicite, pas de relance automatique. Les quatre comptes finaux
du parent ne sont pas un préalable : six références validées suffisent.

Ensuite, seul `MONTHLY_100` est rejoué avec le même contrôleur et les mêmes
audits que30/50. Les anciens dossiers et sources scellées sont préservés,
aucun changement de modèle, YAML ou règles de production.

## Sorties et suivi

Module : `scripts.research.us_winner_monthly100_cycle15_20261025`, phases
`prepare` et `run`. Dossier :
`artifacts/research/us_winner_monthly_selector/20261025-cycle15-pause3m-monthly100-v1`.

- `WAITING_FOR_REFERENCE_ACCOUNTS` : worker démarré, replay100 pas encore lancé.
- `progress.json` : nombre de références prêtes, puis séances du compte100.
- `decisions-100.json` : 60 choix mensuels, dates de disponibilité et scores.
- `cases/MONTHLY_100/report.json` : PnL, DD historique et cycle, taux gagnant,
  gains/pertes, capital utilisé, séances investies/cash, pauses/reprises et audits.
- `report.json` et `annual-summary.csv` : résultat global et par année après audit.

Vérifications : 100 rendements/101 clôtures, absence de fuite du futur,
calendrier complet, références incompatibles rejetées, six références seulement
comme dépendance, installation/restauration des adaptateurs et audits DD15
existants. Ni SQL, API, LLM, collecte, entraînement ni ordre réel.

Périodes déjà explorées, univers survivant, secteurs actuels non PIT,
couverture future J..J+40 et prix OHLC5m : résultat exploratoire, non indépendant,
pas de certification de parité live complète. La fenêtre100 n'est pas choisie
après son résultat ; ne pas l'annoncer meilleure avant comparaison.
