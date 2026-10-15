# Vente à découvert des seuls avis GPT baissiers — 2024–2026

Demande du **15 octobre 2026**, après le test LONG. Utiliser uniquement les
**734 avis BEARISH valides**, sans seuil de confiance ajouté ni nouvel appel GPT.
Ce sont 734 couples titre/date, pour **150 titres distincts**, pas 734 ordres.

| Année | Modèle Oracle parcours | Avis baissiers | Admissibles à J avant risque/exécution |
| --- | --- | ---: | ---: |
| 2024 | `model-factory-20261014113215-437ed1` | 158 | 158 |
| 2025 | `model-factory-20261014113226-102eca` | 387 | 387 |
| 2026, jusqu'au 30 septembre | `model-factory-20261014113232-bc35a7` | 189 | 187 |

Les deux exclusions à J suivent les mêmes contrôles physiques/features que le
test LONG. Pas d'exclusion rétrospective des perdants ni de remplacement hors TOP20.
La direction SHORT vient du **filtre GPT**, pas d'une tête SHORT du modèle Oracle.
Le classement conserve le score Oracle d'amplitude original, pas la confiance GPT.

## Données et règles communes au test LONG

Les scores/rangs, la sélection TOP20 et les décisions viennent de la campagne
SQL terminée. Les 734 réponses brutes baissières sont relues depuis SQL et
revalidées : empreinte de requête/réponse, symbole, date, avis et confiance.
La préparation LONG vérifiée fournit exactement le même historique de prix,
macro, secteurs et les mêmes contrôles d'admissibilité disponibles à J.

- 4 000 USD au départ de chaque année, capital réinitialisé annuellement ;
- levier maximal d'entrée ×2, sans obligation de l'utiliser ;
- entrée à l'open de la séance suivante, filtre natif de gap maximal 3 % ;
- **TP20/SL5**, sans trailing : pour un SHORT, cible à 80 % du prix d'entrée,
  stop à 105 % ; risque de gap défavorable conservé, perte non plafonnée à 5 % ;
- expiration à l'open après vingt séances de détention, sans vente fictive à la
  fin du replay ; positions non terminées de 2026 valorisées au 30 septembre ;
- pas de renforcement ; quantités SHORT **entières**, contrairement aux LONG
  pouvant être fractionnaires ;
- coûts canoniques de vente/rachat, règles de capital, diversification et risque
  conservés ; obligations de marge et emprunt définis ci-dessous ;
- queues historiques après fin 2024/2025 sans nouvelle entrée, jusqu'au
  3 février 2025 / 2 février 2026 pour permettre l'expiration des derniers lots.

Le capital à la fin de l'année civile est distingué du capital après fermeture
de la cohorte. Une position encore ouverte n'est pas un trade réalisé gagnant ou
perdant. Le rendement économique SHORT sur nominal est `(entrée − sortie)/entrée` ;
les métriques réciproques historiques du moteur ne servent pas à calculer le
capital du portefeuille.

## Deux profils de permission SHORT, clairement séparés

Le régime actuel n'autorise pas les nouvelles ventes à découvert en mode normal.
En conserver la règle peut donc donner très peu d'ordres malgré 734 avis.

1. **NATIVE_REGIME** : permissions de régime inchangées. Les shorts ne passent
   que lorsque les règles existantes les autorisent. Ce n'est pas un test où
   chaque avis baissier devient automatiquement un ordre.
2. **RESEARCH_SHORT_NORMAL** : contre-factuel local autorisant aussi les nouvelles
   ventes à découvert en mode normal, à condition que les nouvelles entrées soient
   permises. Tous les autres garde-fous restent actifs : cash-only/close-only,
   caps CP, secteurs, circuit-breaker, capital, prix et exécution. **Aucun changement
   de configuration ou de permission de production.**

Pour chaque profil : bras `GPT_BEARISH_ONLY` et témoin
`ORACLE_TOP20_ALL_SHORT` sans filtre GPT, à règles identiques. Trois années donnent
douze cas figés, sans optimisation de seuils après lecture des résultats.

## Emprunt et marge : hypothèses, pas preuves historiques

**Disponibilité des titres empruntables supposée**, faute d'un historique qualifié.
Aucun locate historique ou preuve de disponibilité pour le courtier n'est inventé.

Le coût natif d'emprunt utilisé est **0,3 % par an**, sur le nominal d'entrée,
proportionnel aux séances détenues/252, facturé au rachat. Ce n'est pas une
cotation de prêt de titres : il peut être gravement sous-estimé pour les titres
HTB. Les rappels d'emprunt et obligations de versement compensatoire des dividendes
ne sont pas modélisés, faute de preuves complètes. Les résultats ne sont donc pas
une estimation exhaustive des coûts d'un portefeuille SHORT exécutable.

