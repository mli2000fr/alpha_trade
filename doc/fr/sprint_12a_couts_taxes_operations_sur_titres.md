# FR — qualification des coûts, taxes et opérations sur titres (12-A)

## Résultat au 4 octobre 2026

Le GO de qualification est exécuté sur les **21 379 chemins candidats H5 de
118 titres** issus du préflight11-A, tests folds6/7 uniquement. Aucune
performance2026, aucun fit, ordre, SQL ou promotion de données n'est effectué.

La qualification est **partielle**, pas un backtest net déjà validé :

- règles historiques de taux TTF vérifiées auprès du BOFiP et archivées ;
- moteur de coûts génériques configurables construit selon le choix utilisateur ;
- assujettissement ISIN encore à établir, liste vide et inconnus bloquants ;
- champs des dividendes/splits et chemins contrôlés, sans preuve officielle
  exhaustive d'actions sur titres, de radiations et de publication historique.

Rapport final :
`artifacts/fr/research/economic_qualification_12a/qualification-20261004-v2/report.json`.
V1 conserve l'état avant choix utilisateur d'une tarification générique.
Les HTML fiscaux sont conservés, hashés, datés de leur vraie observation.

## 1. Tarification indépendante du courtier

Configuration : `config/markets/fr_execution_research_v1.yaml`.
Implémentation : `service/fr/execution_costs.py`.

| Composant | Valeur initiale configurable | Statut |
|---|---|---|
| Commission |1EUR fixe par ordre exécuté |Scénario utilisateur, pas un devis courtier |
| Spread |5bps **complets bid/ask** ;0,5 par exécution |Hypothèse, donc2,5bps par côté |
| Slippage |5bps par exécution |Hypothèse sans fills historiques |
| Devise |EUR |Périmètre FR |
| TTF |Achat concerné seulement, calendrier historique |Assujettissement titre inconnu bloque |

Commission fixe, composante proportionnelle et minimum sont paramétrables.
Spread et slippage portent chacun un statut d'hypothèse, pouvant être remplacés
par un profil futur fondé sur tarif réel ou observations ; ce remplacement
nécessitera la qualification de la source, pas seulement un changement de libellé.
Un ordre non exécuté ne génère aucun de ces frais. Des exécutions partielles
du même ordre devront être agrégées avant la commission fixe : la fonction
ne doit pas être appelée comme une facturation nouvelle pour chaque fragment.

Le calcul restitue séparément `commission`, `spread`, `slippage`, `taxes`
et `total`, en Decimal. Les coûts sont rapportés à un prix de référence ;
ne pas aussi dégrader le fill avec les mêmes frais, sinon double comptage.
Le prix d'achat modélisé intègre spread/slippage pour l'assiette fiscale,
mais pas la commission. Stress×2 des coûts d'exécution : la loi fiscale
ne change pas de taux ; sa base peut varier avec le prix modélisé.

Le profil générique est prêt pour un **scénario de recherche sous hypothèses**.
Il ne fournit pas des coûts historiquement observés et n'active pas le
rejeu/live. Le préflight11-A gelé conserve ses anciens coûts inconnus : un
futur protocole de rejeu doit référencer explicitement ce nouveau profil,
avec les hypothèses visibles dans ses résultats.

## 2. TTF : taux, assujettissement, acquisition

Pour le périmètre historique testé :

| Date d'acquisition fiscale |Taux pour les acquisitions assujetties |
|---|---:|
|2024-01-01 →2025-03-31 |0,3 % |
|2025-04-01 →2025-12-31 |0,4 % |

