# Quotes SIP et republication de l’univers US — 17 octobre 2026

## Correction livrée

Le contrôle des spreads ne doit pas confondre le bid/ask d’une seule place IEX
avec un bid/ask consolidé. Le seuil du preset n’a pas été relevé.

```yaml
market_data:
  quotes_historical_feed: sip
```

Cette option pilote les quotes **historiques** de l’étape 4 et de
`latest_quotes_sync`. Elle est indépendante de `quotes_provider_live` et du
fournisseur des barres. La CLI de collecte accepte désormais uniquement
`--feed sip`. Les anciens audits comparatifs IEX/SIP restent reproductibles,
mais ne constituent pas une collecte opérationnelle ni une qualification IEX.
Aucun fallback SIP → IEX. Une erreur de droits/réseau doit rester visible.

Le batch autonome reste désactivé car intégré à `us_pipeline`. Ses horaires,
le fichier d’univers et les seuils de prix/liquidité/résultats restent inchangés.

## Qualification et reprise

- Borne SIP : dernière **séance effective** demandée clôturée depuis au moins
  quinze minutes ; un week-end en borne finale ne crée pas une séance fictive.
- Le contrôle annuel ne demande plus les quotes jusqu’à la fin d’une année
  future ; il reste borné à la période réellement demandée.
- Les fenêtres courtes n’effectuent plus un appel annuel redondant par titre.
- Chaque quote doit avoir des prix et tailles finis et positifs, ask ≥ bid,
  un spread cohérent, et un timestamp dans les quinze dernières minutes de sa
  propre séance régulière NYSE (prise en compte des clôtures anticipées).
- Les quotes invalides sont archivées et journalisées mais **ne remplacent pas**
  une ligne valide. Une ancienne ligne IEX peut rester physiquement en base,
  sans être considérée qualifiée par le publieur.
- La reprise ne considère plus « jour présent » comme suffisant : fournisseur,
  flux, qualité, timestamp, empreinte et archive doivent être valides. Les
  anciennes lignes IEX ou sans provenance sont donc rechargées progressivement
  sur la fenêtre demandée ; aucune suppression globale de l’historique.

Les archives sont sous `artifacts/quotes/alpaca/<feed>/<date>/<sha256>.json`.
Elles contiennent la quote originale (timestamp haute précision, places,
conditions, tailles), les paramètres sans secrets et la date UTC de collecte.
Leur empreinte, fournisseur, flux, symbole, date, prix, tailles et timestamp sont
vérifiés contre la ligne SQL avant réutilisation. La création exclusive évite
d’écraser une version précédente.

Colonnes ajoutées à `stock_quote_snapshots` : `provider`, `feed`,
`quality_status`, `collected_at`, `source_timestamp`, `raw_payload_sha256`,
`raw_payload_path`. `source_timestamp` est un `DATETIME(6)` ; le timestamp brut
original reste également dans l’archive. La précision de l’ancienne colonne
`quote_timestamp` n’a pas été modifiée sur les neuf millions de lignes.

Un ancien producteur `latest` sans provenance ne peut pas hériter de la
qualification SIP d’une ligne qu’il écrase : ses champs de qualification sont
remis à NULL. Une migration absente déclenche une erreur explicite plutôt que
de perdre silencieusement la provenance à l’upsert.

**Sauvegardes** : conserver les archives `artifacts/quotes` avec la base. Une
archive manquante ou altérée interdit la qualification et entraîne une nouvelle
collecte à la reprise. Sauvegarder seulement SQL ne suffit pas à conserver ces
preuves.

## Republication

Le publieur relit le dernier **snapshot Screener complet** de grade `degraded`,
pour la même date, le même preset et le marché US, même s’il n’est plus canonique.
Il ne repart plus du précédent univers `full`, qui contenait déjà les exclusions
de spread et les aurait conservées après correction.

Il exige des quotes SIP qualifiées, dans la fenêtre d’ancienneté autorisée
(J−5 jours calendaires/J actuellement), et conserve les autres contrôles.
La publication a une empreinte incluant la politique et les entrées quotes.
Un nouveau run devient canonique ; les lignes de l’ancienne publication sont
conservées. Aucun run LLM, risque ou ordre existant n’est réécrit.

Une quote de clôture n’est pas une autorisation d’entrée future : les contrôles
de données/quotes disponibles au moment de l’exécution restent nécessaires.
Ce correctif n’ajoute pas un abonnement SIP temps réel et ne modifie pas les
protections d’exécution. La politique projet ajoutée ensuite bloque explicitement
les nouvelles entrées sans SIP temps réel, sans bloquer les sorties : voir la
[migration IEX vers SIP](migration_iex_vers_sip.md).

## Migration appliquée de façon contrôlée

La base était au marqueur Alembic `0088_us_fact_instrument_constraints`, avec
plusieurs tables ultérieures créées via d’autres chemins. Il ne fallait ni
exécuter tout le reliquat de migrations ni modifier le schéma sans suivi.

La première proposition d’application directe sans changement du marqueur a
été **refusée par le contrôle de sécurité, et n’a pas été exécutée**. La solution
appliquée est une vraie migration Alembic ciblée :

- révision `0106_quote_provenance`, branche additive partant de `0088` ;
- un seul `ALTER ... ADD COLUMN ..., ALGORITHM=INSTANT` obligatoire, sans
  fallback vers une copie/reconstruction ; attente de verrou limitée à 5 s ;
- marqueur Alembic passé normalement à `0106_quote_provenance` ;
- révision de jonction `0107_merge_quote_provenance` sans DDL, pour garder un
  seul head dans le graphe du dépôt. **La jonction et les autres migrations
  0089–0105 n’ont pas été appliquées à cette occasion.** Ne pas lancer un upgrade
  global pour ce correctif ; qualifier les migrations restantes séparément.

