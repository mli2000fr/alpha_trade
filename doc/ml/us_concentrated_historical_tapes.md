# Tapes historiques des sélections Oracle concentrées

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## État au 7 octobre 2026

L'assembleur est implémenté ; le pilote du 2 janvier 2025 est terminé.
**Le traitement des 437 séances est terminé et ses fichiers vérifiés.**
Il ne calcule aucun rendement de stratégie, PnL, Sharpe ou comparaison économique.
Les modèles, tables SQL, paramètres de production et batchs existants ne sont
pas modifiés. Il écrit uniquement des artefacts de recherche locaux.

Script : `scripts/research/us_concentrated_historical_tapes.py`.
Tests : `tests/test_us_concentrated_historical_tapes.py`.
45 tests ciblés passent, dont huit nouveaux tests et les 37 tests du contrat.
Dix avertissements pandas de concaténation non bloquants restent visibles dans
le rapport XML `artifacts/research/us_concentrated_replay/tapes-tests-20261006.xml`.

## 1. Deux niveaux de tape à ne pas confondre

Cette étape construit des **tapes pré-portefeuille, indépendantes, d'une unité**
par candidat/côté. Une unité permet de vérifier le calendrier, le prix simulé,
les protections et les événements. `approved_shares=1` est uniquement un
adaptateur technique à l'API des phases ; ce n'est **pas** une approbation par
PortfolioBuilder. Chaque ligne est marquée `ONE_UNIT_NOT_PORTFOLIO_APPROVED`.

La tape économique finale devra encore faire passer les décisions par le
portefeuille stateful : capital disponible, positions existantes, huit positions
maximum, sizing, contraintes sectorielles, risque et réserves de tradabilité.
Le capital ne doit pas être remis artificiellement à 4 000 $ chaque matin.
Les candidats du même titre peuvent se chevaucher ; leur nombre ne représente
donc jamais un nombre de trades exécutables simultanément. Le rapport final
compte ces chevauchements par côté, avec une convention inclusive au jour de
sortie : leur résolution nécessitera l'ordre des événements du portefeuille.

LONG et SHORT sont deux **hypothèses de côté forcé**, pas des prédictions
directionnelles. Le score Oracle reste une estimation d'amplitude. Aucun
`proba_long`/`proba_short` artificiel n'est présenté comme une sortie de modèle.
La disponibilité historique et les coûts d'emprunt SHORT ne sont pas certifiés.

## 2. Entrées archivées et provenance

- Source figée : `artifacts/research/us_concentrated_replay/prepare-20261006-v1`.
- 156 835 lignes jour/titre du pool Oracle TOP20 %, 818 titres, 437 séances.
- 408 884 barres, avec préchauffage 2024 et SPY pour le calendrier observé.
- Période étudiée : 2025–30 septembre 2026 ; déjà examinée, donc exploratoire.
- Contrat : `artifacts/research/us_concentrated_replay/contract-validation-20261006-v3`.
- Correction BAND : overlay local d'une barre du 18 juin 2026, volume zéro
  remplacé par 1 997 781, sans modification SQL. Preuve fournisseur observée
  le 6 octobre, **pas une preuve historiquement disponible en juin**.

Les empreintes SHA256 des archives, des sources moteur de l'attestation,
du contrat et de l'overlay sont vérifiées avant le lancement. Le manifeste
empreinte aussi l'assembleur et sa configuration. La reprise refuse une
configuration ou un code différent dans le même répertoire de sortie.
Elle vérifie les empreintes de chaque shard déjà achevé.

Le calendrier est celui des barres SPY locales positives et non remplies :
c'est un proxy, pas une certification indépendante du calendrier de bourse.
Les secteurs historiques ne sont pas inventés ; l'adaptateur porte
`UNQUALIFIED_PIT_SECTOR`. Ce champ ne permet pas de certifier la limite de 50 %.

