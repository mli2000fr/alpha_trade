# Achat des seuls avis GPT haussiers — backtests annuels 2024–2026

Demande du **15 octobre 2026**, après la campagne de news : acheter uniquement les
913 avis `BULLISH` parmi le TOP20 Oracle de chaque séance. Ce sont **913 couples
titre/date, pour 126 titres distincts**, pas 913 ordres nécessairement exécutés.

## Périmètre figé avant calcul

| Année | Modèle | Avis haussiers | Admissibles avant risque/exécution |
| --- | --- | ---: | ---: |
| 2024 | `model-factory-20261014113215-437ed1` | 174 | 174 |
| 2025 | `model-factory-20261014113226-102eca` | 265 | 265 |
| 2026, jusqu'au 30 septembre | `model-factory-20261014113232-bc35a7` | 474 | 472 |

Les deux exclusions initiales sont KLAC aux 9 et 30 juillet 2026 : historique J
ou features de prix non qualifiés selon le contrôle commun du test précédent.
Aucune exclusion fondée sur une perte future. Aucun remplacement hors TOP20.

Les avis sont chargés **depuis les snapshots SQL terminés**, puis les 913 réponses
brutes haussières sont relues et revalidées : empreintes, requête, citations,
identité, décision et confiance. Les scores/rangs proviennent des fichiers
immuables de la campagne dont les empreintes sont également dans le snapshot SQL.
Les analyses ne sont ni refaites ni réécrites.

Condition : `BULLISH` **et** statut technique `VALID`. Aucun seuil de confiance
supplémentaire, aucun choix a posteriori d'un sous-ensemble. Les avis observés
commencent à 0,62 de confiance subjective ; ce n'est pas une probabilité de gain.
Les `BEARISH`, abstentions et inconnus ne sont pas achetés. Aucun SHORT.

Le témoin `ORACLE_TOP20_ALL_LONG` achète les candidats du même TOP20 sans lire
leur opinion GPT. Même score Oracle original, mêmes données et règles. Il ne
reprend pas artificiellement les résultats des anciens portefeuilles TOP5/TOP10.

## Capital, exécution et protections

- **4 000 USD au départ de chaque année**, portefeuilles indépendants ; pas de
  capital cumulé entre les trois années.
- Levier maximal d'entrée ×2 ; l'encours réellement engagé dépend du risque, de
  la volatilité, des secteurs, du capital disponible et du régime.
- LONG, entrée à l'ouverture de la séance suivant J ; filtre natif des gaps >3 %.
- **TP fixe 20 %, SL initial fixe 5 %, sans trailing** : mêmes protections que
  le dernier test GPT T1 2025. Aucun ajustement après lecture des résultats.
- Sortie à l'ouverture après exactement vingt séances de détention si les
  protections/risque n'ont pas déjà fermé la position.
- Pas de renforcement d'un titre détenu. Possibilité d'une nouvelle entrée
  ultérieure seulement si le risque l'autorise et un nouveau candidat le propose.
- Frais/spread/slippage natifs conservés. Financement du débit : hypothèse
  annuelle 6,5 %, ACT/360, jours calendaires. Marge historique individuelle non
  certifiée ; l'exposition peut dériver après des variations de prix.
- Contrôles de données à J identiques à l'ancien test : 121 barres propres,
  identité stable, features causales finies et 201 barres SPY. Secteurs actuels
  non PIT explicitement conservés. Les règles macro et garde-fous restent actifs.

Les 913 candidats ne deviennent donc pas 913 achats : répétition d'un titre déjà
détenu, écart à l'ouverture, capital, concentration et règles de risque peuvent
refuser une entrée. Les approbations, exécutions, rejets et positions sont archivés.

## Dates de fin et positions ouvertes

Les décisions s'arrêtent à la fin de l'année pour 2024/2025, au 30 septembre pour
2026. Les deux années anciennes ont une queue de prix jusqu'à l'expiration de
leurs dernières positions, sans nouvelles entrées. Le rapport distingue le
capital **à la fin de l'année civile** et celui **après la queue de détention**.
Ne pas appeler « rendement 2024 » une variation réalisée sur janvier 2025 sans
préciser cette distinction.

