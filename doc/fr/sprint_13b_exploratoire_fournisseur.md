# 13-B exploratoire fournisseur — comparaison économique distincte

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Autorisation et statut

**Mise à jour après réparation :** la [passe 13-C](sprint_13c_reparations_decision_economique.md)
aboutit à 24/24 cellules exploratoires (sortie v8), avec analyse de concentration
et NO-GO shadow pour la politique LONG H5. Les chiffres 4/24 et blocages ci-dessous
décrivent le jalon initial v4, pas l’état actuel. Validation stricte toujours bloquée.

Le 4 octobre 2026, l’utilisateur autorise une expérience **séparée fondée sur les
données fournisseur**. Ce n’est ni la levée des gates du Sprint 12, ni la
qualification indépendante attendue par le [13-B strict](sprint_13b_assemblage_tapes_reporting.md).
Les résultats portent explicitement `EXPLORATORY_PROVIDER_ASSUMED`.

Pas d’écriture SQL, de téléchargement, d’entraînement, de modification des
modèles, des batchs ou des paramètres de production. La confirmation 2026
n’est pas évaluée. Les archives fournisseur contiennent davantage d’historique,
mais seuls les prix nécessaires au développement 2024–2025 sont utilisés.

**Résultat : comparaison incomplète.** Quatre cellules ATR du fold 6 aboutissent,
toutes négatives ; vingt cellules restent bloquées. Aucun classement économique
Oracle/ATR/contrôle n’est défendable sur ces sorties.

## Population et politiques conservées

Le gel 13-A et ses hashes restent inchangés. Le script vérifie les entrées
gelées et reconstruit les intentions depuis les scores causaux : pas de masque
sur les futurs rendements, la complétude du futur ou les chemins qualifiés.

- Population commune : **21 379 lignes candidat/date**, pas 21 379 trades.
- Folds 6 et 7 ; décisions respectivement du 29 juillet 2024 au 23 janvier 2025,
  puis du 24 janvier au 23 juillet 2025.
- Politiques : `atr_top20_long`, `oracle_top20_long`, `uniform_control_long`.
- Capital indépendant de 4 000 € par cellule, huit positions au maximum,
  quantités entières, sans levier ni SHORT, sans empilement du même titre.
- Entrée à l’ouverture de la séance de décision, sortie à la clôture de la
  cinquième séance suivante ; pas de stop, TP ou optimisation de lifecycle.
- Aucun réemploi à l’ouverture des ventes effectuées à la clôture du même jour.
- Les rangs des intentions originales sont conservés. Une intention peut être
  ignorée pour capacité, titre déjà détenu ou cash insuffisant ; ce n’est pas un
  filtrage fondé sur le futur.

## Hypothèses nouvelles et limites

| Élément | Convention exploratoire | Ce qui n’est pas démontré |
|---|---|---|
| Prix | Open/close **non ajustés** de l’archive EODHD, hash contrôlé | Exécution au prix indiqué, indépendance des prix |
| Statut | Volume fournisseur positif et prix positifs | Négociabilité historique officielle, profondeur disponible |
| Disponibilité | Horodatages J+1 du protocole de recherche hérité | Heure historique de publication des données |
| Calendrier | Bibliothèque XPAR | Calendrier exhaustif spécifique à chaque instrument |
| Règlement | T+2 sur ce calendrier, explicitement présumé | Date effective de règlement d’un ordre |
| Opérations | Dividendes et splits fournisseur | Exhaustivité : absence de ligne présumée absence d’événement, non prouvée |
| Fiscalité | Positifs déjà revus conservés, inconnus simulés taxés/non taxés | Une absence de preuve n’est jamais qualifiée d’exonération |
| Coûts | Profil générique EUR configurable | Tarif courtier et spread/slippage historiques réellement observés |

Les noms des champs du moteur séparé sont `supplier_assumption_accepted`, **pas
`economic_verified` ni `verified`**. Les archives et les qualifications strictes
ne sont pas réécrites. Le moteur strict n’accepte pas ces tapes exploratoires.

L’absence d’ouverture documentée pour Artois le 10 octobre 2024 prévaut sur le
proxy fournisseur : refus de l’ordre sans cash, frais ni consommation de capacité.
On ne transforme pas le prix EOD de cette journée en ouverture exécutée.

### Dividendes, splits et blocages conservés

Un dividende nécessite le montant non ajusté, la devise EUR et une date de
paiement valide. La créance naît pour une position déjà détenue à l’ex-date,
contribue à l’equity et devient cash au paiement ; achat à l’ex-date non éligible.
Un paiement un jour fermé est rapproché de la prochaine séance du calendrier
(hypothèse de comptabilisation). Le calendrier commun s’allonge si nécessaire
jusqu’aux paiements ; les métriques d’exposition/Sharpe incluent cette queue de
cashflows, sans nouvelles intentions. Pour le fold 7, la tape va jusqu’au
1er octobre 2025, mais les cellules sont bloquées avant sa fin.

Un split ajuste la quantité ; les rompus restent bloquants faute de règle
cash-in-lieu. Les événements simultanés dont l’ordre n’est pas défini restent
bloquants. Une opération mal renseignée bloque si le titre est détenu ; elle
n’est pas utilisée pour supprimer préalablement le candidat.

**Aucun forward-fill de prix.** Une barre manquante en cours de détention bloque
la cellule entière. Un ledger partiel reste diagnostic, avec métriques finales
à `null` : pas de rendement jusqu’au premier obstacle présenté comme résultat
complet. Aucune date de paiement n’est inventée pour obtenir un backtest.

## Scénarios pré-enregistrés et calcul des métriques