## 3. Sélection et absence de fuite par les labels

Une liste explicite de colonnes conserve seulement date, symbole, score
Oracle, fold d'origine et appartenance aux trois politiques. Les rendements
futurs, déciles réalisés, qualités des endpoints et dates de labels sont exclus
de l'entrée de l'assembleur. Le tri est score décroissant, puis symbole croissant.

Les dix premiers Oracle représentent **dix titres, pas 10 % de l'univers**.
Leur appartenance à l'intersection Oracle/ATR est identique sur les 437 séances.
Les trois politiques sont archivées dans `selection_memberships.parquet` et
raccordées aux tapes ; une même trajectoire technique n'est pas recalculée
trois fois. Ce contrôle identique n'est pas une confirmation supplémentaire.

Aucun candidat n'est remplacé parce que sa trajectoire future est mauvaise,
incomplète ou suspecte. Les motifs de refus d'entrée sont séparés des réserves
rétrospectives sur le chemin réellement parcouru.

## 4. Assemblage technique

```text
Sélection Oracle archivée à J, côté de recherche forcé
   → close/ATR à J, vérifications d'entrée
   → séance suivante, refus si gap absolu > 3 %
   → Phase 3 : fill simulé au prix d'ouverture, quantité technique 1
   → Phase 4 : stop 2,5 ATR, TP min(3 ATR, 7 %), protections/OCO
   → Phase 5 : watcher 0R, transition effective à la séance suivante
   → Phase 7 : résolution conservatrice du TP/stop/trailing
   → vérification et archivage, sans valorisation du portefeuille
```

L'ATR en dollars est recalculé par `BacktestEngine._compute_atr` : moyenne
glissante des true ranges sur 20 séances. Bien que cette fonction accepte un
préchauffage partiel, l'assembleur exige 20 observations OHLC dans la fenêtre.
La qualité complète du préchauffage et des ajustements reste une réserve de
données ; vingt observations ne suffisent pas à prouver leur exactitude.

Le time-stop est OFF, aucune sortie H20 n'est ajoutée. Le chemin est examiné
jusqu'à la sortie du lifecycle ou jusqu'au dernier jour observé. Une position
encore ouverte est signalée, **pas liquidée gratuitement**. La liquidation
terminale prévue au protocole doit être raccordée explicitement à l'étape
portefeuille, avec ses frais. Le dispositif actuel ne certifie pas cette sortie.

Les fills et événements de Phase 3 sont synthétiques : ils ne certifient ni la
liquidité, ni le spread historique, ni des horaires/fills de courtier réels.
Les contrôles de parité portent sur les prix d'ouverture quotidiens à 0,005 $
près, quantités, protections orientées, dates et doublons, pas sur une exécution
intraday prouvée.

## 5. Fichiers et reprise

Run complet : `artifacts/research/us_concentrated_replay/tapes-history-20261006-v1`.
Chaque répertoire `YYYYMMDD-buy` / `YYYYMMDD-sell` contient :

| Fichier | Contenu |
|---|---|
| `entry_audit.parquet` | Tous les candidats, côtés et motifs de refus d'entrée |
| `signals.parquet` | Fills unitaires, protections, watcher, sorties, appartenance aux politiques, réserves |
| `orders.parquet` | État du lifecycle des ordres/protections après Phase 7 |
| `events.parquet` | Événements broker-like transmis par les phases |
| `report.json` | Compteurs et empreintes du shard terminé |

`candidate_id` est stable (date-symbole-côté), contrairement aux UUID internes
des ordres synthétiques. Les fichiers persistés, et non leurs UUID régénérés,
font foi lors de la reprise. Un shard interrompu est régénéré ; un shard achevé
et intègre est relu. La sauvegarde est par jour/côté, sans transaction SQL.

