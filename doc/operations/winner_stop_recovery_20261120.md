# Réparation des stops Winner refusés après achat partiel — 20 novembre 2026

Autorisation utilisateur : « corriger l'anomalie », après audit des positions
PAPER default FLEX/ASX en perte de plus de 7 % sans stop actif. La sélection
source est `q051-b43c2635d2594ad6b805fefc50b1da05`, profils B/SL5 figés.
Aucun achat nouveau ni modification des seuils/horizons de ces campagnes.

## Diagnostic

Les premiers stops ont été soumis alors que les achats marché étaient encore
partiellement exécutés : ASX 22/32, FLEX 12/13, ZS 3/4 sur default. Alpaca a
refusé ces protections avec HTTP403. Le corps détaillé des anciens refus
n'était pas conservé ; la protection anti-wash-trade est une explication
cohérente avec cette chronologie et la documentation fournisseur, pas un motif
ancien certifié par un corps de réponse absent.

Le runtime avait figé les campagnes en `manual_review`, sans réarmer les stops
une fois les achats terminés. STX, rempli en une fois sur default, avait un stop
accepté et a été clôturé par celui-ci.

Audit initial : `artifacts/operations/default_stop_audit_20261120/broker-and-state.json`
et `diagnosis.json`. Ces observations ne sont pas des états broker temps réel.

## Correction

- Avant une protection opposée à un achat encore ouvert, annuler son reliquat
  exact et attendre la confirmation, puis rapprocher les exécutions survenues
  pendant l'annulation. Les quantités remplies sont conservées et protégées.
- Conserver les opérations anciennes, les identifiants broker et OMS et les
  seuils figés. Une réponse ambiguë ne permet jamais de réémettre un ordre.
- Archiver les champs contrôlés du refus (statut, code, message, ordre lié),
  sans headers, clé API ou corps arbitraire.
- Une reprise après rejet définitif exige la réconciliation par client ID,
  l'absence d'ordre contradictoire et une quantité broker correspondant aux
  lots. Les anciens403 génériques exigent l'autorisation opérateur ; seuls
  les motifs structurés reconnus peuvent être récupérés automatiquement.
- Si un stop manquant a déjà été franchi, sortir uniquement les lots concernés
  par un ordre marché régulier journalisé `STOP_EXIT`. Les lots non franchis
  gardent leurs stops initiaux. La réponse perdue se rapproche par le même
  client ID ; aucun second POST aveugle, aucune vente au-delà de la détention.
- Un422 « stop price must be less than current price » est une preuve broker
  de franchissement lors de l'envoi, même si l'endpoint de position affiche
  encore un cours antérieur. Ce cas ne doit ni abaisser le stop ni rester figé.

Le module `execution_engine/winner_protection_recovery.py` s'exécute sous le
verrou canonique du compte. Le contrôleur existant conserve risque et journaux.
La vérification d'âge du watcher inclut ce module et le lecteur Alpaca.
Le lecteur de dernières cotations utilise désormais `verified_session` par
défaut, avec TLS vérifié et les racines système, sans repli IEX ni contournement
du403 d'abonnement SIP. Les sessions explicitement fournies restent respectées.

## Application aux positions PAPER

Script ponctuel : `scripts/operations/repair_default_protections_20261120.py`,
limité aux trois comptes PAPER et aux campagnes de la sélection source. Les
exécutions et états avant/après se trouvent dans les sous-dossiers `repair-*`
de l'audit. Les stops éventuellement actifs ne sont pas annulés pour redémarrer
un watcher. Les anciens verrous de démarrage sont laissés expirer naturellement.

Résultat après rapprochement des opérations :

| Compte | Réparation |
| --- | --- |
| default | ASX32 et FLEX13 clôturés ; ZS3 clôturés et ZS1 protégé par stop193,09 $. |
| test1 | ASX362 et STX21 clôturés selon leurs seuils déjà franchis. |
| test2 | STX23 clôturés selon leurs seuils déjà franchis. |

Ces ventes sont une réparation tardive : les pertes déjà subies ne sont pas
effacées et un SL n'assure pas un prix exact d'exécution. Aucune performance de
backtest n'est déduite de cette opération. Le reliquat et les prix définitifs
doivent être lus dans le dernier reçu broker, pas dans les vieux bilans12.

## Vérification

Tests : achats partiels et exécutions pendant annulation, reprise explicite,
STOP_EXIT sans doublon après réponse perdue, quantités ambiguës bloquantes,
franchissement entre lecture et POST, lots partiellement concernés, motif
de refus sans secrets, TLS vérifié, protections usuelles et watchers natifs.
Reçu : `artifacts/operations/default_stop_audit_20261120/tests.xml`.

**117 tests réussis** après utilisation d'un dossier temporaire court dans le
workspace. Deux tests SIP avaient d'abord échoué en dépassant la longueur de
chemin Windows dans le répertoire temporaire de l'application ; ils passent
avec ce chemin court, sans modification de leur code métier.

Vérification finale directement chez Alpaca, reçue après réparation :

- Les six ordres de réparation sont `filled` (ASX/FLEX/ZS sur default,
  ASX/STX sur test1, STX sur test2). Aucun doublon de vente ni nouvel achat.
- Default conserve une action ZS, avec ordre stop GTC `new` à193,09 $,
  quantité1. Test1 et test2 ne détiennent plus de position.
- Les quantités broker correspondent aux lots canoniques des campagnes
  sources. Les trois watchers sont `RUNNING`, sans dernière erreur, avec le
  code actuel effectivement chargé.

Preuve : `artifacts/operations/default_stop_audit_20261120/final-verification.json`.
Les redémarrages ont été terminés séquentiellement après un conflit SQL
transitoire ; le verrou de test1 acquis avant le premier heartbeat a expiré
naturellement. Aucun verrou de leader actif n'a été supprimé de force.
