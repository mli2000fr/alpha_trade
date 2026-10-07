# Expérience LONG — sans TP, sortie vingt séances après l'entrée

## 1. Protocole figé le 7 octobre 2026

Convention demandée par l'utilisateur : entrée à J+1, puis sortie à la clôture
`calendar[entry_index + 20]`. L'entrée est jour 0 : il y a 21 barres possibles,
entrée comprise. C'est J+21 depuis le signal, **pas** le label H20 depuis J.
L'échéance est programmée dès l'entrée, sans décision fondée sur la clôture future.

| Variante | TP | Trailing | Stop initial | Échéance |
|---|---|---|---|---|
| `CURRENT_NO_EXPIRY` | Actuel | Actuel | Actuel | Aucune hors borne d'observation |
| `REFERENCE_20_AFTER_ENTRY` | Actuel | Actuel | Actuel | Entrée+20 séances, clôture |
| `NO_TP_FIXED_SL_20_AFTER_ENTRY` | OFF | OFF | Conservé jusqu'à sortie | Entrée+20 séances, clôture |
| `NO_TP_TRAILING_20_AFTER_ENTRY` | OFF | Actuel | Remplacé par le trailing selon contrat actuel | Entrée+20 séances, clôture |

Le témoin sans échéance isole l'effet du passage à vingt séances. Stop initial
2,5 ATR et TP min(3 ATR, 7 %) restent ancrés aux tapes archivées ; aucun stop
n'est élargi. Le stop fixe n'est pas transformé en break-even. Dans les variantes
avec trailing, le stop initial est annulé lors de la transition comme dans le
contrat actuel, pas ajouté comme protection supplémentaire.

**LONG seulement**, sur toutes les entrées techniques éligibles, jamais uniquement
sur les titres dont on sait après coup qu'ils ont fait +50 %. Période 2025–septembre
2026 exploratoire, déjà examinée ; aucun sweep d'horizon/poids/seuil. L'Oracle
prédit toujours l'amplitude, pas la direction.

## 2. Entrées et tailles communes

Sources : `artifacts/research/us_concentrated_replay/tapes-history-20261006-v1`
et `prepare-20261006-v1`, contrat `contract-validation-20261006-v3`.
Les 142 414 entrées LONG techniques sont conservées, avec leurs ancres, classement
et appartenances aux politiques. Les refus d'entrée du premier assemblage ne sont
pas remplacés. Dix premiers Oracle et dix premiers dans l'intersection ATR restent
des contrôles identiques sur cette archive.

**Une unité technique n'est pas un sizing approuvé de portefeuille.** Un lifecycle
plus long mobilisera du capital plus longtemps : le futur portefeuille pourra donc
exécuter des trades différents même avec les mêmes candidats, classement et règles
de risque. Ne pas remettre artificiellement le capital à 4 000 $ chaque matin.

## 3. Réconciliation des gaps et du watcher — recherche uniquement

Script : `scripts/research/us_concentrated_exit_variants.py`.
Le résolveur réutilise `resolve_intrabar_exit`, après traitement chronologique
de l'ouverture pour les positions déjà détenues :

1. Open à travers le stop actif : sortie hypothétique à l'open brut, pas au stop.
2. Open au-delà du TP : prix limite conservateur, sans amélioration favorable
   inventée. Cela précède un retournement ultérieur dans la même barre.
3. Sinon, résolution high/low conservatrice, stop prioritaire en cas d'ambiguïté.
4. Trailing calculé sur le sommet des barres précédentes, pas le sommet encore
   inconnu du jour. Watcher 0R déclenché seulement tant que la position survit,
   avec activation à la séance suivante.
5. Protections avant sortie à échéance ; sortie suivie de l'annulation explicite
   des protections et du watcher restants. Aucune activation après extinction.

**Les fonctions partagées Phase 7/BacktestEngine et les defaults live ne sont pas
modifiés.** Ce résolveur corrige les hypothèses de recherche ; la parité avec le
moteur économique reste à valider. Les anciennes tapes sont conservées intactes.
Le rapport compare date/prix du témoin reconstruit avec l'ancienne tape. Une égalité
date/prix seule ne certifie pas l'intégralité des événements et états d'ordres.

Le résolveur ne reçoit qu'une liste explicite d'ancres d'entrée/protection. Aucun
rendement futur, décile ou ancienne sortie ne dirige la nouvelle résolution.
L'ancienne sortie est lue uniquement après coup pour cet audit de parité.

## 4. Qualité et borne finale

Barre absente, OHLC incohérent, volume nul/manquant, remplissage ou changement
d'identité bloquent le chemin au point rencontré. Une séance inconnue n'est pas
sautée pour trouver une sortie ultérieure favorable. Le candidat bloqué n'est pas
remplacé. Les quatre variantes peuvent rencontrer des réserves différentes car
elles détiennent les titres pendant des durées différentes ; cela ne justifie pas
de sélectionner les seules trajectoires favorables à une variante.

