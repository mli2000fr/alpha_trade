# US — couverture CALL/PUT/OI et direction sur TOP10 % Oracle puis TOP5 LONG

## Périmètre fixé

Demande du15novembre2026 : actualiser la couverture de l'univers tradable et
mesurer les informations directionnelles à H5/H10, d'abord sur le TOP10 %
Oracle, puis sur les TOP5 retenus après per-symbol. Aucun nouveau modèle,
Predict servable, appel fournisseur, ordre ou changement de production.

Audit SQL US `alpha_trade` en UTC, REPEATABLE READ et READ ONLY, cutoff réel
**15novembre2026 à20:06:31 UTC**. Univers de référence actuel :
`config/univers_batch/univers_filtred_tradable.txt`, **1 790 symboles**, figé
par empreinte ; pas les13 105symboles du fichier large `stock_bars_daily.txt`,
ni un univers dépendant du capital d'un compte. Ce n'est pas une certification
des membres historiquement tradables à chaque date.

Modèle annuel : `model-factory-20261107222627-db80b0`, Oracle parcoursH10 et
per-symbol LONG/SHORT. **Données d'entraînement arrêtées fin2025**, calibration
et étiquettes disponibles avant les signaux2026 ; poids et AUC vérifiés par
empreinte. Les fichiers et prédictions ont été calculés en novembre2026 :
ces classements historiques sont **reconstruits**, pas des décisions papier
physiquement prises en septembre/octobre. Aucun score de c59bed entraîné sur
2026 n'est substitué à ces scores. Zéro entraînement/inférence supplémentaire.

## Couverture : distinguer reçu, complet et utilisable à une date

Les deux fournisseurs enregistrés sont **Alpaca** : snapshots `indicative`
dans `stock_option_snapshots`, OI provenant des métadonnées des contrats ;
barres options dans `stock_option_bars_delayed`, feed déclaré
`historical_default`. Ne pas assimiler cela à de l'OPRA/NBBO certifié ou à des
ordres acheteurs/vendeurs signés. Le volume est celui des contrats collectés,
pas une garantie de chaîne exhaustive de toutes les options d'une action.

Premiers/derniers reçus :12septembre–14novembre2026 pour les snapshots,
14septembre–14novembre pour les barres ;46datesUTC de collecte pour chaque
table. Les fournisseurs ayant aussi reçu des symboles hors univers, la
couverture ci-dessous est explicitement l'intersection avec les1 790.

| Mesure cumulée dans l'univers | Titres | Couverture |
| --- | ---: | ---: |
| Au moins un snapshot options | 1 652 | 92,29 % |
| Au moins une barre options, tous timeframes | 1 658 | 92,63 % |
| Au moins une barre options **30Min** utilisée par le filtre | 1 615 | 90,22 % |
| Snapshots CALL **et** PUT, pas nécessairement simultanés | 1 630 | 91,06 % |
| OI numérique CALL et PUT, pas nécessairement même strike/date | 1 397 | 78,04 % |
| Volume30Min CALL et PUT | 1 519 | 84,86 % |
| Score combiné techniquement qualifié **au moins une fois**, lecture ASOF72h | 1 024 | 57,21 % |

Ce ne sont pas des taux de couverture quotidienne. À la dernière séance,
**13novembre**, avec les données déjà reçues au cutoff du15novembre :

- **90/1 790, soit5,03 %**, ont le score combiné exploitable en lecture ASOF72h.
- Sur les45séances du14septembre au13novembre : moyenne **218,64titres/jour,
  soit12,21 %**, avec les règles d'échéance/strike actuelles.
- Avec la qualification native strictement identique à la production :
  **0/1 790 sur cette dernière séance**, moyenne195,71/jour (10,93 %) sur
  ces45séances, trois séances totalement sans score.

