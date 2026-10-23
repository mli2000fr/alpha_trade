# Winner seul : pourquoi les trades perdent-ils ?

23 octobre 2026. **AUDIT DESCRIPTIF TERMINÉ ; AUCUN NOUVEAU FILTRE QUALIFIÉ.**
[Protocole figé](winner_audit_pertes_protocole_20261023.md).
[Amendement obligatoire sur l'horloge](winner_audit_pertes_amendement_horloge_20261023.md).
Canonique : `artifacts/research/us_winner_loss_diagnostics/20261023-v2`.
V1 conservée, mais son interprétation des heures de STOP est remplacée :
le moteur inscrit les touches intrabar en FIN de bougie. V2 réserve cette
bougie pour la borne OHLC incertaine et inclut la première bougie entièrement
postérieure. Aucun PnL, effectif principal ou catégorie finale ne change.
Les tables des sondes d'entrée et de leurs statistiques restent exactement
identiques ; une observation immédiate 2025 devient inconnue au lieu de false.

## Conclusion utile

Il n'y a pas un problème unique de « mauvais sens » ni de simples faux départs.
Une partie des pertes a été précédée d'une hausse significative ; une autre
partie rebondit seulement après le stop, parfois après une baisse beaucoup plus
forte. Les quelques sondes connues à l'entrée ne séparent pas régulièrement
gagnants et perdants dans le sens hypothétique figé sur les deux années.
Pas de taux gagnant contrefactuel, règle de sortie, seuil ou modèle promu.

Les gains restitués indiquent un problème possible de gestion du parcours,
mais **ne valident pas un nouveau TP/trailing**. P06 avait déjà essayé de
protéger 50 % du gain après +10 % : taux gagnant supérieur, mais rendement non
confirmé sur les deux années. Ne pas représenter cette idée comme nouvelle.
[Bilan P06](oracle_gain_lock_p06_bilan_20261022.md).

## Quel Winner ?

Uniquement le WINNER_ONLY du moteur actuel, archive
`us_winner_bottom_rank_filter/20261022-v2` : SL7/TR15, sans TP, demi-position,
sans ajout, deux clôtures 5m confirmées, sortie open21 depuis le fill, risque
natif et B4 DD15. Capital annuel 4 000 USD ; coûts 8 bps par jambe, plafond
effectif d'exposition 1x. Pas le HALF_CONTROL historique SL5/TR15 à +12,92 %.

| Période | Trades clôturés | Gagnants | Perdants | Taux gagnant | Positions ouvertes au terme |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | 53 | 9 | 44 | 16,98 % | 0 |
| 2026 au 30/09 | 120 | 38 | 82 | 31,67 % | 6 |

Les six positions ouvertes sont dans `entry-inventory.parquet`, mais sans
étiquette gagnante/perdante réalisée ni diagnostic futur imputé. Leur quantité
est réconciliée au rapport du compte ; la lignée exacte n'est disponible dans
l'archive des trades que pour les 173 clôtures, pas inventée pour les ouverts.
179 achats au total. Ces résultats ne sont pas une nouvelle simulation.

## Partition des pertes : catégories exclusives

1R en prix = 7 % du prix d'entrée. L'ordre comptable est celui du protocole :
gain restitué, faux départ, rebond, ambiguïté OHLC, résidu, inconnu. Des
signatures peuvent se chevaucher ; ne pas additionner les flags non exclusifs.

| Catégorie principale | 2025 : nombre / pertes nettes USD | 2026 : nombre / pertes nettes USD |
| --- | ---: | ---: |
| Hausse certaine >= +7 %, puis perte finale | 12 / −171,20 | 29 / −500,15 |
| Deux premières clôtures sous le haut de la veille | 3 / −62,12 | 5 / −121,47 |
| Stop puis clôture >= entrée +7 % dans la fenêtre | 12 / −255,57 | 25 / −600,89 |
| Bougie de sortie ambiguë autour de +7 % | 0 / 0 | 0 / 0 |
| Fenêtre complète sans les signatures précédentes | 17 / −402,02 | 21 / −521,17 |
| Fenêtre future incomplète/censurée, sans autre signature | 0 / 0 | 2 / −50,42 |
| **Total** | **44 / −890,91** | **82 / −1 794,09** |

Le résidu ne prouve pas une absence de tendance ; c'est seulement l'absence des
signatures définies. Les pertes et gains du tableau sont ceux des trades réels,
pas ce qu'une règle aurait récupéré. Aucun sommet vendu fictivement.

### Gains restitués

12/44 = **27,27 %** et 29/82 = **35,37 %** des pertes avaient atteint au moins
+7 % avant la sortie, de façon certaine. Le MFE médian des pertes est
respectivement +3,08 % et +4,66 %. Vendre tôt aurait aussi touché les gros
gagnants : les cinq plus gros représentent 86,85 % des gains réalisés de 2025
et 41,26 % de ceux de 2026. Aucun calcul de récupération brute ne remplace un
rejeu de portefeuille conservant capital, frais, ordres et risque.

### Faux départs immédiats

Flag non exclusif : 3/44 et 7/82. Les deux clôtures sont observables avant la
sortie pour43/44pertes2025 et82/82en2026 ; le cas inconnu n'est pas considéré
comme un faux départ absent. Deux cas 2026 ont déjà la signature gain
restitué et restent dans cette catégorie prioritaire. La définition est stricte :
cela ne dit pas que toutes les autres cassures étaient bonnes ou qu'un échec
plus tardif était impossible. Après dix minutes, l'information est nouvelle :
elle ne peut pas filtrer rétroactivement l'entrée.

### Rebond après stop : ce n'est pas une preuve d'un stop trop serré

Flag non exclusif parmi les perdants : **20/44** en 2025, **38/76** fenêtres
complètes en 2026 ; six autres fenêtres de perdants sont censurées. Certaines
possèdent déjà une autre signature et ne sont donc pas dans la ligne principale
« rebond ». Rebond = clôture 5m +7 %, après exclusion entière de la bougie de
sortie, avant la fin de la 20e séance théorique depuis l'entrée.

Pour ces rebonds, le délai médian depuis le stop est de **5,57 / 7,11 jours
calendaires**. La baisse médiane depuis le prix d'entrée, observée après la
bougie du stop et avant la clôture de rebond, atteint au moins **11,31 % /
10,21 %**. 13/20 et 21/38 traversent au moins −10 %. Ce sont des bornes : le
low de la bougie du stop peut rendre la baisse plus forte ; son ordre intrabar
est inconnu. L'auditeur publie les deux bornes dans
`poststop-adverse-bounds.csv` (91 rebonds tous trades, à joindre aux pertes).

Exemples descriptifs, pas titres à exclure : BLMN, entrée 27/03/2025, rebond
environ 26 jours calendaires après le stop avec au moins −26,93 % depuis
l'entrée ; MXL, entrée 03/06/2026, rebond environ 26 jours après le stop avec
au moins −32,45 %. Garder ces positions aurait immobilisé du capital et exposé
à ces baisses. Ni suppression du SL, ni conservation « jusqu'au retour ».

## Peut-on reconnaître ces cas à l'entrée ?

Onze sondes fixées avant le calcul, séparées des colonnes de résultats futurs
dans `pre-entry-observables.parquet`. Daily titre agrégé depuis les séances
SIP raw complètes précédentes ; aucune barre future ou totalité du volume du
jour d'entrée. SPY = ancien cache EODHD split, pas nouveau flux SIP.

AUC ci-dessous dans le sens hypothétique fixé ; 0,50 = absence de séparation
par rang dans cet échantillon. Aucun seuil optimisé, ni score combiné ajusté.

| Sonde / hypothèse | AUC 2025 | AUC 2026 | Lecture |
| --- | ---: | ---: | --- |
| Meilleur rang Oracle | 0,563 | 0,495 | Non confirmé en 2026 |
| Signal plus récent | 0,407 | 0,517 | Sens non stable |
| Entrée plus tôt | 0,384 | 0,476 | Pas de confirmation |
| Extension moins forte en ATR | 0,407 | 0,500 | Pas de confirmation |
| Gap plus positif | 0,659 | 0,481 | Avantage 2025 non confirmé |
| Volume de confirmation plus élevé | 0,432 | 0,482 | Pas de confirmation |
| Momentum20 plus fort | 0,250 | 0,515 | Sens non stable |
| Position plus haute face à MA20 | 0,321 | 0,483 | Pas de confirmation |
| ATR relatif plus faible | 0,386 | 0,592 | Avantage 2026 non confirmé |
| Momentum20 SPY plus fort | 0,346 | 0,483 | Pas de confirmation |
| Volatilité20 SPY plus faible | 0,470 | 0,444 | Pas de confirmation |

Ne pas retourner après coup les signes défavorables et les présenter comme
validés. Ce n'est pas un test de toutes les features, du consensus ou des news,
ni une démonstration d'impossibilité de prédire la direction.

Couverture des sondes titres à 21 séances : 33/53 et 109/120, dont seulement
5/33 gagnants couverts en 2025. Autres sondes : 53/53 et 120/120. Après sélection
chronologique de fenêtres 20 séances sans chevauchement par symbole :
27 clôtures (3 gagnantes) et 79 (30 gagnantes). Les AUC 2025 de ce contrôle ne
sont pas publiées, faute des cinq gagnants minimum prévus. Les fenêtres partagent
encore le marché ; pas des essais indépendants. 2025/2026 déjà observés.

## Concentration et contexte du compte

Les cinq plus grosses pertes représentent seulement 17,10 % et 9,41 % des
pertes : pas quelques accidents qui expliqueraient tout. Un symbole peut avoir
plusieurs pertes ET un gros gain : PLTR en 2025 cumule −59,34 USD de pertes mais
reste à +134,67 USD net ; TROX en 2026 −76,16 USD de pertes mais +72,45 USD net.
Ne pas fabriquer une blacklist après lecture.

En 2025, B4 réduit l'allocation dès le 10 avril, puis sur 183 séances ; minimum
0,1. Les 53 clôtures proviennent donc d'entrées janvier–avril, pas de toute
l'année avec exposition constante. En 2026, allocation B4 à 1 sur les séances
du replay. Ce diagnostic est conditionnel aux trades effectivement autorisés.
La table `concentration-month.csv` groupe les PnL clôturés par mois D'ENTRÉE :
ce n'est pas le rendement mensuel du compte, qui inclut positions ouvertes/MTM.

## Vérification et limites

- **12 tests initiaux et un test complémentaire d'horloge passent** : chronologie préfixe, high/low de sortie,
  instant exit, gap, censure, clôture vs mèche, catégories et statistiques.
- 173 contrôles préfixes exactement reproduits ; aucune sonde ne change après
  troncature des données à l'entrée.
- Audit scalaire V2 des173signatures et bornes post-stop à la bonne horloge :
  PASS. Réconciliation des achats/PnL conservée ; tables des features et des
  44cellules statistiques exactement identiques après correction.
- Aucun franchissement des deux ruptures d'identité connues dans le registre
  sur les fenêtres examinées. L'inventaire d'OST du snapshot contient **zéro
  ligne** : il n'est donc PAS une preuve d'absence d'OST/splits/dividendes.
  Les mesures raw et les features gardent cette réserve de qualité.
- Cohorte amont sélectionnée sur couverture future, univers survivant,
  métadonnées actuelles, SPY daily révisable ; pas certification PIT complète
  ni garantie d'exécution au stop. Même assistant, pas seconde revue humaine.
- Aucune modification de modèle, batch, YAML, moteur de risque, protection,
  SQL, téléchargement, entraînement ou backtest économique nouveau.

**Suite non lancée :** aucune règle nouvelle n'est justifiée par cet audit
seul. Conserver le témoin et les stops ; ne pas annoncer une hausse du taux
gagnant. Une future hypothèse devra différer des P02/P05/P06 déjà essayées,
être fixée avant test et jugée au rendement/DD après coûts, pas au seul taux.
