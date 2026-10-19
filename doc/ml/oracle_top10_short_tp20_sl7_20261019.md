# Oracle parcours TOP10 — SHORT forcé, TP20/SL7

Expérience autorisée le 19 octobre 2026. La demande répétait « 2025 » ;
interprétation annoncée : **2024, 2025 et 2026**. Recherche locale uniquement,
sans changement de modèle servi, de batch, de filtre LLM ni de protections live.

## Protocole figé

| Année | Modèle annuel de l'archive | Fin des nouvelles décisions | Fin de valorisation |
|---|---|---|---|
| 2024 | `model-factory-20261014113215-437ed1` | 31/12/2024 | 03/02/2025, queue d'expiration des dernières entrées |
| 2025 | `model-factory-20261014113226-102eca` | 31/12/2025 | 02/02/2026, queue d'expiration des dernières entrées |
| 2026 | `model-factory-20261014113232-bc35a7` | 30/09/2026 | 30/09/2026 ; positions restantes valorisées, pas clôturées fictivement |

Modèles **Oracle parcours H20 d'amplitude**, CatBoost dans ces trois campagnes,
univers archivé de 1 790 titres. Pas le modèle du 16 octobre appliqué en bloc
à des années antérieures, ni une tête SHORT dédiée, ni un tri sur les baisses
réalisées. Les scores/folds/empreintes et dates d'admissibilité des modèles sont
ceux des archives annuelles déjà qualifiées. Inférence initiale rétrospective,
pas une preuve que ces fichiers entraînés en octobre existaient historiquement.

- Les **dix premiers scores Oracle de chaque date**, ordre original score
  décroissant/symbole, tous orientés SHORT par convention de stratégie.
- 252 séances/2 520 candidats en 2024 ; 250/2 500 en 2025 ; 187/1 870 en 2026.
- Aucun filtre GPT, consensus, futur rendement, label ou confiance LLM utilisé.
  Ces champs sont retirés avant le replay. Le cache de l'ancienne recherche GPT
  sert uniquement de conteneur des rangs Oracle et des tapes, pas de signal.
- Sélection TOP10 figée **avant** l'admission qualité ; pas de remplacement par
  le onzième titre si l'un des dix est refusé.
- Entrée à l'ouverture de J+1, selon capital/risque disponibles. Pas de
  renforcement d'un titre déjà détenu, ni de vente réelle au courtier.
- SHORT : TP à **80 % du fill**, SL à **107 % du fill**. Pas d'ATR dans la
  distance du stop, pas de trailing. Sortie à l'ouverture de la 21e séance
  depuis l'entrée si toujours détenu, sauf sortie risque/marge préalable.
- Gap défavorable : perte pouvant dépasser 7 %. Collision daily stop/TP sans
  ordre intraday connu : priorité conservatrice au stop, pas au meilleur cas.

## Portefeuille et coûts

Capital initial **4 000 USD**, réinitialisé par année. Plafond de nouvelles
entrées à **2× l'equity**, pas un engagement de levier constamment égal à deux.
Au plus 40 % d'equity de nominal par position avant modulations, risque de base
2,8 % d'equity pour SL7, plafond secteur 100 % d'equity. Le nombre de positions
est aussi borné par les plafonds SHORT natifs du risque (cinq dans la configuration
résolue). On ne suppose donc pas dix positions finançables et exécutées chaque jour.

Le moteur chronologique partagé conserve cash, quantités entières, coûts
canoniques, gaps, liquidité/qualité, corrélations, secteurs, régimes, circuit
breaker, refus des quantités J devenues non finançables à J+1 et valorisation.
Une autorisation **locale à cette recherche** permet le SHORT en régime NORMAL ;
sans elle, le parcours natif bloquerait les nouvelles positions dans ce régime.
Les autres contrôles restent actifs. Aucun paramètre de production n'est modifié.

Coût d'emprunt hypothétique hérité : **0,3 % annuel**, nominal d'entrée × séances
détenues / 252. Ce n'est pas une cotation historique pour ces titres. Frais
d'emprunt des positions ouvertes déduits dans l'equity publiée, non transformés
en profit grâce au crédit de la vente à découvert. Intérêt de marge : 6,5 %/an
sur cash débiteur, jours calendaires ACT/360. Maintenance simulée : palier de
prix, couverture au prochain open après constat d'un manque de marge.

