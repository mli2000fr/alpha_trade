# GPT : confiance déclarée et gains/pertes — 2024–2026

Étude du **15 octobre 2026**, après la campagne TOP20 et les backtests LONG/SHORT.
Deux demandes distinctes sont traitées, sans modifier les modèles ni la production :

1. Comparer les résultats par tranche de confiance, avec les protections **TP20/SL5
   inchangées** des portefeuilles précédents.
2. Refaire le portefeuille **LONG uniquement, confiance >=0,90, TP20/SL10**.

**Conclusion : aucune relation croissante et stable entre confiance GPT et taux
gagnant n'est démontrée. Le nouveau portefeuille LONG >=0,90 TP20/SL10 ne confirme
pas non plus une rentabilité régulière.** Ce sont des résultats exploratoires,
pas une calibration ni une validation indépendante.

## Sources, population et conventions

Campagne commune : 2024-01-01 au 2026-09-30, TOP20 Oracle par séance.

| Année | Modèle Oracle parcours annuel |
| --- | --- |
| 2024 | `model-factory-20261014113215-437ed1` |
| 2025 | `model-factory-20261014113226-102eca` |
| 2026 | `model-factory-20261014113232-bc35a7` |

913 avis BULLISH/VALID, 734 BEARISH/VALID. Un avis est un couple **titre/date**, pas
une action distincte ni un ordre. Le score `confidence` est déclaré par GPT ;
0,95 **ne signifie pas** 95 % de chances de gain. Aucun appel GPT supplémentaire.

Les données sont reprises des préparations scellées et auditées, elles-mêmes
reconstruites depuis les snapshots SQL et les réponses brutes revalidées.
Empreintes des fichiers/sources vérifiées. Aucun accès API ni écriture SQL ici.

Tranches fixées avant le calcul : `<0,70`, `[0,70;0,80[`, `[0,80;0,90[`,
`[0,90;0,95[`, `[0,95;1]`. Aucun balayage de seuils pour choisir le meilleur.
Le score utilisé est celui de l'avis à l'entrée initiale, sans mise à jour par
une news ultérieure. Le classement reste le score Oracle, pas la confiance GPT.

## 1. Attribution descriptive des positions précédentes : TP20/SL5

Cette analyse **ne recrée pas un portefeuille indépendant pour chaque tranche**.
Elle répartit les positions effectivement exécutées des backtests précédents :

- LONG : `GPT_BULLISH_ONLY`, 335 positions entièrement clôturées ;
- SHORT : `GPT_BEARISH_ONLY`, profil local `RESEARCH_SHORT_NORMAL`, 167 clôturées ;
- quatre LONG et deux SHORT encore ouverts au 30 septembre 2026 sont exclus du
  taux gagnant ; des sorties partielles éventuelles d'un lot encore ouvert ne
  deviennent pas artificiellement une position clôturée ;
- les jambes d'une même position sont regroupées avant de compter gains/pertes ;
- 2024/2025 incluent les sorties des cohortes dans leurs queues prévues de début
  d'année suivante ; 2026 est tronquée au 30 septembre.

Les PnL en dollars sont ceux des positions : coûts de transaction inclus,
emprunt SHORT simulé inclus, mais **intérêts de financement du portefeuille non
répartis par position**. Ce ne sont ni les rendements d'un portefeuille de tranche,
ni des rendements composés entre années. Taille des positions et sélection par
capacité/régime peuvent différer entre tranches.

### LONG

| Confiance | Clôturées | Gagnantes / perdantes | % gagnantes | Somme gains | Somme pertes | Solde PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| <0,70 | 7 | 2 / 5 | 28,57 % | +328,03 $ | −356,33 $ | −28,30 $ |
| 0,70 à <0,80 | 119 | 27 / 92 | 22,69 % | +6 269,40 $ | −6 472,95 $ | −203,55 $ |
| 0,80 à <0,90 | 144 | 45 / 99 | 31,25 % | +9 396,02 $ | −6 102,49 $ | +3 293,53 $ |
| 0,90 à <0,95 | 54 | 13 / 41 | 24,07 % | +2 847,28 $ | −3 187,60 $ | −340,32 $ |
| >=0,95 | 11 | 3 / 8 | 27,27 % | +681,44 $ | −603,69 $ | +77,75 $ |

