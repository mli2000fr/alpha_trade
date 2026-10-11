# Remédiation des collectes FR et audit SQL — 9 octobre 2026

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Résultat et périmètre

**Suite livrée le 9 octobre :** la
[publication quotidienne des barres en staging SQL](publication_quotidienne_staging_sql.md)
est désormais raccordée ; import réel et répétition idempotente validés. Les
constats ci-dessous décrivent l'audit initial, avant cet import. Les autres
familles restent en fichiers et les gates canoniques/LIVE ne sont pas levés.

Audit effectué sur **294 codes fournisseur actifs du référentiel S6C figé**,
pour cinq séances : 2, 5, 6, 7 et 8 octobre 2026. Le dénominateur de couverture
est 1 470 couples titre/séance. Ce référentiel n'est pas l'univers tradable
historique, ni le référentiel quotidien actualisé.

Deux défauts corrigés, trois barres récupérées et quatre enregistrements DILA
réintégrés dans les fichiers de recherche. **La publication quotidienne SQL
n'est pas encore raccordée.** Aucun GO shadow/PAPER/LIVE, ordre, modèle,
canonicalisation ou tâche planifiée modifié.

## Défauts corrigés

### Reprise des barres incomplètes

Une réponse partielle était marquée `COMPLETED`. Avec `resume`, un hash valide
pouvait suffire à la sauter malgré des séances absentes. Désormais :

- `COMPLETED_WITH_GAPS`, liste des dates manquantes et `coverage_complete=false` ;
- seule une fenêtre explicitement complète peut être ignorée par `resume` ;
- les anciens checkpoints sans preuve de complétude sont revérifiés ;
- les anciennes barres non retournées sont conservées, mais signalées comme
  **non reconfirmées**, pas présentées comme preuves de couverture actuelle ;
- un rattrapage peut cibler un sous-ensemble du référentiel vérifié, sans ajouter
  de symbole hors univers, modifier le référentiel ou contourner le verrou.

Les compteurs gardent leurs unités : reçus = réponses de symboles, persistés =
barres nouvelles/modifiées, inchangés = barres identiques. Une réponse vide peut
donc être reçue tout en étant en échec de couverture.

### Dates sentinelles DILA

Quatre lignes avaient `uin_dat_mar=8887-12-31…`, avec une transmission AMF réelle
datée d'octobre 2026. `public_day` prenait le maximum et interprétait cette
sentinelle comme une date réelle très future. Les années sentinelles 8887/8888
sont maintenant exclues du calcul, sans modifier les données brutes.

Les dates explicites valides restantes peuvent qualifier une transmission ;
**elles ne prouvent toujours pas une disponibilité Web intraday**. Une ligne
avec seulement une sentinelle ou une date sans timezone reste non qualifiée.
Le collecteur expose `date_sentinel_count` et conserve son avertissement de
portée. Les autres dates futures continuent à être rejetées par le contrôle de
fenêtre : aucune permissivité générale n'a été ajoutée.

La relance DILA de la fenêtre 1–8 octobre aboutit à SUCCESS : 7 versions nouvelles,
dont les quatre anciennes réserves effectivement retrouvées dans `latest` ;
447 enregistrements versionnés au total, zéro échec et zéro alerte. Les trois
autres versions nouvelles ne sont pas assimilées aux quatre lignes réparées.
Une deuxième relance persiste **zéro** version supplémentaire.
Les anciens rapports et quarantaines restent conservés comme preuves datées.
Les rapports historiques de recherche utilisant l'ancien calcul n'ont pas été
réécrits ni leurs modèles réentraînés.

## Rattrapage des prix et réserves

| Code | Résultat | Décision |
| --- | --- | --- |
| ALBOU.PA | Barre du 8 octobre récupérée | Fichier versionné actualisé |
| MLCHE.PA | Barre du 8 octobre récupérée | Même traitement |
| MLNMA.PA | Barre du 8 octobre récupérée | Même traitement |
| ARTO.PA | 5 et 6 octobre absents de la réponse récente | Anciennes versions conservées, non reconfirmées |
| LHYFE.PA | Réponse encore vide | Réserve fournisseur/identité ouverte |
| PERR.PA | Réponse encore vide | Même réserve |

Le premier rattrapage ciblé persiste **3 barres**, 19 identiques, deux échecs et
une alerte ARTO. La répétition persiste **0 barre**, 22 identiques ; elle conserve
les deux réponses vides et l'alerte, sans fabriquer de donnée.

