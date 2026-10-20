# Évaluateur consensus revenus — TP10/SL5 sur dix séances

## État au 20 octobre 2026

**Implémenté, testé et préparé ; aucun résultat d'efficacité calculé.**

L'évaluateur reste dans la recherche. Il ne modifie aucun modèle, ordre, batch,
table SQL ou configuration de production. Aucun accès fournisseur ou LLM.
Il n'est pas branché aux étapes 10/11/12 du pipeline.

- Cohorte Oracle figée : **349 titres**, entrée théorique du 19 octobre 2026.
- Strict TOP10 séparé des rangs 11–349 ; union TOP20 % explicitement dépendante.
- **Six contextes revenus appuyés**, soit deux dans le TOP10 et quatre au-delà.
- Deux groupes de preuves séparés : DOCN/FUN du dossier initial ;
  TWLO/FIVN/ENTG/AKAM de la qualification publique complémentaire.
- **3 490 clés symbole/séance** attendues, dix séances par titre.
- Dixième clôture : **30 octobre 2026, 20 h UTC / 21 h Paris**.
  Les prix devront ensuite être définitifs et leur export qualifié : l'heure
  de clôture seule ne prouve pas que le fournisseur a finalisé les barres.

La tentative réelle lancée le 20 octobre a renvoyé `WAITING_H10_MATURITY`,
**sans ouvrir de prix ni de manifeste de prix**. Il n'y a aucun calcul de
recherche en cours ni reprise automatique planifiée pour le 30 octobre.

## Périmètre figé et qualification non rétroactive

Le classement est celui du 16 octobre, enregistré avant l'ouverture du 19,
du modèle parcours H20 `model-factory-20261016180250-3b0515`.
Les 349 membres ne sont ni remplacés ni triés selon leurs résultats futurs.
Les dates sans classement contemporain ne sont pas comblées avec ce classement.

Les snapshots revenus sont ceux réellement archivés avant deux ouvertures
successives ; aucun EPS, ni historique inventé à partir de `+1q`. Nombre
d'analystes revenus inchangé et au moins trois, sans prétendre connaître les
identités des contributeurs. Le sens de la variation est recalculé à partir
des deux revenus : hausse stricte LONG, baisse stricte SHORT.

La qualification devise/période effectuée après l'entrée reste **après
l'entrée**. Même les appuis initiaux ne sont pas présentés comme une règle
opérationnelle historiquement déployée. Les quatre ajouts ne deviennent pas
une confirmation indépendante. Tous les champs d'admission live restent faux.

Sources détaillées : [qualification publique du 20 octobre](qualification_consensus_annonces_sec_20261020.md)
et [cohorte TOP20 % du 19 octobre](consensus_revenus_top20pct_20261019.md).

## Règles de parcours, sans optimisation

Le prix de référence est l'**ouverture d'entrée**. Les dix séances incluent
cette séance ; ni dix jours calendaires ni sortie à J+11. Aucun trailing,
réinvestissement, levier ou décalage d'entrée n'a été ajouté.

| Sens théorique | TP | SL | Expiration |
|---|---|---|---|
| LONG | Entrée × 1,10 | Entrée × 0,95 | Dixième clôture |
| SHORT | Entrée × 0,90 | Entrée × 1,05 | Dixième clôture |

Conventions journalières conservatrices :

1. Un gap d'ouverture défavorable au-delà du stop sort au **prix d'ouverture**,
   pas fictivement à −5 %. La perte peut dépasser le stop.
2. Un gap favorable au-delà du TP est plafonné au **niveau du TP** : aucun
   bonus de meilleur prix n'est supposé.
3. Sans franchissement à l'ouverture, si TP et SL sont touchés dans la même
   barre quotidienne, **SL prioritaire**. L'ordre réel n'est pas déductible
   d'OHLC journaliers.
4. Une ouverture déjà au-delà du TP précède les fluctuations intrajournalières :
   on ne transforme pas cette sortie en stop au motif d'un recul ultérieur.
5. Aucune barrière : sortie à la dixième clôture.
6. Les dix barres doivent être qualifiées, même si une barrière semble avoir
   été atteinte tôt. Pas de résultat partiel opportuniste sur les fenêtres
   ensuite incomplètes ou contradictoires.

L'évaluateur distingue `TP_FIRST`, `SL_FIRST`, `EXPIRED`. **Atteindre le TP
avant le SL n'est pas la même mesure que finir avec un rendement positif** :
une expiration peut être positive sans avoir atteint +10 %.

Le rendement brut de parcours est `sens × (sortie / entrée − 1)`, avec sens
LONG = +1 et SHORT = −1. C'est un diagnostic nominal sans financement, pas un
rendement de fonds propres, un rendement net ou une simulation de portefeuille.

