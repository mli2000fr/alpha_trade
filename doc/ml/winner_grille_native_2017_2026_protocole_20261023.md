# Winner natif — grille LONG 02/06/2017–30/09/2026

GO utilisateur du 23 octobre 2026 après confirmation de la période. Protocole
figé avant les résultats. Aucun entraînement, ordre broker, fournisseur,
écriture SQL ou changement de configuration de production dans cette grille.
Les snapshots sont lus dans `alpha_trade` en transaction READ ONLY.

## Périmètre et paramètres

TOP10 Oracle parcours H20 causal déjà figé :
`artifacts/research/us_winner_grid_scores_2017_2026/20261023-v2/`.
Pas de filtrage directionnel, ATR additionnel, reranking ni remplacement d'un
titre mal couvert. Allocation de modèles par année identique à la qualification
des scores : `437ed1` jusqu'en2024, `102eca` en2025, `bc35a7` en2026. Les valeurs
de score prédisent l'amplitude, pas une probabilité de hausse.

**300 profils LONG**, produit cartésien de :

- SL initial : 3 / 5 / 7 % ;
- trailing : désactivé / 3 / 10 / 15 / 20 % ;
- détention : 5 / 10 / 15 / 20 séances entrée incluse, sortie à l'ouverture
  de la séance suivante (open6 / open11 / open16 / open21) ;
- TP en prix : désactivé / 7 / 10 / 15 / 20 %.

10 comptes annuels par profil, **3 000 comptes**. 2017 commence au 2juin,
première entrée possible le5juin. 2026 s'arrête au30septembre. Les positions
encore détenues à la borne sont valorisées au dernier cours, pas liquidées
artificiellement àH20 ni portées dans le compte de l'année suivante.

Rester sur le runtime LONG réellement raccordé. Une grille SHORT ne serait
pas le même contrat : pas de borrow inventé ou de suppression silencieuse
des shorts. Cette demande ne déclenche pas un nouvel essai SHORT.

## Entrée, portefeuille et risque inchangés

Demi-position, sans renforcement. Même cassure fraîche du haut raw de la
séance précédente suivie de deux clôtures régulières5m terminées ; achat au
prochain prix ouvert observé. Attente maximale20séances après le signal.
Ne pas racheter un titre déjà détenu. Sizing natif recalculé selon le SL,
capital disponible et risque ; ce ne sont pas des quantités constantes entre
profils. Refuser une demi-position ne finançant pas une action entière, sans
arrondir vers le haut ni desserrer le budget.

Capital4000USD remis à zéro chaque année. Référence figée de l'expérience
native `us_winner_bottom_rank_filter/20261022-v2/protocol.json` : module B4,
DD configuré15 %, limites de positions/secteur/corrélation, concentration et
réapprobation à chaque entrée réellement raccordés au moteur Winner. Le DD15
n'est pas une garantie de perte maximale15 % (gaps/fréquence/gestion du breaker).

Compte margin, levier autorisé2x mais plafond brut du risque1x conservé :
**pas d'autorisation supplémentaire forcée pour consommer2x**. Le capital
effectivement employé est publié. Surcouche factorielle désactivée identiquement
à la référence faute de bandes factorielles historiques qualifiées.

Frais explicites8bps par jambe,16bps aller-retour, comme la référence. Réserve
de sizing25bps/jambe distincte du coût comptabilisé. Intérêt annuel6,5 % sur
cash négatif, /252séances. Pas de devis bid/ask ni de fills historiques simulés
comme s'ils étaient certifiés. Exécution OHLC déclarée exploratoire.

SL prioritaire siSL/TP touchent la même bougie. GapsSL au prix disponible,
TPgap plafonné au TP. Trailing seulement sur des hauts déjà terminés, jamais
lehigh d'une bougie pour protéger rétroactivement sonlow. Ratchet, sans
desserrer le stop initial. Deadline calculée depuis le fill, pas depuis le
signal Oracle. STOP/TP intrabar datés en fin de bougie ; gaps au début.

## Snapshots, couverture et réserves

