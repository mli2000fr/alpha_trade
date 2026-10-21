# Campagnes LONG : confirmation 5 minutes et renforcement gagnant

État au 21 octobre 2026 : **raccordements watcher / revalidation native /
moteur intraday livrés et testés hors ligne**. Ce n'est pas une validation
opérationnelle du courtier. `winner_pyramiding.enabled` reste **false**.
Aucun ordre, appel fournisseur, entraînement ou écriture SQL de production
n'a été effectué pour cette livraison. La prochaine qualification opérationnelle
se fait en PAPER, avec les droits SIP temps réel et un watcher à jour.

## Parcours réellement raccordé

1. Étape 11 : approbation d'une cible et d'un budget explicite de risque.
2. Étape 12 : admission dans `execution_winner_campaigns`, sous verrou du
   compte ; **pas d'achat immédiat**. Quantité et budget approuvés ne sont
   pas multipliés par le levier ni par le multiplicateur legacy d'exposition.
   Le dry-run ne persiste aucun plan. Un watcher local sain, de même compte
   et mode, non limité à un ancien run et redémarré depuis cette livraison
   est nécessaire avant admission.
3. Le watcher scanne aussi les plans sans parent déjà exécuté. Deux clôtures
   régulières de cinq minutes terminées au-dessus du plus haut RAW de la
   séance précédente, précédées d'une clôture au-dessous/égale, confirment
   une entrée. Pas de bougie en formation ni de mélange daily ajusté / raw.
4. Juste avant CHAQUE achat/ajout : `NativeWinnerRisk` recapture le broker,
   les positions, les ordres en cours, le buying power, les données daily
   qualifiées de la séance précédente, le SIP temps réel et son spread.
   Il appelle `RiskCheckerImpl` / `ConstraintChecker`, vérifie corrélations,
   concentration, opérations connues en attente, régime natif, volatilité
   cible et budget résiduel. Un contexte absent/périmé ou un SIP refusé bloque
   la nouvelle entrée, sans fallback IEX.
5. Achat entier LIMIT IOC, journal OMS canonique et réservation durable avant
   HTTP. Après réponse perdue : réconciliation par identifiant stable, jamais
   nouveau POST aveugle. Un 404 après ambiguïté ne prouve pas l'absence d'achat.
6. Protection des quantités réellement remplies : stop fixe ou OCO TP/SL.
   Trailing par amendement sans desserrage. Les fills partiels cumulés ne
   créent pas de doublons. Absence de timestamp de fill : stop de secours et
   revue explicite, pas d'heure inventée.
7. Ajout facultatif : une seule tentative, uniquement gagnante, sans vente
   antérieure d'un lot, dans le budget résiduel et la cible entière initiale.
8. H20 : vingt séances de détention, **séance du premier fill incluse**, puis
   vente à l'ouverture de la 21e. Un ajout ne décale jamais cette échéance.

Les cibles SHORT conservent leur route séparée. Ce mécanisme n'ajoute ni
renforcement SHORT ni conversion automatique d'un SHORT en LONG.

## État durable et reprise du risque

`alpha_trade.execution_winner_campaigns` contient un identifiant déterministe
compte / mode / approbation risque / titre, un verrou optimiste `version`,
une clé active unique compte-mode-titre et `state_json` LONGTEXT. Celui-ci
conserve la cible, les paramètres figés, les quantités, le budget, les bornes de
validité, les vrais fills, l'échéance, les lots et l'outbox des opérations.
La réactivation terminale ou la libération de lots encore détenus est refusée.
Le type cash/margin et le plafond de levier de l'admission sont également figés :
les valeurs génériques du watcher ne les remplacent pas. La configuration actuelle
peut réduire ce plafond, jamais l'augmenter ; un titre non marginable reste limité
au buying power cash qualifié du broker.

`execution_winner_account_guards` conserve le pic observé, l'épisode B4,
l'allocation, les compteurs et l'empreinte du risque, **par compte et PAPER/LIVE**.
Le redémarrage ne remet pas le pic à l'equity courante. La première initialisation
exige des observations réelles des snapshots broker de ce compte/mode ; ce
n'est pas une NAV historique continue certifiée. Une politique de risque
modifiée nécessite requalification explicite, pas réinitialisation silencieuse.
Les contrôles cinq minutes ne sont pas comptés comme des journées favorables B4.

