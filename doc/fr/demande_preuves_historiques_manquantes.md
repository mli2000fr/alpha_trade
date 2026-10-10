# FR — Bilan public gratuit et demande ciblée de preuves historiques

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

État au 4 octobre 2026. Référence : comparaison économique des folds 6/7,
H5 LONG cash, capital 4 000 EUR, politiques ATR TOP20 / Oracle TOP20 / contrôle
uniforme. Aucun modèle réentraîné, aucune performance 2026 consultée.

**Mise à jour après levée gratuite :** [bilan 12-D](sprint_12d_levee_blocages_gratuits.md).
137/209 couples fiscaux sont désormais positifs ; 72 restent inconnus sur
47 titres. Le refus causal d'ouverture est implémenté et testé ; son overlay
Artois est qualifié, sans application automatique de tape. Le dossier
actualisé est `artifacts/fr/research/execution_public_requests/public-pass-20261004-v5`.
Les chiffres 112/97 ci-dessous décrivent la passe antérieure 12-C.

## 1. Décision et limite de cette passe

Les vérifications publiques ciblées ont été poursuivies avant toute demande
payante : calendriers, listes fiscales BOFiP, identités ESMA, prix publics
Euronext, alternatives Yahoo et annonces des émetteurs. Elles ont produit des
preuves utiles, mais **pas un GO économique**. L'absence d'un communiqué dans
une recherche Web n'est jamais une preuve d'absence d'opération sur titres.

Il serait faux d'affirmer que toutes les sources gratuites sont épuisées :
la revue manuelle des alias fiscaux et des avis historiques reste possible.
Cette passe clôture une collecte publique **bornée**, et fournit le dossier
exact permettant de traiter les réserves restantes sans commander un abonnement
complet par défaut. Aucun devis envoyé, aucun achat effectué.

### Dossiers de référence

- Qualification initiale : `artifacts/fr/research/economic_qualification_12a/qualification-20261004-v2`.
- Qualification publique précédente : `artifacts/fr/research/execution_evidence_12c/qualification-20261004-v4`.
- Prix officiels manquants : `artifacts/fr/research/execution_evidence_12c/missing-prices-euronext-20261004`.
- Nouvelle passe et demandes structurées :
  `artifacts/fr/research/execution_public_requests/public-pass-20261004-v2`.

Le dernier dossier contient les sources brutes accessibles, leurs SHA256,
les erreurs HTTP et des demandes JSON. Les fichiers existants ne sont pas
écrasés ; les tables et les prix canoniques ne sont pas modifiés.

## 2. Ce que les sources gratuites ont réellement apporté

### Règles, identités et prix

La passe 12-C a rapproché **112 couples émetteur/année positifs sur 209** pour
la TTF. Les **97 autres couples, concernant 62 symboles**, restent inconnus,
pas exonérés. Les alias, les sièges sociaux et les instruments particuliers
doivent être examinés ; retirer simplement `SA`, `SE` ou un préfixe d'ISIN ne
constitue pas une qualification négative fiable.

Le calendrier permet le règlement **standard prévu T+2**, pas la preuve qu'un
ordre fictif a réellement été réglé. Les conventions et fermetures TARGET
sont conservées dans le dossier 12-C ; ne pas substituer les jours fériés
français au calendrier EUR.

Pour Artois le 10 octobre 2024, la source publique Euronext donne une clôture
de 9 550 EUR avec volume nul, mais aucune ouverture. Il faut donc implémenter
un refus d'ordre causal avec suivi de la trésorerie et des positions. Le moteur
12-B dispose maintenant de ce refus testé ; la tape réelle reste à assembler
avec la preuve d'absence de transaction, sans promouvoir une performance.
Ne pas interpoler une ouverture, employer la clôture comme fill ou supprimer
le candidat a posteriori.

Pour les quatre autres barres du 30 juillet 2024, les alternatives Yahoo sont
disponibles, mais la fenêtre historique publique du collecteur Euronext ne les
dessert pas. Elles ne sont pas promues en preuves officielles.

### Annonces de dividendes : montant, date, statut, limites

