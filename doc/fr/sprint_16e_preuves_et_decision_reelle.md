# Sprint 16-E — Preuves locales et contrôle à une ouverture réelle

État au 6 octobre 2026, après 21 h Paris : outils livrés, preuves partielles
archivées et contrôles exécutés. **Shadow toujours interdit.** La confirmation
à une nouvelle ouverture n'a pas encore eu lieu ; ne pas clôturer le Sprint 16
sur la seule préparation de cette confirmation.

## 1. Résultat concret

| Travail | Résultat | Limite conservée |
| --- | --- | --- |
| Archivage des pièces émetteurs | 7 sources archivées sur 8 demandées | Société Générale : deux délais réseau, pas de pièce locale validée |
| Lecture des modalités des dividendes | BNP, Odet, Oeneo, SPIE et Trigano relus sur pièces locales | Annonce et décision ne prouvent pas le paiement réalisé ni le traitement des features |
| Devise AMA | Page émetteur : cotation EUR, nominal GBP | Intervalle historique de validité non certifié |
| Devise EC | Page émetteur associant l'ISIN GA0000121459 à une cotation Paris en EUR | Vérification Web descriptive, pas archive locale d'un flux de quotes ni preuve d'intervalle |
| Devise MLZAM | Portail IR : rubrique Euronext en EUR, distincte de Lusaka ZMW et Londres USD | Même réserve d'intervalle et de disponibilité historique |
| Warmup après collecte | 242 calculables, 233 passages locaux | 0 servable ; aucune réserve supprimée automatiquement |
| Rejeu de l'ouverture du 6 octobre | 0 jeu complet et 0 candidat admis | Le bootstrap du soir était indisponible à cette ouverture |

Les cinq dividendes relus représentent six documents/sources (Odet possède
un PDF et un calendrier HTML). Avec AMA, sept sources ont une revue liée à
leur empreinte. Ce ne sont pas sept dividendes et ce n'est pas une seconde
revue humaine indépendante.

## 2. Archivage borné, réexécutable et sans promotion

Implémentation :

- `service/fr/evidence_archive_16e.py` : téléchargement d'une petite liste
  explicite de communiqués et d'une page d'identité émetteur ;
- `config/research_fr/evidence_16e.json` : URLs et modalités candidates ;
- `config/research_fr/evidence_review_16e.json` : revue des pièces réellement
  lues, SHA-256, localisateur et champs confirmés ;
- `service/fr/decision_qualification_16e.py` : audit hors ligne combinant
  assemblage quotidien, référentiel connu et disponibilité des preuves.

L'archivage n'est pas un nouveau batch planifié. Il ne collecte ni quotes,
ni Excel Euronext, ni données provenant de batchs bloqués pour droits/prudence.
Il n'ajoute rien à SQL et n'active aucune fonction de trading.

Chaque source téléchargée possède : URL initiale/finale, format, SHA-256,
taille bornée à 12 Mo, `observed_at`, `available_at`, chemin brut. Les PDF
sont conservés intégralement ; leur texte extrait est une aide à la lecture,
pas une preuve suffisante à lui seul. Les pages utiles ont été rendues et
relues : BNP page 6, Oeneo page 1, SPIE page 4, Trigano page 3, Odet pages
1 et 4. Les bruts restent la référence, pas les PNG ni l'extraction.

Une erreur d'une source est conservée dans `report.json` sans effacer les
pièces déjà reçues. `--source-id` permet un nouvel essai limité dans un autre
dossier. Aucun certificat TLS n'a été désactivé, aucune réponse 403 contournée.

Le statut automatique `ARCHIVED` signifie seulement réception + intégrité.
Le champ `claim_status` reste `CURATED_REQUIRES_CONTENT_REVIEW`. La revue
séparée compare son empreinte à celle du brut ; le contrôle de décision
distingue réception du document, correspondance de revue et heure de revue.

## 3. Dossier réel et disponibilités

Archive principale :
`artifacts/fr/research/evidence_16e/issuer-20261006-v1/`.
Les sept réceptions réussies vont de **19:06:35 à 19:07:04 UTC le 6 octobre**,
soit 21:06:35 à 21:07:04 Paris. La revue est horodatée 19:10:52 UTC.