Décomposition indépendante sur la dernière séance : snapshots reçus récents
pour1 568titres, mais seulement281avec contrats dans15–25jours ;231après
OI numérique/strike à±5 % du spot, puis176avec paire CALL/PUT au même strike
et à la même échéance. Côté volumes,1 215titres reçus dans les96h d'inventaire,
184dans le tenor/séance/fraîcheur requis et97avec paire CALL/PUT d'échéance
commune. Intersection finale **90**. Une partie de l'écart vient donc de la
définition de surface, pas seulement d'un échec de collecte.

## Problème de date détecté, production inchangée

`service/options_directional/history.py` borne les reçus à la journée civile
new-yorkaise deJ. `features.py::_rows` exige aussi reçuNY=J ; pour les volumes,
il exige en plus séance de la barre=J. Les deux conditions rejettent les
barres deJ reçues après minuitNY, même si elles sont arrivées **avant la
décision d'ouverture suivante**.

Exemple réel : barre A du12novembre15:00UTC, reçue le13novembre05:02UTC,
donc00:02NY, avant l'ouverture suivante et son cutoff14:25UTC. Le lecteur
actuel l'exclut à cause de la date de réception. Il ne s'agit pas d'inventer
une disponibilité historique ni du précédent problème d'affichage SQL/UTC.

Deux lectures sont comparées :

1. `STRICT_NATIVE` : lecteur actuel, sans changement.
2. `ASOF_72H`, recherche seulement : volume financier deJ, reçu/observé au plus
   tard cinq minutes avant l'ouverture suivante, aucune ligne de plus de72h,
   timestamp fournisseur non futur ; OI dernière connue dans la même limite.
   Tous les horodatages originaux sont conservés. Pour la dernière séance,
   la décision future est plafonnée au cutoff réellement observé du dimanche.

La fenêtre72h de cette lecture est une règle de **qualification de données de
recherche** ; le `max_age_hours` du store de production sert notamment à l'âge
du rapport de sélection et n'est pas automatiquement transformé ici en nouveau
réglage de production. Aucun fichier du service n'est modifié. Le moteur de
features natif est réutilisé avec un dictionnaire de globals isolé : mêmes
calculs, seule la qualification temporelle change. Quatre tests passent :
parité lorsque les dates concordent, inclusion d'un reçu tardif seulement
après sa disponibilité réelle, rejet des données futures/périmées/mauvaise
séance, absence de mutation du module natif et maintien du pool Oracle sans
forcer une sélection dans les cinq titres per-symbol.

## Classements et cibles, fixés avant résultats

31classements valides du1septembre au14octobre2026 : **179candidats/jour**,
TOP10 % du modèle complet, avant couverture options ou résultats futurs.
Les 31 classements sont conservés, soit **5 549 couples titre/séance**.
Les TOP5 per-symbol sont ceux de Q051, score LONG>0,50 et AUC de calibration
≥0,50 après classement ; pas de remplacement après rejet. Ici les155signaux
passent effectivement ces seuils :35sociétés différentes.

Les scores du15octobre au12novembre ne sont pas présents pour ce modèle.
Le13novembre a1 643scores/1 790 et est exclu du périmètre historique au seuil
modèle figé93 %, sans réutiliser le dénominateur Alpaca actuel du PAPER pour
fabriquer une éligibilité historique. Cette date n'est pas mûre H5/H10 de
toute façon. Les options disposent d'un historique plus long que le croisement
actuellement vérifiable avec les classements. **L'efficacité mesurée ne couvre
donc pas toute la collecte récente de novembre.**

Score inchangé : log(1+volumeCALL)−log(1+volumePUT) et équivalentOI ; rangs
percentiles, moyenne50/50, moitié supérieure et score strictement>0,50,
minimum quatre couverts. Tenor15–25jours calendaires, préférence20 ; OI même
strike CALL/PUT à±5 % du spotJ. Le score est normalisé sur le **même pool
Oracle couvert** pour les deux étages, pas recalculé sur les cinq titres pour
en forcer mécaniquement la moitié. Aucun SHORT automatiquement exécuté.
L'extension à179candidats est propre au test, sans modifier la borne du
formulaire/service de production.