Sources : [ancien BOFiP, taux0,3 %](https://bofip.impots.gouv.fr/bofip/7575-PGP.html/identifiant=BOI-TCA-FIN-10-30-20170503)
et [BOFiP du28 mai2025, taux0,4 % à partir du1er avril](https://bofip.impots.gouv.fr/bofip/7575-PGP.html/identifiant=BOI-TCA-FIN-10-30-20250528).
La date de signal n'est pas la date fiscale. Le commentaire officiel définit
le transfert de propriété à la date de règlement-livraison. Le futur moteur
devra donc porter trade date et settlement date distinctes, en tenant compte
du calendrier/règles de règlement appropriés, notamment autour du1er avril.

Le même commentaire précise l'assiette hors frais et la position nette
acheteuse, par client/PSI/titre et groupe de règlement, avec valeur moyenne
d'acquisition arrondie au centime par excès. Le calcul `ttf_accrual` exige une
quantité nette déjà consolidée ; il ne mélange pas des clients/PSI ou dates
de règlement. Le moteur de coûts par ordre ne couvre que le contrat LONG
comptant sans compensation intraday du même titre prévu11-A. SRD, exonérations
spéciales et opérations complexes ne sont pas pris en charge arbitrairement.

La taxe par trade est une charge modélisée non arrondie à l'euro ; ne pas
confondre avec une déclaration fiscale agrégée du PSI. Les ventes ordinaires
n'ajoutent pas de TTF dans ce modèle. Impôt personnel sur gains/dividendes,
type de compte et retenues spécifiques ne sont pas qualifiés ici : résultat
futur net de frais/TTF **avant fiscalité personnelle**.

La valeur par défaut0,4 % est configurée pour un scénario futur, pas une
certification de la loi future. Les taux historiques priment ; hors périmètre
une revalidation juridique et du calendrier d'assujettissement est nécessaire.

### Liste ISIN/ticker configurable

`config/taxes/fr_ttf_eligibility.yaml` : ISIN prioritaire, ticker de contrôle,
intervalle de dates, `liable: true/false`, preuve obligatoire. Les intervalles
ambigus ou une identité incohérente sont rejetés. Une absence dans ce fichier
donne **UNKNOWN**, jamais une taxe implicitement nulle. La liste reste vide
tant que les rapprochements ne sont pas validés.

Les listes officielles [pour2024](https://bofip.impots.gouv.fr/bofip/9789-PGP.html/identifiant=BOI-ANNX-000467-20231220)
et [pour2025](https://bofip.impots.gouv.fr/bofip/9789-PGP.html/identifiant=BOI-ANNX-000467-20241223)
ont été archivées. Elles nomment les sociétés, sans mapping ISIN automatique.
Le contrôle sur209 couples titre/année trouve13 rapprochements de noms exacts
normalisés et196 inconnus. Les13 sont **des propositions**, pas des statuts
fiscaux validés ; suffixes, changements de nom, siège de l'émetteur, champ
juridique et identité nécessitent une revue. Ni suffixe`.PA`, ni préfixeISIN,
ni cotation en EUR ne prouvent à eux seuls l'assujettissement ou l'exonération.

Export : `tax_issuer_candidates.parquet`. Les listes annuelles sont des
preuves fiscales observées aujourd'hui, pas de nouvelles features ML PIT.

## 3. Contrôle des actions sur titres et des chemins H5

`service/fr/economic_qualification_12a.py` lit les archives EODHD déjà payées,
vérifie chaque payload par SHA256, leur fenêtre et leur statut COMPLETED.
Calendrier XPAR : entrée à l'ouvertureJ, sortie à la clôtureJ+5, six séances
inspectées. Il n'exclut pas les candidats à partir du futur pour créer un
meilleur univers d'achat ; il produit un état d'aptitude du chemin, pas un PnL.

| État fournisseur |Chemins |
|---|---:|
|Aucun événement déclaré dans la détention |20 932 |
|Dividende avec champs monétaires/paiement complets, revue officielle requise |388 |
|Champs de dividende bloquants |50 |
|Prix manquant/non négociable dans le chemin |9 |

Aucun split dans ces chemins ; cela ne qualifie pas en bloc les splits des
autres titres/années. « Aucun événement déclaré » n'est pas une preuve
d'absence de fusion, droits, distribution exceptionnelle ou radiation.

Les50 chemins de dividende bloqués concernent ALSTI, ARG, IPS, LSS, OPM, PLNW,
RBT, SESG et VIRP ; la date de paiement manque ou précède la date ex dans les
données déclarées. Les9 chemins prix concernent ARTO, ERA, GLE, MEDCL et VCT.
Les exports détaillent les dates exactes. Ces lignes ne sont pas corrigées
par interpolation, pas supprimées du pool avant achat et pas promues.

105 événements fournisseur sont exportés pour revue dans la fenêtre élargie ;
ce nombre ne signifie pas105 événements effectivement rencontrés par un trade.

### Convention dividende et split

Pour une entrée à l'ouverture le jour ex, aucun droit au dividende du même
jour n'est créé. Pour un détenteur antérieur, le droit apparaît au jour ex et
le cash sera crédité à la date de paiement ; les créances après sortie devront
rester dans le ledger du portefeuille. `unadjustedValue`, deviseEUR et date de
paiement valide sont contrôlés ; pas de repli silencieux sur un montant ajusté
ni sur une devise manquante. Pas de double crédit avec `adjusted_close`.

L'absence de date de déclaration n'empêche pas automatiquement le calcul
réalisé si les autres preuves sont suffisantes ; elle empêche de transformer
l'événement en feature prédictive connue à une ancienne date. Les dates
publiées/révisées restent distinctes de l'observation du backfill.

Un split requiert ratio et date vérifiés, ajustement de quantité/prix cohérent,
éventuels rompus/cash et traitement de règlement. Le diagnostic ±25 % du
Sprint5 ne suffit pas à valider un facteur officiel. Les séries OHLC restent
intactes et les conventions brut/split-only/total-return ne sont pas mélangées.

Les champs complets des388 chemins ne sont **pas** une confirmation indépendante
des annonces ; aucune flag `economic_return_ready` ou `historical_pit_verified`
ancienne n'est mise à vrai.

## 4. Utilisation, tests et suite

Suite implémentée : [moteur12-B](sprint_12b_moteur_rejeu_economique.md).
Le ledger existe désormais, sans lever les blocages de qualification ci-dessous.

```powershell
python -u -m modelFactory.fr_economic_qualification_12a --output artifacts/fr/research/economic_qualification_12a/nouveau-run
```

Dossier nouveau, pas d'écrasement d'une preuve. Le service reste dans`service/fr` ;
la CLI dans`modelFactory`.12 tests ciblés coûts/qualification/préflight passent,
Ruff passe sur les fichiers concernés. Ils contrôlent composantes séparées,
taux à la frontière avril2025, inconnus fiscaux bloquants, paramétrabilité,
ordre annulé gratuit, stress et champs dividendes jamais inventés.

Déblocage restant : mapping fiscal instrument/date validé, revue indépendante
des dividendes utiles et anomalies de prix, contrat de traitement des événements
complexes/suspensions/radiations, puis ledger portefeuille/fills. Les coûts
génériques permettent ensuite un scénario sous hypothèses, pas une certification
de rentabilité réellement exécutable. **Ne pas déclarer11-A terminé avec un
rendement net fictif ou lever la certification PIT à partir des seules archives.**