| Titre | Résultat de la vérification publique | Réserve conservée |
| --- | --- | --- |
| ABC Arbitrage | Solde 0,04 EUR, ex-date 8 juillet 2025, paiement 10 juillet ; AG du 6 juin adoptée. Le paiement fournisseur au 1er juillet est erroné. | Le communiqué emploie « net » : ne pas inventer une conversion brut/net. Couverture complète distincte. |
| Argan | AG : 3,30 EUR, ex-date 26 mars, paiement 17 avril 2025 ; option actions, numéraire par défaut ; 0,80 EUR remboursement d'apport. | PDF lisible par le moteur Web, téléchargement local 404 ; modalités particulières à conserver. |
| Lectra (`LSS.PA`) | 0,40 EUR approuvé le 25 avril 2025, mise en paiement annoncée le 5 mai. | Ex-date officielle non trouvée dans cette page ; LSS n'est pas Linedata. |
| SES | L'AG du 4 avril 2025 rapporte l'acompte de 0,25 EUR par action A payé le 17 octobre 2024 ; solde de 0,25 EUR payé le 17 avril 2025 confirmé au T1. | Vérifier FDR/classe correspondant à `LU0088087324`, détachements, retenue éventuelle ; accès local 403. Ne pas attribuer 0,50 EUR à chaque versement. |
| Robertet | Résolution 3 : 10 EUR, paiement 1er juillet 2025 ; texte et résultat des votes archivés. | Relecture croisée de la résolution et du vote, classe action/certificat, ex-date officielle. |
| STIF | Rapport 2024 propose 0,59 EUR à l'AG du 22 mai 2025. | Proposition ≠ approbation/paiement. Dates et décision finale restent requises ; local 403. |
| OPmobility | Solde proposé 0,36 EUR le 2 mai 2025, différent du total annuel 0,60 EUR. | Approbation finale et ex-date à corroborer ; ne pas compter à nouveau l'acompte. |
| Vetoquinol | Avis d'AG : paiement au plus tard le 6 juin 2025. | Une date limite n'est pas une date de paiement exacte ; approbation et détachement requis. |
| Jacquet Metals | Calendrier émetteur annonce paiement le 3 juillet 2025. | Montant approuvé et ex-date ; local 403. |
| Planisware | Avis de la Bourse de Vienne : ISIN, 0,31 EUR, détachement 24 juin et paiement 26 juin 2025. | Événement précis corroboré, pas une couverture complète XPAR. |
| Virbac | Historique émetteur : 1,45 EUR, paiement le 26 juin 2025. | Ex-date 24 juin reste fournisseur uniquement. |

Ces résultats sont des revues de champs, **pas des tapes économiques admises**.
Les PDFs archivés ne sont pas automatiquement parsés et promus. Le fichier
`public_event_reviews.json` conserve les statuts proposition / calendrier /
approbation / paiement rapporté, les réserves et le lien vers la source.
Les preuves Web lisibles mais impossibles à archiver localement restent marquées
inaccessibles dans le manifeste local. Aucun contournement de restriction.

Sources primaires consultées :