Contrôle préalable : MySQL 8.0.46/InnoDB. Dossier d’exploitation :
`artifacts/operations/quote_sip_remediation/20261017-v1/`.
`schema_migration.json` contient le résultat et le schéma ; `before_quotes.json`
préserve les **1 649 lignes existantes datées du 16 octobre**, avant remplacement.
L’audit précédent comptait 1 650 quotes sélectionnées car il incluait ACVA datée
du 15 octobre.

## Exécution de remédiation

Test réel limité à cinq titres : quatre quotes SIP persistées, un titre sans
quote renvoyée. Puis reprise du **16 octobre uniquement**, univers de 1 790
titres `config/univers_batch/univers_filtred_tradable.txt` :

```powershell
python -u -m dataIntegrityEngine.sync_latest_quotes `
  --from-date 2026-10-16 --to-date 2026-10-16 `
  --symbol-source universe-file:config/univers_batch/univers_filtred_tradable.txt `
  --feed sip
```

Journal : `artifacts/operations/quote_sip_remediation/20261017-v1/sync.log`.
Le premier passage historique J−7/J peut prendre davantage de temps après ce
correctif, car les journées précédentes sans provenance SIP seront elles aussi
requalifiées à leur prochaine demande.

Les compteurs finaux et la republication sont à lire dans le bilan de remédiation
de ce dossier. Le proxy historique nommé `quote_iex_vs_consolidated_*` est une
mesure mid de quote versus close daily, **pas une comparaison directe IEX/SIP**.
Les nouveaux résumés portent `quotes_feed` et l’IHM adapte le libellé SIP ; les
noms des anciennes clés sont conservés pour compatibilité.

### Bilan final appliqué

Rattrapage terminé le 17 octobre à **23:02:36 Paris** (durée 728,81 s).
Run CLI `sync-latest-quotes-20261017205027-ff84c7` : 1 790 titres examinés,
1 644 quotes supplémentaires persistées, quatre déjà qualifiées par le smoke
test et ignorées à la reprise, **1 648 quotes SIP qualifiées au total**.
Une réponse croisée APD (bid 299,40 / ask 299,39 $) a été archivée et rejetée ;
141 titres n’ont pas renvoyé de quote. Aucun échec technique terminal.

Les 1 648 quotes persistées ont été relues : aucune erreur de qualité ni de
correspondance avec les archives. La publication a ensuite été effectuée depuis
le Screener `universe-c1452ee4a9144590accb6a56e8d3681e`.

Nouvelle publication canonique :
`universe-2daaab47b37b41ae9d8676e832a0b98d`, date **2026-10-16**, preset
`capital_2001_5000`, 1 790 lignes et 1 790 symboles uniques.

| Premier motif | Avant | Après |
| --- | ---: | ---: |
| Autorisés | 297 | **1 493** |
| Spread excessif | 1 233 | **2** |
| Quote non qualifiée/absente | 41 | 43 |
| Blackout résultats | 16 | 49 |
| Prix trop bas | 69 | 69 |
| Liquidité insuffisante | 94 | 94 |
| Historique insuffisant | 40 | 40 |

Les deux spreads encore trop larges sont BST (63,1845 bps) et FRHC
(67,6028 bps), au-dessus du seuil **inchangé de 60 bps**. Les 33 blackouts
supplémentaires étaient auparavant masqués par le motif de spread, testé avant.

1 197 titres deviennent autorisés, 296 restent autorisés, 296 restent exclus.
**ACVA est le seul titre auparavant autorisé désormais exclu** : son ancienne
quote du 15 octobre était IEX et aucune quote SIP qualifiée du 16 octobre ne
la remplace. Il n’a pas été forcé à passer. Les nouvelles 43 absences regroupent
aussi les titres sans quote qualifiée, pas une preuve d’impossibilité d’exécuter
sur tout le marché.

FMC reste exclu pour `close_below_minimum` (close 5,66 $), malgré son spread SIP
désormais beaucoup plus faible. Aucun filtre source n’a été contourné.

Les lignes historiques de l’ancienne publication ont une empreinte identique
avant/après republication ; seul son statut canonique est normalement remplacé
par le nouveau run. Aucun ordre, run risque ou réponse LLM modifié. Les autres
dates historiques n’ont pas fait l’objet d’un rattrapage global dans cette
intervention.

Pièces finales : `report.json` et `after_universe.json` dans le dossier de
remédiation. La clé `collection_summary` est le résumé brut du processus démarré
avant l’ajout du nouveau libellé IHM ; ses anciennes clés `quote_iex_*` sont donc
à lire avec la réserve ci-dessus. Le bilan de remédiation indique explicitement
`quotes_feed: sip`.

## Vérification

Tests : quotes invalides/hors séance/périmées, flux sans fallback, archive altérée
ou non correspondante, reprise avec changement de flux, schéma legacy, sélection
depuis le Screener d’origine, conservation des anciens snapshots et graphe
Alembic ciblé. Les tests n’émettent ni ordre ni notification externe.

Résultat : **292 tests ciblés réussis**. Un test secteur non lié
(`test_update_sector_main_emits_structured_summary`) a été écarté de cette passe
car il réclame une connexion réelle malgré les identifiants volontairement
désactivés pendant les tests. Il n’a pas été présenté comme validé.

Sources de cadrage : [Alpaca — données historiques SIP](https://docs.alpaca.markets/us/docs/market-data-faq),
[MySQL — DDL instantané](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl.html).
