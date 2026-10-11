# 12-C — Qualification des preuves d'exécution FR

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Bilan au4octobre2026

La demande est de qualifier les preuves avant le comparatif économique réel.
**Qualification partielle réalisée ; aucun comparatif net réel encore lancé.**
Un moteur qui sait traiter un dividende ne prouve pas que tous les événements
historiques sont présents. Un nom fiscal rapproché ne prouve pas qu'un autre
émetteur absent est exonéré. Ces deux distinctions restent bloquantes.

| Famille | Ce qui est acquis | Ce qui reste inconnu |
|---|---|---|
| TTF |112 couples titre/année positifs, sur209 |97 couples inconnus, jamais assimilés à des exonérations |
| Identité |61 titres ont au moins une année positive |62 titres ont au moins une année inconnue ; les groupes se recouvrent |
| Règlement |252 dates calculées avec règle standardT+2 et calendrierEUR distinct |Ce sont des règlements prévus, pas des règlements réellement observés |
| Dividendes |Planisware : montant/ex/paiement corroborés ; Virbac : montant/paiement émetteur |Ex Virbac indépendant, autres dates/événements et couverture exhaustive |
| Prix manquants |Artois : source officielle sans transaction ni prix d'ouverture ; alternatives Yahoo pour4autres |Les4dates du30juillet2024 sont hors fenêtre publique Euronext actuelle |
| Rejeu |Archives, overlays et files de revue traçables |0chemin promu économique ; PnL toujours absent |

Les sources observées en octobre2026 ne sont jamais antidatées pour devenir
des features PIT2024/2025. La recherche sur la réalisation d'un cashflow et la
disponibilité prédictive de l'annonce sont deux contrats différents.

## 1. Fiscalité : rapprochement positif documenté

Service : `service/fr/execution_evidence_12c.py`. Les listesBOFiP2024/2025
archivées au12-A sont vérifiées par hash et rapprochées des versions officielles
ESMA présentes dans`artifacts/fr/sprint6c_reference/identities.jsonl.gz`.

Un rapprochement est accepté seulement si :

- le symbole correspond au même ISIN dans les deux sources locales ;
- une versionXPAR d'action ordinaire (`CFI` débutant par`ES`) couvre toute
  l'année, éventuellement via plusieurs versions contiguës sans chevauchement ;
- le nom ESMA correspond **exactement**, après normalisation des accents/casse
  et ponctuation, au nom de la liste fiscale officielle ;
- l'instrument n'est pas l'exception compositeURW, exclue du rapprochement
  automatique tant que son assiette propre n'est pas qualifiée.

Cela augmente fortement la couverture par rapport à la comparaison initiale
du seul nom commercial EODHD, souvent suffixé«SA» ou«SE». Aucun rapprochement
flou n'est introduit et aucune absence de nom n'est interprétée comme exonération.
Le résultat est une qualification **de recherche des achats ordinaires sans
exemption**, pas une certification fiscale d'un compte ou une tablecanonique.

La liste séparée est
`artifacts/fr/research/execution_evidence_12c/qualification-20261004-v4/ttf_eligibility_research.yaml`.
Elle contient des lignes positives, leur année, les hashes et les versionsESMA.
La liste globale`config/taxes/fr_ttf_eligibility.yaml` n'est pas écrasée.
Un futur rejeu explicitement qualifié pourra choisir cette liste avec
`--eligibility`. Les absents continuent à provoquer un blocage.

Les112couples positifs **ne permettent pas** de supprimer les autres de la
population figée pour améliorer la performance. Un éventuel nouveau comparatif
sur un sous-univers qualifié doit être pré-enregistré comme une autre expérience,
avec biais de couverture, mêmes règles et même population pour chaque politique.

## 2. Règlement : règle standard distincte des fills réels

Le calendrierEUR utilise jours ouvrés hors1janvier, vendredi saint, lundi de
Pâques,1mai,25et26décembre. Les dates mobiles2024/2025 sont explicitement
versionnées, pas déduites des seuls jours fériés français ni du calendrierXPAR.
Le8mai français n'est ainsi pas traité comme une fermetureTARGET.