Entrée de référence openJ+1. **Direction = mouvement absolu dominant à
l'intérieur deH5/H10** : maximum de hausse comparé au maximum de baisse
depuis cette entrée. Ce n'est pas le seul rendement du dernier jour.
Les égalités sont exclues des taux directionnels/AUC. Une autre cible évalue
les trades LONG indépendants SL5, sans TP/trailing, vente open6/open11 et
frais8pb par achat/vente. Ce n'est pas un replay Winner à capital partagé,
avec confirmations, coûts de financement, quotes, dividendes et limites
d'occupation répliqués.

## Résultats ASOF72h — lecture temporelle explicite

Croisement options/classements : **23dates du14septembre au14octobre**.

| Étage | Candidats avant options | Couverts volume+OI | Retenus par options |
| --- | ---: | ---: | ---: |
| TOP10 % Oracle | 5 549 | 848 / 15,28 % | 397 / 106sociétés / 23dates |
| TOP5 LONG per-symbol | 155 | 36 / 23,23 % | 10 / 8sociétés / 10dates |

Les pourcentages directionnels suivants comparent les cas **couverts** avant
filtre et les retenus. L'AUC utilise tous les cas couverts, pas seulement les
retenus. Au TOP5 les dates ne sont pas toutes identiques ; contrôle dates
communes fourni juste après, sans attribuer l'effet de couverture au score.

| Étage | Horizon | Haussiers parmi couverts | Haussiers après filtre | AUC combinée |
| --- | --- | ---: | ---: | ---: |
| TOP10 % Oracle | H5 | 425/846 =50,24 % | 221/397 =55,67 % | 0,561 |
| TOP10 % Oracle | H10 | 405/847 =47,82 % | 205/397 =51,64 % | 0,567 |
| TOP5 per-symbol | H5 | 8/36 =22,22 % | 3/10 =30,00 % | 0,500 |
| TOP5 per-symbol | H10 | 9/36 =25,00 % | 3/10 =30,00 % | 0,533 |

AUC volume seul / OI seule sur les mêmes cas : OracleH5 **0,534/0,562**,
OracleH10 **0,554/0,555** ; TOP5H5 **0,536/0,536**, TOP5H10 **0,551/0,556**.
Ces variantes sont décrites, aucun poids ou seuil n'est réoptimisé. AUC moyenne
par date, score combiné :0,552/0,588surOracleH5/H10. Les AUC quotidiennes TOP5
sont particulièrement instables, calculées sur quelques titres seulement.

### Traduction en trades LONG protégés SL5

Pour isoler la sélection des dates actives, la comparaison ci-dessous utilise
les couverts sur les **mêmes dates où le filtre admet une entrée**.

| Étage | Horizon | Sans filtre, couverts aux mêmes dates | Après filtre options |
| --- | --- | ---: | ---: |
| TOP10 % Oracle | H5 | 363/848 =42,81 %gagnants | 186/397 =46,85 % |
| TOP10 % Oracle | H10 | 269/848 =31,72 % | 127/397 =31,99 % |
| TOP5 per-symbol | H5 | 6/23 =26,09 % | 3/10 =30,00 % |
| TOP5 per-symbol | H10 | 3/23 =13,04 % | 2/10 =20,00 % |

Le TOP5 complet sans restriction de couverture avait50/155gagnantsH5
(32,26 %) et38/155H10 (24,52 %). Le sous-groupe couvert est moins favorable,
avec7/36H5 (19,44 %) et5/36H10 (13,89 %). Ne pas présenter30/20 % après filtre
comme une amélioration face au TOP5 complet : ces taux sont inférieurs et
l'effectif n'est que10. Le score ne doit pas recevoir le mérite d'une variation
due au choix des sociétés disposant d'options.

