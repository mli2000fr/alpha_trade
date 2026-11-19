# Q051 PAPER : réparation OPG, réconciliation et validité DAY

État vérifié le 19 novembre 2026 vers 21:52 Europe/Paris. Sélection concernée :
`q051-6af2c1804fbb43e6acbd49ddf76b4a00`, signal du 18 novembre ; modèle
`model-factory-20261118172104-2f6a31`, B témoin sans application de l'anti-SL.

## Origine et décision

OPG était un choix d'implémentation de l'application pour traduire « entrée à
l'ouverture suivante ». L'utilisateur n'avait pas demandé de limiter l'ordre
à la seule enchère d'ouverture. Chez Alpaca, OPG ne reste pas exécutable pendant
le reste de la séance. Un statut final `expired` peut néanmoins comporter un
remplissage partiel. La raison détaillée des non-remplissages du simulateur
PAPER n'est pas fournie dans les réponses reçues.

Les nouvelles sélections du parcours quotidien B utilisent désormais les
réglages explicites suivants dans `config.yaml` :

```yaml
us_pipeline:
  b_anti_sl_reference:
    entry_time_in_force: day
    exit_time_in_force: day
```

L'achat `market DAY` peut être préparé après clôture du signal pour J+1 et
reste admissible durant la séance régulière J+1. Aucune exécution en horaires
étendus n'est activée. Ni achat après la clôture de J+1, ni report automatique
sur un jour ultérieur. La vente temporelle reste préparée pour open11 après
dix séances de détention, entrée incluse ; DAY évite de la limiter à la seule
enchère. Une exécution au prix exact d'ouverture n'est pas garantie : le
backtest de référence qui utilise ce prix ne devient pas une reproduction
exacte des remplissages PAPER par ce changement.

Les deux durées sont enregistrées dans la sélection scellée, puis dans les
plans. Les anciennes sélections/plans sans ces champs restent OPG par défaut.
Les anciens achats expirés du 19 novembre n'ont pas été transformés en nouveaux
achats DAY. La page Pipeline affiche maintenant les durées actives.

## Bugs corrigés

- Le watcher générique resérialisait un ordre Q051 OPG avec sa configuration
  générique, incompatible avec l'exception Q051. Le pont broker utilise
  désormais le profil figé du plan, après validation stricte compte/PAPER.
- Les quantités réellement remplies sont réconciliées même si le solde de
  l'achat expire. Le stop et l'échéance partent du remplissage réel, sans
  doubler les écritures ni resoumettre l'achat.
- Une entrée terminale sans remplissage devient EXPIRED/CANCELED et libère le
  plan actif. Les onze achats du jour expirés sans remplissage sont EXPIRED.
- Le refus définitif d'un stop est signalé en revue manuelle ; une réponse
  ambiguë demeure réservée, sans répétition aveugle de l'appel broker.
- Le heartbeat devient ERROR en cas d'échec réel du cycle de protection
  Winner, même si la boucle Python tourne encore.
- Sous Windows, la détection du service distingue le lanceur Python du
  véritable worker. Le redémarrage attend la fin du worker et vérifie son
  identité, sous verrou du compte ; aucun arrêt global des processus.

## Réparation des positions réellement détenues

Les actions ci-dessous concernent exclusivement les comptes Alpaca PAPER.
Elles ont utilisé les verrous de compte, les identifiants stables d'ordres et
la réconciliation native ; aucun nouveau signal ni achat n'a été lancé.

| Compte | Titre | Constat et traitement vérifiés chez le broker |
| --- | --- | --- |
| test1 | IONS | 101 détenus, prix moyen 27,33 USD ; stop GTC 101 à 25,96 USD, statut `new` |
| test1 | ASX | 8 détenus, prix moyen 31,82 USD ; stop GTC 8 à 30,23 USD, statut `new` |
| test2 | GLW | SL5 déjà dépassé ; vente DAY de 112, intégralement exécutée à 106,453839 USD |
| default | SHOP | Ancienne position atteinte par le même défaut ; SL5 déjà dépassé ; vente DAY de 4, intégralement exécutée à 132,0225 USD |

Les comptes default et test2 sont sans position broker après ces ventes.
IONS et ASX ont une échéance figée au **4 décembre 2026 à 14:30 UTC**, soit
**15:30 Europe/Paris**, avec les jours fériés officiels pris en compte. Leur
seule durée de validité de sortie a été amendée explicitement de OPG à DAY,
après vérification des deux stops. L'entrée historique OPG, les quantités,
les stops, le profil, les dates et les références de risque restent inchangés.
Le stop peut vendre avant l'échéance H10 ; la date n'impose pas de revendre
des titres déjà sortis.

Le retard de protection ne permet pas de présenter les pertes GLW/SHOP comme
plafonnées à 5 %. Les seuils étaient déjà franchis au moment de la réparation.

## Déploiement et validation

Les trois services ont été redémarrés avec le code corrigé. Dernier contrôle :

| Compte | PID worker vérifié | Heartbeat | Échecs Winner du dernier cycle observé |
| --- | ---: | --- | ---: |
| default | 40908 | RUNNING | 0 |
| test1 | 4704 | RUNNING | 0 |
| test2 | 50468 | RUNNING | 0 |

Des avertissements subsistent sur d'anciens plans hors Q051, bloqués par des
conditions SIP/politique d'entrée. Ils ne sont pas assimilés à une protection
effective et leurs contrôles n'ont pas été désactivés. Les stops IONS/ASX ont
été vérifiés directement chez Alpaca, indépendamment des heartbeats.

**315 cas de test distincts passent**, sans erreur, échec ou test ignoré dans
les trois rapports finaux réunis. Ils couvrent les profils PAPER, les ordres
DAY/OPG, les remplissages partiels expirés, le stop, l'échéance H10, les refus
et réponses ambiguës, les doublons, les heartbeats et le redémarrage Windows.
Les tests utilisent des brokers simulés et n'envoient aucun ordre réel.

Reçus sous `artifacts/operations/q051_watcher_fix/20261119T202238Z/` :

- `final-before.json`, `final-after.json` : positions, ordres et état des services ;
- `test1-result.json` : remise en place des deux stops ;
- `glw-stop-recovery-result.json`, `shop-recovery-result.json` : ventes correctives ;
- `exit-validity-ASX-before.json`, `exit-validity-IONS-before.json`,
  `exit-validity-amendment.json` : amendement audité des deux sorties ;
- `deployment-final2.json` et `deployment-final2/` : dernier déploiement et logs ;
- `tests-final.xml`, `tests-protection.xml`, `tests-day-exit.xml` : tests finaux.

Les anciens reçus de sélection, de risque et d'exécution sont conservés. Aucun
verrou ambigu n'a été supprimé pour forcer une nouvelle soumission.

Documentation Alpaca :
https://alpaca.markets/sdks/python/api_reference/trading/enums.html#alpaca.trading.enums.TimeInForce
