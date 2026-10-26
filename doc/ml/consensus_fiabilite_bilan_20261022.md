# Consensus EODHD : fiabilité de collecte et premier recul directionnel

22 octobre 2026. **AUDIT TERMINÉ / COPIE FIDÈLE SUR LE PÉRIMÈTRE CONTRÔLÉ /
RÉSERVES D'HORLOGE ET DE SÉMANTIQUE / PAS DE SIGNAL DIRECTIONNEL VALIDÉ.**

Ce bilan distingue trois questions : copie du fournisseur, comparabilité
économique des prévisions, et prédiction du prix. Une copie exacte ne prouve
ni l'exactitude des bénéfices futurs ni une stratégie LONG/SHORT rentable.

[Protocole initial](consensus_fiabilite_protocole_20261022.md),
[amendement prix SIP avant résultats](consensus_fiabilite_sip_amendement_20261022.md).

Canonique :
`artifacts/research/us_consensus_reliability/20261022-v1/sip-only-v2/`.
Le parent `20261022-v1` conserve l'export et l'arrêt technique avant résultat
sur prix multi-sources ; il ne remplace pas le dossier SIP validé.

## 1. Historique réellement disponible

Cutoff figé : **22 octobre 2026,20:15:54.864550UTC /22:15:54Paris**.
Inventaire READ ONLY / REPEATABLE READ, puis ROLLBACK.

- Toute la table EODHD au cutoff : **3 528 509 lignes,5 743 symboles**, premières
  réceptions le11octobre ; ce ne sont pas3,5millions de jours d'historique.
- Univers tradable courant : **1 790 titres** ; du11 au21octobre, **1 778 titres
  chaque jour**, soit99,33 %, environ146 000 périodes/horizons par date.
- **Onze dates complètes de collecte**, pas onze séances de trading indépendantes.
- Le22octobre, le run automatique est **RUNNING au cutoff** : seulement57titres
  avaient déjà été inscrits dans cet instantané. Ce n'est pas déclaré un échec.
  Ses174lignes proches-périodes sont réservées faute de fin de run au cutoff.
- Export technique borné : **57 800 lignes**, horizons`0q/0y`, périodes déclarées
  juin2026–juin2027. Le reste du contenu historique fournisseur n'est pas
  présenté comme intégralement audité au niveau de chaque payload.

La date fiscale d'un item,`+1q`, ou les comparaisons J−7/30/60/90 reçues
aujourd'hui ne donnent pas des vintages réellement collectés à ces anciennes dates.
La base préserve la première observation quotidienne : une relance le même
jour ne remplace pas automatiquement ce premier état.

## 2. La collecte recopie-t-elle correctement EODHD ?

**Sur les57 800lignes contrôlées :57 800/57 800 concordent avec leur item brut**
(hash, code émetteur, ancrage, horizon et tous champs normalisés). Ce résultat
vérifie la copie locale, pas la vérité financière du consensus.

Échantillon fixé sans prix : vingt émetteurs changés,dix stables,plus les
six contextes précédemment documentés. **112/112items** retrouvés exactement
dans **87enveloppes fournisseur** déjà archivées ; zéro enveloppe invalide.
Ce n'est pas une certification exhaustive des enveloppes du corpus.

### Deux incohérences déjà présentes chez le fournisseur

**15observations sur deux titres**, confirmées15/15dans15enveloppes :

| Titre | Observations proches-périodes | Anomalie |
|---|---:|---|
| ORCL |11,du11au21octobre | Période2026-08-31,`0q` : EPS moyen1,7383, inférieur au minimum1,81 ; maximum2,04 |
| EXE |4,du11au14octobre | Période2026-09-30,`0q` : revenu minimum1,994Md, moyenne0 et maximum0 |

Ces anomalies **ne sont pas introduites par notre normalisation**. Elles sont
réservées, pas corrigées arbitrairement. EXE ne devient pas un signal SHORT
parce qu'une estimation non disponible semble être encodée0. Une incohérence
EPS n'est pas automatiquement une incohérence de revenus ; contrôles séparés.

Sur toutes les anciennes périodes du fichier tradable, l'inventaire détecte
également22intervalles EPS et environ1 957–1 958intervalles revenus incohérents
par date complète. Beaucoup peuvent se répéter : ne pas annoncer autant
d'erreurs indépendantes ou que tout le reste est financièrement exact.

