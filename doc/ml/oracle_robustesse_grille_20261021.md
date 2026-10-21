# Robustesse de la grille Oracle : protocole borné

GO du21octobre2026. Audit rétrospectif de la grille complète1x/B4DD15 ; pas
nouvel entraînement, seuil optimisé, données SQL/fournisseur/LLM ou ordre.
Référence préexistante : **SL7 / trailing15 / H20 / sansTP**. Capital4kUSD
indépendant chaque année/sens ;2025 et2026au30septembre déjà étudiées.

## Critères déclarés avant les nouveaux calculs

Sur tous les144profils par sens de la grille scellée : voisin=une seule
dimension modifiée d'un cran dans les niveaux testés. OFF est un niveau
catégoriel explicite, pas une distance numérique. Description de plateau
positif : centre positif dans les deux années et au moins75%de ses voisins
positifs dans les deux années. Les DD et dispersions sont publiés séparément ;
«plateau positif» ne signifie pas risque acceptable ni validation live.
Aucun nouveau champion ne sera choisi sur ce classement rétrospectif.

Famille bornée pour les nouveaux stress : référence et cinq voisins immédiats :
SL5/TR15/H20/sansTP ; SL7/TR10/H20/sansTP ; SL7/TR20/H20/sansTP ;
SL7/TR15/H15/sansTP ; SL7/TR15/H20/TP10.

**86rejeux**, LONG et SHORT, deux années, dans un dossier neuf :

- 4témoins de la référence, reproduction obligatoire des transactions,
  positions ouvertes et valorisations5m de la grille scellée.
- 24stress coûts sur les six profils :8→25bps par opération, achat ET vente.
- 24stress délai : entrée retardée d'une bougie5m, prix d'open réellement
  observé ; signal d'origine conservé, limite de gap recontrôlée. Pas de
  report à la séance suivante si la bougie contiguë n'existe pas.
- 4stress conjoints25bps+5m sur la référence.
- 16rejeux sans chacun des trois principaux contributeurs positifs, puis sans
  les trois ensemble. Classement par PnL net original incluant MTM des positions
  ouvertes. **Sensibilité avec recul**, pas liste noire déployable ni prévision.
- 14rejeux sans nouvelles entrées pendant chacun des trimestres couverts
  (4en2025,3en2026), séparément. Conserver tous les prix et positions anciennes,
  le cash et l'état B4 continus : ne pas soustraire un PnL ou remettre le compte à zéro.

## Fidélité des calculs

Coûts via le modèle canonique : commission1bps, demi-spread5bps ; slippage2→19bps.
Débit réel dans le simulateur à chaque jambe ; marge disponible, quantités,
equity et B4 recalculés. Pas simple retrait de frais des transactions d'origine.
Borrow SHORT0,3%annuel/252 et financement6,5%ACT360 inchangés.
Le budget de taille suit les formules natives historiques, sans ajouter une
nouvelle réserve de risque spécifique aux frais.

Audit historique réutilisé sans modifier son fichier : seules ses trois
constantes de frais8bps sont spécialisées au taux du cas via AST contrôlé,
afin de garder tous ses contrôles cash/exits/B4. Nombre de remplacements exact
et non-modification du module testés ; audit de coût indépendant prévu en plus.
SL/TP/trailing/gaps sont toujours résolus selon l'ancien contrat intraday
conservateur. Les gaps réellement archivés sont décrits, pas de faux chocs
de prix artificiels ajoutés ou de stop garanti supposé.

Ancien horizon **J+HdepuisOracle, attente incluse**, pas le nouveau runtime de
vingt séances depuis l'entrée/open21. Demi-position1x, max8positions et risques
de concentration historiques, mêmes admissions, bornes annuelles et reprises.

## Limites et interprétation

Même213campagnes/72titres, OracleparcoursCatBoost de recherche, pas champion
LightGBMproduction ni tout TOP10historique. Sélection par prix futurs complets,
univers actuel et daily retraité : biais de couverture/survivants et réservePIT.
Intraday2024 nonqualifié. Fills/borrow/CA noncertifiés, pas paritélivecomplète.

2025/2026 déjà vues : définir aujourd'hui ces critères n'en fait pas un
protocole historiquement exante ni un nouvel échantillon indépendant. Publier
tous les résultats, pas seulement les positifs ; aucun p-value ou Sharpe
«déflaté» de fonction nonqualifiée. Les suppressions de titres/trimestres sont
des diagnostics d'un système dépendant de son chemin, pas des contributions
causales additives. La conclusion peut être «fragile/nonpromouvable».

