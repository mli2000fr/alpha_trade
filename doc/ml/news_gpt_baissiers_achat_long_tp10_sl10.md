# Acheter les avis GPT baissiers — LONG TP10/SL10

Demande du **15 octobre 2026** : inverser l'usage des **734 avis BEARISH valides**
de la campagne historique TOP20, et acheter les titres en LONG avec **TP +10 % /
SL −10 %**, sans seuil de confiance ajouté.

Expérience séparée : aucune modification des modèles, du filtre de production,
des paramètres live, des batchs ou des anciens résultats. Aucun nouvel appel GPT,
entraînement, ordre courtier ni écriture SQL.

## Sélection figée

| Année | Modèle Oracle parcours | Avis BEARISH | Admissibles à J avant risque/exécution |
| --- | --- | ---: | ---: |
| 2024 | `model-factory-20261014113215-437ed1` | 158 | 158 |
| 2025 | `model-factory-20261014113226-102eca` | 387 | 387 |
| 2026 au 30 septembre | `model-factory-20261014113232-bc35a7` | 189 | 187 |

734 couples titre/date, soit 150 titres distincts, pas 734 ordres. Les deux
exclusions physiques/features à J restent celles des préparations précédentes,
sans examiner les rendements futurs. Toutes les confiances BEARISH/VALID sont
admises ; ni seuil 0,90 ni tri par confiance ne sont ajoutés.

La source est la préparation scellée du test SHORT, dont les 734 réponses SQL
brutes avaient été revalidées. Le présent test réutilise ces fichiers locaux après
contrôle des empreintes : **aucun nouvel appel GPT ni accès SQL nécessaire**.
Ordre d'examen : score Oracle original décroissant, sans remplissage hors TOP20.
L'Oracle reste un modèle d'amplitude : aucune tête directionnelle n'est entraînée.
La décision « avis BEARISH → achat LONG » est une règle explicite de recherche.

## Portefeuille et protections

- 4 000 USD au début de chaque année, capital réinitialisé annuellement ;
- levier d'entrée maximal x2, sans obligation de l'utiliser ; cap de position
  de 40 % de l'equity avant les limites natives ; budget risque `0,4 x SL`, soit
  4 % avant ajustements, comme la formule précédente ;
- achat à l'ouverture de la séance suivante ; filtre natif de gap maximal 3 %,
  admissibilité des prix, capital, secteurs, circuit-breaker et régimes conservés ;
- pas de renforcement d'un titre détenu ; fractions LONG possibles selon le moteur ;
- **TP fixe à 110 % du prix d'entrée, SL fixe à 90 %**, sans trailing ;
- collision TP/SL intrabar : résolution conservatrice du moteur ; un gap adverse
  peut dépasser la perte théorique de 10 %, un TP limite n'est pas rempli au prix
  plus favorable d'une ouverture en gap ;
- expiration à l'open après vingt séances depuis l'entrée ; les gardes natifs
  peuvent imposer une sortie plus tôt ; pas de vente fictive au terme du replay ;
- coûts canoniques de transaction inclus ; débit financé à 6,5 %/an ACT/360,
  hypothèse fixe de simulation, pas taux historique qualifié ; aucun frais de prêt
  de titres SHORT puisque toutes les positions sont LONG ;
- queues sans nouvelles décisions jusqu'au 3 février 2025 / 2 février 2026 pour
  fermer les cohortes anciennes ; 2026 valorisée au 30 septembre, positions ouvertes
  conservées en MTM et exclues du taux gagnant des clôturées.

Capital civil et capital après fermeture de cohorte sont distingués. Les jambes
de sorties partielles sont regroupées ; un lot encore ouvert n'est pas compté
comme une position gagnante/perdante clôturée. La somme des PnL fermés, le latent
et le financement doivent réconcilier le capital.

## Exécution et contrôle

Module : `scripts/research/us_news_gpt_bearish_long.py`.
Audit : `scripts/research/us_news_gpt_bearish_long_audit.py`.
Dossier : `artifacts/research/us_news_gpt_bearish_long/20261015-v1`.

```powershell
python -u -m scripts.research.us_news_gpt_bearish_long --output artifacts/research/us_news_gpt_bearish_long/20261015-v1
Get-Content artifacts/research/us_news_gpt_bearish_long/20261015-v1/progress.json
python -u -m scripts.research.us_news_gpt_bearish_long_audit --output artifacts/research/us_news_gpt_bearish_long/20261015-v1
```

Verrou exclusif du dossier ; cas terminés réutilisés seulement après contrôle
des empreintes. `protocol.json`/`ready.json` figent les règles et sources avant
les nouveaux résultats. Chaque année possède trades, courbe, exécutions,
décisions, régimes, expirations, maintenance et positions ouvertes.
`report.json` agrège les trois années ; `audit.json` confirme les contrôles.
HTTP bloqué explicitement dans le processus de backtest.

**27 tests ciblés passent**, dont 12 propres à cette inversion : sélection de
BEARISH/VALID même à faible confiance, refus des BULLISH/ABSTAIN/invalides,
vraies exécutions LONG, TP/SL10, collisions, gaps défavorables/favorables,
expiration en parité native et valorisation des positions non terminées.

## Résultats