| Source | Empreinte SHA-256 | Modalités effectivement relues |
| --- | --- | --- |
| BNP PDF | `1e1711513bc664081dddd41cc4c0937a93f9bc339e7a256a697ffb5858d67f79` | 3,23 EUR, détachement 24/09, paiement cash annoncé 28/09 |
| Odet PDF | `c517642bffa7b3ecc5f865ec554c29d71b36e07845be4e5924a25e222a16f26e` | 380 EUR, paiement annoncé 29/09 |
| Odet calendrier | `464bb1f14f7257cd21b8b9d8afd31685aeafdefcd88ece85f3941c096ededd64` | Détachement 25/09, record date 28/09, paiement 29/09 |
| Oeneo PDF | `735b28d90bf6240e42b7679ea74e4b87d6f3e86310b8d46a0739a5197e78f8b4` | 0,35 EUR en numéraire adopté en AG, détachement 30/09, paiement annoncé 02/10 |
| SPIE PDF | `37c70916b85515bc861536b650f4249e196bca055cca433b740d827cdd2eb005` | 0,32 EUR en numéraire, détachement 15/09, paiement annoncé 17/09 |
| Trigano PDF | `a257f7c486d85f3d4d2962e9d7a1216de9158c7d9265505aeabafafc86b6bd43` | Deuxième acompte 2,40 EUR, détachement 29/09, paiement à partir du 01/10 |
| AMA identité | `da7e7de2c237d3731fd2c584e75f958bd76983726f8d0f96943147edeb5dcfb3` | ISIN GB00BNKGZC51, devise Euro et nominal GBP distincts |

L'échec Société Générale est tracé dans l'archive principale et dans
`artifacts/fr/research/evidence_16e/gle-retry-20261006-v1/report.json`.
Son communiqué reste consultable par navigateur mais les deux essais de
réception locale ont dépassé le délai autorisé. Il s'agit d'une difficulté
technique, **pas d'une démonstration qu'une source payante est indispensable**.

### Sources complémentaires et nouvelles qualifications