Pour les positions encore ouvertes, le reporting déduit aussi les frais
d'emprunt courus de la valeur de marché. Il conserve l'equity native avant cette
provision pour réconciliation. Le moteur de risque natif voit l'emprunt au rachat,
pas une facture quotidienne reconstruite rétroactivement ; cette limite est
documentée, pas présentée comme une parité courtier parfaite.

Autres conventions de simulation :

- intérêts de débit de cash : hypothèse 6,5 %/an ACT/360 ; pas de rendement inventé
  sur le produit de vente à découvert ;
- produit de la vente **pas assimilé à un bénéfice** : la dette de rachat est
  intégralement portée en valeur de marché et dans le buying power ;
- maintenance de marge hypothétique : si prix <5 USD, `max(2,50 USD, prix)` par
  action ; sinon `max(5 USD, 30 % du prix)` ; ce n'est pas un barème certifié du
  courtier pour le titre et la date considérés ;
- violation à la clôture : demande de couverture à l'open suivant, sans nouvelles
  approbations tant que l'obligation n'est pas satisfaite ;
- opération sur titres créant une obligation inconnue envers le prêteur : échec
  explicite du cas, pas d'invention de livraison/cash ni suppression du titre après coup.

## Implémentation et vérifications

Module séparé : `scripts/research/us_news_gpt_bearish_portfolio.py`. Réutilise le
ledger SHORT, coûts et protections existants, avec adaptation de recherche pour
levier/marge, échéance à l'open et positions ouvertes. Les moteurs partagés, modèles,
batchs et règles live ne sont pas modifiés.

37 tests ciblés passent : prix TP/SL dans le bon sens, quantités entières,
crédit de vente/dette de rachat, emprunt, gaps et collisions intrabar,
réduction partielle, interdiction native en normal, variante locale explicite,
expiration strictement identique à la boucle native et MTM SHORT avec emprunt couru.
Les tests de parité comportent de vraies entrées simulées, pas deux livres vides.

HTTP bloqué dans le processus, SQL en lecture seule : **zéro nouvel appel GPT,
ordre courtier, entraînement ou écriture SQL**.

## Exécution et fichiers

```powershell
python -u -m scripts.research.us_news_gpt_bearish_portfolio --phase run --output artifacts/research/us_news_gpt_bearish_portfolio/20261015-v1
Get-Content artifacts/research/us_news_gpt_bearish_portfolio/20261015-v1/progress.json
```

Ne pas lancer deux instances : verrou de dossier. Les cas terminés sont relus
après contrôle de leurs empreintes. `protocol.json` fige les hypothèses et
sources ; `sql-bearish-validation.json` trace les 734 réponses SQL revalidées ;
`candidates.parquet` conserve les admissions/motifs ; chaque dossier de cas
contient trades, courbe, décisions, exécutions, dette ouverte, frais d'emprunt,
maintenance et expirations ; `report.json` regroupe les douze résultats/échecs.

**Terminé le 15 octobre 2026 : 12 cas sur 12, aucun échec.** `audit.json`
contrôle les empreintes des sources et résultats, les 734 réponses déjà validées,
les entrées à la séance suivante, les protections, l'expiration et les comptes.
Le contrôle reconstruit **chaque journée** : crédits de vente, dette de rachat,
rachats partiels, emprunt couru, cash, equity et nombre de positions. Le produit
de la vente à découvert n'est donc jamais compté comme du profit.

Commande de vérification hors ligne, sans API ni SQL :

```powershell
python -u -m scripts.research.us_news_gpt_bearish_audit --output artifacts/research/us_news_gpt_bearish_portfolio/20261015-v1
```

## Résultats : shorts autorisés aussi en régime normal, recherche seulement

Valeurs au **31 décembre 2024/2025 et au 30 septembre 2026** ; départ annuel
indépendant de 4 000 USD. Coûts simulés et emprunt couru inclus, hors coût GPT déjà
payé lors de la campagne commune. Aucun nouvel appel GPT pour ces tests.

| Année | Capital | Rendement | DD maximal | Entrées SHORT | Fermées gagnantes / perdantes | Taux gagnant des fermées |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 3 101,34 USD | −22,47 % | −27,16 % | 55 | 11 / 44 | 20,00 % |
| 2025 | 4 909,75 USD | +22,74 % | −13,39 % | 37 | 10 / 27 | 27,03 % |
| 2026 au 30/09 | 3 831,99 USD | −4,20 % | −23,58 % | 77 | 17 / 58 | 22,67 % |