`manifest.json` contient le contexte figé ; `progress.json` est mis à jour
après chaque journée complète LONG/SHORT ; `report.json` global apparaît à la
fin réussie. En cas d'erreur capturée, la progression passe à `FAILED` et
conserve le message. Un arrêt brutal du processus peut laisser `RUNNING` :
vérifier aussi le processus et le journal, pas seulement le statut du fichier.

Commande de lancement/reprise, **ne pas lancer une seconde instance simultanée** :

```powershell
python -u -W ignore::FutureWarning -m scripts.research.us_concentrated_historical_tapes --output artifacts/research/us_concentrated_replay/tapes-history-20261006-v1
```

Suivi :

```powershell
Get-Content artifacts/research/us_concentrated_replay/tapes-history-20261006-v1/progress.json -Raw | ConvertFrom-Json | Select-Object status,completed_dates,planned_dates
Get-Content artifacts/research/us_concentrated_replay/tapes-history-20261006-v1/stderr.log -Tail 10
```

## 6. Pilote et réserves nouvelles

Pilote retenu : `artifacts/research/us_concentrated_replay/tapes-pilot-20261006-v2`.
Sur le 2 janvier 2025 : 360 candidats par côté, 352 tapes par côté ; huit
refus de gap par côté. Les compteurs portent donc sur 720 hypothèses
candidat/côté, pas 720 transactions de portefeuille.

- **71 chemins** : ouverture au-delà du stop de sortie. Phase 7 reçoit high/low
  mais pas les opens ; vérifier son prix de stop face au moteur et au protocole
  de gap. Ne pas considérer automatiquement ce prix comme exécutable.
- **75 chemins** : gap favorable au TP. Une exécution au prix limite peut être
  une hypothèse conservatrice valide ; ce drapeau est une revue de convention,
  pas une preuve de bug ou une autorisation de prendre l'open plus favorable.
- **9 chemins** : watcher planifié effectif après une sortie déjà réalisée.
  Le traitement séquentiel des phases doit être réconcilié avec l'annulation
  des protections ; ne pas certifier une transition après extinction de position.

Ces catégories peuvent se recouvrir. Les tapes conservent les cas signalés.
Sur le traitement complet, s'ajoutent les contrôles de barres manquantes,
volume nul, remplissage, identité changeante, saut de clôture >= 50 % et
absence de sortie terminale. Un saut réel comme MP n'est pas automatiquement
une erreur de prix. Ces flags ne sont pas des règles d'entrée PIT.

## 7. Gate avant comparaison économique

Le statut final de ce traitement, même réussi, est
`PRE_PORTFOLIO_TAPES_ASSEMBLED_NOT_ECONOMICALLY_CERTIFIED`, jamais
`READY_FOR_ECONOMIC_REPLAY`. Il reste à :

1. lire le rapport complet et arbitrer les réserves de prix/chronologie ;
2. assembler les quantités et décisions du portefeuille stateful réel,
   sans recyclage fictif de capital ni duplication de positions ;
3. qualifier les scores/OOF, tradabilité, secteurs et opérations sur titres
   historiquement disponibles ;
4. raccorder liquidation terminale et coûts, puis emprunt pour SHORT ;
5. vérifier la parité sur les trades effectivement retenus.

Aucune comparaison économique ne doit être lancée à partir des unités
techniques en prétendant utiliser le portefeuille de 4 000 $.

Voir aussi [contrat et qualification](us_concentrated_contract_qualification.md)
et [protocole de recherche](us_concentrated_replay_protocol.md).

## 8. Résultat complet vérifié le 7 octobre 2026

`progress.json` est `COMPLETED` ; le rapport global confirme 437 séances,
874 shards et la période complète. Les SHA256 des **3 496 fichiers** de shards
ont été recalculés et comparés avec leurs empreintes archivées : aucun écart.
Les identifiants candidat sont uniques dans chaque shard et les quantités
persistées valent exactement une unité. Ce contrôle d'intégrité ne certifie
pas pour autant la vérité historique des prix ou les contraintes de portefeuille.

