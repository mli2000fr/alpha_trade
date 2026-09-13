# E8-A3 — Connecteur ThetaData et smoke d’éligibilité

## Statut

Le connecteur et le smoke sont implémentés. La piste est désormais classée
`ABANDON_COÛT` : l'historique options nécessaire exige un abonnement payant que
le projet a décidé de ne pas prendre. Le premier run avait terminé avec :

```text
BLOCKED_THETA_TERMINAL_NOT_RUNNING
```

Artefact :

```text
artifacts/research/thetadata_options/thetadata-options-smoke-20260910185522/report.json
```

Ce verdict technique ne rejetait pas ThetaData. Il signifie que le serveur REST local
Theta Terminal ne répond pas sur `127.0.0.1:25503` et que la variable
`THETADATA_API_KEY` n’est pas présente dans l’environnement du processus.

## Architecture

Le connecteur `modelFactory.thetadata_options` est strictement research-only :

- il accepte uniquement `http://localhost`, `127.0.0.1` ou `::1` ;
- aucun identifiant n’est transmis par le client Alpha-Trade ;
- l’authentification est déléguée à Theta Terminal ;
- les réponses sont demandées en JSON ;
- 429 et erreurs serveur sont reprises avec backoff ;
- les erreurs d’autorisation, terminal absent et qualité sont distinguées ;
- chaque réponse est journalisée avec paramètres, taille, durée, empreinte SHA-256
  et payload brut dans un JSONL gzip ;
- aucune table de production n’est écrite.

Endpoints utilisés :

```text
GET /v3/option/list/contracts/quote
GET /v3/option/history/quote
```

Le premier fournit les contrats réellement cotés à la date demandée. Le second
fournit les NBBO OPRA historiques à une minute. Les deux droits `call` et `put`
sont demandés ensemble pour le même strike.

Documentation officielle :

- https://docs.thetadata.us/operations/option_list_contracts.html
- https://docs.thetadata.us/operations/option_history_quote.html
- https://docs.thetadata.us/Articles/Getting-Started/Getting-Started.html

## Échantillon préfixé

Le run sélectionne cinq dates réparties sur toute la période et deux événements
Oracle TOP20 par date : le plus faible et le plus fort dollar-volume disponible.
Cela teste volontairement un titre moins liquide et un titre liquide.

| Signal | Faible liquidité | Forte liquidité |
|---|---|---|
| 2022-03-07 | ADMA | AAL |
| 2022-10-05 | ARLO | APA |
| 2023-05-08 | ARLO | ZS |
| 2023-12-05 | NMRK | DKNG |
| 2024-07-09 | MAC | TTD |

Les dix calendriers J+1/H3/H5/H10/H20 sont complets dans `stock_bars_daily`.

## Contrat d’exécution du smoke

Pour chaque événement :

1. lister à J+1 les contrats ayant reçu une quote ;
2. limiter le DTE à 55 jours ;
3. conserver les paires call/put de même expiration et strike entre 35 et 55 DTE ;
4. choisir la paire la plus ATM, puis la plus proche de 45 DTE ;
5. prendre la première paire NBBO synchrone entre 09:35 et 10:00 à J+1 ;
6. prendre la dernière paire synchrone entre 15:30 et 15:55 à H3/H5/H10/H20 ;
7. rejeter bid nul, ask nul, marché croisé ou écart call/put supérieur à 60 secondes ;
8. vérifier que chaque timestamp appartient à la date demandée.

## Gates

Le pilote de 60 dates n’est ouvert que si :

- 10 événements ont été évalués ;
- Theta Terminal répond et l’abonnement autorise les endpoints ;
- au moins 80 % ont une paire historique call/put ;
- au moins 80 % portent sur des contrats aujourd’hui expirés ;
- au moins 80 % possèdent entrée plus quatre sorties complètes ;
- tous les timestamps appartiennent aux dates demandées.

## Accès possible, mais non retenu

ThetaData propose désormais une bibliothèque Python officielle (`thetadata`
1.0.9 ou supérieure pour l'authentification par clé) qui se connecte directement
en HTTPS/gRPC et ne nécessite ni Theta Terminal ni Java. Elle couvre bien les
deux opérations du POC : `option_list_contracts()` et
`option_history_quote()`. Le projet utilise Python 3.14 et satisfait donc le
minimum Python 3.12.

Cette simplification technique ne rend pas les données historiques gratuites :
les endpoints requis restent réservés au niveau Options Value ou supérieur.
En conséquence, aucun paquet n'est installé, aucun rerun n'est programmé et la
suite de cette section est conservée uniquement comme procédure historique.

## Préparation historique de Theta Terminal

ThetaData indique que Java 21 ou supérieur est nécessaire. Télécharger
`ThetaTerminalv3.jar` uniquement depuis la documentation officielle, générer la
clé dans le portail ThetaData puis exposer `THETADATA_API_KEY` au processus qui
lance le terminal. Éviter de passer la clé sur la ligne de commande, car elle
serait visible dans la liste des processus.

Exemple dans une console PowerShell dédiée :

```powershell
$env:THETADATA_API_KEY = Read-Host "Clé ThetaData"
java -jar C:\chemin\ThetaTerminalv3.jar
```

Attendre que le serveur REST v3 écoute sur le port 25503. Ne pas lancer plusieurs
terminaux avec le même compte.

## Relance

Depuis `F:\projets` :

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.thetadata_options_smoke --log-level INFO
```

Le rerun recrée le même protocole dans un nouvel artefact. Il ne remplace pas le
premier rapport bloqué, ce qui conserve la traçabilité.

## Fichiers produits

```text
selected_events.parquet   calendrier causal des dix événements
event_results.parquet     résultats normalisés, si le terminal répond
raw_responses.jsonl.gz    réponses brutes et métadonnées d’appels
report.json               gates et verdict
```

Si le verdict devient `GO_E8_A2_PILOT_60_DATES`, la prochaine étape autorisée
sera la collecte de 60 dates réparties dans le temps. Aucun backtest d’options
ou changement de serving n’est autorisé avant ce gate.
