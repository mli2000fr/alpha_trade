# Comparaison appariée des règles LONG TP10/SL10 — BEARISH, BULLISH, TOP20 entier

GO du **15 octobre 2026**, point 1 de l'audit de la proposition reçue : vérifier
si acheter les avis GPT baissiers apporte un avantage par rapport à des témoins
qui emploient **exactement les mêmes protections et règles de portefeuille**.
Pas de nouvel entraînement ni de recherche de paramètres.

## Les trois bras

| Bras | Population avant risque | Sens exécuté |
| --- | --- | --- |
| `GPT_BEARISH_AS_LONG` | BEARISH/VALID : 734 couples titre/date, 732 admissibles à J | LONG |
| `GPT_BULLISH_AS_LONG` | BULLISH/VALID : 913 couples titre/date, 911 admissibles à J | LONG |
| `ORACLE_TOP20_ALL_LONG` | TOP20 Oracle quotidien complet, après les mêmes contrôles à J | LONG |

Aucun seuil de confiance ajouté. Le témoin sans filtre **conserve** les avis
absents, les abstentions et les erreurs techniques de GPT : ils ne sont pas
interprétés comme neutres ni comme des veto. Ce témoin mesure une politique
sans usage des avis, pas seulement une sous-population disposant de news.

13780 couples, 689 séances, même sélection quotidienne avant les labels futurs.
Les deux rejets BEARISH et deux rejets BULLISH restent ceux de l'admissibilité
physique/features à J, sans consulter le futur. Aucun remplacement hors TOP20,
aucune redistribution fictive d'un candidat rejeté ; le rang de priorité est
le score Oracle d'origine, jamais la confiance GPT.

| Année | Modèle Oracle parcours annuel |
| --- | --- |
| 2024 | `model-factory-20261014113215-437ed1` |
| 2025 | `model-factory-20261014113226-102eca` |
| 2026 au 30 septembre | `model-factory-20261014113232-bc35a7` |

Les trois résultats BEARISH du test précédent sont repris après vérification de
leurs empreintes, sans les réécrire. Six nouveaux contrôles sont calculés :
trois BULLISH et trois TOP20 sans filtre. Neuf résultats comparés, pas neuf
nouvelles simulations. Aucun nouvel appel GPT, SQL ou fournisseur.

## Contrat commun

- 4 000 USD au début de chaque année, capital réinitialisé annuellement ;
- levier d'entrée maximal x2, cap par position de 40 % avant gardes ; budget
  risque `0,4 x SL` = 4 % avant ajustements ; règles de capital, concentration,
  régimes et circuit-breaker identiques ;
- entrée à l'open de la séance suivante, garde de gap 3 % ; LONG fractionnaire
  possible, pas de renforcement d'un titre détenu ;
- TP fixe +10 %, SL fixe −10 %, ancrés au fill simulé ; **sans trailing** ;
- collision intrabar traitée conservativement, gaps conservés ; perte non
  plafonnée artificiellement à 10 %, TP limite non exécuté au-delà de sa limite ;
- expiration à l'open après vingt séances depuis l'entrée, sauf sortie native
  de risque/protection plus tôt ; pas de liquidation fictive à fin de replay ;
- mêmes coûts de transaction, frais et slippage canoniques ; financement de
  débit de cash à 6,5 %/an ACT/360, hypothèse fixe et non taux historique ;
- même bande de prix/identités, même macro, mêmes secteurs actuels, mêmes
  opérations sur titres et contrôles de données ; aucun prêt de titres SHORT ;
- décisions 2024/2025 jusqu'au 31 décembre, queues jusqu'au 3 février 2025 /
  2 février 2026 sans nouvelle décision ; 2026 jusqu'au 30 septembre avec
  positions restantes valorisées, pas artificiellement fermées.

**Même capital et mêmes règles ne signifient pas même exposition réalisée.**
Le nombre d'avis disponibles, le calendrier des trades, le cash libéré et les
pertes/gains modifient les décisions suivantes. La comparaison mesure les
portefeuilles complets sous les mêmes règles, pas un alpha à risque égal.

## Traçabilité et incident technique

Le premier lancement est arrêté **avant simulation** par les empreintes strictes.
L'audit établit que les écarts portent uniquement sur la conversion LF vers CRLF
de fichiers Python ; les octets normalisés LF reproduisent **exactement** les
SHA256 historiques. Aucun contenu, prix, configuration ou ancien manifeste n'a
été corrigé ou remplacé. Pas d'acceptation générale d'un changement de code.

Une attestation distincte `source-line-endings.json` conserve les anciens hashes,
les nouveaux et leur égalité après normalisation. Les nouveaux fichiers sont
ensuite liés à leurs **octets bruts actuels** ; données et configuration restent
strictes. L'audit final recalcule indépendamment cette preuve. Une variation du
contenu Python ou de la configuration demeure bloquante.
Les premiers logs d'échec sont conservés, reprise dans `*-retry1.log`.