Ces tables ne sont pas créées à l'import ni par le replay. La création de
schéma intervient à l'admission/initialisation explicite du mécanisme.
Les essais utilisent SQLite et des brokers simulés.

## Configuration

Section racine `winner_pyramiding` de [config.yaml](../../config.yaml).
Les fractions ne sont pas des pourcentages entiers :

| Paramètre | Valeur préparée / effet |
| --- | --- |
| `enabled` | false ; interdit les nouvelles entrées, ne retire pas les stops existants |
| `initial_position_fraction` | 0.5 ou 1.0 ; demi-position ou complète |
| `reinforcement_enabled` | false ; un seul ajout si activé |
| `reinforcement_trigger_pct` | 0.05 ; confirmation du gain depuis les fills initiaux |
| `confirmation_bars` | 2 clôtures régulières contiguës de cinq minutes |
| `stop_loss_pct` | 0.05 |
| `take_profit_pct` | null ; pas de TP en prix |
| `trailing_stop_pct` | 0.15 ; null pour le désactiver |
| `horizon_sessions` | 20 ; 10/15 possibles, null pour aucune échéance |
| `entry_valid_sessions` | 20 ; attente maximale après signal, distincte de la détention |
| `max_quote_age_seconds`, `max_bar_delay_seconds` | 60 ; fraîcheur requise |
| `cost_reserve_bps_per_leg` | 25 ; réserve de sizing, pas frais réellement facturés |

Ces paramètres remplacent les protections ordinaires/LLM **uniquement pour les
nouvelles campagnes**. L'ancien watcher ne reprend pas leurs stops selon un
autre profil. Les contraintes globales restent supérieures. Le levier est une
capacité maximale, pas une obligation de l'utiliser ; les minima d'equity,
caps individuels/sectoriels et limites de risque peuvent maintenir l'exposition
bien en dessous de deux fois le capital. Aucun paramètre ici n'est promu comme
optimum économique.

## Lancer soi-même le backtest intraday

Le point d'entrée explicite est maintenant :

```powershell
python -u -m backtesting.winner_campaign_replay --oracle-batch-id ID_MODELE_PARCOURS --start-date 2025-01-01 --end-date 2025-12-31 --top-n 10 --initial-equity 4000 --max-leverage 2 --research-assumptions --output-dir artifacts/backtests/winner/ESSAI-NEUF
```

Remplacer l'ID et choisir un dossier inexistant. Le fichier d'univers par défaut
est `config/univers_batch/univers_filtred_tradable.txt` ; surcharge via
`--symbol-source universe-file:CHEMIN`. `--max-leverage 1` réduit le plafond.
Le plafond 2 ne relève jamais une limite de production inférieure.
`--account-type cash` applique le cash réglé et le règlement T+1.
Le financement annuel est explicite, défaut 6,5 %, convention native /252 séances ;
surcharge `--margin-interest-annual`.

Le CLI active la politique uniquement dans sa configuration locale de replay,
pas dans le YAML. Il lit les prédictions Oracle **parcours H20 déjà présentes**,
leur lineage et les poids/protocoles archivés. Il vérifie disponibilité du modèle
strictement antérieure au signal, hash du modèle/profil et classement score
décroissant, ex aequo par symbole. Aucun réentraînement/prédiction/LLM/téléchargement.
Une journée sans suffisamment de scores qualifiés provoque un refus explicite.

La lecture de `alpha_trade` est une transaction READ ONLY / REPEATABLE READ.
Prix de remplissage et niveaux de cassure : exclusivement SIP RAW régulier
5m existant dans `stock_bars_intraday`, `is_filled=0`. Daily ajusté utilisé
séparément pour corrélations, volatilité et ADV, jamais comme niveau raw d'entrée.
Le capital est partagé entre titres, pas dupliqué par ligne. Les frais canoniques
sont débités aux entrées ET sorties, intérêts de marge inclus. Même coordinateur
que le watcher ; revalidation native des quantités/caps/breaker à chaque achat.

