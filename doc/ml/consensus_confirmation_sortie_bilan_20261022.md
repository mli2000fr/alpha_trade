# Consensus : trois variations consécutives et sortie sur information inverse

22 octobre 2026. **CALCUL BORNÉ TERMINÉ / EFFECTIF INSUFFISANT / H5 EN ATTENTE
DE PRIX ET DE MATURITÉ / PAS DE PROMOTION.**

La confirmation produit très peu de signaux. H3 donne un petit résultat positif,
mais sur **sept cas d'une seule date**. La sortie sur information inverse n'a
pas encore de parcours complet permettant d'en mesurer l'apport. Ni rejet
universel de la piste,ni gain démontré.

[Protocole figé](consensus_confirmation_sortie_protocole_20261022.md),
[amendement technique de base de prix avant résultats](consensus_confirmation_sortie_amendement_split_20261022.md).
Canonique : `artifacts/research/us_consensus_confirmation_exit/20261022-v2/`.

## Périmètre et absence de nouvelle collecte

- Même univers courant **1 790 titres**, pas uniquement Oracle TOP10.
- Réutilisation des **13 448 paires** du dernier audit de consensus, huit dates
  de décision13–22octobre ; cutoff de features inchangé **20:15:54UTC le22**.
- Nouveau cutoff de prix **22octobre20:55:43.605556UTC /22:55:43Paris**.
  Une actualisation READ ONLY des prix déjà stockés ne fournit toujours que
  **11 548 barres SIP,1 651symboles incluantSPY,12–20octobre**.
- Pas de fournisseur/LLM,entraînement,écritureSQL,ordre,modèle/configuration/batch
  modifié. Les collectes et téléchargements en cours sont préservés.
- V1 conserve la préparation,non exécutée sur les prix. V2 adapte seulement
  la validation à la vraie base **SIP split-adjusted** ; même features,cutoffs,
  protections et signaux. Aucun prix n'est rebaptisé raw,pas de fallback.

Les réserves du [bilan de fiabilité](consensus_fiabilite_bilan_20261022.md)
persistent : horloge d'ingestion locale non certifiéeUTC,max conservateur,
devise/trimestre non qualifiés globalement,contributeurs inconnus,univers
actuel survivant,prix rétrospectifs/OST non intégralement certifiés. Les chiffres
ne sont donc pas des signaux de production ou un backtest portefeuille fidèle.

## Règles réellement comparées

**A** : une variation positive de revenu moyen→LONG,négative→SHORT.

**B** : trois variations non nulles de même signe,connues avant trois ouvertures
NYSE successives. Cela nécessite une chaîne exacte de **quatre observations**,
même ancrage fiscal,au moins3analystes,nombre inchangé à travers toutes les
paires. Stabilité,manque,compte changé,période différente ou jour absent cassent
la confirmation. Trois copies du même consensus ne sont pas trois confirmations.

**C** : mêmes entrées queB ; aprèsH1,sortie au premier open où une variation
inverse comparable est déjà connue. Stabilité/manque n'inventent pas une
sortie. Compte et ancrage doivent rester compatibles avec l'entrée. Pas de
retournement automatique de la position dans l'autre sens.

Protections communes **TP10/SL5**,sans trailing,reprises du contrat consensus
existant : pas optimisation et pas les paramètres Winner de production.
Gap-stop exécuté à l'open avant sortie d'information ; gapTP plafonné ;
sortie d'information à l'open avant lecture de son futur low/high ; collision
intrajournalière stop/TP non résolue→stop d'abord. Sinon close de l'horizon,
entrée incluse. H5primaire,H1/H3secondaires,H10maturité seulement.

Les résultats deA diffèrent donc du précédent audit **sans barrières** :
ne pas attribuer cette différence à la confirmation. Ici tous les bras ont
exactement les mêmes protections.

## Fréquence : 12 signaux seulement

