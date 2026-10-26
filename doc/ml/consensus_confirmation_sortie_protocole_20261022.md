# Consensus : confirmation de trois variations et sortie sur information inverse

22 octobre 2026. Expérience séparée, bornée, sans entraînement, fournisseur/LLM,
ordre, écriture SQL ou changement des modèles/batchs/protections de production.

## Source et horloge

Réutiliser les features du dossier scellé
`us_consensus_reliability/20261022-v1/sip-only-v2`. Même univers courant1790,
réceptions réellement datées,`0q`,ancrages candidats,comparabilité limitée,
réserve UTC d'ingestion conservée. Les huit décisions13–22octobre ne deviennent
pas un historique long. Aucun EPS ni vintage inventé à J−7/30/60/90.

Fixer un nouveau cutoff **d'observation des prix**, pas de nouvelle date
historique d'information. Export READ ONLY de prix SIP quotidiens déjà en base,
au plus jusqu'à ce cutoff ; aucun téléchargement et aucun fallback EODHD/IEX.
Les décisions et leurs features ne sont pas rafraîchies selon leurs résultats.

## Entrées figées

- A : variation de revenus moyenne strictement positive→LONG,négative→SHORT.
- B : trois variations de même signe sur trois **ouvertures NYSE successives**.
  Chaque paire technique doit être recevable,≥3analystes,nombre inchangé ;
  même ancrage et même nombre à travers les trois paires. Les IDs doivent
  former une chaîne exacte de **quatre observations**. Zéro,manque,rupture
  de période,compte changé ou jour manquant brisent la confirmation.
- C : exactement les mêmes entrées que B, puis surveillance des nouveaux
  consensus disponibles avant chaque ouverture suivante.

Un weekend n'est pas trois séances ; plusieurs copies ne créent pas de signal.
Les trois décisions désignent les changements connus à ces opens, pas une
entrée avant publication. Les nouvelles révisions ne sont pas des votes
indépendants des mêmes analystes, dont les identités restent inconnues.

## Sorties et protections communes

Choix repris du protocole consensus déjà présent : **TP10/SL5**,sans trailing.
Ce n'est pas une optimisation, ni les paramètres Winner en production.
H5 primaire ; H1/H3 secondaires. H10 inventaire de fréquence/maturité seulement,
aucun résultat H10 ni relance de l'ancien évaluateur avant sa maturité.

A et B : protections fixes,jusqu'à la clôture de l'horizon entrée incluse.
C : après au moins une séance de détention,une première révision de signe
inverse,période identique,pair technique,nombre d'analystes inchangé et identique
à celui d'entrée→sortie à **l'open auquel cette information était disponible**.
Information reçue après clôture H1→open H2, jamais close H1 rétroactif.
Stable,manquante ou non comparable→pas sortie par consensus ; protections restent.

À chaque séance : gap au-delà du stop d'abord au vrai open,puis gap TP plafonné
au target,puis sortie d'information connue avant l'open,puis franchissements
intrajournaliers. Deux barrières dans une bougie non résolue→stop d'abord.
Pas utilisation du futur high/low de la bougie après sortie à son open.
À H1,B et C doivent être identiques avec une surveillance quotidienne.

## Mesures et réserves

Compter toutes les entrées B avant prix,les symboles,dates et sens. Pas de
seuil de fréquence abaissé. Les résultats éventuels restent descriptifs ;
la confirmation historique50dates/100épisodes n'est pas assouplie.

Pour comparer les sorties, exiger la même fenêtre future complète et mature
pour B et C,même si C aurait déjà vendu tôt. Les données manquantes restent
inconnues,pas des pertes ni une invitation à conserver les seuls gagnants.
Tous OHLCV non remplis,valeurs positives,géométrie valide,source SIP,ajustement
raw/identité stables,ruptures connues réservées. Pas de certification exhaustive OST.

Publier effectifs,moyennes/médianes brutes,fréquences gagnantes,coûts illustratifs
16bps aller-retour,motifs de sortie et durées. LONG/SHORT séparés,pondération
par date,delta C−B sur les **mêmes entrées**,contrôles toujoursLONG/SHORT au
même open/close. Pas de PnL annuel,capital,levier,emprunt ou exécution certifiés.

Opportunités chevauchantes descriptives ET contrôle conservateur : réserver
chronologiquement Hséances par titre sur tous les jours de features,avant le
filtre et les prix,donc sans recycler le créneau d'une abstention ou d'un stop
précoce. Cela évite de fabriquer plusieurs positions indépendantes sur le même titre.

Les années/journées ont déjà été vues ; règles écrites après d'autres résultats.
Ni univers production,ni signal validé,ni nouveau modèle n'en découle.