## 3. Réserve d'horloge constatée

Le serveur MySQL utilise par défaut`SYSTEM`, heure locale Paris, alors que
`observed_at`,`available_at` et les fins de run sont explicitement en UTC.
`ingestion_at` est un DATETIME rempli par défaut via`CURRENT_TIMESTAMP(6)`.

Dans les57 800lignes, ingestion−observation vaut **environ7 200secondes**
(minimum7 200,004s,médiane7 200,179s,maximum7 203,599s). Pour les57 626lignes
de runs terminés, l'ingestion interprétée naïvement UTC paraît postérieure
à la fin du run. La lecture directe des horloges confirme **+2h** entre
`CURRENT_TIMESTAMP()` et`UTC_TIMESTAMP()` sur cette période.

**Conclusion : l'heure d'ingestion n'est pas qualifiée comme UTC.**
Le max conservateur utilisé par ce pilote ajoute donc ici un retard artificiel.
Vérification descriptive sans correction : retirer ce champ du max ne change
la première ouverture admissible pour **aucune des57 626lignes terminées**.
Le diagnostic n'est ni recalculé pour l'améliorer ni requalifié en production.

À corriger séparément avant un usage PIT strict : écrire une ingestion UTC
explicite ou imposer UTC à la connexion du collecteur ; vérifier les horloges
du pipeline concerné et conserver les reçus originaux. **Ne pas soustraire
automatiquement deux heures à tout l'historique** : fuseaux de session et
changements d'heure doivent être établis pour chaque périmètre. Aucune ligne
SQL, configuration ou collecte n'a été corrigée par cet audit.

Preuve distincte : `clock-audit/server-clock.json` et`clock-audit/report.json`.
L'audit arithmétique des cutoffs n'est pas une certification sémantique UTC.

## 4. Variation de consensus et direction du prix : ce qui est mesurable

**Tout l'univers tradable**, pas uniquement TOP10. Paires entre deux ouvertures
successives, informations effectivement reçues avant les cutoffs, même titre,
ancrage et`0q`, état courant candidat à±100jours, au plus4jours de vieillissement.
Cela reste un heuristique d'ancrage, pas une certification du trimestre courant.

**13 448comparaisons,1 693titres,huit dates d'entrée du13au22octobre.**
Revenus à nombre d'analystes inchangé et≥3 :674hausses,625baisses,9 953stables.
Avec nombre changé :344hausses,293baisses et une stabilité. Manque ou<3 :
42hausses,50baisses et1 466stabilités/manques. Ces comptes précèdent les
contrôles de prix et ne sont pas des trades qualifiés.

Règle primaire figée : revenu moyen en hausse→LONG,baisse→SHORT ; stable/manquant
→abstention. Aucun seuil d'amplitude ajusté. Nombre d'analystes inchangé ne
signifie pas nécessairement mêmes personnes. Les conventions EPS restent
inconnues ; elles interviennent seulement dans les diagnostics secondaires.

### Prix utilisés

Deux flux quotidiens coexistent pour certaines dates en base. Le parent
s'arrête avant résultat plutôt que choisir un doublon arbitrairement.
La variante canonique utilise **Alpaca SIP uniquement**, sans fallback,
avant tout calcul de performance : **11 548barres,1 651symboles incluant SPY**,
du12au20octobre. Les prix manquent donc pour21/22octobre dans cet export.
Pas d'appel fournisseur ou rattrapage lancé par l'audit.

Tous les OHLCV de la fenêtre doivent être présents/valides/non remplis,
ajustement/source/identité stables et séance close avant cutoff. Pas de
remplissage, d'écrêtage ou d'utilisation d'un prix du jour inachevé.
Prix raw SIP, pas certification complète des OST, quotes ou exécutions.

### Résultats primaires courts

Le prix est mesuré depuis **l'open réellement postérieur à l'information**,
jusqu'à la clôture H1/H3/H5, entrée incluse. Sens correct = rendement terminal
dans le sens du changement de consensus ; **pas un TP avant SL**.

| Horizon | Occasions avec prix | Dates d'entrée distinctes | Bon sens | Retour signé moyen brut | Après16bps illustratifs |
|---|---:|---:|---:|---:|---:|
| **H1 primaire court** |937|**5**|**48,24 %**|**−0,171 %**|**−0,331 %**|
| H3 secondaire |621|4|43,48 %|−0,423 %|−0,583 %|
| H5 secondaire |239|2|38,91 %|−0,950 %|−1,110 %|