### Contrôles de dépendance

Les397cas ne sont pas397observations indépendantes. En espaçant les signaux
deHséances selon le calendrier, sans choisir les dates par rendement :

- OracleH5 :5dates, couverts69/140gagnants (49,29 %), retenus36/66 (54,55 %).
- OracleH10 :3dates,40/110 (36,36 %) contre20/52 (38,46 %).
- TOP5H5 :5datescouvertes/3datesretenues,2/10 contre0/3gagnants.
- TOP5H10 :3datescouvertes/1dateretenue,1/6 contre0/1gagnant.

En ne gardant que le premier cas couvert de chaque société : OracleH5
47,02→53,03 %gagnants (151→66cas), OracleH10 35,10→37,88 % ; TOP5
36,36→40 %H5 et27,27→40 %H10, mais seulement11→5cas. Aucun de ces petits
contrôles ne démontre un avantage robuste après per-symbol. Pas d'intervalle
de confiance binomial naïf ignorant le chevauchement.

## Comparaison avec le lecteur natif

Au TOP10 %, le lecteur natif historique fournit781cas couverts et369retenus :
haussiersH5 51,41→56,10 %, H10 48,33→51,76 % ; AUC0,551/0,554. TradesSL5
43,53→47,43 %H5 et31,88→32,25 %H10. Au TOP5 :32couverts,8retenus,
AUC0,490/0,536 ; taux sur huitcas trop petits pour être interprétés.
Les sorties complètes des deux modes restent dans les fichiers ; la lecture
ASOF n'est pas présentée comme déjà déployée.

## Conclusion et validation

**Petit indice directionnel dans le pool Oracle, surtout H5 ; pas de gain
incrémental confirmé sur le TOP5 per-symbol.** L'AUC voisine0,56 ne signifie
pas56 % de trades gagnants, et l'amélioration de cible de parcours H10 ne
se transforme presque pas en taux gagnant SL5. Une application bloquante après
per-symbol ne se justifie pas sur dix cas et une couverture aussi sélective.
Ne pas entraîner un nouveau modèle ni ajuster les poids sur cet échantillon.

Le problème de qualification de date est concret et doit être distingué de
l'efficacité financière du signal. Il faudra raccorder et tester séparément
une lecture avant décision avant de tirer une conclusion opérationnelle.
Q051 reste inchangé, aucun filtre options n'est ajouté à sa référence.
Après remise du bilan, l'utilisateur abandonne cette piste : aucune activation
ou optimisation supplémentaire n'est engagée.

66exports SQL bornés, comptés et scellés sans troncature :512 948snapshots et
399 458barres30Min dans l'univers ; prix/prédictions exportés et figés.
Validation indépendante **PASS** :5 549candidatsOracle,155per-symbol,
horodatages non futurs, couverture finale90recalculée par un deuxième chemin,
cohortes/numérateurs/dénominateurs recomptés, modèles et sources vérifiés.
Quatre tests de qualification temporelle et de sélection passent. Correction de type Decimal
du lecteur de recherche avant reprise en `analysis-v2`, sans changement des
prix ou des règles ; première préparation `analysis` conservée comme tentative
échouée, sans résultat publié. Production non modifiée.

Archives : `artifacts/research/us_options_q051_top_fraction/20261115-v1/` :
`inventory.json`, `raw-component-coverage.json`, `latest-qualification-funnel.json`,
`protocol.json`, `snapshot-seal.json`, exports sous`raw/`, puis`analysis-v2/`
avec`report.json`, `summary.csv`, `universe-daily-coverage.csv`,
`oracle-coverage.csv`, `decisions-before-outcomes.parquet`, `outcomes.parquet`,
`validation.json`. Scripts d'inventaire/analyse et validateur datés20261115
dans`scripts/research/`. Zéro appel fournisseur/LLM, fit, Predict, ordre ou SQLwrite.
