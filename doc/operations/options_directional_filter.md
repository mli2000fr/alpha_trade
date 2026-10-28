# Filtre options après Oracle — expérimental PAPER, 26 octobre 2026

## Activation et périmètre

`config.yaml → options_directional_filter.enabled: true` active le défaut du
batch `us_pipeline` et de la case **📊 Filtrage options — volume CALL/PUT + OI
après Oracle — PAPER uniquement**. Le compte doit être `default` en mode PAPER.
Une case décochée désactive le filtre pour le lancement IHM, pas pour le batch.
`enabled: false` coupe les deux. GPT/DeepSeek reste désactivé ; aucun appel LLM,
achat de données, téléchargement additionnel ou entraînement n'est effectué par
ce filtre. Ne pas confondre cette activation expérimentale avec une validation
de rentabilité. Les règles de backtest existantes ne sont pas modifiées.

### Univers de prédiction par défaut (27 octobre 2026)

La page Pipeline (workflow et bloc **10. ML Predict**) utilise par défaut
`universe-file:univers_filtred_tradable.txt`, résolu dans `config/univers/`.
Le batch `us_pipeline` conserve son chemin explicite
`config/univers_batch/univers_filtred_tradable.txt` dans `batch.yaml`.
La sélection d'un modèle ne réapplique plus automatiquement son ancien fichier
d'entraînement, notamment `oracle_balanced_400_202512.txt`. Une session déjà
ouverte sur cet ancien défaut est migrée une seule fois ; les choix manuels
ultérieurs restent possibles. Aucun fichier d'univers ni contrat de modèle
n'est modifié, et les symboles hors contrat restent refusés.

### Affichage du tableau après un batch (28 octobre 2026)

Le tableau de l'étape 10 accepte désormais les deux identifiants de fichier
ci-dessus comme alias **d'affichage uniquement**, si leurs listes de symboles
sont toutes deux identiques à l'univers conservé dans les entrées scellées.
Une simple égalité de nom de fichier ne suffit pas. Le rapport reste inchangé,
avec sa source exacte, et les contrôles de date, modèle, compte, preset,
empreintes, âge et fenêtre de séance sont conservés. La qualification utilisée
par le risque et l'exécution reste stricte ; aucun nouvel appel de prédiction,
de collecte ou d'ordre n'est nécessaire pour corriger l'affichage.

Incident vérifié : le dernier batch de la séance du 27 octobre a publié
`opt-1cb6b98e226e42a19910a6b807c9195a`, **50 lignes Oracle, 26 couvertes,
13 retenues LONG**. Les deux fichiers d'univers avaient la même empreinte,
mais leur comparaison textuelle masquait le tableau. Le lecteur IHM corrigé
retrouve les 50 lignes. Un autre contexte incompatible affiche désormais son
motif précis, sans remplacer le run par une ancienne sélection.

## Règle figée

Les valeurs ci-dessous décrivent les défauts initiaux du code (TOP20, seuil 0.50).
Pendant le raccordement, le fichier utilisateur a été modifié à **TOP50 et seuil
0.70** ; ces modifications sont conservées. Les valeurs effectives proviennent
toujours du fichier et sont affichées dans l'IHM puis figées par run.

1. Prédiction Oracle parcours, séance US exacte J et modèle explicite. Couverture
   minimale du classement : `min_oracle_coverage_ratio: 0.95` de l'univers choisi.
   Les horodatages MySQL `TIMESTAMP` des scores et de leur lineage sont
   comparés au cutoff par `UNIX_TIMESTAMP`, puis archivés en UTC. Le fuseau
   SQL local (`SYSTEM`, Paris, DST) ne doit ni masquer les scores déjà produits,
   ni rendre admissible une ligne future. Le lecteur ne modifie pas le fuseau
   global/session SQL et ne supprime pas le contrôle de disponibilité.
2. Fixer les `oracle_top_n: 20` premiers par score décroissant, symbole croissant
   en cas d'égalité. **20 titres**, pas 20 %. Aucun titre N+1 ne remplace un absent.
3. Sur les seuls titres doublement couverts : volume CALL/PUT, OI CALL/PUT,
   reçus le jour J en heure de New York, avant le cutoff UTC réel. Pas de report
   du dernier jour connu ni d'historique présenté comme disponible à l'époque.