## Références de comparaison

Pour chacun des deux groupes de preuves, et leur union exploratoire séparée :

- **CONSENSUS_DIRECTION** : sens de la variation de revenus ;
- **ALWAYS_LONG_MATCHED** : LONG systématique sur exactement les mêmes titres,
  dates et fenêtres ;
- **ALWAYS_SHORT_MATCHED** : SHORT systématique sur les mêmes fenêtres.

Deux références supplémentaires ne filtrent pas les membres Oracle selon la
présence d'un consensus : **ORACLE_LONG_UNFILTERED** et
**ORACLE_SHORT_UNFILTERED**, soit l'ensemble des 349 titres, avec TOP10 séparé.
Cela distingue la valeur éventuelle du sens choisi d'un simple changement de
composition ou d'exposition au marché.

Chaque référence utilise les mêmes dix barres et protections. Les taux ont
pour dénominateur **tous les épisodes prévus du bras**, pas seulement ceux qui
ont un prix disponible. Un épisode non qualifié reste manquant ; si un bras
est incomplet, aucun taux ni rendement moyen agrégé n'est publié pour ce bras.
Les résultats individuels qualifiés restent traçables. Un autre bras complet
peut fournir son descriptif sans être présenté comme une comparaison complète
avec le bras incomplet.

Les unions de groupes/rangs ne sont pas des observations indépendantes.
Une seule date d'entrée et six titres ne permettent pas d'établir une
robustesse, même avec un pourcentage favorable. Pas de p-value optimisée,
nouveau seuil de révision, recherche du meilleur TP/SL ou sélection après pertes.

## Contrat des prix : aucune qualification par défaut

La préparation écrit **des exigences**, pas un certificat de prix.
`price-requirements.json` porte explicitement
`REQUIREMENTS_ONLY_NOT_A_QUALIFIED_MANIFEST` et chaque fenêtre
`REQUIRES_QUALIFICATION`. Ce fichier ne peut pas être utilisé tel quel pour
produire des résultats.

Après maturité, il faudra produire un **export de recherche séparé** des prix
déjà disponibles, puis le qualifier. Aucun export SQL ni téléchargement n'a
été lancé dans ce travail. La qualification devra porter sur toute la fenêtre,
pas seulement sur le jour d'entrée.

### Parquet de prix

Colonnes : `symbol`, `date`, `open`, `high`, `low`, `close`, `volume`,
`is_filled`, `instrument_id`, `data_source`, `data_adjustment`.

- `date` : séance normalisée, sans heure/fuseau, stockée comme date compatible
  ou timestamp minuit ; une seule barre par titre/séance.
- OHLC positifs, finis et géométriquement cohérents ; volume positif ;
  `is_filled = 0` explicitement.
- Identité, source et base d'ajustement connues et constantes sur la fenêtre,
  raccordées au manifeste. **IEX est explicitement refusé** pour cette étude.
  Pour Alpaca, la preuve de source doit démontrer SIP, pas un simple nom
  générique masquant un autre flux.
- Splits et opérations sur titres doivent être vérifiés : une absence dans
  une table vide n'est pas une preuve d'absence d'opération. Aucune conversion,
  réparation de prix, identité ou ajustement ne sera inventé par l'évaluateur.
- Une base ajustée doit être cohérente pour **tous** les OHLC, pas seulement
  une clôture ajustée mélangée à des hauts/bas bruts. La formule n'incorpore pas
  les dividendes, retenues fiscales, paiements compensatoires de SHORT ou flux
  de titres : réserver les événements non résolus dans ce contrat de prix.

### Manifeste qualifié

Format `us_consensus_h10_prices_v1`, statut `QUALIFIED_RESEARCH_INPUT` :

- `prices_sha256` lie le fichier exact ;
- `retrieved_at_utc` est l'heure réelle de capture, après la dernière clôture
  requise et avant le cutoff d'évaluation ; pas une disponibilité historique
  inventée ni un timestamp fiscal ;
- `evidence_files` lie par empreinte les pièces archivées sous
  `artifacts/research/`, sans chemin externe ou remontée `..` ;
- `windows` contient les fenêtres titre/date d'entrée, leur dernière séance,
  devise USD, identité, source, ajustement, statut, et `evidence_paths` ;
- `final_sessions_verified = true` doit être **appuyé par les preuves**, pas
  simplement activé pour franchir le contrôle ;
- `corporate_actions_status` doit être `CLEAR_VERIFIED` ou `RESOLVED_VERIFIED`,
  avec preuve adéquate de couverture et de traitement.