### SHORT, autorisé aussi en régime normal uniquement pour la recherche

| Confiance | Clôturées | Gagnantes / perdantes | % gagnantes | Somme gains | Somme pertes | Solde PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| <0,70 | 1 | 0 / 1 | 0,00 % | 0,00 $ | −32,91 $ | −32,91 $ |
| 0,70 à <0,80 | 19 | 4 / 15 | 21,05 % | +764,38 $ | −931,25 $ | −166,87 $ |
| 0,80 à <0,90 | 80 | 21 / 59 | 26,25 % | +4 146,84 $ | −3 470,12 $ | +676,73 $ |
| 0,90 à <0,95 | 42 | 6 / 36 | 14,29 % | +1 340,29 $ | −2 353,53 $ | −1 013,24 $ |
| >=0,95 | 25 | 7 / 18 | 28,00 % | +1 219,85 $ | −899,16 $ | +320,69 $ |

Les petits groupes <0,70 et >=0,95 ne justifient pas une règle de production.
Les groupes les plus confiants ne gagnent pas systématiquement plus souvent.
Le bon résultat de la tranche LONG 0,80–<0,90 **ne permet pas de choisir ce seuil
après coup et de le présenter comme confirmé**.

### Comparaison fixée >=0,90 contre <0,90

| Sens | Confiance | Clôturées | Gagnantes / perdantes | % gagnantes | Solde PnL |
| --- | --- | ---: | ---: | ---: | ---: |
| LONG | <0,90 | 270 | 74 / 196 | 27,41 % | +3 061,67 $ |
| LONG | >=0,90 | 65 | 16 / 49 | 24,62 % | −262,57 $ |
| SHORT | <0,90 | 100 | 25 / 75 | 25,00 % | +476,95 $ |
| SHORT | >=0,90 | 67 | 13 / 54 | 19,40 % | −692,55 $ |

### Stabilité annuelle du taux gagnant

| Année | LONG <0,90 | LONG >=0,90 | SHORT <0,90 | SHORT >=0,90 |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 20,59 % (68) | 10,00 % (10) | 28,13 % (32) | 8,70 % (23) |
| 2025 | 38,20 % (89) | 23,08 % (26) | 31,58 % (19) | 22,22 % (18) |
| 2026 au 30/09 | 23,01 % (113) | 31,03 % (29) | 20,41 % (49) | 26,92 % (26) |

Le groupe très confiant fait mieux sur le taux gagnant en 2026, mais moins bien
en 2024 et 2025, dans les deux sens. La combinaison de plusieurs années ne doit
pas masquer cette instabilité. Le nombre entre parenthèses est l'effectif clôturé.

## 2. Nouveau portefeuille LONG >=0,90, TP20/SL10

Trois backtests terminés et audités. **163 avis** retenus avant risque : 25 en
2024, 53 en 2025 et 85 en 2026. Tous passent l'admissibilité à J préexistante ;
les règles de risque/exécution donnent ensuite **74 achats**, pas 163.

Règles : 4 000 USD réinitialisés chaque année ; levier d'entrée maximal x2,
cap de 40 % de l'equity par position avant les gardes natifs ; entrée à l'open
suivant, filtre de gap 3 %, pas de renforcement, pas de remplacement hors TOP20.
TP à +20 %, SL à −10 %, sans trailing, expiration à l'open après vingt séances.
Un gap peut dépasser la perte théorique de 10 %. Les régimes et gardes de risque
sont conservés. La formule de budget risque reste `0,4 x distance SL` : elle
passe de 2 % à 4 % avant gardes, pour conserver la même logique de cap de position.
La quantité exécutée et le capital mobilisé ne sont donc pas supposés identiques.

Coûts natifs et financement de débit à 6,5 %/an ACT/360 inclus. Marge/financement
historiques non certifiés ; pas de rendement total avec dividendes complets.

