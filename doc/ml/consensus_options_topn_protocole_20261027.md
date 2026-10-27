# Consensus dans les TOP10/20/50 Oracle — protocole du 27 octobre 2026

Audit exploratoire hors ligne, sans entraînement, nouvelle inférence, accès SQL,
API fournisseur, LLM, ordre ni changement du filtre de production.

## Population figée avant les nouvelles issues

Reprendre exactement les classements scellés de
`artifacts/research/us_options_oracle_topn/20261026-v1` : modèles parcours H20,
univers courant 1 790 titres et couverture Oracle >=95 %. Ni le véritable TOP
futur, ni un TOP recalculé après disponibilité consensus/options. N est un nombre
de titres. Aucun remplacement par N+1. Le seuil actuel 90 % de production ne
remplace pas rétrospectivement le seuil scientifique du parent.

Les parents options sont coupés au 26 octobre ; le parent consensus au 22 octobre.
Leur intersection d'information est une seule date d'entrée : 19 octobre 2026.
Ce premier audit borné ne prétend pas exploiter toute la base au 27 octobre.
Il ne peut pas établir une généralisation sur plusieurs régimes de marché.

Si les scripts/documentations parents ont changé depuis capture, conserver les
empreintes attendues/actuelles comme réserve de reproductibilité, sans réécrire
les sceaux. Tous les fichiers de données doivent toujours correspondre aux
hashes archivés. Reproduire indépendamment les rangs à partir des scores bruts
scellés (batch par mois, univers, couverture, tri score/symbole) avant les issues.
Toute modification d'un poids ou contrat de modèle référencé reste bloquante.

## Signaux sans poids appris

Réutiliser les observations EODHD et reçus terminés archivés : même titre,
période fiscale et horizon 0q ; pas de comparaison 0q/+1q. Recontrôler hash brut,
normalisation, cohérence et disponibilité conservatrice avant 09:25 New York,
avec état âgé au plus quatre jours. Conserver les réserves d'horloge d'ingestion,
de période fiscale, de devise et de base EPS du parent ; aucune requalification
de RESEARCH_ONLY en donnée financière certifiée.

- Signal principal : `(révisions EPS hausse 30j - baisse 30j) / somme`, avec
  nombre d'analystes EPS >=3. Deux compteurs explicitement nuls donnent neutre 0 ;
  un compteur absent reste manquant, jamais imputé. Pas de DOWN7 inventé.
- Diagnostic EPS : `(EPS actuel - EPS reçu à J-30)/abs(EPS reçu à J-30)`,
  dénominateur non nul, >=3 analystes. Ce point reçu aujourd'hui n'est pas un
  vintage physiquement reçu trente jours auparavant ; base EPS inconnue.
- Diagnostic revenus : variation réellement observée entre les deux états
  archivés précédant deux ouvertures successives, même ancrage/horizon,
  nombres d'analystes inchangés et >=3, valeurs positives et cohérentes.

Convertir chaque signal en rang quotidien au sein du TOPN couvert AVANT lecture
des issues. Calculer chaque AUC sur sa couverture explicitement indiquée.
Comparaison incrémentale principale à effectif identique : volume seul, OI seul,
leur mélange existant 50/50, révisions EPS30 seules, puis un seul nouveau mélange
`50 % options + 50 % révisions EPS30`. Aucun choix de poids/seuil après résultat.
Les noms EPS et revenus ne certifient pas une comparabilité comptable parfaite.

## Issues et limites

Même cible que l'audit options : excursion favorable sur H5/H10/H20 depuis
l'ouverture suivante, arrêt à SL10 propre au LONG et au SHORT, comparaison
des bornes. Ambiguïtés OHLC réservées ; aucun ordre high/low inventé, aucun prix
de séance non clôturée. H20 primaire, H5/H10 secondaires descriptifs. Pas du
rendement terminal à H20 ni d'un TP réalisable au sommet.

Prix EODHD et SIP séparés, aucune substitution d'un fournisseur manquant.
Résultats sur le consensus seul et sur la couverture commune options/consensus,
AUC quotidiennes et poolées, effectifs/dates/titres, contrôle premières
observations par titre et dates espacées de H séances. Séparer la présence
physique des scores Oracle avant décision du seul caractère causal du fold.

Une seule date informative ou quelques sociétés ne constituent pas une
validation. Pas de PnL, capital, frais, levier ni prétendue hausse du taux gagnant.
Les résultats déjà vus des parents rendent cet audit non indépendant ; aucune
promotion en production ni recherche de meilleurs paramètres n'est autorisée
par ses seules observations.
