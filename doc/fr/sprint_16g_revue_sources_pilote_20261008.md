# Sprint 16-G — revue ciblée des preuves du pilote, 8 octobre 2026

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Conclusion opérationnelle

La recherche documentaire sur AIR.PA, OR.PA et SAN.PA apporte des
corroborations ponctuelles, mais **ne qualifie pas encore la devise de cotation
et les opérations sur titres sur toute la fenêtre**. Aucun titre supplémentaire
n'est libéré. Aucune collecte suspendue n'est réactivée.

Cette revue complète le [pilote](sprint_16g_pilote_devises_actions.md) et la
[nouvelle fenêtre prospective](sprint_16g_nouvelle_fenetre_prospective.md).
Elle ne remplace pas leurs rapports figés. C'est une seconde passe technique
du même assistant, pas une attestation humaine indépendante.

## Résultat par titre

| Titre et identité | Élément effectivement retrouvé | Conclusion permise | Réserve restant ouverte |
|---|---|---|---|
| AIR.PA — NL0000235190 / XPAR | Communiqués Airbus de rachats des 11–18 et 21–25 septembre, tableaux en EUR agrégés XPAR/XETA | Transactions ponctuelles exprimées en EUR ; rachats distincts d'un split | Pas de preuve spécifique à XPAR sur chacune des séances, ni de couverture exhaustive des opérations |
| OR.PA — FR0000120321 / XPAR | AG du 24 avril : dividende ordinaire 7,20 EUR, détachement le 29 avril ; deux notices DILA de capital/droits de vote, corps désormais lu | Identité et événement daté hors fenêtre ; les deux langues ne font pas deux opérations | Monnaie du dividende différente de la preuve de devise de cotation ; déclaration de capital insuffisante |
| SAN.PA — FR0000120578 / XPAR | Dividende ordinaire 4,12 EUR, détachement le 5 mai ; quatre notices DILA alliance/aide-mémoire en deux langues, corps désormais lu | Distinguer l'action SAN des ADS SNY ; événement hors fenêtre | Pas de couverture exhaustive septembre–octobre ; ces annonces ne donnent pas d'instruction d'ajustement |

Sources primaires de corroboration :