Sorties : `report.json`, `annual-summary.csv`, `trades.csv`, `events.csv`,
`equity-daily.csv`, `equity-5m.csv`, `risk-5m.csv`, protocole et reçus/hashes.
`progress.json` affiche séances faites/total et estimation restante.
Le rapport donne capital final, DD cinq minutes, gagnants/perdants, gains/pertes
moyens, durées, capital moyen/max engagé, frais et positions encore ouvertes.
Le capital final inclut leur valorisation ; aucune liquidation finale fictive.
Les statistiques de trades portent sur les lots fermés ; un ajout peut faire un
deuxième lot. Les années d'un même run sont continues, pas trois comptes réinitialisés.

### Limites explicites du replay

`--research-assumptions` est indispensable : `full_live_parity=false`.
Le mode bougies suppose un prix disponible à l'open suivant la confirmation,
des coûts spread/slippage canoniques et une capacité de remplissage ; il ne
possède pas les bid/ask, rangs de file ou fills historiques. Contact SL/TP
dans la même bougie : **SL prioritaire** ; gap stop : prix d'open, pas SL garanti.
L'heure d'un contact intrabar est bornée à la fin de bougie, pas inventée.
Les métadonnées secteur/univers actuelles ne sont pas PIT et l'historique daily
peut avoir été révisé. Il n'y a pas de tape complète du régime macro ni
d'affirmation de reproduction de toutes les branches de PortfolioBuilder.

Trou d'un candidat : exclusion explicite et statut INCOMPLETE_COVERAGE ;
trou pendant une détention : arrêt FAILED, jamais forward-fill de prix.
Dividendes cash : droit au titre détenu avant l'ex-date, créance puis paiement
si devise USD, montant et date de paiement qualifiés. Action sur titres de
type split/fusion pendant une détention : arrêt, pas de faux PnL en prix raw.
L'inventaire des opérations connues ne prouve pas une couverture exhaustive.
Facteur activé sans tape, market-neutral/inter-jambes, commissions tiered ou
interdiction globale de sortie le jour même ne sont pas assimilés à des cas
supportés : les configurations non qualifiées sont refusées.
Un échec conserve son dossier ; aucune reprise silencieuse ni écrasement du run.

Le seuil de DD est un contrôle des nouvelles entrées, **pas une garantie** de
perte maximale ni une liquidation forcée de tous les lots à ce seuil.

## Disponibilité du watcher et courses de sortie

MOO préparée seulement 10 à 2 minutes avant l'open officiel, après annulation
confirmée des protections et réception des fills intervenus pendant l'annulation.
Sinon : sortie marché tardive en séance, étiquetée comme telle. Une réponse
incertaine de vente reste bloquée pour réconciliation urgente : jamais un second
ordre aveugle. Un rejet/annulation confirmé réarme un stop de sécurité sur les
quantités restantes où le broker le confirme, puis exige une revue opérateur.

PC éteint : aucune entrée/renforcement ni mise à jour locale du trailing.
Les stops déjà acceptés chez le broker restent actifs. Avec une absence
07:30–20:00 Paris, **l'ouverture de la 21e séance n'est pas garantie** :
une infrastructure en ligne à ce moment reste nécessaire. Le replay suppose
cette disponibilité ; il ne prétend pas reproduire une machine éteinte.

La qualification PAPER (droits SIP, IOC/OCO/amendements réels, déconnexions et
courses de fills) reste à réaliser avant promotion LIVE. Les tests automatisés
hors ligne ne peuvent pas prouver les droits de l'abonnement ni le comportement
réel d'un courtier. Voir les suites `tests/test_winner_*.py` et le rapport
de non-régression associé à cette livraison. Dernière passe : **322 tests réussis**,
rapport `artifacts/tmp/winner-delivery-final-20261021-v3.xml`, incluant configuration,
ancien exécuteur/watcher, garde d'entrée, broker, compte/risque et parité des labels.