Trois politiques × deux folds × deux conventions fiscales × deux coûts =
**24 cellules**. Le protocole et les hashes sont archivés avant leurs résultats.

Les deux conventions fiscales sont `unknown_untaxed` et `unknown_taxed`.
Les positifs déjà revus sont taxés dans les deux. Les taux datés restent ceux
du profil existant : 0,3 % avant le 1er avril 2025, 0,4 % ensuite, selon la date
de règlement présumée. Cela simule les inconnus, sans requalifier leur statut.
Ce ne sont pas des bornes mathématiques du PnL : les frais peuvent modifier la
quantité accessible, le cash et les achats suivants.

Nominal : 1 € de commission par exécution, spread complet 5 bps dont moitié
facturée par côté, slippage 5 bps par côté. Stress : commission, spread et
slippage ×2, **pas le taux de taxe**. La taxe totale peut néanmoins varier si
quantités ou base d’acquisition changent. Valeurs lues depuis le fichier de
configuration, non codées en dur.

Les métriques réconcilient cash final, PnL des trades et frais détaillés :
rendement net, Sharpe quotidien (252 séances, rf=0, écart-type échantillon),
drawdown depuis le capital initial, exposition moyenne brute/nette LONG,
turnover aller-retour non annualisé, ordres exécutés, trades clos, win rate,
commission/spread/slippage/taxes, dividendes, contributions par titre et
semestre. Pas d’alpha contre un benchmark total-return non qualifié ; pas
d’agrégation des folds indépendants en une performance continue fictive.

## Résultats constatés

Sortie de référence : `artifacts/fr/research/provider_exploratory_13b/exploratory-20261004-v4`.
Le fold 6 ATR couvre du 29 juillet 2024 au 30 janvier 2025, avec **168 trades clos**.

| Fiscalité inconnue | Coûts | Rendement net | Sharpe | Drawdown maximal | Win rate |
|---|---|---:|---:|---:|---:|
| Présumée non taxée | Nominal | −35,22 % | −2,63 | 37,07 % | 36,31 % |
| Présumée non taxée | Stress ×2 | −44,14 % | −3,52 | 44,52 % | 30,95 % |
| Présumée taxée | Nominal | −38,17 % | −2,92 | 39,35 % | 34,52 % |
| Présumée taxée | Stress ×2 | −46,70 % | −3,79 | 46,70 % | 29,76 % |

ATR fold 6 nominal, inconnus non taxés : commission 336 €, spread 34,40 €,
slippage 68,81 €, taxes 51,63 €. Exposition moyenne : 78,69 % de l’equity.
Les chiffres sont issus d’hypothèses fournisseur, pas d’exécutions réelles.

| Cellules bloquées | Premier obstacle rencontré |
|---|---|
| Fold 6 Oracle, quatre scénarios | Barre ERA.PA absente au 30 juillet 2024 pendant détention |
| Fold 6 contrôle uniforme, quatre scénarios | Barre GLE.PA absente au 30 juillet 2024 pendant détention |
| Fold 7 ATR, quatre scénarios | Dividende SESG.PA, ex-date 15 avril 2025, date de paiement absente/antérieure |
| Fold 7 Oracle, quatre scénarios | Dividende ALSTI.PA, ex-date 29 mai 2025, date de paiement absente/antérieure |
| Fold 7 contrôle, quatre scénarios | Dividende OPM.PA, ex-date 29 avril 2025, date de paiement absente/antérieure |

Le premier obstacle ne constitue pas une liste exhaustive des réparations :
d’autres peuvent apparaître après sa résolution. Les rendements Oracle et du
contrôle sont **inconnus**, pas nuls. On ne conclut pas qu’Oracle est meilleur ou
pire qu’ATR, ni que D1/D10 est résolu. Le mauvais résultat ATR est descriptif,
pas un motif pour changer les seuils sur cette même période.

## Implémentation et reprise

Configuration : `config/research_fr/provider_exploratory_13b_v1.yaml`.
Service : `service/fr/provider_exploratory_13b.py`.
Moteur comptable séparé : `service/fr/provider_exploratory_engine_13b.py`, copie
isolée de la logique cash 12-B avec contrat explicite d’hypothèses ; le moteur
strict n’est pas modifié. Reporting séparé : `provider_exploratory_metrics_13b.py`.

```powershell
python -m modelFactory.fr_provider_exploratory_13b --output artifacts/fr/research/provider_exploratory_13b/exploratory-nouvelle-version
```

Choisir un dossier neuf ; aucun écrasement d’un résultat précédent.
`progress.json` indique le nombre de cellules traitées sur 24 ; chaque cellule
écrit son ledger, même si bloquée. `report.json` contient les métriques seulement
pour les cellules complètes, le statut de comparaison, les motifs et les hashes
des sorties. Les tapes communes et hashes des payloads sont archivés par fold.
Une erreur de lancement écrit `failure.json` si le dossier a déjà été créé.

Les sorties v1 (erreur technique initiale), v2/v3 (diagnostics de développement)
ne sont pas la référence finale ; elles ne doivent pas être additionnées à v4.

Tests : `tests/test_fr_provider_exploratory_13b.py`, plus tests stricts 12-B,
13-A, 13-B et coûts : **46 tests ciblés passent**, sans désactiver aucun test.
La couverture globale de tout le dépôt n’est pas attestée par cette sélection.

Prochaine étape utile : retrouver les barres et champs manquants dans des
sources identifiables, les archiver/versionner, puis rejouer **les mêmes
intentions**. Ne pas retirer ERA/GLE ou les titulaires de dividendes après
observation du chemin. Les gates stricts restent ouverts indépendamment de
cette expérience ; aucune activation live n’en découle.