Sur **156 835 candidats par côté**, 142 414 tapes par côté sont produites,
soit **284 828 tapes techniques LONG/SHORT** au total. Les 28 842 hypothèses
non assemblées se répartissent ainsi :

| Motif | Hypothèses candidat/côté |
|---|---:|
| Gap absolu d'entrée supérieur à 3 % | 27 918 |
| Barre de décision invalide | 116 |
| Protection LONG non positive / garde symétrique de l'adaptateur | 96 |
| Open suivant manquant | 8 |
| Aucune séance suivante dans la période | 704 |

Le dernier motif concerne la borne d'observation, pas une erreur du fournisseur.
La garde nommée `NONPOSITIVE_LONG_PROTECTION` est appliquée aux deux côtés
dans cet adaptateur : ce libellé ne constitue pas une qualification autonome
de l'éligibilité SHORT. Toute décision économique doit repasser par les règles
directionnelles et le sizing réels.

### Réserves, séparées par politique et côté

| Contrôle | TOP20 % LONG | TOP20 % SHORT | Dix premiers LONG | Dix premiers SHORT |
|---|---:|---:|---:|---:|
| Tapes assemblées | 142 414 | 142 414 | 3 547 | 3 547 |
| Au moins un drapeau | 30 743 | 28 769 | 1 020 | 853 |
| Open au-delà du stop de sortie | 8 653 | 11 491 | 148 | 188 |
| Gap favorable au TP, convention limite conservatrice | 12 599 | 9 320 | 335 | 221 |
| Watcher effectif prévu après la sortie | 6 050 | 5 080 | 481 | 392 |
| Encore ouvert à la borne finale | 3 289 | 2 747 | 56 | 52 |
| Volume nul ou manquant sur le chemin | 296 | 238 | 0 | 0 |
| Barre manquante sur le chemin | 87 | 70 | 0 | 0 |
| Barre remplie sur le chemin | 2 | 1 | 0 | 0 |
| Saut de clôture >= 50 %, à examiner | 48 | 61 | 5 | 2 |

Les drapeaux peuvent se recouvrir ; ne pas sommer les lignes pour compter
des tapes distinctes. Une ouverture favorable au-delà d'un TP peut légitimement
rester exécutée au prix limite conservateur. Une transition watcher enregistrée
après la sortie doit être arbitrée en examinant les événements/annulations,
pas assimilée sans examen à une position encore vivante.

Les dix premiers Oracle et les dix premiers dans l'intersection ATR restent
identiques, y compris pour les compteurs de tapes et réserves. Aucun bénéfice
économique additionnel d'ATR n'est donc démontré par cette comparaison identique.

Le compteur de chevauchements sur un même titre vaut **132 738 LONG** et
**132 525 SHORT** pour le pool TOP20 %. Il confirme qu'additionner ces tapes
indépendantes pour former un portefeuille produirait une simulation invalide.
Il ne s'agit pas de doublons dans les fichiers, mais de signaux répétés dont
les intervalles d'exposition hypothétiques se recouvrent.

### Ordre de la suite

1. Réconcilier les prix de stop en gap entre Phase 7 et le simulateur ; fixer
   explicitement la convention conservatrice des gaps favorables au TP.
2. Réconcilier le watcher et l'annulation des protections lorsqu'une sortie
   précède la transition prévue ; ajouter des fixtures historiques minimales.
3. Construire les décisions et quantités de portefeuille stateful, puis la
   liquidation terminale explicite et ses coûts.
4. Réexaminer les réserves des chemins réellement retenus, ainsi que la
   tradabilité/lineage et l'emprunt SHORT, avant la comparaison économique.

**Aucun PnL calculé à la clôture de cette étape.** L'assemblage pré-portefeuille
est terminé ; la certification économique ne l'est pas. Les données et modèles
de production n'ont pas été modifiés lors de cette vérification.
