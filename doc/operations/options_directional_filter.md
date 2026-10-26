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

## Règle figée

Les valeurs ci-dessous décrivent les défauts initiaux du code (TOP20, seuil 0.50).
Pendant le raccordement, le fichier utilisateur a été modifié à **TOP50 et seuil
0.70** ; ces modifications sont conservées. Les valeurs effectives proviennent
toujours du fichier et sont affichées dans l'IHM puis figées par run.

1. Prédiction Oracle parcours, séance US exacte J et modèle explicite. Couverture
   minimale du classement : `min_oracle_coverage_ratio: 0.95` de l'univers choisi.
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
automatiquement : vérifier son état avant toute reprise.
Modifier les paramètres ne recalcule pas un ancien rapport : relancer 10 pour
produire une nouvelle sélection et reprendre ensuite 11/12 sur celle-ci.

La fenêtre autorisée reste clôture J ≤ maintenant < ouverture de la séance US
suivante, plus `max_age_hours: 72`. Les boutons historiques/shadow ignorent ce
filtre prospectif sur leur copie locale. Un cumul LLM + options n'a pas été validé :
IHM exclut le cumul, batch refuse une double activation explicite.

## Archives et exploitation

`artifacts/options_directional/opt-.../` contient :

- `inputs.json` : univers, classement Oracle et lignes sources lues, sans prix futur ;
- `report.json`, `seal.json` : configuration figée, cutoff, scores, motifs et empreintes ;
- après 11 : `risk.claim.json`, `risk_summary.json`, `risk_binding.json` ;
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