Ce sont des moyennes par occasion, **pas des rendements cumulés ou annuels**,
ni un backtest de portefeuille. Pas de capital,sizing,levier,TP/SL,marge,
emprunt SHORT,spread ou remplissage certifiés.16bps est une hypothèse fixe,
pas la mesure du tarif réel.

Les références toujours LONG/SHORT sont calculées sur les mêmes occasions :
à H1, respectivement−0,029/+0,029 % bruts, contre−0,171 % pour le sens consensus.
À H3,toujours LONG+0,733 % ; à H5,+2,159 %. Les signes consensus ne corrigent
donc pas simplement un effet haussier général sur ce petit échantillon.
L'excès SPY et la pondération par date ne révèlent pas d'avantage primaire :
excès signé équipondéré par date H1/H3/H5 **−0,095/−0,659/−1,289 %**.

À H1 : hausses de revenus469cas,45,42 %corrects,moyenne−0,200 % ; baisses468cas,
51,07 %corrects mais moyenneSHORT−0,142 %. Un taux légèrement>50 % ne suffit pas.

Contrôle sans chevauchement,tous motifs réservant leur créneau avant prix :
H1identique ; H3 **217occasions/deux dates**,48,85 %corrects,moyenne−0,191 % ;
H5 **27occasions/une date**,29,63 %corrects,moyenne−1,602 %. Ne pas lire des
centaines de sociétés comme des centaines de régimes indépendants.

## 5. Autres champs examinés, sans chercher un gagnant après coup

### EPS et concordance des deux métriques

EPS à nombre inchangé,base comptable inconnue : H1 **1 010cas,50,30 %corrects,
−0,031 %brut** ; H3 699cas,48,21 %,−0,212 % ; H5 272cas,39,34 %,−0,802 %.
EPS ET revenus concordants : H1 **489cas,48,47 %,−0,115 %brut** ; H3 322cas,
41,61 %,−0,611 % ; H5 129cas,34,88 %,−1,246 %. Aucun filtre promu.

### Le compteur baissier à sept jours est absent, pas zéro

Sur **57 800/57 800items**,`epsRevisionsDownLast7days` est absent des items bruts.
Les seules clés révisions présentes sont`epsRevisionsUpLast7days`,
`epsRevisionsUpLast30days`,`epsRevisionsDownLast30days`.
Pas de variante alternative de casse retrouvée. Le ratio UP7−DOWN7 n'est
donc pas calculable ; ce n'est pas un consensus unanimement haussier.

À clarifier avec le fournisseur si nécessaire : absence signifie-t-elle
« non fourni » ou un problème d'endpoint ? En attendant aucune imputation0.

### Diagnostic explicite ajouté après les premiers résultats, non confirmatoire

Le dossier `rolling-diagnostic/` a un protocole séparé **post-hoc** : les cinq
champs disponibles sont tous examinés et publiés, sans substitution silencieuse
du DOWN7 absent ni choix d'un meilleur après lecture. Leur réception à la
date actuelle n'est jamais antidatée à J−7/30/60/90.

| Diagnostic à H1 | Occasions | Dates | Bon sens | Retour signé brut moyen |
|---|---:|---:|---:|---:|
| UP30−DOWN30 |6 773|6|49,37 %|environ−0,05 %|
| EPS courant−EPS J−7 fournisseur |5 733|6|48,70 %|environ−0,07 %|
| EPS courant−EPS J−30 fournisseur |6 617|6|48,51 %|environ−0,08 %|
| EPS courant−EPS J−60 fournisseur |7 281|6|48,10 %|environ−0,07 %|
| EPS courant−EPS J−90 fournisseur |7 637|6|49,22 %|environ−0,04 %|

Les cinq diagnostics sont également négatifs en moyenne signée à H3 et H5.
Les contrôles sans chevauchement et références LONG/SHORT restent dans le
rapport, sans promotion. EPS de base inconnue, rotation des contributeurs,
ancienneté de la période et petit nombre de dates empêchent une validation.

## 6. Les six contextes déjà documentés ne sont pas encore une preuve