Pour 2026, arrêt de valorisation au **30 septembre 2026**. Une position encore
ouverte n'est pas vendue artificiellement et n'est pas classée gagnante/perdante
réalisée. Les avis du dernier jour n'entraînent pas une entrée sans ouverture
suivante dans la fenêtre de replay. La performance finale comprend la valeur
de marché des positions ouvertes et en affiche séparément le PnL latent.

## Parité et implémentation isolée

Script : `scripts/research/us_news_gpt_bullish_portfolio.py`.
Pas de modification du moteur partagé ou de la production. Le ledger de
recherche dérive de celui des derniers tests : cash, sizing, risque, coûts,
settlement, corporate actions et marge sont partagés.

La seule adaptation de boucle fait appliquer l'expiration dans le hook
d'ouverture, après les opérations sur titres et avant les protections de gap.
Elle permet de conserver un portefeuille inachevé en MTM au 30 septembre sans
contourner les protections. Un test avec **entrées réellement exécutées** compare
l'ancien moteur et ce hook : courbes quotidiennes et trades strictement identiques.
Un second vérifie une position non terminée : aucune liquidation fictive,
réconciliation exacte du capital avec le latent.

Sept tests isolés passent. À chaque cas, contrôle supplémentaire : seules des
entrées issues du bon bras et du TOP20 figé, au prochain open, sont exécutées ;
le SL reste 5 %, aucune sortie trailing/terminale artificielle et le capital se
réconcilie avec PnL réalisé + latent − financement.

## Sauvegarde et suivi

Run : `artifacts/research/us_news_gpt_bullish_portfolio/20261015-v1`.

```powershell
python -u -m scripts.research.us_news_gpt_bullish_portfolio --phase run --output artifacts/research/us_news_gpt_bullish_portfolio/20261015-v1
Get-Content artifacts/research/us_news_gpt_bullish_portfolio/20261015-v1/progress.json
```

Ne pas lancer une seconde instance : verrou de dossier. Les résultats complets
sont repris depuis leurs fichiers vérifiés, sans refaire les cas terminés.

- `protocol.json` : paramètres, sources et empreintes gelés ;
- `sql-snapshots.json` : identifiants et empreintes des 66 snapshots SQL ;
- `candidates.parquet` : avis, ordre Oracle, admissibilité et motifs ;
- `2024-GPT_BULLISH_ONLY/` etc. : courbe, trades, décisions, exécutions,
  expirations, positions ouvertes et `case-report.json` ;
- `report.json` : bilan des six cas, y compris tout échec explicite ;
- `progress.json` : avancement global, plus un fichier par cas.

HTTP est bloqué dans le processus : **zéro nouvel appel GPT**, zéro ordre courtier,
zéro entraînement et zéro écriture SQL. Le coût historique de collecte (~2,50 USD)
reste une dépense de recherche déjà engagée, distincte des frais d'exécution du
portefeuille ; il n'est pas une nouvelle facture de ce test.

## Interprétation obligatoire

Les news ont été importées et peuvent être révisées ; leurs textes ne sont pas
certifiés comme disponibles historiquement à J. La mémoire future du LLM n'est
pas exclue par le prompt. Macro, secteurs, dividendes et marginabilité présentent
les mêmes réserves que les études précédentes. Les achats/fills OHLC sont simulés,
pas des exécutions courtier observées. Ce test est **exploratoire**, sans promotion
live ou affirmation de gain directionnel robuste.

## Bilan terminé et audité — 15 octobre 2026

Les six cas sont terminés, aucun échec, aucun nouvel appel GPT. L'audit hors
ligne vérifie les empreintes des sources/résultats, l'appartenance des entrées,
TP20/SL5, les expirations à exactement vingt séances et la réconciliation des
capitaux. Preuve : `audit.json`, générée par
`scripts/research/us_news_gpt_bullish_audit.py`. 14 tests ciblés passent en incluant
les tests de gaps, TP, ambiguïté intrabar et statistiques du précédent replay.