**734 avis ne signifient pas 734 ordres** : 732 sont admissibles à J, puis les
positions déjà détenues, dates d'entrée, gaps, capital et gardes de risque limitent
les exécutions. Au total : 169 entrées, 167 positions fermées et deux ouvertes.
La sélection ne remplace pas les candidats éliminés par des titres hors TOP20.

| Année | Somme des PnL fermés positifs | Somme des PnL fermés négatifs | Latent brut de provision d'emprunt | Emprunt sur positions fermées |
| --- | ---: | ---: | ---: | ---: |
| 2024 | +1 105,66 USD | −2 004,32 USD | 0,00 USD | 4,04 USD |
| 2025 | +2 850,19 USD | −1 940,44 USD | 0,00 USD | 2,83 USD |
| 2026 au 30/09 | +3 515,52 USD | −3 742,21 USD | +58,70 USD | 5,07 USD |

Les PnL fermés intègrent déjà les coûts du rachat et l'emprunt : ne pas les
soustraire une deuxième fois. Les deux positions ouvertes de 2026 sont **APP**
(deux actions, entrée le 24 septembre) et **FICO** (une action, entrée le
30 septembre). Provision d'emprunt ouvert : 0,03005 USD, également déduite du
capital affiché. Ce latent n'est ni un gain réalisé ni un troisième trade gagnant.
Les cohortes GPT 2024/2025 sont intégralement fermées ; leur capital ne change
pas après les queues de replay prévues en début d'année suivante.

## Témoin : vendre tout le TOP20 à découvert

Même permission locale de SHORT en régime normal, mêmes coûts/protections et
contraintes ; seule l'exigence d'avis GPT BEARISH est retirée.

| Année | GPT BEARISH : rendement | Tout le TOP20 SHORT : rendement | Écart GPT, points | DD du témoin |
| --- | ---: | ---: | ---: | ---: |
| 2024 | −22,47 % | −35,89 % | +13,42 | −44,96 % |
| 2025 | +22,74 % | −26,74 % | +49,49 | −31,84 % |
| 2026 au 30/09 | −4,20 % | −32,26 % | +28,06 | −40,95 % |

Le témoin termine respectivement à 2 564,53 / 2 930,25 / 2 709,61 USD aux
bornes civiles. Quatre positions restent ouvertes à fin 2024 ; après leur
fermeture prévue, le capital de cette cohorte passe à 2 536,65 USD (−36,58 %).
Cinq positions témoins restent ouvertes au 30 septembre 2026.

**Avantage relatif observé, pas rentabilité régulière démontrée.** Le filtre
réduit les pertes et le DD dans cette variante sur trois années, mais deux années
restent négatives. Les expositions moyennes ne sont pas appariées : GPT
0,339 / 0,184 / 0,529 fois l'equity, contre témoin 0,696 / 0,150 / 0,435.
Le chemin du capital et les gardes de risque divergent aussi. Ce résultat ne
mesure donc pas un alpha de sélection à risque égal, ni un test prospectif
indépendant ; les modèles/périodes et protections ont déjà été examinés.

## Résultats avec les permissions de régime actuelles inchangées

| Année | Entrées GPT SHORT | Capital GPT | Rendement GPT | Capital témoin |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 0 | 4 000,00 USD | 0,00 % | 4 000,00 USD |
| 2025 | 5 | 3 799,94 USD | −5,00 % | 4 082,95 USD |
| 2026 au 30/09 | 0 | 4 000,00 USD | 0,00 % | 4 000,00 USD |

Les cinq positions filtrées de 2025 sont perdantes ; le témoin natif réalise
cinq entrées également, une gagnante/quatre perdantes, pour +2,07 %.
Les années sans ordre ne permettent pas d'évaluer la qualité des avis baissiers.
Ce profil natif ne confirme donc pas l'avantage de la variante recherche.
Les permissions de production sont conservées : **aucun déblocage SHORT live**.

## Réserves historiques

Les mêmes réserves que le test LONG subsistent : import/révision des news après J,
mémoire future du LLM non exclue, secteurs actuels et macro non certifiés PIT,
prix ajustés fournisseur et fills OHLC simulés. L'hypothèse d'emprunt ajoute une
réserve majeure : **un résultat positif éventuel ne prouve pas un SHORT réalisable
historiquement ou en production**. Pas de promotion live ni de déclaration de
signal robuste sur la base de ce seul test.