DOCN,FUN,TWLO,FIVN,ENTG,AKAM ont des appuis documentaires de devise/période
sur l'ancrage septembre2026, **sans qualification rétroactive de l'entrée**.
Sept observations changées ont un prix H1 sur seulement deux dates : deux
dans le bon sens,retour signé moyen−0,631 %. Une seule observation est mesurable
à H3/H5 dans ce petit groupe. Ces chiffres ne valident ni ne rejettent les six titres.

**Aucun H10 de ce nouveau dossier n'est encore mature au cutoff** : première
clôture admissible26octobre. L'ancien pilote du19octobre,TP10/SL5 sur10séances,
attend toujours le **30octobre après clôture**, puis des prix qualifiés.
Aucun retour H10 ni diagnostic-H10 n'a été calculé par cet audit.

## Conclusion et suite bornée

1. **Ne pas jeter les snapshots** : copie fidèle et matière prospective utile,
   mais origine fidèle≠estimations justes≠signal directionnel rentable.
2. **Corriger séparément la sémantique UTC d'ingestion**, sans supprimer ou
   antidater l'historique. Les15valeurs incohérentes doivent rester réservées.
3. Ne pas injecter ces simples signes comme nouvelle règle de trading ou
   feature déjà validée. Le recul est cinq/six dates courtes,deux à H5 ; la
   confirmation précédente50dates/100épisodes n'est pas assouplie.
4. Prix SIP en base arrêtés au20octobre : il faut des prix supplémentaires
   qualifiés pour les observations suivantes, pas remplir les résultats inconnus.
5. Continuer la collecte existante ; attendre les maturités et une diversité
   réelle d'annonces/périodes. **Pas de preuve justifiant un modèle dédié ou
   un abonnement supplémentaire à partir de ce bilan.** Aucun arrêt automatique
   ni nouvelle collecte ou tâche de suivi n'a été créé.

Cette recherche porte sur la réaction des cours, **pas sur la précision des
prévisions de revenus/EPS contre les résultats publiés**. Cette dernière
nécessite réalisé et estimation comparables sur la même période,unité/devise,
base comptable et dates de connaissance ; l'EPS Trends ne fournit pas toutes
ces preuves. Aucun taux d'erreur financier « vrai consensus » n'est inventé.

## Livrables, contrôles et reproduction

- Parent : sources immuables,inventory.json,consensus.parquet,runs.parquet,
  features.parquet,row-quality.parquet,preuves et prix multi-sources conservés.
- Enfant SIP : mêmes features et cutoff,prix d'une seule source,diagnostic-H1/H3/H5,
  report.json,final-audit.json,large-changes-reserve.csv.
- `anomaly-proof/` :15/15anomalies confirmées dans les enveloppes,aucune correction.
- `rolling-diagnostic/` : cinq diagnostics EPS explicitement post-hoc,tous résultats.
- `clock-audit/` : horloges MySQL,décalage et contrôle du premier open admissible.

**83tests passent**, dont19nouveaux sur l'audit et la sélection du flux.
Revue technique distincte : **13 448paires**, cutoffs et signes, **38 276prix
scalaires** recalculés ; statut `PASS_CAUSAL_RECEIPTS_SIGNS_MATURITY_AND_SCALAR_PRICES`.
Les calculs passent ; cela ne lève ni la réserve UTC ni les réserves économiques.
Même assistant,pas seconde revue humaine indépendante. Une vérification
supplémentaire reproduit **201 720signes dérivés rolling** depuis les champs
natifs et leurs moyennes (`rolling-diagnostic/technical-audit.json`). Ces
descriptions supplémentaires ne constituent pas une nouvelle validation de modèle.

Rapport canonique SHA256 :
`fb6f0f7e0a2fd7f21a9e48704347e5ed8e6b6473681092265c89c4e49a5cea68`.

Scripts de recherche :
`us_consensus_reliability_20261022.py`,
`us_consensus_reliability_sip_20261022.py`,
`us_consensus_reliability_20261022_audit.py`,
`us_consensus_reliability_rolling_20261022.py`,
`us_consensus_reliability_clock_20261022.py` dans `scripts/research/`.

Aucune écriture SQL,modification de modèle/configuration/batch,restauration
Yahoo,API fournisseur/LLM,commande broker ou entraînement. Les collectes et
téléchargements en cours n'ont pas été touchés.
