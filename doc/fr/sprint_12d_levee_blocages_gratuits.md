# Sprint 12-D — Levée gratuite des réserves économiques FR

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

État vérifié le 4 octobre 2026. **Avancement partiel, pas de GO économique.**
Cette étape ne commande aucun extrait et ne modifie ni les tables, ni les
prix canoniques, ni les modèles, ni les batchs en cours. Les politiques H5,
les folds 6/7 et les coûts restent figés ; aucun résultat 2026 n'est exploité.

Pour réutiliser les sources : [catalogue détaillé des sources gratuites,
usages et contrat d'intégration](catalogue_sources_gratuites_validation_historique.md).

## Suite exécutée : 12-E

[Inventaire du périmètre exploitable](sprint_12e_perimetre_exploitable.md) :
21 379 chemins conservés, 16 032 passant les contrôles partiels, aucun entièrement
qualifié. Couverture partielle des intentions Oracle 30,24 %, ATR 37,11 % et
contrôle uniforme 74,99 % : ne pas comparer des sous-échantillons différents
ni filtrer à l'entrée sur le futur chemin. Aucun PnL calculé.

## 1. Bilan mesurable

### Reprise du 4 octobre — nouvelles pièces et raccord Artois

Référence courante : `artifacts/fr/research/free_blocker_review/review-20261004-v6`.
**137/209 positifs, 72 inconnus sur47titres**, aucune exonération implicite.
Les chiffres134/75du tableau ci-dessous sont conservés comme bilan antérieur.
ADP2024/2025 est désormais corroboré par le communiqué annuel2024 archivé sur
Euronext ; Artois2024 par une publication AMF225C0150. Les2casBolloré restent
inconnus : PDFémetteur403, pageEuronext non reçue correctement. Aucun
contournement, ni assimilation de lectureWeb à une archive locale.

Sources alternatives reçues :
- [ADP — résultats annuels2024](https://live.euronext.com/sites/default/files/company_press_releases/attachments/2025/02/19/cpr03_lesechos_16165_1316157_Aroports_de_Paris_SA__Rsultats_annuels_2024.pdf).
- [Artois — publication AMF](https://bdif.amf-france.org/back/api/v1/documents/2025/225C0150/5D20A8FF0BC0A996C0D22A290FFF0804005B6035371E63982D5C147E49DDBED4.pdf).

La relance conserve les sources identiques déjà archivées, avec contrôle duSHA,
URLidentique et date d'observation originale. Elle ne dégrade pas une preuve
valide parce qu'une nouvelle requête réseau échoue. Les snapshots de manifeste
et anciennes sorties sont conservés.

`remaining_tax_requests.json` ajoute, pour chaque cas, les pièces requises et
`scope_review_complete`. Les70autres cas sont triés :58sans correspondance
annuelle qualifiée,10de scope d'émetteur étranger,2de scope composéURW.
**Ce tri n'est pas la revue juridique individuelle achevée de70cas.** Il faut
encore leurs pièces historiques, sièges/classes et, selon le motif, capitalisation
au1erdécembre précédent ou autre justification d'exclusion du scope.

Raccordement Artois : `service/fr/opening_evidence_overlay.py`, commande
`modelFactory.fr_opening_evidence_overlay`, sortie
`artifacts/fr/research/opening_evidence_overlay/artois-20261004`.
Le module vérifieSHAde la réponse bruteEuronext et des identités, déchiffre
la pièce, lit les en-têtes corrects Close/Numberofshares et produit un overlay
`opening_execution.status=NO_OPENING_TRANSACTION` relié auUID/ISIN/MIC/date.
**Une intention d'entrée** est concernée ; aucun autre chemin détenu concerné
dans la population examinée. Le cours porté9550EUR n'est pas un prix exécutable.
L'overlay est compatible avec le refus du moteur, mais n'est pas automatiquement
appliqué à une tape réelle : assemblage/rejeu complet toujours non lancé.

Dossier actualisé : `artifacts/fr/research/execution_public_requests/public-pass-20261004-v5`
avec72inconnus,4barres à corroborer,105pistes d'événements et12revues publiques.
Dividendes : pas de nouvel événement entièrement qualifié par cette reprise.
28tests ciblés passent etRuff passe. **0chemin promu, aucun PnL, aucun achat,
aucune modification des tables, aucun entraînement/backtest.**

### Décision du 4 octobre : pas de source payante

L'utilisateur ne souhaite pas prendre d'abonnement. Les recherches déjà faites
ne sont pas présentées comme un épuisement exhaustif du gratuit. Les deux cas
Bolloré, les revues individuelles de scope et les preuves de dividendes restent
ouverts, sans statut favorable inventé.

Prochaine étape : inventorier les blocages par chemin et mesurer, par fold et
politique figée, le périmètre commun réellement exploitable avec les preuves
disponibles. Documenter les exclusions et leur biais potentiel avant toute
comparaison. Ne pas choisir les exclusions selon le rendement réalisé. Si la
couverture complète des opérations sur titres demeure absente pour tous les
chemins, conserver le blocage économique plutôt que lancer un backtest réputé
qualifié. Aucun nouveau modèle n'est nécessaire pour cet inventaire.

Les sections suivantes conservent le bilan historique de la première passe ;
les chiffres courants sont ceux de la reprise ci-dessus (137/209 et 72 inconnus).

| Contrôle | Avant | Après cette passe |
| --- | --- | --- |
| Couples titre/année TTF positifs | 112/209 | **134/209** |
| Couples fiscaux inconnus | 97 | **75, concernant 49 titres** |
| Exonérations déduites implicitement | 0 | **0** |
| Refus causal pour absence prouvée d'ouverture | Non implémenté | Implémenté et testé dans le moteur de recherche |
| Revues publiques de termes de dividendes | 10 | 12, toujours partielles |
| Chemins admis pour une performance économique qualifiée | 0 | **0** |
| Demandes payantes envoyées | 0 | **0** |

Le nombre de couples fiscaux n'est pas le nombre de trades. Les 21 379 chemins
candidats, 118 titres et 212 enveloppes de couverture restent inchangés.

## 2. Fiscalité : rapprochements explicites, non approximatifs

Le manifeste `config/research_fr/ttf_alias_review_20261004.yaml` contient
16 correspondances examinées manuellement. Le service
`service/fr/free_blocker_review.py` relit tous les 97 inconnus initiaux.
Une correspondance positive exige : symbole et ISIN exacts, libellé ESMA
explicitement autorisé, nom présent dans la liste BOFiP de l'année concernée,
classe action ordinaire, continuité annuelle XPAR et archive primaire d'identité.
La source HTML doit contenir l'ISIN ; les documents PDF sont des pièces revues
manuellement, et non une extraction sémantique automatique réputée infaillible.
Les SHA256 de l'identité et des listes fiscales sont vérifiés avant traitement.

Les 22 ajouts concernent BNP, Getlink, GTT, Maurel & Prom, Odet, OVH, Publicis,
Hermès et Schneider en 2024 et 2025 ; JCDecaux, M6 et Ubisoft en 2025 ;
Opmobility en 2024. Aucun statut n'est étendu automatiquement à une autre année.

Les cinq cas ADP 2024/2025, Bolloré 2024/2025 et Artois 2024 disposent d'une
piste de rapprochement mais leur archive d'identité n'a pas été reçue : les
tentatives DILA ont échoué. Ils restent inconnus. Une lecture Web ou un libellé
plausible ne remplace pas la pièce locale traçable exigée par ce contrat.
Les autres cas nécessitent une revue de scope, de siège fiscal, de classe de
titre ou de liste annuelle. URW composé doit notamment être traité séparément.
Ni ISIN étranger ni absence d'un nom de la liste ne prouvent seuls une exonération.

Référence :
`artifacts/fr/research/free_blocker_review/review-20261004-v2/report.json`.
Le YAML d'éligibilité produit est **de recherche seulement** ; il ne remplace
pas la configuration fiscale globale.

## 3. Artois : rejet au moment de l'ouverture, pas sélection rétrospective

Le moteur `service/fr/portfolio_replay_12b.py` accepte désormais, pour une
intention d'achat, une barre portant `opening_execution.status =
NO_OPENING_TRANSACTION`. Il exige simultanément une ouverture absente,
`economic_verified: true`, une preuve de barre et une preuve spécifique
d'absence de transaction. Une ouverture existante contredit ce statut et bloque.

Le journal conserve le candidat, son rang et un ordre `REJECT` avec motif et
preuve. Aucun achat, commission, taxe ou mouvement de trésorerie n'est créé.
La capacité reste disponible pour le candidat suivant. Les gates fiscaux et
de couverture future ne s'appliquent pas à un achat non exécuté. Cela ne permet
pas de masquer un prix de valorisation manquant sur une position déjà détenue.
Un simple `open: null` sans preuve demeure bloquant.

Il s'agit d'une règle du moteur testée sur fixtures, **pas encore d'une tape
réelle assemblée et qualifiée pour Artois**. Ne pas présenter ce changement
comme un rendement historique calculé, ni remplacer son ouverture par 9 550 EUR.

## 4. Dividendes : nouvelles pièces, limites inchangées

Le rapport semestriel Ipsos au 30 juin 2025, section 6.4.6, indique un dividende
de 1,85 EUR au titre de 2024 mis en paiement le 3 juillet 2025. Le titre affiché
par le moteur de recherche mentionne erronément 2024 : c'est le document lui-même
qui identifie le semestre 2025. L'archive PDF est reçue, son format et son SHA
sont contrôlés. La date de détachement et la convention net/brut restent à
qualifier ; aucune date n'est déduite du paiement moins deux jours.

Le BALO STIF 2501055 du 16 avril 2025 annonce un paiement proposé le 2 juin
pour 0,59 EUR. Le téléchargement local reçoit un 403. Cette piste reste
`PROPOSED_TERMS`, sans preuve de vote final ni de paiement effectif.
Les annonces déjà recueillies restent des preuves de champs : elles ne prouvent
pas la complétude des opérations sur titres sur tous les jours de détention.

Référence du dossier actualisé :
`artifacts/fr/research/execution_public_requests/public-pass-20261004-v4`.
Il contient les 75 demandes fiscales restantes, les quatre journées de prix
non qualifiées, les 105 événements fournisseurs à corroborer, les 212 enveloppes
de couverture et les 21 379 fenêtres exactes. Une archive reçue n'est jamais
promue automatiquement en événement vérifié.

## 5. Travail gratuit restant avant toute demande payante

1. Obtenir une archive primaire alternative accessible pour les cinq cas
   ADP/Bolloré/Artois ; vérifier ISIN, classe et noms datés, puis relancer la revue.
2. Traiter les 70 autres inconnus fiscaux avec justificatifs annuels de scope.
   Une liste ISIN d'un dépositaire datée de 2026 ne doit pas être appliquée
   rétrospectivement en 2024/2025. La piste publique LuxCSD repérée n'a pas encore
   fourni une archive historique utilisable.
3. Chercher les dates de détachement, votes finaux et avis d'opérations manquants
   dans les publications émetteurs, BALO/AMF et avis Euronext accessibles.
   Réconcilier les classes et modalités cash/actions, sans convertir les
   propositions en événements réalisés.
4. Qualifier la couverture indépendante, y compris les journées sans événement.
   L'absence de résultat dans une recherche Web n'atteste pas cette couverture.
5. Assembler la tape Artois avec sa preuve publique ; maintenir les quatre
   autres barres du 30 juillet 2024 comme inconnues tant qu'elles ne sont pas
   corroborées. Aucun prix Yahoo n'est promu en preuve officielle par défaut.
6. Refaire la qualification et seulement ensuite le rejeu économique réel.

**Les sources gratuites ne sont pas déclarées épuisées.** L'extrait payant
reste différé ; la présente passe réduit les réserves sans les dissimuler.

## 6. Reproduction et tests

Créer chaque fois un nouveau dossier, sans écraser les preuves précédentes :

```powershell
python -u -m modelFactory.fr_free_blocker_review --output artifacts/fr/research/free_blocker_review/nouvelle-revue
python -u -m modelFactory.fr_public_evidence_requests --evidence artifacts/fr/research/free_blocker_review/nouvelle-revue --output artifacts/fr/research/execution_public_requests/nouvelle-passe
```

La collecte est bornée, TLS vérifié, au maximum trois requêtes simultanées,
échecs visibles. Les dates de collecte ne sont pas antidatées en dates PIT.
26 tests ciblés passent : alias/ISIN/continuité, statut proposé vs payé, absence
d'ex-date, refus sans ouverture, preuves contradictoires, capacité libérée,
trésorerie, taxes, coûts et invariants du rejeu. Ce résultat ne vaut pas
exécution de toute la suite du projet.