Sur les13 448paires : **1 299 variations simples** admissibles contre
**12 confirmations**,9titres,deux dates,4LONG et8SHORT.

| Entrée | LONG confirmés | SHORT confirmés |
|---|---|---|
|16octobre | CME,H,NCLH | BLDR,NDAQ,WYNN,XYL |
|19octobre | CME | AXSM,BLDR,VMC,WYNN |

Ce sont12opportunités,**pas12positions indépendantes d'un portefeuille** :
certains titres réapparaissent pendant qu'une précédente position pourrait
encore être détenue. Les statistiques principales sont par occasion ; le
contrôle sans chevauchement figure séparément,aucun capital n'est simulé.

Motifs de non-confirmation :9 927zéros/manques/paires non admissibles,
3 479séquences sans trois jours successifs,30signes contraires. Aucun seuil
abaissé pour augmenter l'effectif. Les journées ont déjà été examinées dans
d'autres diagnostics : pas une confirmation indépendante.

## Résultats des parcours complets

Exiger le **même chemin complet et mature** pourB etC,même si une sortie
anticipée aurait pu survenir. Ne pas conserver uniquement les sorties rapides
connues lorsque les parcours de comparaison sont incomplets.

| Horizon | Variante | Évaluées | Dates | Gagnantes brutes | Moyenne brute | Après16bps illustratifs |
|---|---|---:|---:|---:|---:|---:|
| H1 | A,variation seule |937|5|48,24 %|−0,138 %|−0,298 %|
| H1 | B,trois variations |12|2|50,00 %|+0,028 %|−0,132 %|
| H1 | C,+sortie inverse |12|2|50,00 %|+0,028 %|−0,132 %|
| H3 | A,variation seule |621|4|41,71 %|−0,568 %|−0,728 %|
| H3 | B,trois variations |7|1|42,86 %|+0,377 %|+0,217 %|
| H3 | C,+sortie inverse |7|1|42,86 %|+0,377 %|+0,217 %|
| **H5primaire** | B etC |**0**|**0**|non mesuré|non mesuré|non mesuré|

Pas de rendement cumulé,annuel,DDmax ou montant final calculé.16bps est une
friction aller-retour **hypothétique**,pas un tarif réel ; capital,sizing,
levier,empruntSHORT,quotes et fills non certifiés. Les protections sont des
barrières nominales non arrondies au cent,pas des ordres broker vérifiés.

À H3,la médianeB/C reste **−0,337 %**,malgré la moyenne positive. Parmi ces
sept cas :3LONG tous positifs,moyenne+1,817 % ;4SHORT tous négatifs,moyenne−0,703 %.
Une seule date ne valide ni LONGniSHORT. À H1 :4LONG,25 %gagnants et−0,785 %
brut ;8SHORT,62,5 %gagnants et+0,434 %brut. Pas de choix du côté après ces chiffres.

### Comparaisons moins trompeuses

- Aux **mêmes dates d'entrée queB**,A donne−0,029 %brut àH1(506cas/deuxdates)
  et−0,206 %àH3(190cas/unedate). Cela contextualise la baisse d'effectif sans
  créer une preuve de sélection robuste.
- Sur les **mêmes12/7entrées et mêmesTP/SL**,contrôles toujoursLONG/SHORT :
  H1−0,551/+0,551 % ; H3+1,180/−1,180 %. La confirmation signéeH3+0,377 %
  ne bat donc pas le simpleLONG sur ces mêmes sept cas. Ce contrôle n'autorise
  pas non plus la promotion d'une stratégieLONG,dont l'effectif est minuscule.
- **Delta C−B :0point**,12casH1 et7casH3. Aucune sortie inverse exécutée
  dans les fenêtres complètes connues. ÀH1,cette identité est mécanique avec
  des snapshots quotidiens : une information aprèsH1close ne permet pas une
  vente rétroactive à ce close.