Couverture des fichiers avant rattrapage : **1 457/1 470 = 99,12 %**.
Après : **1 460/1 470 = 99,32 %** de présence conservée. En retirant les deux
anciennes barres ARTO non reconfirmées : **1 458/1 470 = 99,18 %**.
Il ne faut ni masquer ces réserves parce que la couverture dépasse 95 %, ni
présenter ces barres fournisseur comme prix indépendamment qualifiés.

Les épisodes ESMA archivés montrent pour LHYFE et PERR une clôture du segment
XPAR et une ouverture ALXP en septembre. Le statut fournisseur actif S6C figé
ne garantit donc pas la continuité du code `.PA` sur ce changement de segment.
Une recherche EODHD par ISIN a retrouvé uniquement des lignes Allemagne/UK,
pas de remplaçant Paris. **Aucune substitution de place ni changement de ticker
automatique effectué.** Cela motive une vérification fournisseur par ISIN, sans
conclure que les sociétés sont radiées de toutes les places ou suspendues.

## Constat réel en base

Connexion vérifiée sur `alpha_trade_fr`, transaction explicitement en lecture
seule. Aucun INSERT, UPDATE, DELETE ni migration exécuté.

| Table | Lignes observées | Portée |
| --- | ---: | --- |
| `fr_provider_bars_staging` | 2 101 100 | Historique du 1/1/2016 au 1/10/2026 |
| `fr_provider_actions_staging` | 4 940 | Staging historique |
| `fr_raw_payloads` | 4 656 | Archives historiques référencées |
| `stock_bars_daily` | 0 | Canonique non publié |
| `fr_provider_bars_daily` | 0 | Non alimenté par ces collectes |
| `fr_corporate_actions` | 0 | Canonique non publié |
| `instruments` | 0 | Identités de recherche restées en fichiers |
| `market_sessions` | 0 | Calendrier de recherche resté en fichiers |

Sur les cinq séances auditées, le staging SQL contient **0/1 470** couples
attendus. Ce n'est pas une perte des fichiers : les collecteurs 15-B/C/E sont
explicitement en mode fichiers, sans publication SQL. AMF/DILA/référentiel et
calendrier suivent aussi ce contrat de recherche ; leur succès ne démontre pas
une insertion dans une table canonique.

Le descriptif `fr_daily_bars_sync` de `batch_fr.yaml` a été corrigé pour ne plus
suggérer une publication automatique déjà livrée. Ne pas remplir directement
`stock_bars_daily` pour obtenir une couverture verte : la publication staging
versionnée et la canonicalisation stricte sont des travaux différents.

## Audit reproductible et tests

```powershell
python -m service.fr.collection_coverage_remediation --start 2026-10-02 --end 2026-10-08 --output-dir artifacts/fr/research/collection_remediation/nouvel-audit
```

Le répertoire de sortie doit être nouveau. `--recheck-provider` ajoute six appels
EODHD ciblés, avec la clé d'environnement existante, sans impression de token,
sans modification des collecteurs ni SQL. Les observations nouvelles portent
leur disponibilité réelle : aucune disponibilité historique reconstruite.

- Audit initial et six réponses : `artifacts/fr/research/collection_remediation/audit-20261009-v1/`.
- Audit final de filiation fichiers et SQL : `…/audit-20261009-v3/report.json`.
- Répétitions : `…/audit-20261009-v3/bars-repeat.json` et `dila-repeat.json`.
- Tests finaux : **86 réussis, zéro échec/erreur/ignoré**, rapport
  `artifacts/fr/research/collection_remediation/tests-20261009-v4.xml`.

L'audit vérifie les dates, qualité OHLCV, timezone, existence et hash du brut,
ainsi que la présence effective de chaque barre dans son payload référencé.
La présence SQL distingue les versions par `raw_payload_id` ; plusieurs versions
ne sont pas automatiquement des doublons métier. Sur cette semaine sans SQL,
aucune version supplémentaire n'est constatée ; la répétition fichiers réelle
est validée, **pas une idempotence d'un futur importeur SQL**.

## Suite bornée

1. Qualifier le code/segment EODHD Paris des deux ISIN, via fournisseur ou preuve
   publique autorisée ; ne pas substituer Francfort/Londres.
2. Arbitrer les anciennes barres ARTO contre les nouvelles absences, sans les
   admettre à l'exécution tant que cette contradiction subsiste.
3. Concevoir puis qualifier la publication **staging SQL quotidienne**, versionnée,
   reprenable, avec disponibilité réelle et tests d'idempotence. Cela ne doit
   pas promouvoir automatiquement de données vers les tables canoniques.
4. Continuer la qualification PIT/identités/événements du sous-ensemble avant
   de rouvrir le shadow. Les protections courtier et le LIVE restent bloqués.