Tests : sélection correcte des trois bras, absence de filtre de confiance,
conservation des avis inconnus dans le témoin, score Oracle inchangé, rejet des
doublons, même ledger LONG et budget risque. Le test de compatibilité n'accepte
que l'équivalence CRLF des `.py`, pas un changement de contenu ou de YAML.
Les tests natifs TP10/SL10 avec vrais trades couvrent collisions, gaps,
expiration et MTM des positions ouvertes.

## Exécution

Module : `scripts/research/us_news_gpt_long_comparison.py`.
Audit : `scripts/research/us_news_gpt_long_comparison_audit.py`.
Dossier : `artifacts/research/us_news_gpt_long_comparison/20261015-v1`.

```powershell
python -u -m scripts.research.us_news_gpt_long_comparison --output artifacts/research/us_news_gpt_long_comparison/20261015-v1
Get-Content artifacts/research/us_news_gpt_long_comparison/20261015-v1/progress.json
python -u -m scripts.research.us_news_gpt_long_comparison_audit --output artifacts/research/us_news_gpt_long_comparison/20261015-v1
```

Protocole figé avant les nouveaux PnL. Verrou exclusif ; reprises des cas terminés
uniquement après contrôle des empreintes. `source_folder` identifie explicitement
les fichiers repris versus les nouveaux, sans dupliquer ni réécrire les anciens.
`report.json` contient les neuf résultats, `audit.json` les comptes vérifiés et
les écarts BEARISH−BULLISH et BEARISH−TOP20 entier par année.

## Résultats

**Terminé et audité le 15 octobre 2026 : neuf cas sur neuf, aucun échec de
simulation.** Six nouveaux témoins et trois résultats BEARISH repris. L'arrêt
préparatoire sur les fins de ligne ne correspond pas à un cas économique échoué.
Les 16 tests ciblés passent ; aucun paramètre n'a été modifié après les résultats.

### Rendements aux bornes civiles

Valorisation au 31 décembre 2024/2025 et au 30 septembre 2026, net des frais
simulés et du financement, latent des positions ouvertes inclus. Départ annuel
indépendant de 4 000 USD ; les rendements ne sont pas composés entre années.

| Année | BEARISH achetés LONG | BULLISH achetés LONG | TOP20 entier LONG |
| --- | ---: | ---: | ---: |
| 2024 | **+55,88 %** | −26,04 % | −17,24 % |
| 2025 | **+20,80 %** | −2,35 % | +14,66 % |
| 2026 au 30/09 | −18,82 % | **−14,04 %** | −19,67 % |

| Année / bras | Capital civil | DD maximal civil | Achats | Gagnantes / perdantes de cohorte clôturée | Taux gagnant |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 BEARISH LONG | 6 235,36 USD | −16,48 % | 82 | 48 / 34 | 58,54 % |
| 2024 BULLISH LONG | 2 958,47 USD | −30,08 % | 72 | 33 / 39 | 45,83 % |
| 2024 TOP20 entier LONG | 3 310,27 USD | −40,16 % | 175 | 96 / 79 | 54,86 % |
| 2025 BEARISH LONG | 4 832,07 USD | −28,24 % | 130 | 75 / 55 | 57,69 % |
| 2025 BULLISH LONG | 3 905,85 USD | −29,40 % | 108 | 66 / 42 | 61,11 % |
| 2025 TOP20 entier LONG | 4 586,48 USD | −34,37 % | 189 | 106 / 83 | 56,08 % |
| 2026 BEARISH LONG | 3 247,12 USD | −31,98 % | 82 | 38 / 42 | 47,50 % |
| 2026 BULLISH LONG | 3 438,23 USD | −28,77 % | 109 | 56 / 51 | 52,34 % |
| 2026 TOP20 entier LONG | 3 213,34 USD | −34,93 % | 196 | 97 / 91 | 51,60 % |

Les taux/compteurs des cohortes 2024/2025 incluent leurs dernières clôtures dans
les queues prévues de début d'année suivante ; ils ne sont pas limités aux seuls
trades fermés avant le 31 décembre. Les positions encore ouvertes en 2026 ne
sont pas comptées comme gagnantes/perdantes. Le nombre de gains n'explique pas
seul le capital : tailles, sorties partielles/anticipées, gaps et financement
interviennent ; par exemple le BULLISH 2025 a le taux gagnant le plus élevé sans
le meilleur rendement.

### Après fermeture complète des cohortes anciennes

| Cohorte | BEARISH LONG : capital / rendement | BULLISH LONG : capital / rendement | TOP20 entier LONG : capital / rendement |
| --- | ---: | ---: | ---: |
| 2024 | 6 481,76 USD / **+62,04 %** | 2 958,47 USD / −26,04 % | 3 703,82 USD / −7,40 % |
| 2025 | 4 835,69 USD / +20,89 % | 4 117,99 USD / +2,95 % | 5 041,68 USD / **+26,04 %** |