4. Volume : contrats de 15 à 25 jours calendaires d'échéance, somme des barres
   30 minutes par type et échéance, CALL et PUT présents, échéance la plus proche
   de 20 jours. Feature `log(1+volume_CALL)-log(1+volume_PUT)`.
5. OI : même fenêtre d'échéance, paire CALL/PUT de même strike/échéance,
   strike à moins de 5 % du close J, choix déterministe échéance puis proximité
   du strike. Feature `log(1+OI_CALL)-log(1+OI_PUT)`. L'échéance OI peut différer
   de celle du volume, comme dans l'audit ; les deux sont archivées.
6. Rangs centrés `(rang_moyen-0.5)/effectif_couvert`, puis moyenne **50/50**.
   Retenir au maximum `floor(effectif_couvert/2)` titres avec le score combiné le
   plus élevé, **strictement supérieur** à `min_combined_score: 0.5`. Les égalités
   de sélection sont départagées par rang Oracle. Tous les scores égaux à 0.5 :
   aucun retenu. Moins de `min_covered: 4` titres couverts : aucun retenu.
7. **LONG uniquement**, sans création de SHORT ni inversion de position. L'ordre
   Oracle des titres retenus est conservé ; le score options n'est pas utilisé
   comme probabilité, avantage attendu ou multiplicateur de sizing.

La moitié supérieure porte donc sur les titres couverts, pas sur les vingt
titres si seulement quatre ont des options. Avec quatre couverts, au maximum
deux retenus. Zéro est une abstention valide et documentée ; une panne SQL,
un classement insuffisant ou une erreur technique échoue, sans retour implicite
au pipeline non filtré.

## Sources et limites

- `stock_option_snapshots` : Alpaca, `feed=indicative`, réception/observation J.
- `stock_option_bars_delayed` : Alpaca, `timeframe=30Min`, timestamp de barre J
  ET réception J. Les lignes incluent leur feed et `provenance_status` dans l'archive.
- `stock_bars_daily` : close J non rempli, préférence EODHD/SIP commune au projet.
- `oracle_extreme_predictions` : batch/date/univers exacts ; contrat/lineage du
  modèle parcours contrôlé, aucun champ de rendement futur lu.

L'OI indicative n'est pas assimilée à une OI OPRA certifiée ; la provenance OPRA
du volume collecté n'est pas démontrée. La réception J ne prouve pas la date de
référence économique de l'OI. Les doublons conflictuels, valeurs invalides,
horodatages manquants ou futurs sont exclus. Les limitations de couverture et
les petites cohortes de l'audit demeurent. **Ce n'est pas une preuve de rendement
ni un filtre autorisé en argent réel.**

Ce score est le même quel que soit l'horizon ensuite observé dans l'audit H5/H10/H20.
Il ne transforme pas l'Oracle en modèle directionnel calibré et ne change pas
l'horizon de détention, le SL, le TP ou le trailing du portefeuille.

## Collecte OI alignée sur le filtre (27 octobre 2026)

Le diagnostic de la sélection `opt-d1682793383e4fedb878c37c4dfdf6ff`
(séance du 26 octobre) retrouve **6 titres calculables sur le TOP50**, dont
2 retenus ; 44 n'ont pas les deux features qualifiées. Ce n'est pas une absence
de score Oracle. La collecte OI s'arrêtait à J+24 alors que le filtre accepte
J+25 : l'échéance mensuelle du 20 novembre était ainsi exclue. Des strikes
CALL/PUT choisis séparément pouvaient aussi ne plus former de paire après
les contrôles de cotation et d'OI.

Dans `batch.yaml → oracle_options_indicative_snapshot` :

```yaml
dte_tolerance_days: 5
ensure_directional_oi_pair: true
```

Le collecteur couvre désormais au moins J+15 à J+25 inclus lorsque cette option
est active. Il conserve son échantillonnage historique et ajoute, si nécessaire,
au plus deux contrats constituant une paire CALL/PUT au **même strike et à la
même échéance**, dans les 5 % du cours de référence collecté du sous-jacent.
La paire est choisie après les contrôles existants de bid/ask, spread et OI
minimal, par proximité de J+20 puis du strike. Une racine ajustée ne peut pas
remplacer le sous-jacent demandé. Aucune OI manquante n'est inventée.
Le filtre conserve son contrôle final par rapport au close J.