- [Airbus, 11–18 septembre](https://www.airbus.com/en/newsroom/press-releases/2026-09-airbus-reports-share-buyback-transactions-11-18-september-2026).
- [Airbus, 21–25 septembre](https://www.airbus.com/en/newsroom/press-releases/2026-09-airbus-reports-share-buyback-transactions-21-25-september-2026).
- [L'Oréal, AG du 24 avril 2026](https://www.loreal-finance.com/fr/communique-de-presse/assemblee-generale-mixte-du-24-avril-2026).
- [Sanofi, dividende de l'action et des ADR](https://www.sanofi.com/en/investors/sanofi-share-and-adrs/dividend).

Ces consultations sont postérieures à l'ouverture du 8 octobre. La date
affichée de publication ne démontre pas une réception historique par Alpha
Trade. Aucun fait n'est injecté rétroactivement dans les features.

## Premier essai DILA : échec de l'outil de consultation

Trois PDF français représentatifs ont été essayés dans l'outil de consultation,
sur leur URL exacte et sur le miroir officiel de même chemin :

| Notice | Chemin relatif après `INFOFI/` ou `OPENDATA/AMF/` | Résultat |
|---|---|---|
| L'Oréal, capital/droits de vote | `MKW/2026/10/FCMKW116486_20261006.pdf` | Non accessible par l'outil |
| Sanofi, alliance | `MKW/2026/10/FCMKW115651_20261001.pdf` | Non accessible par l'outil |
| Sanofi, aide-mémoire | `MKW/2026/10/FCMKW116372_20261006.pdf` | Non accessible par l'outil |

Hôtes essayés : `https://fr.ftp.opendatasoft.com/datadila/INFOFI/` et
`https://echanges.dila.gouv.fr/OPENDATA/AMF/`. Six tentatives au total.
Les autres versions n'avaient pas encore été relues lors de ce premier essai.

L'outil de consultation ne fournissait pas de statut HTTP exploitable : **ne pas transformer cet
échec en 404, 403, retrait de document ou interdiction juridique**. Aucun PDF
DILA n'avait été téléchargé, extrait ou validé visuellement lors de ce premier essai.
Les métadonnées locales restent des métadonnées. Le service de pilote ne
doit pas les compter comme des événements effectivement qualifiés.

## Un document Euronext utile, mais insuffisant pour cette qualification

Le [guide Euronext Securities PSET, version août 2025](https://www.euronext.com/sites/default/files/2025-08/euronext_securities_-_place_of_settlement_change_guidelines_-_v.1_august_2025.pdf)
a été consulté, avec contrôle visuel demandé des pages PDF 9 et 20
(numérotation du fichier, sections 2.1 et 4.1).

Il décrit un changement de lieu de règlement-livraison pour les transactions
en euros des marchés concernés, dont XPAR, prévu le 21 septembre 2026 avec
une date de secours au 12 octobre. Ce document de planification ne démontre
ni l'exécution effective de la migration, ni la devise de chaque instrument.
Un changement de dépositaire ne justifie pas un facteur d'ajustement OHLCV.
Pas de modification du calendrier, des bars, des taxes ou du moteur à partir
de cette seule pièce.

## Autorisations : ne pas élargir les collecteurs par déduction

Les [conditions L'Oréal Finance](https://www.loreal-finance.com/fr/mentions-legales)
prévoient un usage personnel et privé des contenus téléchargeables et des
restrictions sur leur réutilisation. Les [conditions Sanofi](https://www.sanofi.com/en/terms-of-use)
encadrent aussi la reproduction, avec une exception limitée de copie privée
personnelle non commerciale. Ces pages ne sont pas traitées comme une
autorisation générale d'aspiration automatisée ou d'utilisation ML.

Les conditions d'autres sous-domaines Airbus ne sont pas substituées à celles
du site consulté. Les droits applicables à un jeu de métadonnées DILA ne sont
pas étendus automatiquement à tous les PDF des émetteurs. Aucun nouveau
collecteur n'a été créé sur ces sites. Voir l'[audit des autorisations](audit_autorisations_collectes_20261006.md).
Ce choix prudent n'est ni une déclaration d'illégalité de toute consultation,
ni un avis juridique garantissant les usages futurs.

## Ce qui débloque réellement la suite

1. Obtenir, par une source dont l'usage est autorisé, une preuve de **devise de
   négociation** liant ISIN, MIC et intervalle effectif. Conserver source,
   version, empreinte et heure réelle de réception/qualification.
2. Qualifier les avis d'opérations applicables : identité, nature, date de
   détachement/effectivité, montant/devise ou ratio, traitement retenu.
   Conserver explicitement la portée de la recherche ; un endpoint vide ou
   trois communiqués ne prouvent pas l'absence de toute opération.
3. Raccorder ces pièces au dossier prospectif uniquement après leur revue.
   La présence d'une URL ne suffit pas ; aucun booléen de qualification ne
   doit être basculé manuellement pour masquer une réserve.
4. Continuer l'inventaire des bars/références jusqu'à la clôture du 12 octobre,
   puis contrôler la disponibilité à l'ouverture du 13. **Attendre cette date
   ne résout pas les deux premières exigences.**

On ne conclut pas que toute source gratuite est épuisée ni qu'un abonnement
est indispensable. En revanche, la promotion stricte reste bloquée tant que
ces preuves manquent. Une variante exploratoire fondée sur EODHD serait un
protocole distinct, soumis à un nouveau GO, et non une qualification
indépendante déguisée. Aucun entraînement n'est nécessaire pour cette revue.

## Deuxième voie officielle — accès débloqué et lecture effectuée

Après GO, un accès HTTP direct au miroir officiel `echanges.dila.gouv.fr`
a réussi : **6 demandés, 6 archivés, 0 échec**. Rapport conservé :
`artifacts/fr/research/issuer_pilot_16g/documents-20261008-v1/report.json`.
Le rapport a été achevé le 8 octobre à **22:12:28 Paris**. Chaque pièce a
son heure réelle de réception, son SHA256 et l'URL exacte du miroir.

Les six documents ont été extraits et leurs **16 pages rendues et examinées**.
Le manifeste de rendu est `extraction-v2/manifest.json` dans ce dossier.
Le premier essai d'extraction a échoué sur l'encodage de sortie Windows après
trois documents ; sa sortie partielle reste conservée. La v2 est complète.
Les avertissements pypdf d'objets mal pointés sont distincts d'un échec de
téléchargement : les pages ont pu être rendues et les passages utiles comparés.

| Groupe documentaire | Conclusion après lecture du corps et des notes |
|---|---|
| L'Oréal, capital/droits de vote, FR et EN | 532 649 827 actions ; ISIN dans le pied de page. La monnaie du capital social n'est pas une devise de négociation. Pas d'instruction d'ajustement extraite. |
| Sanofi/Regeneron, alliance, FR et EN | Annonce commerciale et paiements entre sociétés. Les montants en dollars ne sont ni un dividende actionnaire ni une preuve de cotation en USD. |
| Sanofi, disponibilité aide-mémoire, FR et EN | **Annonce de disponibilité**, pas l'aide-mémoire contenant les tableaux. La mention d'effets de change ne donne pas la devise de cotation. |

Les versions linguistiques sont regroupées pour la lecture, mais restent
archivées séparément. Elles ne sont pas certifiées identiques mot pour mot.
Pour Sanofi, l'ISIN provient du rattachement DILA vérifié ; les corps consultés
mentionnent les tickers SAN/SNY, pas un ISIN explicite. Aucune substitution
SAN/SNY n'est autorisée.

Revue structurée, **non chargée par le serving** :
`config/research_fr/pilot_document_review_16g.json`. Les empreintes lient les
conclusions aux six versions exactes. Le rapport de téléchargement reste
immuable avec son statut initial « archivé, non relu » ; la revue est distincte.

### Recherche complémentaire de devise

Les index [opérations L'Oréal](https://www.loreal-finance.com/fr/operations-sur-titres)
et [rachats Sanofi](https://www.sanofi.com/en/investors/sanofi-share-and-adrs/share-repurchases)
ont été consultés ponctuellement. Les déclarations de transactions retrouvées
ne fournissent pas ici une couverture complète septembre–octobre 2026.
Le programme Sanofi annoncé en février, même avec une échéance décembre,
ne démontre pas des transactions effectives quotidiennes sur tout l'intervalle.
Pas de collecte automatisée de ces sites ni de téléchargement de leurs PDF.

**Réserve technique d'accès DILA levée ; réserves de contenu non levées.**
La lecture n'a identifié aucune instruction qualifiant un ajustement de prix
dans ces six pièces. Cela n'est pas une preuve qu'aucune autre opération
n'a existé. La devise de cotation sur l'intervalle reste non qualifiée pour
les trois titres : l'élargissement à 20 titres n'est donc pas lancé.

### Reproduction et garde-fous

Service de recherche ponctuel : `service/fr/pilot_documents_16g.py`.
Il accepte seulement les chemins DILA exacts des six pièces du pilote,
refuse les redirections, limite chaque PDF à 8 Mo, conserve les échecs,
ne réécrit aucun ancien rapport et ne certifie jamais le contenu automatiquement.
La disponibilité des métadonnées n'est jamais réutilisée comme réception PDF.

```powershell
python -u -m service.fr.pilot_documents_16g --output-dir artifacts/fr/research/issuer_pilot_16g/nouvelle-collecte-documents
python -m pytest tests/test_fr_pilot_documents_16g.py --no-cov -q
```

**186 tests ciblés Sprint 16 passent**, dont dix nouveaux cas : URL/mirroir,
identité, absence de promotion/antidatage, préservation des sorties, réponse
non PDF et limite de taille. Ce résultat ne certifie pas toute l'application.

## Périmètre des changements

Complément postérieur : le [POC MiFIR actions](sprint_16g_preuve_devise_mifir.md)
établit EUR sur XPAR pour les trois titres pendant la séance du 7 octobre.
Il ne lève pas la réserve sur tout l'intervalle ni sur les opérations sur
titres. Réception réelle le 8 octobre à 22:22 Paris, sans antidatage.
Après ajout du lecteur et de ses tests, 200 tests ciblés Sprint 16 passent.

Cette passe ajoute un collecteur ponctuel de recherche, un outil local de
rendu/extraction, les tests et les notes de qualification.
Aucune écriture SQL, aucun changement de modèle ou de batch, aucune inférence,
aucun ordre et aucun run lourd ne sont lancés.