Sources : [guideBCE, §2.6page25](https://www.ecb.europa.eu/paym/target/consolidation/profuse/shared/pdf/2025.APR_p1_fundamentals.en.pdf),
[Euronext, cycleT+2 actuel avantT+1](https://www.euronext.com/en/regulation/t1-programme).
Le contexte historique du passage àT+2 est aussi confirmé par
[BCE, rapportT2S2014](https://www.ecb.europa.eu/press/intro/publications/html/t2s2014.en.html).
Le guideBCE et la pageEuronext sont archivés et hashés dans le dossier12-C.

Exemples testés :

- achat28mars2025 → règlement standard1avril2025 ; la date fiscale ne reste
  pas celle du signal de mars ;
- achat17avril2025 →23avril, après le week-end de Pâques ;
- achat28mars2024 →3avril ;
- achat7mai2025 →9mai, sans ajouter artificiellement le jour férié français.

Ces dates sont`QUALIFIED_STANDARD_INTENDED_T2_NOT_OBSERVED` si les sources sont
archivées. La règle ne simule pas les défauts de livraison. Une preuve de
calendrier standard suffit à définir un scénario de recherche déclaréT+2 ; elle
ne doit pas être présentée comme une observation de transaction réglée.
Le périmètre s'arrête en2025 : un règlement débordant en2026 est refusé.

## 3. Dividendes : revue et overlays, sans réécrire le fournisseur

Le fichier`dividend_field_overrides.json` contient les lignes exactes extraites
des tableaux indépendants, leurs URLs, hashes et portée :

- **Planisware** : ISINFR001400PFU4,0,31EUR, ex24juin2025,
  paiement26juin2025, corroborés par la
  [Bourse de Vienne](https://www.wienerborse.at/en/news/vienna-stock-exchange-news/walt-disney-dividends-global-market-06242025).
  La présence de ces termes ne prouve pas toute l'histoireCA de Planisware.
- **Virbac** :1,45EUR, paiement26juin2025, dans le tableau historique de
  [l'émetteur](https://corporate.virbac.com/home/investors/shareholders-area.html).
  Le jour ex24juin présent chez EODHD reste à corroborer indépendamment.
  Il n'est pas calculé par«paiement moins2jours».

Deux autres dossiers sont documentés mais non activés comme overlays complets :

- **Argan** : l'[AGMdu20mars2025](https://www.argan.fr/wp-content/uploads/2025/03/20250321-AG-Argan-2025-Votes-et-plan-de-developpement.pdf)
  approuve3,30EUR, ex26mars, paiement17avril et une option en actions ; défaut
  numéraire pour l'actionnaire qui n'opte pas.0,80EUR constitue un remboursement
  d'apport. Pièce lisible par la recherche web mais téléchargement local404 :
  ne pas la déclarer archivée ni appliquer une réparation sans pièce conservée.
- **Ipsos** : les documents préparatoires annoncent1,85EUR, ex1juillet,
  paiement3juillet. La proposition ne remplace pas la confirmation finale.
  La récupération locale de la pièce échoue et reste signalée dans le rapport.

Les autres dossiers à compléter sontSTIF, Lectra, OPmobility, Robertet etSES
(deux dates). Attention :LSS est **Lectra**, pas Linedata. Les titres, ISIN et
classes doivent être vérifiés avant de relier un communiqué à un événement.
SES a une retenue luxembourgeoise et les annonces disponibles divergent sur
une date de paiement2024 ; ne pas assimiler son dividende brut à un cash net
universel ni choisir silencieusement l'une des dates.

Aucun champ historiqueEODHD ni flag`economic_return_ready` n'est modifié.
Le dividende brut et la fiscalité personnelle restent séparés ; les retenues
à la source attachées au flux/instrument sont à qualifier, pas à ignorer.

## 4. Prix : résultat du contrôle officiel ciblé

Collecte ciblée existante réutilisée, sans changer son code :
`modelFactory.fr_fold7_euronext_proofs`. Rapport :
`artifacts/fr/research/execution_evidence_12c/missing-prices-euronext-20261004/report.json`.

Les cinq barres correspondent aux neuf chemins bloqués du12-A :

| Titre/date | Résultat |
|---|---|
|ARTO /10octobre2024|Euronext : volume0, aucun open/high/low, close9550. Ce close n'est pas un prix d'ouverture exécutable.|
|ERA /30juillet2024|Yahoo a une barre positive ; source officielle hors fenêtre publique.|
|GLE /30juillet2024|Même situation.|
|MEDCL /30juillet2024|Même situation.|
|VCT /30juillet2024|Même situation.|

Le collecteur respecte la restriction historique retournée par Euronext,
sans forcer le fournisseur à servir une fenêtre inaccessible. Aucun prix n'est
interpolé, aucune clôture n'est substituée à une ouverture, aucune archive
EODHD n'est modifiée. La barreYahooArtois à volume0 confirme qu'un cours porté
sans transaction ne suffit pas. Les quatre alternatives restent candidates
de réparation, pas des preuves officielles ni des fills.

## 5. Reproduire et débloquer la comparaison

```powershell
python -u -m modelFactory.fr_execution_evidence_12c --output artifacts/fr/research/execution_evidence_12c/nouveau-dossier
```

La CLI archive les sources accessibles, laisse les erreurs visibles, qualifie
les rapprochements positifs et exporte`official_price_requests.json` pour le
collecteur de prix. Dossier nouveau obligatoire. Aucun fit, SQL, serving ou
performance2026.29tests ciblés passent, dont frontières fiscales, joursTARGET,
chevauchements d'identités et maintien des inconnus ; Ruff passe sur le service.

Il manque encore pour le comparatif11-A sur sa **population inchangée** :

1. Statuer les97couples fiscaux inconnus : preuve d'identité/alias et scope,
   pas une exonération par défaut.
2. Corroborer la couvertureCA de chaque fenêtre détenue et résoudre les
   événements aux champs incomplets ou particuliers ; les388chemins à champs
   complets du fournisseur ne constituent pas encore une revue indépendante.
3. Obtenir la preuve des4barres2024 hors fenêtre publique, et raccorder le refus
   d'exécution pour Artois sans ouverture (implémenté en12-D ; pas supprimer sa ligne).

Actualisation : [levée gratuite 12-D](sprint_12d_levee_blocages_gratuits.md).
La revue fiscale passe de112 à134 positifs/209 ;75 restent inconnus. Les
chiffres initiaux de ce document sont conservés comme résultat historique12-C.
4. Assembler les tapes par politique/fold avec cette preuve, puis lancer
   nominal et stress. Le moteur12-B est prêt, les données ne le sont pas toutes.

Si ces preuves ne sont pas accessibles gratuitement, il faut soit une source
historique/annonces supplémentaire, soit une **nouvelle expérience explicitement
sous hypothèses fournisseur**. Cette dernière demanderait un changement du
contrat de qualification, pas le passage automatique des flags à vrai. Elle
ne serait pas le comparatif économique qualifié demandé ici.

## 6. Complément public et demande précise — 4 octobre 2026

La suite est conservée dans le
[dossier de preuves historiques manquantes](demande_preuves_historiques_manquantes.md).
Collecte supplémentaire de 13 sources ciblées, revue de 10 faits/champs,
corroboration du paiement ABC Arbitrage au 10 juillet 2025 contre le 1er juillet
erroné du fournisseur. Les 97 cas fiscaux demeurent inconnus : revue gratuite
d'identité d'abord, pas exonération ou achat implicite.
Exports : quatre barres officielles à demander, 212 intervalles CA pour 118
symboles, 105 événements fournisseur et toutes les 21 379 fenêtres candidates.
Aucun chemin promu, PnL non calculé (`null`, pas un rendement zéro), aucune demande payante envoyée.
L'exhaustivité des sources gratuites n'est pas revendiquée.