- [Oeneo, communiqué d'AG](https://www.actusnews.com/fr/telechargement/oeneo/2026/07/22/99455-cp-oeneo-cr-ag-2026-vf.pdf) : la pièce refusée par l'outil Web en 16-D a été reçue lors de cet essai local et relue. Le constat ancien est conservé mais ne représente plus l'état actuel.
- [SPIE, communiqué semestriel complet](https://www.spie.com/sites/www.spie.com/files/2026-07/H1%202026%20%20-%20Communiqu%C3%A9%20de%20presse_vDef.pdf) : le PDF complète la page HTML et précise le paiement annoncé du 17 septembre et le numéraire.
- [AMA, informations sur l'action](https://www.amaxperteye.com/share-information/) : confirme la distinction cotation Euro / nominal GBP.
- [TotalEnergies EP Gabon, cotation](https://ep.totalenergies.ga/cotation) : associe l'ISIN Gabon à une présentation de cotation EUR ; ne pas confondre avec l'action TotalEnergies SE.
- [ZCCM, portail IR](https://zccm-ih.financifi.com/share-price-information/) : distingue explicitement les devises des trois places pour le même ISIN. Cette page ne constitue pas une licence de collecte de quotes ; aucun flux de quotes n'a été archivé pour ce travail.

Les annonces historiques trouvées ce soir ne sont **jamais** datées à leur
ancienne date de publication dans `available_at`. Pour l'application, la
preuve nouvelle est connue à réception, et sa revue seulement après revue.
Cela empêche de réécrire le passé pour rendre un backtest artificiellement PIT.

## 4. Contrôles exécutés et séparation des trois horloges

Il faut distinguer :

1. **Temps économique** : séance, détachement, décision du conseil, paiement annoncé.
2. **Temps documentaire** : date imprimée et éventuellement publication prouvée.
3. **Temps de l'application** : heure réelle de réception et de qualification.

Rapports recalculés :

- `artifacts/fr/research/data_readiness_16c/qualification-20261006-16e-v1/report.json` : contrôle au soir, 242/233/0, empreinte des features inchangée ;
- `artifacts/fr/research/daily_feature_adapter_16b/opening-20261006-16e-v1/report.json` : contrôle strict à l'ouverture, 0 feature complète, 0 candidat ;
- `artifacts/fr/research/observed_reference_16d/opening-20261006-16e-v1/report.json` : master connu jusqu'au 4 octobre, reçu le 5 octobre, une séance de retard ;
- `artifacts/fr/research/decision_qualification_16e/opening-20261006-v1/report.json` : dossier combiné, intégrité des pièces et disponibilité avant décision.

Les 233 passages locaux du soir ne contredisent pas les 0 candidats du
matin. La collecte de démarrage a été reçue **après** le matin. L'intégrité
de toutes les archives est contrôlée ; aucune erreur de lecture n'est masquée.
Les réserves du modèle, du Sprint 15 et de continuité ESMA sont inchangées.

## 5. Confirmation à la prochaine ouverture : procédure prête

Ne pas fabriquer un rapport prospectif avant l'heure réelle. Le service
16-E refuse toute ouverture encore future par rapport à l'heure de l'audit.
Il ne lance ni collecte, ni entraînement, ni inférence de modèle.

Après l'ouverture du **7 octobre 2026 à 9 h Paris**, si les collectes normales
ont fourni les données disponibles avant cette ouverture :

```powershell
python -u -m service.fr.decision_qualification_16e --decision-date 2026-10-07 --bootstrap-dir artifacts/fr/research/data_readiness_16c/bootstrap-20261006-v1 --evidence-dir artifacts/fr/research/evidence_16e/issuer-20261006-v1 --output-dir artifacts/fr/research/decision_qualification_16e/opening-20261007-v1
```

Pour une autre séance, changer la date et choisir un nouveau dossier. La
fenêtre de 21 séances est recalculée ; si la barre du 6 octobre ou la couverture
des actions manque avant ouverture, le rapport restera bloqué. La présence du
bootstrap ne remplace pas une séance nouvelle manquante.

Contrôler `daily_assembly`, `reference`, `evidence` séparément. Un master connu
avec une séance de retard peut être décrit par 16-D, **pas admis par le contrôle
strict 16-B**. Une modalité relue ne qualifie pas automatiquement un ajustement.
Même si des pièces deviennent connues avant le 7 octobre, elles ne lèvent pas
les réserves de continuité ou de release du modèle.

## 6. Ce qu'il reste à lever avant le shadow

| Réserve | Travail nécessaire | Peut-on la masquer par configuration ? |
| --- | --- | --- |
| GLE non archivé | Réception valide du communiqué émetteur, empreinte et lecture | Non |
| Intervalle de devise ALAMA/EC/MLZAM | Preuve de validité pour la séance concernée, réception avant décision | Non |
| Dividendes dans les features | Qualifier l'effet sur les barres/formules et éviter double ajustement ; compléter les droits/modalités utiles | Non |
| ACAN/ALGTR/ARTO | Qualifier séparément les événements et les chemins non calculables ; ne pas les considérer résolus par les cinq pièces ci-dessus | Non |
| Dernière séance non couverte | Collecte observée à temps ou protocole explicitement approuvé de référence retardée | Non |
| Continuité ESMA | Résoudre ou accepter explicitement un périmètre/protocole limité, sans inventer des Deltas absents | Non |
| Revue indépendante / modèle / exploitation | Gates 16-A et réserves Sprint 15 | Non |

On a avancé sur la preuve documentaire, pas démontré une amélioration D1/D10.
Les réserves restantes n'ont pas été transformées en hypothèses silencieuses.
Le Sprint 16-E est une **qualification partielle et une procédure livrée**,
pas une clôture de toutes les conditions du shadow.

## 7. Tests

75 tests ciblés passants : contrôle des dates de réception et revue,
interdiction de décision future, intégrité de pièces, échec partiel conservé,
URLs HTTPS explicites, périmètre FR et aucune promotion serving, plus les
régressions 16-A/B/C/D, features et collecteurs FR. Ce résultat ne certifie pas
l'ensemble de la suite du projet ni les preuves encore manquantes.