**Trois cas sur trois terminés et audités le 15 octobre 2026, aucun échec.**
La sélection et les protections n'ont pas été modifiées après lecture des
résultats. Réconciliation quotidienne indépendante cash/positions/equity/intérêts,
bonne date d'entrée et identité BEARISH, sens LONG, TP/SL, gaps, collisions et
expirations vérifiés. Les trois événements d'identité de 2026 n'affectent aucun
lot détenu dans cette expérience ; aucune conversion ni créance non valorisée.

### Capital aux bornes civiles

Valeur au 31 décembre 2024/2025 et au 30 septembre 2026, avec coût des transactions,
financement et latent inclus. Chaque année part indépendamment de 4 000 USD.

| Année | Capital civil | Rendement | DD maximal civil | Achats exécutés | Positions ouvertes à la borne civile |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | 6 235,36 USD | +55,88 % | −16,48 % | 82 | 1 |
| 2025 | 4 832,07 USD | +20,80 % | −28,24 % | 130 | 7 |
| 2026 au 30/09 | 3 247,12 USD | −18,82 % | −31,98 % | 82 | 2 |

### Positions clôturées et fin des cohortes

Les taux ci-dessous incluent les sorties nécessaires après fin 2024/2025 dans
les queues historiques prévues, sans nouvelles décisions. Ils ne sont pas un
décompte des seules sorties avant le 31 décembre. Les deux positions encore
ouvertes au 30 septembre 2026 restent exclues du taux gagnant.

| Cohorte | Capital après queue / borne 2026 | Rendement de cohorte | Clôturées | Gagnantes / perdantes | % gagnantes | % perdantes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 6 481,76 USD | +62,04 % | 82 | 48 / 34 | 58,54 % | 41,46 % |
| 2025 | 4 835,69 USD | +20,89 % | 130 | 75 / 55 | 57,69 % | 42,31 % |
| 2026 au 30/09 | 3 247,12 USD | −18,82 % | 80 | 38 / 42 | 47,50 % | 52,50 % |

Au total : **294 achats**, dont **292 positions clôturées**, **161 gagnantes /
131 perdantes**, soit **55,14 % / 44,86 %**, et deux ouvertes. Ce total pondère
les trades, pas les années ; les rendements annuels ne sont pas additionnés pour
annoncer une performance composée, car le capital est réinitialisé chaque année.

| Cohorte | Somme PnL fermés positifs | Somme PnL fermés négatifs | Intérêts de financement | Exposition brute moyenne / equity |
| --- | ---: | ---: | ---: | ---: |
| 2024 | +7 218,33 USD | −4 659,12 USD | 77,45 USD | 1,009 |
| 2025 | +7 982,80 USD | −7 080,14 USD | 66,96 USD | 0,823 |
| 2026 au 30/09 | +2 877,88 USD | −3 560,02 USD | 6,88 USD | 0,385 |

Les sommes des PnL fermés sont déjà nettes de coûts de transaction, pas des
intérêts de financement listés séparément. Le levier maximal x2 n'est donc pas
une exposition permanente x2 ; les gardes natifs peuvent fortement la réduire.

Positions ouvertes au 30 septembre 2026 :

- **APP** : 2,100548631 actions, entrée le 24 septembre à 315,50 USD, mark
  290,43 USD, latent après coût d'entrée **−53,19 USD** ;
- **FICO** : 1,064881028 action, entrée le 30 septembre à 602,02 USD, mark
  592,47 USD, latent après coût d'entrée **−10,68 USD**.

Le latent total de **−63,87 USD** est inclus dans le capital 2026 sans vente
fictive. Les cohortes 2024/2025 sont entièrement fermées après leurs queues.

### Conclusion bornée

L'inversion LONG des avis BEARISH, avec TP10/SL10, est bénéficiaire sur deux
années sur trois dans cette simulation, mais **ne résout pas 2026** et présente
un DD allant jusqu'à près de 32 %. Elle n'établit ni rentabilité transversale
ni capacité de GPT à prédire systématiquement à l'envers. Aucune promotion live.
Il manque notamment un témoin LONG non inversé aux mêmes TP10/SL10, même risque
et même période pour isoler un avantage de sélection ; il n'a pas été lancé ici.
Les comparaisons aux anciens TP20/SL5 ou au LONG >=0,90 TP20/SL10 ne séparent
pas l'effet du sens, de la sélection, des protections et du chemin du capital.

## Portée et réserves

Hypothèse exploratoire proposée **après** l'observation des pertes des expériences
précédentes : pas un test indépendant hors échantillon au sens de la sélection
d'hypothèse. Ne pas rechercher ensuite les seuils qui rendent ce même échantillon
gagnant et les présenter comme confirmés.

La comparaison au SHORT précédent ne peut isoler l'effet de l'inversion : ses
protections étaient TP20/SL5, ici TP10/SL10 ; les permissions LONG/SHORT, quantités
et contraintes diffèrent aussi. Un éventuel résultat positif ne prouverait pas
que GPT prédit « systématiquement à l'envers », ni un alpha à exposition égale.

Réserves communes : news historiques importées/révisables, mémoire future du LLM
non exclue, secteurs actuels et macro non certifiés PIT, OHLC fournisseur et fills
simulés, dividendes incomplets et marge historique non qualifiée. Aucune promotion
live ou conclusion de rentabilité robuste sans validation supplémentaire.