### Capital à la fin de l'année civile — ou au 30 septembre 2026

Chaque ligne repart de 4 000 USD. Frais d'exécution et financement simulés inclus,
positions ouvertes valorisées, pas vendues fictivement.

| Année | Capital GPT haussier | Rendement GPT | DD max quotidien GPT | Témoin Oracle sans filtre GPT | Écart de capital GPT − témoin |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | 2 947,62 USD | −26,31 % | −32,61 % | 2 874,82 USD / −28,13 % | +72,81 USD |
| 2025 | 6 991,65 USD | +74,79 % | −15,89 % | 8 086,91 USD / +102,17 % | −1 095,26 USD |
| 2026 au 30/09 | 4 607,48 USD | +15,19 % | −25,16 % | 4 038,88 USD / +0,97 % | +568,60 USD |

Deux positions filtrées restent ouvertes au 31 décembre 2025 ; quatre au
30 septembre 2026. Le témoin en possède respectivement huit au 31/12/2024, six
au 31/12/2025 et sept au 30/09/2026. Ne pas assimiler leurs valorisations à du cash.

### Après traitement des dernières positions des cohortes anciennes

Pas de nouvelle entrée après la fin de l'année. Queue disponible jusqu'au
3 février 2025 pour la cohorte 2024, au 2 février 2026 pour la cohorte 2025.
Le capital peut se stabiliser avant la dernière date si tout est déjà fermé.

| Cohorte | Capital final GPT | Rendement GPT | Capital final témoin | Rendement témoin |
| --- | ---: | ---: | ---: | ---: |
| 2024, positions toutes fermées | 2 947,62 USD | −26,31 % | 3 001,25 USD | −24,97 % |
| 2025, positions toutes fermées | 7 138,62 USD | +78,47 % | 8 787,65 USD | +119,69 % |
| 2026, MTM au 30/09 | 4 607,48 USD | +15,19 % | 4 038,88 USD | +0,97 % |

L'avantage apparent de 2024 à la date civile n'est donc pas conservé après la
fermeture du témoin : le filtré termine 53,62 USD en dessous. Les deux critères
de fin sont fournis pour éviter de choisir rétrospectivement le plus favorable.

### Achats filtrés effectivement réalisés

Statistiques des positions **fermées sur toute la cohorte**, queue comprise pour
2024/2025. Une position réduite en plusieurs jambes est comptée une seule fois.
Les positions encore ouvertes de 2026 ne sont pas classées gagnantes/perdantes.

| Année | Avis haussiers | Achats exécutés | Fermées gagnantes / perdantes | Taux gagnant fermé | Positions encore ouvertes en fin de cohorte |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | 174 | 78 | 15 / 63 | 19,23 % | 0 |
| 2025 | 265 | 115 | 40 / 75 | 34,78 % | 0 |
| 2026 | 474 | 146 | 35 / 107 | 24,65 % | 4 |

Au total : **339 achats, 335 positions fermées et quatre ouvertes**. Les 913 avis
représentent 126 titres distincts ; les contrôles et le portefeuille empêchent
d'en faire artificiellement 913 trades indépendants sans contrainte de capital.

### Risque et exposition

Le DD du témoin est −38,14 % / −26,25 % / −36,60 % : le filtré présente un DD
plus faible sur les trois années. Mais son exposition brute moyenne est aussi
inférieure : environ 0,44× / 0,80× / 0,55× l'equity contre
1,13× / 0,93× / 0,95× pour le témoin, sur les fenêtres de cohorte. Ce ne sont
pas des portefeuilles appariés en exposition. Une amélioration du DD ne prouve
donc pas à elle seule que GPT distingue mieux les futures hausses.

**Conclusion bornée : pas de domination régulière du rendement.** 2026 est plus
favorable au filtre ; 2025 sacrifie du rendement pour un DD observé plus faible ;
2024 reste perdant, sans avantage après la queue. Ni réglage des seuils/protections
sur ces résultats, ni promotion live. Les réserves historiques/PIT demeurent.
