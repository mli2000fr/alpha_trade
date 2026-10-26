# US : combinaison volume call/put et open interest, protocole figé

26 octobre 2026. GO humain : examiner le mélange de deux associations faibles,
sans entraînement, poids optimisés, fournisseur, LLM, SQL écrit ou changement live.

## Hypothèse et règle unique

Sur le fichier tradable courant, pas uniquement TOP10 Oracle, reprendre les
formules du diagnostic du 10 octobre :

- volume = log(1+volume CALL) − log(1+volume PUT), barres journalières Alpaca ;
- OI = log(1+OI CALL) − log(1+OI PUT), snapshots indicatifs Alpaca ;
- un score élevé est orienté LONG, sans inversion après résultats ;
- rang quotidien de chaque variable parmi TOUS les candidats ayant les deux
  preuves avant décision, puis mélange 50/50. Aucune issue future dans les rangs.

Même date locale d'observation pour les deux familles, pas de report artificiel.
Décision 09:25 New York à la séance suivante, entrée à son open. Dernier état
réellement reçu avant décision ; observed_at ET available_at pris en compte.
OI : CALL/PUT même échéance/strike, racines standard, 15–25 jours calendaires,
plus proche de 20, distance au spot ≤5 %. Volume : somme des contrats collectés
par côté pour une échéance commune, 15–25 jours, plus proche de 20. Le sous-panier
volume n'est pas nécessairement le même contrat que l'OI : conserver les deux
échéances, publier leur recouvrement, ne pas assimiler ce volume au flux signé.
Un côté/compteur absent n'est pas zéro. Volume négatif/manquant invalide le groupe.
Barres historiques téléchargées tardivement exclues par date de réception réelle.
Versions contradictoires au même instant réservées, pas de choix arbitraire.

## Cible et prix

Primaire H20 ; H5/H10 descriptifs secondaires. Vingt séances incluent l'entrée.
Pour chaque sens, excursion maximale favorable AVANT stop fixe adverse 10 %.
LONG gagnant de classement si sa borne basse dépasse la borne haute SHORT,
et inversement. Sinon ambiguïté/égalité réservée. Ce ne sont pas des gagnants
de trades, un TP avant SL, un rendement terminal ni une vente réalisable au pic.
Gaps stoppants prioritaires ; pic/stop sur même daily bar bornés, ordre non inventé.
Conserver dates des maxima et ordre indéterminé si nécessaire.

Prix uniquement Alpaca SIP split, sans fallback EODHD et sans changement du YAML.
Ce choix de recherche évite un changement de source dans le parcours ; l'EODHD
disponible s'arrête le 16 octobre et le SIP le 23 au contrôle préliminaire.
Identité instrument non nulle et stable, sessions officielles closes, OHLCV
valides, aucun remplissage. Pas de chemin partiel transformé en H20 mature.
Les prix sont une lecture actuelle, pas une archive certifiée as-known des
ajustements/OST/deliverables ; cette limite reste explicitement non levée.

## Comparaison, contrôles et limites

Trois scores sur EXACTEMENT les mêmes observations : volume, OI, mélange.
AUC quotidienne moyenne et AUC groupée distinctes, constantes =0,5 sur dates
à deux classes. Aucune sélection d'un horizon ou du meilleur composant après coup.
Corrélation des rangs, écarts appariés par date, moitiés chronologiques,
dates d'entrée espacées de H séances ET première observation par titre.
Dates de contrôle choisies avant qualité/maturité future. Retrait d'une date
publié comme sensibilité descriptive, pas une validation croisée/OOS.

Séparer observations jusqu'au 9 octobre inclus (fenêtre déjà étudiée) et depuis
le 10 octobre (extension non utilisée dans le rapport initial, pas holdout vierge).
Collectes depuis le 10 septembre, jusqu'à dernière séance close au cutoff réel.
Pas de preuve de persistance sur plusieurs régimes ni de rendement économique.
Les anciens 0,547 sont des AUC de déciles TERMINAUX à H5/H3 et ne constituent
pas des attentes pour cette cible différente. Ne pas additionner des AUC.
OI/quotes indicatifs, provenance OPRA des volumes non attestée ; recherche seulement.
Pas de Yahoo, pas de données FR, aucune source bloquée restaurée.

## Exécution et archivage

Module `scripts.research.us_options_equal_mix_20261026`, phase snapshot READ ONLY
alpha_trade/REPEATABLE READ/rollback, puis phase analyze hors ligne. Répertoire
neuf et refus d'écrasement. Protocole enregistré avant calcul des issues et
scores combinés ; empreintes sources, entrées et sorties conservées. Les tests
de causalité, ambiguïtés, manquants, maturité et contrôles précèdent l'analyse.