## Suivi

Commande : `python -u -m scripts.research.us_oracle_grid_robustness`.
Dossier faisant foi : `artifacts/research/us_oracle_grid_robustness/20261021-v2`.
V1 interrompue sur faux écart de comparaison dates en mémoire/JSON ; conservée
avec source et note de terminaison. Transactions et marques déjà identiques.
V2 compare les exports des deux côtés et recalcule les86cas, sans fusion partielle.
`progress.json` suit les86cas ; `neighborhoods.csv` publie les288profils
LONG/SHORT sur deux années ; `annual-summary.csv`, contributions originales,
transactions/équités et audits gardent toutes les mesures.

## Résultats terminés et contrôlés

**V2 :86/86rejeux terminés, zéro échec, environ3min04 hors préparation.**
Quatre témoins reproduits avec comparaison exacte des valeurs/dtypes des
transactions et marques5m, et des positions JSON scellées. Audits historiques
paramétrés des coûts/exits/cash/B4 passent sur les86comptes ; audit distinct
des6907lots admis et des identités prix/frais/emprunt/MTM : erreur maximale
1,34e-11USD. **105tests réussis**, rapport
`artifacts/tmp/oracle-robustness-final-tests-20261021.xml`.
Même assistant, pas revue humaine indépendante. Résultats exploratoires,
pas certification de parité opérationnelle/live.

### 1. Voisinages de la grille complète

Sur144profils LONG, **14 sont positifs dans les deux années** ; un seul satisfait
le critère descriptif centrepositif+75%devoisinspositifs. C'est la référence
déjà suivie SL7/TR15/H20/sansTP, pas un nouveau champion trouvé aujourd'hui.
SHORT :0/144profils positifs dans les deux années, aucun plateau positif.

La référence LONG a **4/5voisins positifs dans les deux années**, mais les
montants sont très variables. Même voisinage, mêmes frais8bps et B4DD15 :

| Modification unique par rapport à la référence | LONG2025 | LONG2026au30/09 |
| --- | ---: | ---: |
| Aucune :SL7/TR15/H20/sansTP | +26,83% | +16,94% |
| SL5 au lieu deSL7 | +4,57% | +9,61% |
| Trailing10 au lieu de15 | +12,51% | +2,44% |
| Trailing20 au lieu de15 | +21,24% | +38,30% |
| H15 au lieu deH20 | +33,59% | +1,14% |
| TP10 au lieu de sansTP | −12,21% | +20,45% |

Médiane des cinq voisins :+12,51/+9,61%, minimum annuel−12,21%, DD maximum
22,81%. La stabilité locale du signe est donc réelle dans l'échantillon,
mais ne justifie pas de dire que le rendement ou le risque sont stables.

### 2. Coûts et délai d'entrée, vrais rejeux

La référence LONG reste positive sur les deux années pour les trois stress :

| Scénario | Rendement2025 | DD2025 | Rendement2026 | DD2026 |
| --- | ---: | ---: | ---: | ---: |
| Témoin8bps/jambe | +26,83% | 22,36% | +16,94% | 20,32% |
| Frais25bps/jambe | +19,57% | 23,23% | +4,62% | 19,21% |
| Entrée retardée de5min,8bps | +37,51% | 22,99% | +4,91% | 18,67% |
| Frais25bps et retard5min | +33,58% | 22,38% | +4,09% | 19,19% |

Chaque ligne part de4kUSD par année ; 2026 n'est pas une année complète.
Capital final au stress conjoint :5343,37USD en2025 et4163,72USD en2026,
contre5073,27/4677,77USD pour les témoins. Ils ne s'enchaînent pas comme un
compte continu. Un retard qui améliore2025 mais dégrade2026 n'est pas une
raison d'introduire un délai «optimal» ; le scénario montre la sensibilité
aux fills et à la trajectoire de capital.

Sur les six profils LONG de la famille, seuls **trois restent positifs dans
les deux années pour les deux stress individuels** : référence, H15 et
trailing20. Les marges de certains sont minuscules :H15+0,53%en2026 au délai,
trailing20+0,36%en2026 aux frais25bps alors que son témoin gagnait+38,30%.
SL5 bascule négatif2026 aux frais et dans les deux années au délai ; trailing10
devient négatif2026 aux frais. Aucun profil SHORT ne passe ces stress.
Ne pas confondre «positif dans ces hypothèses» et avantage statistiquement démontré.