Par année, snapshots SIP Alpaca raw5m/réguliers/US_EQ/non remplis, daily
split/non remplis (IEX refusé pour les données utilisées), secteurs actuels
et inventaire d'OST. Requêtes intraday par symbole et bornes temporelles sur
cléprimaire, pas de scanCOUNT de toute la table. Fichiers et reçus parsymbole,
reprise sans relecture des fichiers déjà scellés. Une reprise peut réunir
des observations prises à des instants différents : ne pas prétendre un
snapshotglobal transactionnel unique.

Séance intraday qualifiée : grille officielle exacte, ycompris séances
écourtées, OHLCV positifs/cohérents, durée5m et hashpayload présent. Cohorte
commune à tous profils : deJ àJ+40séances, tronquée à la fin du compteannuel,
afin de couvrir attente20+détention20. Réserver les titres sans secteur, les
fenêtres incomplètes et tout événement connu dans la fenêtre. Les motifs et
effectifs sont publiés ; aucune remontée du11e titre pour remplir les trous.

Cette sélection sur couverture future a un **biais explicite** : elle n'est
pas un filtre deployable àJ. Inventaire d'OST actuel potentiellement incomplet,
univers survivant actuel et secteurs nonPIT ; daily ajustés/révisables. Ne pas
utiliser ces rendements comme preuve de performance live certifiée.

2018 n'est pas figée tant que son rattrapage n'est pasCOMPLETED sans échec.
Les autres années peuvent être traitées avant, sans lancer un nouveau
téléchargement. Si la collecte2018 s'arrête encore terminalement, le bilan
reste incomplet, sansTOP3 global définitif. Le script n'essaie pas de réparer
ou relancer un fournisseur.

## Validation et remise

Tests unitaires de grille, causalité, configuration, couverture et calendrier.
Smoke2017 sur vingt séances, profilSL3/TR3/H10/TP15. Audit scalaire séparé du
résolveur des sorties, contrôle des achats, cash, frais, positions finales,
DD et capital utilisé. Le même audit est imposé à chaque compte complet.
Une année échouée s'arrête au premier cas en échec, sans promouvoir un
compte partiel. Reprise par compte annuel/profil déjà scellé et vérifié.

Deux processus maximum, un parannée en cours, sans changer les fichiers de
production. Chaque année charge ses bandes une fois et rejoue ses300profils.
Progression globale et progression parannée ; aucune estimation de durée
annoncée avant mesure. Années réordonnées pour laisser finir2018.

Classement prédéfini **sur2017–2023 seulement** : médiane des rendements
annuels nets / max(5points, pireDDannuel en valeur absolue), puis nombre
d'années positives, pire rendementannuel et nom de profil. Retenir les trois
premiers et publier2024–2026 telsquels, sans sélectionner ànouveau selon
leurs résultats. Ces années ont déjà été examinées : confirmation temporelle,
pas un holdout indépendant intact. Publier aussi les profils ne différant
que d'unparamètre, sans confondre diagnostic des voisins et nouveau critère
de sélection. Aucun profil n'est déclaré rentable ou recommandé à l'avance.

Par compte : rendement/capital final, DDmax5m, gagnants/perdants, gains/pertes
totaux et moyens, durées calendaires et en séances, frais/intérêt, capitalbrut
moyen/maximal et ratio au capital, positionsouvertes, motifs d'exclusion.
`annual-summary.csv`, `profile-ranking.csv`, `top3-one-parameter-neighbours.csv`
et `report.json` ne sont finaux que si les3000comptes sont terminés et audités.

Sortie : `artifacts/research/us_winner_native_grid_2017_2026/20261023-v1/`.
Script : `scripts/research/us_winner_native_grid_2017_2026_20261023.py`.
PhasesCLI : `--phase prepare`, puis `--phase smoke`, puis `--phase run`.
Le même dossier permet la reprise, sous verrou exclusif ; ne pas modifier
sources/protocole entre deux passages. Un amendement nécessite un nouveau
dossier et un protocole distinct, pas l'effacement des échecs historiques.