Les détails de collecte et le log final indiquent les titres avec/sans paire
qualifiée, les contrats ajoutés, les rejets de liquidité et d'OI. « Sans paire »
inclut aussi les titres sans cours, sans chaîne ou en échec technique ; cela ne
signifie pas que tous ces titres sont dépourvus d'options. La fenêtre 15–25 jours
et la cible J+20 sont partagées entre collecteur et filtre dans
`common/options_directional_contract.py`.

La modification est **prospective** : elle ne remplit pas rétroactivement l'OI
du 26 octobre. Une nouvelle collecte puis une nouvelle étape 10 sont nécessaires
pour mesurer la couverture obtenue. Aucun batch ni ordre n'a été relancé pour
cette livraison. Le volume CALL/PUT doit toujours être disponible séparément ;
une meilleure collecte OI ne garantit pas un score pour tous les titres.

Tests hors ligne : fenêtre J+25, paire ajoutée réellement exploitable par le
calcul de features, absence de paire/OI, rejets de cotations, conservation de
l'échantillon historique et désactivation explicite de l'ajout de paire.
Validation ciblée : **110 tests réussis**, sans appel fournisseur ni écriture SQL
de production (collecteur, filtre, commandes et orchestration).

## Raccordement 10 → 11 → 12

Le module `service.options_directional.pipeline` orchestre les trois phases.
Un workflow crée un ID `opt-<32 caractères hexadécimaux>`, partagé entre ses étapes,
et fige la séance US. Le batch exige l'étape 10 si 11/12 utilisent le filtre.

- **10** : prédiction, puis lecture des données et archivage local immuable.
  Le bloc affiche rang Oracle, scores volume/OI/mélange, sélection et motifs.
- **11** : sélection exacte retrouvée ; le moteur normal continue d'appliquer
  univers tradable, gate Oracle/ATR s'il est actif, prix frais, régime, corrélation,
  capital, sizing et protections. Le filtre options est un veto supplémentaire
  sur les nouvelles entrées LONG, pas un remplacement de ces contrôles. Le résumé
  risque contient `options_filter_run_id` et est lié au rapport par empreintes.
  Le preset d'univers est celui du rapport options qualifié
  (`capital_preset_key`), et non un autre preset recalculé depuis le solde du
  compte. L'equity réelle, les budgets de risque et les règles de sizing restent
  inchangés. Un preset absent/inconnu, une publication incomplète ou un symbole
  non tradable restent bloquants ; aucun fallback vers un autre univers.
  Oracle parcours est contrôlé via son contrat signé et la lineage causale des
  scores/politiques de J, pas via l'ancien registre de modèles par symbole.
  La fraîcheur suit la séance clôturée J avant l'ouverture J+1. Le contrôle de
  quotes SIP du risque est optionnel via
  `risk_management.quote_spread_check_enabled` (défaut `false`) ; les contrôles
  d'exécution et protections restent distincts, voir
  [le réglage dédié](controle_spread_etape11.md). Les paires de
  barres EODHD/SIP suivent `market_data.daily_bars_preferred_source` ; les vrais
  doublons ambigus restent bloquants, sans choisir une ligne valide de secours
  quand la ligne du fournisseur préféré est invalide.
- **12** : run risque lié explicitement, aucune recherche « latest targets ».
  Contrôle supplémentaire des cibles contre la sélection et les positions broker :
  pas de nouvelle exposition hors sélection, mais les réductions de positions
  existantes restent possibles. Les protections/watcher existants ne sont pas retirés.

Pour des lancements manuels séparés, 11/12 utilisent le rapport le plus récent
correspondant **exactement** à la séance, au modèle, à l'univers, au preset et au
compte. Un résultat plus récent invalide ne fait pas revenir à une ancienne
sélection. L'identifiant et le cutoff sont journalisés. Si 10 est relancé après
11, refaire 11 sur ce nouveau résultat avant 12 ; pas de substitution d'un ancien
run risque. Un run ayant déjà une tentative risque/exécution n'est pas rejoué
automatiquement, sauf l'échec précisément qualifié ci-dessous.
Modifier les paramètres ne recalcule pas un ancien rapport : relancer 10 pour
produire une nouvelle sélection et reprendre ensuite 11/12 sur celle-ci.