Un saut >=50 % est signalé, pas automatiquement rejeté. Overlay BAND appliqué
localement avec empreinte, sans SQL ; preuve observée ultérieurement, non PIT.
Le calendrier SPY reste un proxy. OHLC cohérents ne certifient ni ajustements et
corporate actions, ni tradabilité, ni lineage Oracle/OOF.

Une position encore ouverte au 30 septembre 2026 reçoit une **hypothèse explicite
de clôture terminale**. Si vingt séances ne sont pas observables, elle est marquée
`HOLDING_WINDOW_CENSORED`. Ce n'est pas un horizon complet ni une liquidation
réelle gratuite. Les frais et contraintes de liquidation ne sont pas valorisés
à cette étape. Le témoin sans échéance reçoit aussi cette hypothèse à la borne.

## 5. Tests et pilote

Neuf nouveaux tests couvrent échéance exacte, stop gappé, TP gappé avant conflit
intraday, TP désactivé, absence de watcher posthume, sommet précédent du trailing,
barre absente, borne censurée et refus du SHORT. **54 tests ciblés passent**,
avec dix avertissements pandas préexistants non bloquants.
Rapport : `artifacts/research/us_concentrated_replay/exit-variants-tests-20261007.xml`.

Pilote : `exit-variants-pilot-20261007-v1`, première séance, 352 entrées communes
par variante. Sans TP/stop fixe : 256 sorties à échéance, 96 au stop. Sans TP/
trailing : 106 à échéance, 246 au trailing. **Ces chiffres ne sont pas des win
rates ni des performances** : seule la mécanique des sorties est testée.

## 6. Run complet et reprise

Run terminé et vérifié le 7 octobre : `artifacts/research/us_concentrated_replay/exit-variants-history-20261007-v1`.
437 séances complètes, dossiers `YYYYMMDD` avec `variant_tapes.parquet` et rapport
de compteurs/empreintes. `protocol.json` fige variantes et empreintes du code et
des entrées. Reprise par journée, refus d'un protocole différent ; chaque shard
source est vérifié avant utilisation, chaque shard achevé avant reprise.

```powershell
Get-Content F:\projets\artifacts\research\us_concentrated_replay\exit-variants-history-20261007-v1\progress.json -Raw | ConvertFrom-Json | Select-Object status,completed_dates,planned_dates
Get-Content F:\projets\artifacts\research\us_concentrated_replay\exit-variants-history-20261007-v1\stderr.log -Tail 10 -Wait
Test-Path F:\projets\artifacts\research\us_concentrated_replay\exit-variants-history-20261007-v1\report.json
```

Commande de reprise, seulement si aucune instance n'est encore active :

```powershell
python -u -m scripts.research.us_concentrated_exit_variants --output artifacts/research/us_concentrated_replay/exit-variants-history-20261007-v1
```

## 7. Gate économique

Statut final prévu : `EXIT_VARIANT_UNIT_TAPES_COMPLETE_NOT_ECONOMIC_REPLAY`.
Aucun PnL/SQL/entraînement, aucun paramètre de production modifié. Après le run,
examiner les changements du témoin, puis raccorder au portefeuille stateful,
coûts et liquidation terminale, avec parité moteur testée. Qualifier les réserves
de données avant comparaison économique.

Mesures économiques prévues : rendement net, drawdown, pertes extrêmes, durée,
exposition et gains rendus depuis le sommet ; distinguer horizons complets et
censurés. Même sizing, classement, candidats, capital, frais et contraintes entre
variantes. Aucun résultat de stratégie n'est encore démontré.

Voir [tapes initiales](us_concentrated_historical_tapes.md) et
[contrat moteur](us_concentrated_contract_qualification.md).

## Incident de checkpoint et reprise du 7 octobre

Le premier processus s'est arrêté sur `PermissionError: WinError 5` pendant
le remplacement de `progress.json`. La lecture simultanée, l'antivirus ou un
autre programme peut provoquer ce verrouillage Windows ; son détenteur précis
n'a pas été identifié. Ce n'est pas une erreur du calcul des sorties.

282 lots achevés, jusqu'au 18 février 2026, ont été contrôlés par SHA256 sans
écart. Le compteur était resté à 281 : le lot suivant était déjà sauvegardé
avant l'échec de la progression. La reprise relit ces lots et ne les recalcule pas.

`atomic_json` utilise désormais un temporaire unique voisin, flush/fsync et
jusqu'à 20 tentatives bornées de remplacement en cas de `PermissionError`.
Le dernier checkpoint n'est jamais supprimé pour contourner le verrou. Un
refus permanent reste bloquant et visible, pas ignoré. Ce correctif ne constitue
pas un verrou multi-processus : ne pas lancer deux instances sur la même sortie.

56 tests ciblés passent, dont verrou temporaire et refus permanent. Le script
de variantes et son protocole sont inchangés ; seule l'utilité d'écriture est
renforcée. La provenance est consignée dans `checkpoint-repair-20261007.json`
du répertoire du run. Les traces du premier échec sont conservées.

**Journal du processus de reprise** :

```powershell
Get-Content F:\projets\artifacts\research\us_concentrated_replay\exit-variants-history-20261007-v1\stderr.retry1.log -Tail 10 -Wait
```