À fin décembre, les positions encore ouvertes étaient respectivement 1/0/6 en
2024 et 7/3/8 en 2025, dans l'ordre BEARISH/BULLISH/TOP20 entier. Elles ont toutes
été fermées dans les queues prévues, sans nouvelle décision. Le petit avantage
civil 2025 de l'inversion sur le témoin entier **ne tient pas** après fermeture
complète : delta de rendement de cohorte **−5,15 points**.

### Écart BEARISH LONG moins témoins

| Année | Contre BULLISH : rendement civil, points | Contre TOP20 entier : rendement civil, points | Contre TOP20 entier après queue, points |
| --- | ---: | ---: | ---: |
| 2024 | +81,92 | +73,13 | +69,45 |
| 2025 | +23,16 | +6,14 | **−5,15** |
| 2026 au 30/09 | **−4,78** | +0,84 | +0,84, cohorte encore ouverte |

L'inversion bat donc le TOP20 entier aux trois bornes civiles, mais sans avantage
uniforme une fois les cohortes anciennes achevées. En 2026, elle perd davantage
que le BULLISH et ne réduit que modestement la perte du témoin entier :
**+33,77 USD**, soit +0,84 point sur les 4 000 USD de départ.

### Exposition et positions ouvertes

| Année | BEARISH : brut moyen / equity | BULLISH : brut moyen / equity | TOP20 entier : brut moyen / equity |
| --- | ---: | ---: | ---: |
| 2024 | 1,009 | 0,589 | 1,178 |
| 2025 | 0,823 | 0,519 | 0,868 |
| 2026 au 30/09 | 0,385 | 0,569 | 0,883 |

Ces moyennes portent sur le calendrier de replay commun à chaque année, queues
prévues incluses. La stratégie BEARISH 2026 a beaucoup moins d'exposition que le
témoin entier ; le petit écart de rendement ne démontre pas un alpha à risque égal.

Au 30 septembre 2026 :

- BEARISH LONG : **APP/FICO**, deux positions, latent total **−63,87 USD** ;
- BULLISH LONG : **RARE/COHR**, deux positions, latent total **−22,52 USD** ;
- TOP20 entier LONG : huit positions, listées dans son `open-positions.json`.

Elles restent valorisées, pas artificiellement liquidées. Totaux des trois cohortes :

| Bras | Achats | Clôturées | Gagnantes / perdantes | Taux gagnant | Encore ouvertes |
| --- | ---: | ---: | ---: | ---: | ---: |
| BEARISH LONG | 294 | 292 | 161 / 131 | 55,14 % | 2 |
| BULLISH LONG | 289 | 287 | 155 / 132 | 54,01 % | 2 |
| TOP20 entier LONG | 560 | 552 | 299 / 253 | 54,17 % | 8 |

### Conclusion

**Avantage rétrospectif intéressant surtout en 2024, mais pas de supériorité
stable démontrée pour l'inversion GPT.** Les règles/protections sont maintenant
appariées : l'effet n'est plus confondu avec le précédent passage TP20/SL5 à
TP10/SL10. Cependant les expositions, disponibilités d'avis et chemins de capital
diffèrent, et le résultat 2025 dépend du choix borne civile/fin de cohorte.
2026 reste perdante dans les trois bras ; l'inversion n'apporte pas la protection
recherchée contre cette période et est inférieure au BULLISH.

Ne pas conclure « GPT doit être inversé » ni intégrer cette règle au live.
Ce contrôle borne l'intérêt de cette variante ; il n'exclut pas l'utilité de toute
information de news ou d'un événement factuel différent. Aucun nouveau modèle,
seuil optimisé ou scénario supplémentaire n'a été lancé après ce bilan.

Audit final : `AUDITED_MATCHED_RULES_EXPLORATORY_NOT_PIT`, neuf cas réconciliés
journellement, source/score/dates d'entrée, TP/SL, gaps, collisions, échéances,
frais/financement, positions ouvertes et preuve d'équivalence des fins de ligne
revérifiés. Données, anciens résultats et configuration de production conservés.

## Limites

2024–2026 et le choix d'inverser BEARISH ont déjà été observés ; ce n'est pas un
holdout vierge. Les avis s'appuient sur des news historiques importées/révisables,
la mémoire future du LLM n'est pas exclue, les secteurs sont actuels et les
vintages macro non certifiés PIT. Prix OHLC/fills simulés, dividendes incomplets
et marge historique non qualifiée. Pas de promotion live.

Les avis valides sélectionnent aussi des dates/titres avec certaines news et une
couverture différente : une différence avec TOP20 entier ne s'attribue pas
automatiquement au sens de GPT. Aucun résultat financier n'est inventé pour les
cas futurs ou non terminés ; les positions ouvertes sont séparées des clôturées.