### 3. Concentration par symbole, avec rejeu du portefeuille

Principaux contributeurs nets originaux, valorisation des positions ouvertes
incluse. Ce sont des informations connues après coup, pas des signaux d'entrée :

| Année LONG | Premier | Deuxième | Troisième | Somme des trois |
| --- | ---: | ---: | ---: | ---: |
| 2025 | MP+502,60USD | PLTR+386,53USD | SNDX+353,29USD | +1242,42USD |
| 2026 | MU+645,51USD | DOCN+274,80USD | QDEL+268,04USD | +1188,34USD |

Ces sommes dépassent les bénéfices nets totaux1073,27/677,77USD : le reste
contribue négativement dans le chemin d'origine. Cela ne donne PAS les
rendements d'un portefeuille sans eux ; les véritables contrefactuels rejoués sont :

| Nouvelles campagnes supprimées, par symbole | LONG2025 | LONG2026 |
| --- | ---: | ---: |
| Sans le premier contributeur | +16,35% | +0,47% |
| Sans le deuxième | +12,39% | +14,23% |
| Sans le troisième | +19,58% | +8,42% |
| Sans les trois ensemble | **−12,33%** | +5,64% |

2025 dépend nettement de ce groupe ;2026 dépend très fortement deMU pris
isolément. La suppression simultanée des trois2026 donne paradoxalement mieux
que la seule suppression deMU : interactions de cash/B4/tailles/admissions,
pas contributions additives ni preuve que les autres sont nuisibles.
Ces tests ne servent pas à retirer/réintroduire des symboles dans les univers.

### 4. Sensibilité aux trimestres d'entrée

Suppression des nouvelles entrées du trimestre indiqué, sans retirer les prix
ni fermer les positions antérieures. Ce n'est PAS le PnL du trimestre manquant :

| Trimestre sans nouvelles entrées | LONG2025 | LONG2026 |
| --- | ---: | ---: |
| T1 | +14,23% | +21,89% |
| T2 | +43,16% | **−0,38%** |
| T3 | +13,24% | +25,95% |
| T4 | +27,54% | Non couvert |

Les entrées deT2sont importantes au résultat2026 dans ce replay. En2025leur
suppression améliore au contraire le résultat : pas de règle saisonnière
«ne pas traderT2» défendable à partir de ces deux années. La perte restante
ne permet pas non plus de déduire un régime macro causal ; ce serait le point3
à diagnostiquer séparément, pas un filtre nouvellement validé.

### 5. Risque de queue toujours présent

Référence :9/8sortiesGAP_STOP LONG en2025/26,17/14SHORT. Pire rendement net
d'un trade LONG−16,14%/−9,76% et SHORT−50,90%/−15,98%. SL7 et B4DD15 ne
garantissent donc ni un trade limitéà−7%, ni un DD global limitéà15%.
Référence LONGDD22,36/20,32%, SHORT37,05/27,63%, inchangées dans les témoins.

Les43rejeux SHORT de cet audit restent tous négatifs, de−31,19%à−12,51%.
Il n'y a pas de justification à chercher à les sauver par une autre combinaison
de ce voisinage après lecture des résultats.

## Verdict et suite bornée

**LONG : stabilité locale et résistance aux stress testés, mais forte
concentration et fragilité de trajectoire ; pas validation pour promotion.**
Ce n'est pas uniquement un sommet isolé de la grille, mais ce n'est pas non
plus une performance robuste au sens large : supprimer un petit groupe de
contributeurs ou un trimestre peut annuler/inverser le résultat.

**SHORT : aucun avantage économique soutenu dans ce périmètre.**

Référence conservée comme témoin de recherche, pas nouveau paramétrage.
Pas de choix du trailing20 à cause de2026, de blacklist future des perdants,
de décalage d'entrée choisi sur2025, ni d'extrapolation au levier2x ou au
nouveau contrat de détention du watcher. Les critères fixés aujourd'hui
restent rétrospectifs ; une validation future réellement figée et une meilleure
couverture sont nécessaires pour une conclusion plus forte.

Les scénarios, frais, gagne/perd/durées, capital engagé, positions ouvertes et
réponses B4 sont tous sauvegardés dans `scenario-effects.csv` et les dossiers
des86cas. Tables complémentaires : `family-stress-summary.csv`,
`cost-audit.csv`, `neighborhoods.csv`, `original-symbol-contributions.csv`.
Contrôles : `final-review.json`, `post-review.json`.
Aucun modèle, configuration de production, univers, donnée SQL ou ordre modifié.
