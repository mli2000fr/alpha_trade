# Sprint 17-C — Correspondances et préparation du contrat Trading212

## Périmètre figé le 8 octobre 2026

Une seconde lecture DEMO a confirmé EUR et cinq endpoints accessibles ;
l'historique répond toujours HTTP 403. Preuve :
`artifacts/fr/research/trading212_demo_17b/demo-20261008213427001326/report.json`.
L'absence d'historique est `null`, jamais assimilée à zéro ordre historique.

Airbus possède deux cotations EUR dans les métadonnées : `AIRp_EQ` associé
au calendrier Euronext Paris et `AIRd_EQ` associé à Xetra. Pour le pilote Paris,
la première est sélectionnée. Cela ne prouve pas la place où l'ordre sera exécuté.

Le dossier de revue contient 233 ISIN : 164 XPAR, 68 ALXP, 1 XMLI.
Le premier pilote d'adaptateur est volontairement **XPAR seulement** :

- **138** correspondances XPAR + STOCK + EUR + calendrier Euronext Paris ;
- **26** titres XPAR sans correspondance unique selon ces critères ;
- **69** titres ALXP/XMLI hors périmètre initial, sans les renommer XPAR.

Les 171 correspondances uniques du POC précédent concernent tous les MIC du
dossier : ce chiffre n'est donc pas le nombre de titres XPAR du pilote.
Résoudre Airbus porte le nombre de correspondances Paris/EUR tous MIC à 172,
mais ne permet pas d'affirmer que ces 172 titres sont autorisés à l'exécution.

Le manifeste produit sous `artifacts/fr/research/trading212_mapping_17c/`
conserve correspondances, exclusions motivées et hashes des sources originales.
Il est **recherche uniquement**, pas un univers tradable historique et pas une
configuration du routeur. Aucune base, aucun modèle ou batch n'a été modifié.

## Programme et tests

`service/fr/trading212_mapping_17c.py` reconstruit les correspondances depuis les
réponses originales, après vérification SHA-256 des métadonnées et du dossier
FR. Il refuse les ISIN invalides/dupliqués et les collisions de ticker ; les
ambiguïtés, devises différentes, calendriers inconnus et MIC hors pilote sont
exclus. Le code ne contient aucun client réseau ni méthode de soumission.

```powershell
python -m service.fr.trading212_mapping_17c --snapshot-dir artifacts/fr/research/trading212_demo_17b/demo-20261008213427001326
python -m pytest tests/test_fr_trading212_mapping_17c.py tests/test_fr_trading212_demo_17b.py tests/test_fr_broker_contract_17a.py --no-cov -q
```

42 tests ciblés passent. Ils ne certifient pas le comportement d'ordres externes.

## Adaptateur : travaux restant à implémenter

Le [contrat officiel](https://docs.trading212.com/api) sépare DEMO et réel,
limite les ordres à la devise principale et utilise une quantité négative
pour vendre. Le futur port doit distinguer une vente de position d'un short.

La [description OpenAPI](https://docs.trading212.com/_bundle/api.json?download=)
documente des soumissions non idempotentes et une annulation qui ne garantit
pas l'absence de fill. Aucun endpoint OCO explicite n'a été trouvé dans cette
description consultée : ne pas transformer deux ordres indépendants en OCO
supposément atomique.

| Fonction du moteur | Contrat de sécurité à livrer |
| --- | --- |
| Soumission | DEMO seulement au début, compte EUR, mapping figé, plafond notionnel, identifiant local unique |
| Timeout de soumission | État UNKNOWN, pas de retry aveugle ; réconcilier avant toute nouvelle demande |
| Statuts / fills | Conserver quantité demandée, cumul rempli et restant ; gérer fills partiels et statuts inconnus |
| Annulation | Demande acceptée distincte d'annulation confirmée ; continuer la réconciliation |
| Stop / TP / OCO | Capacités natives à qualifier ; aucun OCO synthétique en production sans preuve de gestion des courses |
| Remplacement de stop | Pas d'atomicité supposée entre annulation et remplacement |
| Compte / positions | Devise vérifiée, solde et quantité disponibles, identités non ambiguës |
| Marché ouvert / prix | Horaires et fraîcheur des prix à qualifier ; calendrier de cotation non suffisant pour prouver l'exécution |
| Arrêt d'urgence | Interdire nouvelles entrées ; suivre ordres et positions existants jusqu'à état réconcilié |

L'implémentation actuelle n'est **pas** un `ExecutionBrokerPort` : aucun raccord
au `BrokerRouter` n'a été fait. Les réserves de données du Sprint 16 restent
ouvertes et la preuve du MIC réel d'exécution n'est pas acquise.

## Action utilisateur, puis prochaine tranche

**Mise à jour du 9 octobre :** la permission History – Orders a été vérifiée
avec succès (HTTP 200). Le manifeste a été régénéré, sans changer le périmètre
de 138 titres. Le refus historique est levé ; voir
[17-D et ses réserves](sprint_17d_reconciliation_simulee.md).
La procédure suivante concernait le blocage de la première lecture.

Vérifier **History – Orders** sur la clé créée en mode entraînement. Ne pas
activer **Orders – Execute** pour résoudre ce refus de lecture. Si une nouvelle
clé est nécessaire, mettre à jour les variables d'environnement sans l'envoyer
dans le chat. Refaire ensuite le POC en lecture seule.

Pendant ce blocage, les tests synthétiques de réconciliation/protection peuvent
être préparés. Un ordre DEMO, même minuscule, nécessitera un GO explicite séparé.
Le Sprint 17 reste partiellement livré ; aucun GO PAPER/LIVE.