- Contrôle conservateur sans chevauchement,résorption des créneaux sur tous
  les jours de features avant le filtre : H1B/C12cas ; H3sept ; H5zéro.
  Ce dernier zéro provient de ce calendrier de réservation et n'affirme pas
  qu'il n'existe aucune opportunitéH5 ; ce n'est pas une simulation de portefeuille.

## Ce qui empêche d'évaluer la sortie inverse et H5

Les sept entrées du16octobre ont leur cinquième clôture le **22octobre**,
déjà passée au cutoff. Mais les barresSIP des21/22octobre manquent dans
l'export : elles sont **inconnues**,pas perdantes ou réussies.
Les cinq entrées du19octobre sont immaturesH5 jusqu'au **23octobre après clôture**.
ÀH3,les cinq entrées du19requièrent le close21octobre,absent lui aussi.

**Un exemple réel de variation inverse apparaît : CME,le21octobre.** Le consensus
de revenus baisse alors après les confirmations haussières,avec le même
ancrage/nombre. La règleC aurait demandé une sortie à l'open21,bien après
réception de l'information et sans utiliser son futur low/high. Le prixSIP
de cet open manque : aucune plus-value/perte de cette vente n'est inventée.
Les occurrencesCME16/19 se chevauchent et ne sont pas deux positions
indépendantes. Aucun bienfait de cette sortie n'est encore démontré.

Il n'y a **aucun résultat H10** ; les douze confirmations sont encore immatures.
L'ancien évaluateurH10 du19octobre n'a pas été relancé ni modifié.

## Décision et reprise précise

**Pas de promotion,pas d'abandon universel.** H1ne couvre pas les coûts
illustratifs ; H3est un petit résultat positif sur une seule journée ; H5et
l'apport de la sortie inverse restent non évaluables. La confirmation50dates/
100épisodes précédente n'est pas assouplie.

Suite bornée,uniquement après nouveauGO :

1. Actualiser les prixSIP manquants via les collectes existantes,conserver leur
   provenance,ne pas basculer vers une autre source pour améliorer le résultat.
2. Attendre les fins de fenêtres ; nouveau cutoff de prix et dossier immuable,
   mêmes 12 entrées, aucune analyse de seuils ou choix de gagnants après observation.
3. Pour surveiller les opens futurs,archiver les nouvelles observations réellement
   reçues avant ces opens. Une absence de feature future dans le dossier figé
   ne signifie pas « aucun signal inverse ». Les anciennes entrées restent figées.
4. RefaireB/C sur mêmes chemins,notammentCME21 ; conserver les réserves restantes.

Aucune collecte supplémentaire,réparationSQL,commande d'exécution,activation,
surveillance automatique ou entraînement n'a été lancé ici.

## Livrables et contrôles

`protocol.json`,`frequency.json`,`features.parquet`,`prices.parquet`,
`prices-ready.json`,`cases-H1/H3/H5.parquet`,`report.json`,`final-audit.json`,
`inverse-feature-coverage.csv`,`confirmed-matched-protection-controls.csv`.
Les inconnus/immatures restent dans les cas et rapports ; aucune ligne effacée
pour embellir les moyennes. PréparationV1conservée,pas écrasée.

**105tests passent**,dont22nouveaux sur confirmation,chronologie,stop/TP et
baseSIPsplit. Revue technique séparée :13 448séquences,12confirmations et
**1 835parcours scalaires** ; sorties H1B/C identiques,priorité des gaps,
dates de disponibilité et appariements vérifiés. Même assistant,pas seconde
revue humaine indépendante. Aucune certification complète du fournisseur/OST/live.

Rapport SHA256 :
`ef1dc6144062e74be446e7b04a493d62cfc54fb924505e1661accdd8a1560060`.

Sources :
`scripts/research/us_consensus_confirmation_exit_20261022.py`,
`scripts/research/us_consensus_confirmation_exit_split_20261022.py`,
`scripts/research/us_consensus_confirmation_exit_audit_20261022.py`.