Un workflow personnalisé **11 → 12**, sans étape 10, résout et fige également
ce rapport existant au démarrage. Il ne crée pas un nouvel identifiant `opt-...`
sans analyse associée et ne refait pas une sélection « latest » entre 11 et 12.
Un identifiant explicite reste prioritaire : s'il est introuvable ou non qualifié,
le workflow s'arrête sans substitution. Seul un workflow incluant 10 génère un
nouvel identifiant pour une nouvelle analyse.

### Reprise après échec du chargement d'univers (27 octobre 2026)

Un verrou système `risk.lock` interdit deux tentatives de risque simultanées sur
la même sélection. Chaque tentative possède un identifiant unique dans
`risk.claim.json`. Si le chargement de l'univers échoue **avant toute publication
de décisions/cibles**, le CLI scelle
`risk.prepublication_failure.<attempt_id>.json`, lié à la tentative et au rapport
par empreintes. Un nouvel appel de l'étape 11 peut alors archiver le claim dans
`risk_attempts/<attempt_id>/risk.claim.json` et refaire le calcul de risque.
L'ancienne preuve est conservée ; le rapport options n'est jamais remplacé.

Les contrôles de séance, fraîcheur, compte et intégrité sont réappliqués.
L'absence de preuve, un ancien claim sans identifiant, une erreur à un stade
ultérieur, un résumé (même partiel), un binding ou une tentative d'exécution
interdisent cette reprise automatique. Une erreur inconnue n'est pas assimilée
à une absence de publication. L'étape 12 conserve son claim à usage unique.
Les anciens claims exigent une vérification et une libération ciblées, jamais
une suppression globale des verrous.

La fenêtre autorisée reste clôture J ≤ maintenant < ouverture de la séance US
suivante, plus `max_age_hours: 72`. Les boutons historiques/shadow ignorent ce
filtre prospectif sur leur copie locale. Un cumul LLM + options n'a pas été validé :
IHM exclut le cumul, batch refuse une double activation explicite.

## Archives et exploitation

`artifacts/options_directional/opt-.../` contient :

- `inputs.json` : univers, classement Oracle et lignes sources lues, sans prix futur ;
- `report.json`, `seal.json` : configuration figée, cutoff, scores, motifs et empreintes ;
- `failure.json` si la couverture Oracle est insuffisante : date/modèle/univers,
  couverture réelle, seuil et liste complète des titres sans score ; aucun
  rapport de sélection ni sceau de réussite n'est publié. Les compteurs sont
  aussi émis dans le résumé d'étape. Un échec récent de ce périmètre interdit
  de substituer automatiquement une ancienne sélection réussie aux étapes 11/12 ;
- après 11 : `risk.claim.json`, `risk_summary.json`, `risk_binding.json` ;
- contrôle des reprises 11 : `risk.lock`, preuves d'échec prépublication et
  claims antérieurs archivés dans `risk_attempts/` ;
- avant une tentative 12 : `execution.claim.json`.

**Pas de nouvelle table SQL métier** : archives dédiées sur disque ; le résumé
ordinaire du pipeline en référence l'identifiant et le chemin. Les tables LLM ne
sont pas réutilisées. Les fichiers ne sont jamais écrasés par une nouvelle analyse.
Les claims évitent les reprises accidentelles ; ils ne certifient pas à eux seuls
qu'un ordre a ou n'a pas été envoyé.

Cette livraison ne lance ni pipeline ni ordre. Les tests sont hors ligne et
mockés ; un passage PAPER opérationnel reste à observer après une clôture US,
avec la couverture réellement disponible. Un batch déjà démarré conserve ses
anciennes options et n'est pas modifié rétroactivement.

## Vérification de livraison

Suite ciblée finale : **324 tests réussis** (filtre, orchestration, risque,
commandes, watcher, serving Oracle, lineage et abstention sans cible).
Parité numérique des deux features avec les
archives scellées de l'audit : six titres vérifiés, sans nouvel appel fournisseur.
Compilation et contrôle de diff exécutés.

Deux tests généraux restent KO hors de cette suite ciblée :
`test_background_run_can_be_stopped` (état Windows encore `running` à l'attente
du test) et `test_apply_selected_capital_preset_for_small_account_sets_expected_values`
(attend 8 positions, la configuration utilisateur en prévoit 20). Ni le mécanisme
d'arrêt ni le preset ne sont modifiés par cette livraison. Il ne s'agit donc pas
d'une certification de réussite de l'ensemble des tests du projet.
