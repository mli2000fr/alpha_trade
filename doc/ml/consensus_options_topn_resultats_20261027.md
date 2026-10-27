# Consensus sur TOP10/20/50 Oracle et complément des options

27 octobre 2026 — **AUDIT BORNÉ TERMINÉ / UNE DATE / EXPLORATOIRE / AUC H20
NON MESURABLE / AUCUNE PROMOTION DU FILTRE.**

[Protocole figé](consensus_options_topn_protocole_20261027.md).
Résultats : `artifacts/research/us_consensus_options_topn/20261027-v1/`.
Relecture : dossier voisin `20261027-v1-review/`.

## Périmètre réellement testé

Même population que l'audit options précédent : les N premiers **titres** Oracle
parcours H20, avant disponibilité des features et résultats futurs. Ni TOP20 %,
ni classement réalisé. Les 27 982 rangs archivés ont été reproduits directement
à partir des scores bruts scellés, avec les batchs mensuels, l'univers 1 790,
la couverture >=95 % et le tri score décroissant/symbole croissant.

Les cohortes comprennent 160/320/800 candidats sur seize dates de signaux.
Mais le consensus archivé commence le 11 octobre ; l'intersection comporte
**une seule date d'entrée, le 19 octobre**. La présente étude réutilise les
archives figées comparables, pas une extraction exhaustive de la base au 27.
Pas de remplissage des dates Oracle manquantes ni de substitution par N+1.

| TOP Oracle | Révisions EPS30 disponibles | EPS actuel/J−30 | Variation de revenus observée |
|---|---:|---:|---:|
| 10 | 8 | 8 | 9 |
| 20 | 16 | 16 | 17 |
| 50 | 43 | 42 | 43 |

Les informations sont connues avant 09:25 NY : reçus terminés, max conservateur
des horloges, même ancrage et 0q, raw hash et normalisation recontrôlés. Pas de
DOWN7 manquant converti en zéro, ni de comparaison 0q/+1q. EPS >=3 analystes ;
revenus positifs, cohérents et nombre d'analystes déclaré inchangé >=3.
Un nombre inchangé ne certifie pas les mêmes personnes.

## Résultats H5 : prix SIP, diagnostic secondaire prévu

La cible compare les **excursions** LONG/SHORT sur cinq séances, après l'open
d'entrée et avant le SL10 propre à chaque sens. Ce n'est ni la clôture H5,
ni un trade vendu au sommet, ni un taux de réussite TP/SL.

AUC quotidienne (une seule date informative quand les deux classes existent) :

| TOP | Révisions EPS30 | EPS actuel contre J−30 | Revenus : changement observé |
|---|---:|---:|---:|
| 10 | non calculable, 8 cas SHORT | non calculable, 8 cas SHORT | 0,563 — 9 cas |
| 20 | 0,654 — 16 cas | 0,821 — 16 cas | 0,567 — 17 cas |
| 50 | 0,315 — 43 cas | 0,487 — 42 cas | 0,543 — 42 cas |

Pour les seize cas EPS du TOP20 : seulement **3 LONG et 13 SHORT** au sens de
cette cible. Les 0,821 ne sont pas une preuve de prévision fiable ni 82,1 % de
trades gagnants. L'effet ne se retrouve pas en élargissant au TOP50. Les
combinaisons TOP10/20/50 sont imbriquées, pas des réplications indépendantes.

Le parcours revenus TOP50 exclut une observation sans prix. Les prix sont SIP
split uniquement et les identités restent constantes ; aucun fallback EODHD.
Le flux EODHD primaire de l'archive n'a **aucune barre du 19 au 23 octobre** :
zéro issue H5 qualifiée dans l'intersection consensus. Ce manque de l'archive
ne signifie pas que ces cours sont absents de la base actuelle.

## Apport au volume options + open interest

Une seule combinaison nouvelle, fixée avant résultats :
50 % mélange options existant + 50 % rang des révisions EPS30.
Comparateurs sur **exactement les mêmes observations** :

| TOP | Cas communs H5 valides | Dates | AUC options seules | AUC révisions seules | AUC mélange |
|---|---:|---:|---:|---:|---:|
| 10 | 0 | 0 | — | — | — |
| 20 | 1 | 1 | non calculable | non calculable | non calculable |
| 50 | 5 | 1 | 0,750 | 0,750 | 0,875 |

Les cinq cas TOP50 ont des scores Oracle physiquement enregistrés avant la
décision. Cela ne certifie pas les conventions comptables, le vintage des prix,
ni le caractère OPRA du volume indicatif. Les contrôles sans chevauchement et
première observation par titre restent limités à la même date : ils ne créent
pas de validation temporelle. **Cinq cas ne démontrent pas un gain incrémental.**

## H10/H20 et réserves

Zéro issue mature H10 ou H20 pour les signaux consensus présents, au cutoff de
prix parent. Aucun taux/AUC/PnL n'est extrapolé de H5 à H20. Les états à J−30
reçus dans un snapshot ne sont pas trente jours de vintages collectés.

Les réserves fournisseur restent inchangées : base EPS inconnue, mois fiscal
normalisé, composition des analystes non observée, devises/périodes pas toutes
certifiées. Statut **RESEARCH_ONLY**, pas de données promues SQL.

Dix références de scripts/documents/tests parents ne correspondent plus à leurs
empreintes au moment de capture. Leurs données et sceaux sont intacts ; les
anciens générateurs ne sont pas présentés comme rejoués à l'identique. Les
différences sont consignées dans le protocole/rapport du nouvel audit. Les rangs
ont été revérifiés indépendamment des générateurs parents ; les valeurs brutes
des observations utilisées ont été recontrôlées. Aucun sceau ancien n'a été modifié.

## Conclusion et contrôles

Pas de preuve suffisante pour ajouter le consensus au filtre de production.
Un signal EPS30 TOP20 mérite une observation ultérieure sur des dates inédites,
mais pas une recherche de poids/seuils sur cette seule séance. Le mélange
options/consensus reste non validé. Ce n'est pas un verdict général négatif
sur le consensus ; c'est une mesure très limitée par l'historique commun.

35 tests passent (11 nouveaux). Relecture par le même assistant : 15 fichiers
scellés, 7 680 lignes de panels, 72 contrôles d'effectifs et 144 vérifications
d'AUC par comparaison explicite des paires, sans reprendre la formule sklearn.
Ce n'est pas une revue humaine indépendante.

**Aucun accès SQL, fournisseur, LLM, fit, inférence nouvelle, ordre, changement
de batch, configuration ou filtre de production pendant cet audit.**
