# Contrôle strict des données des nouvelles entrées US

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## But et périmètre

Le mode partiel de l'étude Oracle/ATR n'autorise jamais une entrée sur données
manquantes. `service/market/new_entry_data_guard.py` contrôle les nouvelles
entrées LONG **et** SHORT du flux US PAPER/LIVE, sans consulter les rendements
futurs, déciles réalisés ou la table d'étude. Il ne désactive pas les autres
contrôles : univers tradable, sélection GPT/ML, borrow pour SHORT, régime,
capital, sizing, protections et frais restent applicables.

## Contrat des cours et de l'historique

- Le signal doit être daté de la dernière séance NYSE clôturée et disponible,
  selon la clôture réelle plus le délai configurable. Aucun calendrier simplifié
  lundi/vendredi, aucune supposition de clôture constante Paris/New York.
- La veille reste le signal utilisable la nuit et avant la prochaine clôture :
  par exemple à 8 h Paris le 9 octobre, les données du 8 octobre sont valables.
  La nouvelle séance ne doit pas servir avant sa clôture/disponibilité.
- Pour chaque symbole, **toutes** les dernières séances requises doivent être
  présentes, sans doublons. Défaut : 61 séances, couvrant 60 rendements de
  corrélation et ATR/ADV 20. Le risque peut imposer davantage avec ses fenêtres.
- Chaque barre doit être réelle (`is_filled=0`), OHLC positif fini et cohérent,
  volume positif, source renseignée, ajustement `split`. Aucune interpolation,
  aucun report du dernier cours, aucune exclusion silencieuse d'un jour manquant.
- Les dates d'ingestion/mise à jour doivent être connues et antérieures à
  l'instant du contrôle. Historique de true range entièrement nul refusé.
- Les objets utilisés par le sizing doivent avoir cours, ATR et ADV positifs
  finis ; dates du prix et de l'ATR exactement égales à celle du signal.

## Raccordement au risque et à l'exécution

1. Dans `risk_management/cli.py`, avant le sizing des candidats ML/GPT PAPER/LIVE,
   les titres non qualifiés sont exclus des **nouvelles entrées**, sans remplacement
   dans la shortlist. Les objets cours/ATR/ADV sont contrôlés après chargement.
2. Les motifs sont journalisés sous `NEW_ENTRY_DATA_REJECTED`, remontés dans la
   progression et dans `new_entry_data_rejections` du résumé métier du risque.
3. Dans `execution_engine/executor.py`, chaque nouvel intent d'entrée est
   contrôlé à nouveau avant réservation du capital et soumission broker.
   La date du prix de la cible doit elle aussi correspondre au signal.
   Le refus produit un événement `PRECHECK_FAILED` et le compteur
   `new_entry_data_rejected`. Aucun ordre d'entrée correspondant n'est envoyé.
4. Une erreur de base, calendrier ou configuration refuse les entrées concernées
   (fail-closed), plutôt que laisser passer ou exploiter une donnée par défaut.

Ces contrôles **ne vendent pas** les positions détenues et ne modifient ni les
SL/TP/trailing existants ni les ordres de sortie/protection du watcher. Ils
n'empêchent pas les autres motifs de sortie légitimes déjà implémentés.
L'exécution dry-run et les backtests historiques ne consultent pas cette horloge
opérationnelle ; ils gardent leurs propres contrats de simulation/PIT.

## Paramètres

```yaml
new_entry_data_guard:
  min_sessions: 61  # minimum 21, augmenté si le risque exige plus
  publication_delay_minutes: 15
```

Ce délai ne prouve pas à lui seul que le fournisseur a fini la publication :
la présence et validité des barres restent exigées. Les historiques IEX ne sont
pas assimilés à du volume consolidé SIP ; ce contrôle ne transforme pas une
source indicative ou partielle en donnée officielle consolidée.

## Limites à connaître

Le contrôle porte sur les cours/historique/ATR/ADV utilisés pour l'entrée.
Il ne certifie pas toutes les features du modèle, la justesse des identités,
la totalité des corporate actions, ni l'absence de toute erreur fournisseur.
`ingested_at`/`last_updated` vérifient l'existence à l'heure courante : ils ne
reconstituent pas les anciennes versions d'une barre corrigée pour un backtest.
Les anciens garde-fous macro/ML/quotes/borrow conservent leur propre contrat.

Après déploiement, les nouveaux processus risque/exécution chargent ce code.
Un processus déjà en mémoire doit être redémarré pour charger une modification ;
aucun service existant ni ordre n'a été lancé ou interrompu pendant cette tâche.

## Vérification du 10 octobre 2026

274 tests ciblés passent sur l'étude, le schéma, le calendrier, le risque,
l'exécution, les protections et l'IHM. Le test du refus d'entrée vérifie
explicitement qu'aucun ordre broker n'est soumis.

Smoke opérationnel **en lecture seule**, signal du 9 octobre : AAPL et MSFT
sont refusés parce que les barres locales des 8 et 9 octobre sont absentes.
BK manque de nombreuses séances récentes et est également refusé.
Ce sont des refus attendus tant que les données requises ne sont pas alimentées,
pas une autorisation de remplacer les prix ni de vendre les positions détenues.
