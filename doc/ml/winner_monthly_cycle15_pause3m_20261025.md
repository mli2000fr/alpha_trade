# TOP20 — liquidation DD15 de cycle, pause trois mois, sans plafond global

Demande utilisateur du 25 octobre 2026 : rejouer la sélection mensuelle en
supprimant le plafond global25 et en remplaçant la pause DD20 par une pause
après **chaque DD15**. Aucun changement en production.

## Règle appliquée

- Mesurer l'equity (cash et positions ouvertes) depuis le pic observé du cycle.
- Au franchissement de 15 %, liquider toutes les positions au prochain prix
  régulier observable, après résolution des stops/MOO déjà en place.
- Annuler les plans non financés et interdire toutes nouvelles entrées et tous
  renforts pendant trois **mois calendaires**, pas 90 jours ou 63 séances.
- Compter la pause depuis la date new-yorkaise de liquidation effective ;
  fin de mois rabattue sur la fin du mois cible. Reprendre à la première
  ouverture officielle à cette date ou après.
- Reprendre avec le **capital restant**, sans apport ni retour artificiel
  à 4 000 $. Remettre à zéro le DD de cycle et l'épisode B4 à cette equity.
- Réadmettre seulement le signal de la dernière séance clôturée, puis les
  nouveaux signaux ordinaires ; confirmation 5m et revalidation du risque
  restent nécessaires. Pas d'achat automatique à l'ouverture de reprise.
- Conserver les séquences de pertes et l'historique de concentration des titres.
- **Aucun plafond historique DD25**, aucune liquidation partielle préalable.
  Le pic historique et le DD depuis ce pic restent mesurés pour le bilan,
  mais n'empêchent pas la reprise d'un nouveau cycle.

Un DD15 est un seuil de déclenchement, pas une garantie de perte maximale.
Gaps, frais et délai au prochain prix exécutable peuvent le dépasser. Plusieurs
cycles perdants peuvent cumuler des pertes bien supérieures à 15 % ou 25 %.
La remise à zéro du compteur ne supprime aucune perte économique.

## Comparabilité

Les dix comptes sont recalculés avec cette même règle, sans réutiliser les
courbes DD20/global25 pour choisir les profils : six shadows depuis juillet
2019, deux sélections mensuelles30/50 et deux témoins fixes depuis janvier2020,
jusqu'au 31 décembre 2024. Les shadows ne sont pas six dépôts ajoutés au compte
évalué ; ce sont des comptes de référence séparés pour classer les profils.

TOP20 Oracle d'origine, LONG, capital initial4 000USD, cap brut1x, positions
complètes sans renfort, vingt places, dix entrées par titre/180 jours, frais8pb
par jambe. Profils individuels SL/TP/trailing/horizon inchangés. Choix mensuel
sur les 30/50 rendements journaliers déjà observables, latents et frais compris.
Une position financée garde le profil fixé à l'entrée.

Le moteur existant exigeait soft < cycle < plafond global ; un adaptateur
de contrôleur **limité au processus de recherche** remplace ce contrat pour
cette seule variante. Les ventes, annulations et la remise à zéro B4 utilisent
les composants natifs. Aucun faux plafond à 99,9 %, aucun changement des
sources originales scellées, du YAML ou des autres calculs en cours.

## Vérification

Tests du contrat, absence de liquidation partielle, répétition de plusieurs
pauses au-delà de 25 % de perte historique, absence d'apport, fins de mois,
jour férié, reprise réelle du moteur et entrée avec signal récent. Audits
indépendants : cash/frais, chaque entrée et sortie normale, chaque vente
globale, seuil observé, quantités, première ouverture exécutable, durée exacte
de pause, absence de positions/achats pendant la pause et capital conservé.
Les rapports contrôlent aussi toute reprise devenue exigible avant la fin.

Les mesures du DD sur clôtures5m et sur ouvertures/clôtures vues par le risque
peuvent différer ; conserver les deux. Rapporter le nombre de cycles, reprises,
jours investis et cash moyen pour ne pas présenter cinq ans calendaires comme
cinq ans d'investissement actif.

## Lancement et fichiers

Module `scripts.research.us_winner_monthly_cycle15_20261025` ; phases
`--phase prepare`, `--phase smoke --smoke-sessions 20`, `--phase run`.
Archives d'entrée uniquement :
`artifacts/research/us_winner_monthly_selector/20261024-v1/inputs`.

Dossier de sortie neuf :
`artifacts/research/us_winner_monthly_selector/20261025-cycle15-pause3m-no-global-cap-v1`.
`progress.json` donne le compte courant et les séances ; les décisions
mensuelles sont produites après les six shadows, pas avant. `cases/*/report.json`
contient le journal de chaque pause/reprise et les audits ; `report.json`
racine est écrit après les dix comptes. Un smoke ne compte pas comme un compte.

Les anciens runs et leurs règles sont conservés. Pas de SQL/API/LLM, collecte,
entraînement ou ordre. Périodes déjà explorées, univers survivant, secteurs
actuels non PIT et sélection de couverture J..J+40 future : résultat
**exploratoire**, pas de parité live complète ni validation indépendante.