Le logiciel vérifie dates, empreintes, références et cohérence des barres ; il
ne prétend pas qu'une case de manifeste prouve à elle seule le fond d'un
document. Les pièces devront être revues lors de la qualification de l'export.
Manifeste absent/invalide ou prix douteux : blocage explicite, jamais zéro
rendement ou exclusion silencieuse.

## Ce que ce test ne promet pas

Les références SHORT sont **des contrefactuels de prix** : disponibilité du
prêt, marge, frais de prêt et exécution ne sont pas qualifiés ici. Les sorties
de barrière ne sont pas des fills Alpaca prouvés.

Commission, spread, slippage, fiscalité, dividendes, financement, capital et
sizing ne sont pas modélisés : `net_return = null`, `net_pnl = false`.
On ne doit donc pas comparer ces chiffres bruts à un portefeuille live ou
affirmer que le consensus est rentable après frais. Un éventuel test économique
nécessitera un contrat de coûts/exécution commun et une nouvelle autorisation.

## Commandes et reprise

Depuis `F:\projets`, dans l'environnement virtuel :

```powershell
python -u -m scripts.research.us_consensus_revenue_h10_evaluation --phase prepare --output artifacts/research/us_consensus_revenue_h10_evaluation/20261020-v1
```

Préparation déjà réalisée. Ne pas réécrire ou modifier le protocole pour changer
les six titres ou les paramètres. La configuration de recherche figée est
`config/research/us_consensus_revenue_h10_evaluation_20261020.json` ; elle ne
modifie pas le `config.yaml` applicatif.

Audit de préparation **déjà exécuté** : `preparation-audit.json`,
`PASS_PREPARATION_NO_PRICES`. Il est immuable, une seconde création est refusée.

Tentative sans prix, possible pour vérifier l'attente sans lancer de collecte :

```powershell
python -u -m scripts.research.us_consensus_revenue_h10_evaluation --phase evaluate --output artifacts/research/us_consensus_revenue_h10_evaluation/20261020-v1
```

Avant le 30 octobre après clôture : attente explicite. Après maturité, cette
commande seule bloque tant qu'aucun export qualifié n'est fourni.
Une fois un vrai export qualifié disponible, ajouter `--prices CHEMIN_PARQUET`
et `--price-manifest CHEMIN_JSON`. Ces deux noms sont des paramètres à fournir,
pas des fichiers déjà générés ou à remplir fictivement. Un `--as-of` optionnel
exige un fuseau et ne peut pas dépasser l'heure réelle.

Le processus Python distingue : 0 = diagnostic complet/préparation,
3 = attente de maturité, 2 = données absentes ou couverture incomplète,
erreur = contrat invalide. Certains lanceurs PowerShell affichent simplement
un code non nul générique ; **lire avant tout le statut du rapport**.
Chaque essai écrit dans un sous-dossier `attempts/horodatage-identifiant` neuf,
sans écraser le précédent. Une attente n'est ni un succès de performance ni
un calcul encore actif.

## Livrables et vérifications

Racine : `artifacts/research/us_consensus_revenue_h10_evaluation/20261020-v1/`.

- `protocol.json`, `ready.json`, `preparation-audit.json` ;
- `evaluation-cohort.parquet` : les 349 membres et les six sens, sans prix ;
- `required-price-keys.csv` et `price-requirements.json` ;
- un premier rapport d'attente, sans `outcomes.parquet` ;
- plus tard seulement, par essai : `outcomes.parquet`, `price-inputs.parquet`,
  `arms.json`, `report.json`, si le contrôle de maturité autorise leur calcul.

**208 tests ciblés passent, dont 44 pour cet évaluateur.** Scénarios synthétiques
LONG/SHORT, barrières inclusives, gaps, ambiguïtés, expiration, jours fériés,
barres manquantes/dupliquées/remplies, changements d'identité/source/base,
IEX, finalité, horodatages, empreintes, dénominateurs et qualification tardive.
Un scénario de bout en bout utilise uniquement des prix synthétiques : ses
résultats artificiels ne sont pas des résultats Alpha Trade.

L'audit de préparation reproduit les 349 membres, six contextes et 3 490 clés.
Le contrôle réel d'attente a été exécuté sans prix. Les règles LF spécifiques
de `.gitattributes` préservent les empreintes des quatre nouvelles sources
référencées, malgré `core.autocrlf=true` sur Windows ; aucun ancien sceau changé.

## Prochaine reprise

Après le **30 octobre, 21 h Paris**, attendre les barres finales puis exporter
et qualifier les dix séances nécessaires. Lancer le diagnostic figé, conserver
TOP10/extension et preuves initiales/tardives séparés. Si les prix ne sont pas
qualifiables, rapporter le manque plutôt que forcer un résultat. Même complet,
ce premier bilan restera exploratoire et trop petit pour une promotion live.