- [ABC Arbitrage, compte rendu AG 2025](https://www.abc-arbitrage.com/wp-content/uploads/2025/06/ABCA-CP-AG-2025-compte-rendu-assemblee-generale-VF.docx.pdf).
- [Argan, vote et modalités 2025](https://argan.fr/wp-content/uploads/2025/03/20250321-AG-Argan-2025-Votes-et-plan-de-developpement.pdf).
- [Lectra, dividende](https://www.lectra.com/fr/investisseurs/information-actionnaires/dividende).
- [SES, résultats AG](https://www.ses.com/press-release/ses-announces-annual-general-meeting-voting-results) et [résultats T1 2025](https://www.ses.com/press-release/ses-q1-2025-results).
- [Robertet, résolutions](https://www.robertet.com/wp-content/uploads/2025/12/ACTUS-0-16121-robertet-sa-agm-2025-texte-des-resolutions.pdf) et [votes](https://www.robertet.com/wp-content/uploads/2025/12/ACTUS-0-16359-robertet-resultat-du-vote_ag-4-juin-2025.pdf).
- [STIF, rapport 2024](https://investir.stif.fr/wp-content/uploads/2025/03/20250327_STIF_RA2024_VDef-1.pdf).
- [OPmobility, DEU 2024](https://www.opmobility.com/wp-content/uploads/2025/03/opmobility-deu-2024-fr.pdf).
- [Vetoquinol, avis 2025](https://www.vetoquinol.com/fr/publication/6009/view).
- [Jacquet Metals, calendrier T1 2025](https://www.jacquetmetals.com/fichiers/communiques/2025/JM_CP_T125_FR.pdf).

## 3. Demande minimale n°1 — quatre journées de prix officiels

La demande porte sur **ces quatre couples uniquement**, pas tout l'historique :

| Symbole local | ISIN | MIC | Séance |
| --- | --- | --- | --- |
| ERA.PA | FR0000131757 | XPAR | 2024-07-30 |
| GLE.PA | FR0000130809 | XPAR | 2024-07-30 |
| MEDCL.PA | FR0004065605 | XPAR | 2024-07-30 |
| VCT.PA | FR0000031775 | XPAR | 2024-07-30 |

Champs nécessaires : ouverture réellement cotée, high, low, clôture, volume
en actions, devise, MIC, statut de séance/instrument, présence ou absence de
transaction d'ouverture, nature de la clôture et convention de série.
Les prix de fill doivent être **bruts/non ajustés** ; si une série ajustée est
fournie, joindre les facteurs et les événements responsables séparément.

Demander la provenance (bourse ou distributeur licencié), la version, les
corrections ultérieures et le droit de conservation pour recherche interne.
Un prix porté sans transaction, une clôture seule ou une seconde copie EODHD
ne remplissent pas cette demande. Fichier attendu : CSV/JSON, une ligne par
ISIN/MIC/date, plus notice de provenance. `requests_prices.json` inclut aussi
Artois, mais `request_paid_price=false` pour ce cas déjà expliqué publiquement.

## 4. Demande n°2 — couverture des opérations sur titres

Population figée : **118 symboles**, **212 intervalles titre/fold** couvrant
les fenêtres candidates entre le **29 juillet 2024 et le 30 juillet 2025**.
Ce sont **21 379 chemins candidats**, pas 21 379 trades exécutés. Ne pas réduire
la demande aux gagnants ou aux titres sélectionnés après calcul des rendements.

Pièces jointes prêtes :

- `requests_coverage.json` : ISIN, symbole, MICs, fold, début/fin et nombre
  de chemins ; chaque intervalle est une enveloppe de collecte, pas l'affirmation
  que le portefeuille détient le titre en permanence.
- `exact_holding_windows.parquet` : chaque fenêtre exacte entrée/sortie.
- `requests_events.json` : **105 événements fournisseur** à corroborer,
  dates/montants actuels, contrôles en échec et ISIN. Le fournisseur est un
  point de départ, pas une preuve indépendante. Ce nombre n'est pas le nombre
  d'événements réellement subis par les futurs portefeuilles.

Demander **tous** les événements des intervalles, y compris ceux absents du
fournisseur : dividende ordinaire/spécial, acompte/solde, remboursement de
capital, split/reverse split, droits, distribution d'actions, option numéraire/
actions, fusion, scission, échange d'ISIN et radiation. Pour chaque événement :

- identifiant stable, ISIN avant/après, MIC, classe, devise ;
- date d'annonce, publication, ex-date, record-date, paiement et effet ;
- montant brut par titre, montant net si fourni et règle de retenue ;
- ratio split/échange, cash component, droits et traitement des fractions ;
- options, choix par défaut et échéance d'élection ;
- référence d'avis officiel, version/correction et provenance.

La source doit expliciter sa **couverture** par intervalle. Un export vide
signifie « aucun événement » seulement si le fournisseur garantit le périmètre
et l'exhaustivité de son fichier ; sinon c'est « non observé ». Ne pas demander
une attestation absolue impossible : une liste complète du feed licencié et
ses limites documentées peut être examinée, sans les masquer.

Les paiements postérieurs à la sortie restent dus aux détenteurs éligibles :
conserver la date future de paiement dans la notice même si elle dépasse la
fenêtre détenue. Un événement connu en 2026 peut corroborer un flux historique
2025, mais ne devient pas une feature disponible en 2025 par rétrodatation.

## 5. Demande n°3 — fiscalité : revue gratuite avant achat

`requests_tax.json` fournit les **97 couples ISIN/année inconnus**, leurs
symboles/MICs et noms ESMA datés. Ce fichier est une liste de **revue d'identité**,
pas une commande de prix payants. La priorité est de relier explicitement le
nom BOFiP à l'émetteur légal et à sa classe de titre pour 2024 et/ou 2025.

Pour chaque ligne : obtenir dénomination légale datée, siège/pays fiscal,
ISIN/classe, changement de nom, entrée/sortie de scope et référence officielle.
Pour une réponse négative, conserver le motif et sa preuve : absence de
correspondance textuelle ou ISIN étranger ne suffisent pas automatiquement.
Traiter séparément les instruments composés/dépositaires et éviter d'appliquer
une preuve d'action ordinaire à un certificat. L'éligibilité fiscale n'est pas
une preuve d'exécution réelle.

Les 112 positifs déjà qualifiés restent dans le fichier de recherche 12-C.
La configuration globale des taxes n'est pas modifiée.

## 6. Ce qu'il ne faut pas acheter pour cette comparaison

Pas de nouvelles features directionnelles, options, news, quotes temps réel,
consensus ou réentraînement. Les spreads et slippages restent les hypothèses
configurables acceptées par l'utilisateur, pas des mesures qualifiées. Les
commissions génériques restent 1 EUR par ordre ; la TTF est séparée.

Un abonnement complet n'est donc pas justifié par ce dossier seul. Si les
sources gratuites ne suffisent pas, demander d'abord : **un extrait ponctuel
des quatre barres**, puis **un extrait CA sur les intervalles joints**, avec
prix, couverture, droits et échantillon de format. Aucun tarif supposé ici.

## 7. Réception, admission et prochain GO

1. Archiver les pièces originales, provenance, date de collecte et SHA256.
2. Réconcilier ISIN/MIC/devise/date ; comparer brut et ajusté sans écrasement.
3. Qualifier chaque champ, les règles fiscales et la couverture CA. Garder
   explicites les champs inconnus et les contradictions.
4. Raccorder la preuve Artois au refus causal implémenté ; conserver son intention.
5. Construire les tapes selon le contrat 12-B et les politiques figées ;
   vérifier créances/dividendes, trésorerie, quantités, coûts et taxes séparés.
6. Seulement après admission complète, exécuter nominal/stress par fold et
   publier les rendements nets. Pour l'instant : **0 chemin promu**, aucun PnL.

Une renonciation aux preuves indépendantes serait une nouvelle expérience
« sous hypothèses fournisseur », pas la clôture de ce contrat.

## 8. Reproduire la collecte / maintenance

```powershell
python -u -m modelFactory.fr_public_evidence_requests --output artifacts/fr/research/execution_public_requests/nouveau-dossier
```

Nouveau dossier obligatoire. Service : `service/fr/public_evidence_requests.py`.
CLI : `modelFactory/fr_public_evidence_requests.py`. Collecte bornée de 13 URLs,
3 téléchargements simultanés au maximum, TLS vérifié, timeout, PDF contrôlé,
erreurs visibles. Les revues sont manuelles et n'alimentent pas le moteur
automatiquement. Aucun batch quotidien ajouté ; aucun run existant touché.

Vérification locale : 19 tests ciblés du dossier public, du règlement/fiscalité
et du moteur 12-B passent ; Ruff passe sur les trois nouveaux fichiers Python.
Le dossier final archive 7 sources ; 6 téléchargements restent explicitement
inaccessibles (403/404). Leur lecture via le moteur Web n'est pas présentée
comme une archive brute locale qualifiée.