Chaque dossier annuel archive `runtime-configuration.json` avec les réglages
effectifs de risque, exécution et coûts ; ce fichier fait foi pour les valeurs
commission/slippage/spread appliquées, pas un tarif courtier supposé.
Modèle de coûts constaté : `spread_bps=5`, `commission_bps=1`, `slippage_bps=2`,
tick minimal 0,01 USD, en plus de l'emprunt. Ce sont des hypothèses de simulation.

## Réserves : résultat exploratoire, pas preuve de shortabilité historique

- Emprunt/locates supposés disponibles, pas de reconstitution des recalls.
- **Dividendes à rembourser au prêteur non complètement modélisés.** Les
  rendements ne sont donc pas une performance nette intégrale certifiée du SHORT.
- Univers de survivants et secteurs actuels ; macro/quotes/fills historiques
  pas tous qualifiés PIT. Ajustements prix et réserves des tapes hérités.
- Régimes et limites peuvent réduire l'exposition ; les marquages de prix
  peuvent faire dériver le levier EOD au-delà du plafond d'admission.
- Les périodes ont déjà servi à d'autres recherches : pas un nouveau holdout.
- 2026 partiel : distinguer pertes/gains clôturés et valeur latente restante.
- Pour 2024/2025, distinguer capital au 31 décembre et résultat de la cohorte
  annuelle après expiration des dernières entrées dans l'année suivante.

## Intégrité et évolution du code

Les données, prix, classements, poids de modèles et autres artefacts hérités
ont conservé leurs empreintes. **26 fichiers de code/config ont évolué depuis
l'ancienne campagne** : les différences sont listées dans `protocol.json`, avec
ancien/nouveau hash. Elles ne sont pas maquillées en parité bit-à-bit ancienne.
Le nouveau runtime est figé séparément, avec 504 empreintes de sources vérifiées
à nouveau en fin de calcul. Une modification d'un artefact de données n'est
jamais acceptée comme simple dérive du code.

Le runner interdit HTTP et connexions réseau ; les variables SQL et clés LLM
sont neutralisées au lancement. Aucun entraînement, collecte, écriture SQL,
appel LLM ou ordre broker. Les archives précédentes restent inchangées.

## Livrables et suivi

Dossier : `artifacts/research/us_oracle_top10_all_short_tp20_sl7/20261019-v3`.

- `protocol.json`, `ready.json`, `candidates.parquet` : contrat, empreintes et
  sélection/admission observable des dix par jour.
- `progress.json` racine : années terminées ; chaque dossier annuel contient
  son propre `progress.json`, nombre de séances, dernière date et positions.
- Par année : `daily.parquet`, `trades.parquet`, `decisions.json`,
  `executions.json`, motifs de refus, audit d'expiration/marge, positions ouvertes,
  configuration résolue et `case-report.json`.
- `decision-audit.json` par année : candidats, approbations/refus, permissions,
  limites SHORT et multiplicateur de risque par date.
- `report.json` racine : calculs terminés ; **lire aussi `final-audit.json`**,
  qui conserve la réserve de qualification du régime 2025.
- V1 : préparation initiale ; v2 : première exécution ; v3 : ajout du journal
  de refus, sans changer la stratégie. Equity finale, trades et DD se reproduisent
  exactement sur les trois années entre v2 et v3. V3 fait référence.

Commande de suivi :

```powershell
Get-Content F:\projets\artifacts\research\us_oracle_top10_all_short_tp20_sl7\20261019-v3\progress.json
```

Recherche : `scripts/research/us_oracle_top10_all_short_tp20_sl7.py`.
Tests initiaux : **18 passent**, incluant le parcours SHORT réutilisé, protection
TP20/SL7 au fill, collision conservatrice, unités entières, absence de
renforcement, emprunt latent, neutralisation des champs GPT/futurs et causalité
des modèles. Les avertissements pandas de concaténation sont non bloquants.

## Résultats

**Calculs terminés, empreintes vérifiées ; réserve sur les permissions 2025.**
Capital initial de chaque cohorte : 4 000 USD. Les positions encore ouvertes en
2026 sont valorisées nettes de l'emprunt couru, pas transformées en cash.

| Cohorte de décisions | Capital final simulé | Rendement | DD maximal | Positions clôturées gagnantes / perdantes | Taux gagnant |
|---|---:|---:|---:|---:|---:|
| 2024, avec sorties jusqu'au 03/02/2025 | 2 828,29 $ | −29,29 % | −38,33 % | 31 / 78 | 28,44 % |
| 2025 — **réserve de régime** | 4 328,16 $ | +8,20 % | −19,28 % | 9 / 16 | 36,00 % |
| 2026 jusqu'au 30 septembre | 2 577,06 $ | −35,57 % | −42,57 % | 25 / 67 | 27,17 % |