| Année | Capital civil | Rendement | DD maximal civil | Achats | Gagnantes / perdantes clôturées | % gagnantes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 3 226,05 $ | −19,35 % | −25,06 % | 12 | 2 / 10 | 16,67 % |
| 2025 | 4 019,75 $ | +0,49 % | −18,55 % | 32 | 15 / 17 | 46,88 % |
| 2026 au 30/09 | 3 454,23 $ | −13,64 % | −20,61 % | 30 | 11 / 18 | 37,93 % |

2024/2025 sont entièrement fermées ; les queues prévues après le 31 décembre ne
modifient pas les capitaux affichés. Une position **VICR** reste ouverte au
30 septembre 2026 : 2,584744273 actions, entrée le 23 septembre à 266,50 USD,
mark 288,94 USD, latent après coût d'entrée +57,45 USD inclus dans l'equity.
Au total : **28 gagnantes / 45 perdantes clôturées**, soit 38,36 % / 61,64 %,
et une ouverte exclue du taux. Ce taux supérieur au précédent n'est pas une preuve
d'amélioration du filtre : le SL10 laisse davantage de temps pour rebondir et
augmente la taille des pertes possibles.

| Année | Somme PnL fermés positifs | Somme PnL fermés négatifs | Intérêts de financement |
| --- | ---: | ---: | ---: |
| 2024 | +359,90 $ | −1 133,45 $ | 0,39 $ |
| 2025 | +2 853,98 $ | −2 823,62 $ | 10,61 $ |
| 2026 au 30/09 | +1 260,47 $ | −1 863,19 $ | 0,51 $ |

L'ancien portefeuille LONG tous avis, TP20/SL5, réalisait −26,31 % / +74,79 % /
+15,19 % aux mêmes bornes civiles. Le nouveau couple seuil+SL améliore 2024,
mais dégrade 2025/2026. **Deux paramètres ont changé simultanément** : ni l'écart
de rendement ni celui du taux gagnant n'isole un effet causal de la confiance.
Aucune autre combinaison n'a été optimisée ici.

## Vérifications, fichiers et limites

Dossiers distincts, sans réécriture des expériences précédentes :

- attribution : `artifacts/research/us_news_gpt_confidence_analysis/20261015-v1` ;
- nouveau portefeuille : `artifacts/research/us_news_gpt_bullish_confidence/20261015-v1`.

Attribution : `protocol.json`, `report.json`, `position-attribution.parquet`
avec chaque avis, symbole/date, clé du cache, confiance, jambes, PnL et retour
net sur nominal d'entrée. 502 positions clôturées réparties sans perte/doublon.
Les métriques SHORT n'utilisent pas le rendement réciproque historique du moteur.

Portefeuille : `ready.json`/`protocol.json`, candidats et rapports annuels,
exécutions, trades, courbes, protections/expirations, positions ouvertes et audit.
Réconciliation indépendante **journalière** cash/positions/equity/intérêts ;
TP/SL réancrés au prix réellement simulé à l'open, collisions conservatrices,
sorties de gap/expiration et entrées de la bonne date contrôlées.

30 tests ciblés passent : seuil inclusif, rejets invalides/NaN, collisions,
protection10/20, expiration native, MTM ouvert, attribution de sorties partielles,
frontières des tranches et calcul du rendement SHORT.

```powershell
python -u -m scripts.research.us_news_gpt_confidence_analysis --output artifacts/research/us_news_gpt_confidence_analysis/20261015-v1
python -u -m scripts.research.us_news_gpt_bullish_confidence --output artifacts/research/us_news_gpt_bullish_confidence/20261015-v1
python -u -m scripts.research.us_news_gpt_bullish_confidence_audit --output artifacts/research/us_news_gpt_bullish_confidence/20261015-v1
```

Zéro nouvel appel GPT, entraînement, écriture SQL, ordre courtier ou changement
de configuration. Les limites initiales restent entières : news importées/révisables
et mémoire future LLM, secteurs actuels, macro non certifiée PIT ; SHORT sans
preuve historique d'emprunt, frais hypothétiques et dividendes compensatoires
non modélisés. Petits effectifs, répétition de titres/dates, dépendance de la
sélection aux contraintes du portefeuille et périodes déjà explorées. Ces
résultats ne permettent ni une calibration de `confidence` ni une promotion live.