Le chemin de `progress.json` et celui de `report.json` final restent identiques.

## 8. Résultats techniques complets — vérification du 7 octobre 2026

Le statut est `COMPLETED` et le rapport final porte
`EXIT_VARIANT_UNIT_TAPES_COMPLETE_NOT_ECONOMIC_REPLAY`.
Les 437 fichiers parquet de sortie ont été relus et leurs SHA256 contrôlés
sans écart : **569 656 lignes**, soit 142 414 entrées communes × quatre variantes.
Chaque candidat présent possède exactement quatre variantes, sans doublon
candidat/variante dans les lots. Les trajectoires résolues vérifiées n'ont
ni activation effective ni événement daté après leur sortie ; leur dernier
événement annule explicitement protections et watcher restants.

### Pool Oracle TOP20 % : mécanique des sorties LONG

| Variante | TP | Stops, gaps inclus | Échéance entrée+20 | Clôture à la borne | Chemins bloqués |
|---|---:|---:|---:|---:|---:|
| Actuelle, sans échéance | 82 362 | 56 554 | 0 | 3 202 | 296 |
| Référence avec échéance | 79 429 | 53 652 | 6 320 | 2 748 | 265 |
| Sans TP, stop fixe | 0 | 52 027 | 84 790 | 5 061 | 536 |
| Sans TP, trailing | 0 | 95 704 | 42 222 | 4 037 | 451 |

Chaque ligne totalise 142 414. Les sorties TP comprennent les gaps favorables
exécutés au prix limite conservateur. Les stops comprennent les gaps exécutés
à l'open. « Stops » ne signifie pas nécessairement pertes : un trailing peut
sortir en gain. « Échéance » ne signifie pas gain non plus.

Proportion des entrées atteignant la sortie programmée : **4,4 %** avec TP,
**59,5 %** sans TP/stop fixe, **29,6 %** sans TP/trailing. Dénominateur : toutes
les 142 414 hypothèses, chemins bloqués et bornes terminales compris.
Supprimer le TP permet donc mécaniquement de conserver plus longtemps les
positions, mais le trailing en coupe encore une grande partie avant vingt séances.
Cela ne démontre ni une capture profitable des +50 %, ni un meilleur rendement.

### Contrôle des dix premiers Oracle

3 547 entrées communes par variante. Aucun chemin n'est bloqué selon ces seuls
contrôles locaux ; ce n'est pas une certification indépendante des prix.

| Variante | Sorties à échéance | Clôtures à la borne |
|---|---:|---:|
| Actuelle sans échéance | 0 | 56 |
| Référence avec échéance | 159 (4,5 %) | 53 |
| Sans TP, stop fixe | 2 386 (67,3 %) | 143 |
| Sans TP, trailing | 1 349 (38,0 %) | 132 |

Les dix premiers dans l'intersection ATR ne constituent toujours pas une
politique distincte sur ces archives. Les lignes jour/titre restent des
hypothèses unitaires avec expositions qui se chevauchent, pas autant de trades
réalisables par un portefeuille de huit positions.

### Réconciliation du témoin avec les tapes d'origine

- 130 299 dates/prix de sortie identiques ;
- **8 617 dates ou prix changés**, à expliquer et raccorder au moteur ;
- 296 chemins bloqués par la qualification locale ;
- 3 202 cas ouverts dans l'ancienne tape, avec hypothèse terminale ou sortie
  reconstruite explicite.

Ces quatre catégories totalisent 142 414. Le contrôle de chronologie des nouveaux
événements passe, mais les 8 617 changements montrent pourquoi le PnL ne doit
pas être calculé directement en mélangeant ancienne Phase 7 et nouveau résolveur.
Les nouvelles règles de gap doivent avoir des fixtures de parité dans le moteur
économique. Les métadonnées événementielles de recherche ne sont pas des preuves
de fills ou d'OCO réellement reçus d'un courtier.

### Conclusion et prochaine étape

La préparation des variantes est terminée. **Aucun classement par profit n'est
disponible à cette étape**. On ne peut pas encore déclarer le stop fixe supérieur
au trailing, ou les versions sans TP supérieures à la référence.

La suite est le raccordement au portefeuille stateful : parité des exits/gaps,
quantités approuvées, capital occupé, frais aux deux jambes et liquidation finale.
Conserver le même protocole et les mêmes règles d'entrée ; ne pas éliminer les
cas bloqués d'une seule variante pour favoriser son résultat. Les chemins
réservés, ajustements, tradabilité et lineage demeurent à qualifier, et les
horizons tronqués doivent être distingués des horizons complets.

Mise à jour du 7 octobre 2026 : le [raccordement exploratoire au portefeuille](us_concentrated_portfolio_replay.md)
est implémenté et testé. Les quatre variantes TOP10 sont calculées avec capital,
sizing et frais ; le TOP20 % a également terminé ses quatre replays. LBRDK
n'est pas financé par les règles PIT de sizing : aucun prix futur ne sert à
l'exclure. Les chemins réservés restent bloquants si une quantité positive est
approuvée. Aucune activation live ni certification complète.