Au **31/12/2024**, avant la queue d'expiration des dernières entrées, le capital
était de **2 901,04 $ (−27,47 %)**. Le résultat 2025 n'a plus de position ouverte
au 31 décembre et ne change pas pendant sa queue de calendrier.

| Cohorte | Gains clôturés cumulés | Pertes clôturées cumulées | PnL clôturé net | PnL latent au terme |
|---|---:|---:|---:|---:|
| 2024 | +3 824,95 $ | −4 996,66 $ | −1 171,71 $ | 0,00 $ |
| 2025 | +1 463,40 $ | −1 135,24 $ | +328,16 $ | 0,00 $ |
| 2026 | +1 898,05 $ | −3 329,37 $ | −1 431,32 $ | +8,47 $ avant 0,08 $ d'emprunt latent |

2026 : **96 entrées, 92 positions clôturées et quatre encore ouvertes**
(SIMO, DOCN, CCOI, SSTK). Pas de liquidation fictive au 30 septembre.
Les taux gagnants portent uniquement sur les positions clôturées, pas sur les
quatre restantes. Chaque sortie et quantité est rapprochée des prix/protections
et des flux cash ; erreur de réconciliation inférieure à 1,1×10⁻¹¹ USD.

Exposition brute moyenne : 2 947,07 $ en 2024, 703,33 $ en 2025, 1 278,68 $ en
2026 ; leviers moyens respectifs **0,82× / 0,19× / 0,44×**, maxima EOD observés
1,99× / 1,94× / 1,94×. Ce test n'a donc pas été exposé en permanence à ×2.

### Réserve déterminante en 2025

Il n'y a que **25 entrées**, en janvier–mars ; dernière décision approuvée le
**5 mars 2025**. Le journal ajouté en v3 permet de distinguer deux mécanismes :

1. Au début de mars, la baisse d'allocation rend des quantités entières trop
   petites : refus `rejected_notional_below_enforced`, sans remplacer les candidats.
2. Ensuite, **177 séances au régime affiché NORMAL**, du 15 avril au 31 décembre,
   ont `max_short_positions=0`. Ce n'est pas une absence de candidats : les dix
   continuent d'être fournis, avec des scores et une admission qualité valides.

Reproduction pure, sans SQL ni portefeuille : `evaluate_from_snapshot` reçoit
une sortie CAPITAL_PRESERVATION → snapshot NORMAL (âge 150 jours), mais transmet
des compteurs de sortie et de calme **constamment à zéro** à la machine d'états.
La transition reste « sortie défensive en attente (exit_streak=0/3, calm=0/2) »
avec `allow_short=False`. Le garde risque applique alors zéro place SHORT.
Même si le snapshot affiché est normal et son allocation restaurée, la permission
de transition peut donc continuer de bloquer la stratégie.

**Le +8,20 % est le résultat brut reproductible de ce moteur, pas une validation
du SHORT systématique sur toute l'année 2025.** La même incohérence NORMAL/quota
SHORT nul n'a pas été observée pendant les années de décisions 2024 et 2026.
Les contrôles propres aux régimes défensifs demeurent, eux, volontairement actifs.

Le moteur de production n'a pas été corrigé silencieusement pour obtenir un autre
résultat. Pour une comparaison 2025 définitive, il faut qualifier/corriger ce
raccord des transitions et refaire le replay. Les anciens tests SHORT peuvent
être concernés ; leur réaudit n'a pas été lancé dans cette expérience.

### Interprétation et limites des métadonnées génériques

Le SHORT systématique des TOP10 **ne montre pas de robustesse transversale** :
pertes en 2024 et 2026, 2025 non validé comme test continu. Pas de promotion,
de recherche d'un meilleur seuil ou d'abandon définitif de l'Oracle d'amplitude.

Certains champs de confort du rapport natif restent génériques
(`sizing_unchanged`, `trailing_unchanged`, `expiry_open_sessions=null`). Ils ne
décrivent pas les surcharges du ledger de recherche : ici sizing explicitement
configuré, trailing OFF, expiration dans le hook dédié après 20 séances. Le
protocole, la configuration résolue, les protections réelles des trades et
`final-audit.json` font foi. Aucun SL 5/10 % ni trailing n'a été utilisé.
