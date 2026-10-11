# Premier audit news/sentiment × intraday — janvier/février 2025

Audit terminé le 11 octobre 2026. Lecture SQL uniquement ; aucun appel fournisseur,
entraînement, écriture SQL ou modification du téléchargement intraday en cours.

## Périmètre figé

Univers courant `config/univers_batch/univers_filtred_tradable.txt`. Source unique
`stock_bars_intraday`, fournisseur `alpaca`, flux `alpaca_iex`, intervalle `5m`.
News `news_raw`, scores contextualisés `news_ticker_sentiment`, inférence réussie.
Pas de mélange entre IEX, SIP et EODHD.

L'instantané a été pris pendant un backfill : la couverture n'est pas définitive.

| Mois | Barres disponibles | Titres avec barres | Dates avec barres |
|---|---:|---:|---:|
| Janvier 2025 | 1 593 066 | 1 672 | 20 |
| Février 2025 | 551 611 | 552 | 19 |

Il y a 24 192 lignes article/symbole scorées dans l'extraction et 7 706 événements
avec au moins une fenêtre valide. Une cohorte commune de **552 titres** possède
au moins dix dates avec barres régulières valides dans chacun des deux mois.
Cela ne certifie pas leur couverture complète. L'univers courant implique un
biais de survivance ; les radiés ne sont pas reconstitués par cette expérience.

## Protocole fixé avant calcul

- Seuil strict **> 0,90**, sans calibration sur le résultat.
- Événement = symbole × heure de publication. Les articles au même instant sont
  regroupés. Positive-only, negative-only, mixte, ou aucun score fort ; un score
  >0,90 n'est pas une probabilité de hausse/baisse.
- Les heures exactement minuit UTC sont exclues des vues horodatées : possibilité
  de dates seules. Cela ne prouve pas que les autres heures sont toutes exactes.
- Pendant la séance : entrée à l'ouverture de la barre située à l'arrondi supérieur
  de publication au pas 5 minutes, **plus cinq minutes**. Délai de 5 à 10 minutes.
  La barre contenant la news n'est donc pas utilisée comme rendement post-news.
- Sortie au close de la dernière barre entièrement terminée, après 5, 15, 30 ou
  60 minutes depuis cette entrée. Les horizons ne partagent pas tous le même
  échantillon, car les fenêtres longues sont plus souvent incomplètes.
- Une fenêtre exige toutes ses barres successives, volume positif, OHLC cohérents,
  prix bruts et séance régulière. Aucun forward-fill, prix inventé ou rendement
  traversant la fermeture n'est permis.
- Avant ouverture : étude secondaire depuis l'open de la séance, pas depuis
  l'heure de publication ni depuis la clôture précédente. Plusieurs publications
  d'un même titre peuvent partager cette fenêtre : observations non indépendantes.
- Sensibilité : aucun autre article **scoré** du symbole dans la fenêtre de 30
  minutes. Ce n'est pas la preuve de l'absence de toutes les news.
- Le groupe sans score fort est une référence descriptive parmi les titres avec
  news, pas une baseline appariée marché/secteur/volatilité.

## Résultat principal : publications pendant la séance

Cohorte commune des 552 titres, rendements moyens à 30 minutes après l'entrée,
sans coûts. `n` = événements avec cette fenêtre, pas titres distincts.

| Mois | Sentiment | n | Rendement moyen | Médiane | Proportion de hausse |
|---|---|---:|---:|---:|---:|
| Janvier | Très positif uniquement | 122 | +0,088 % | +0,046 % | 56,6 % |
| Janvier | Très négatif uniquement | 92 | +0,069 % | +0,114 % | 60,9 % |
| Janvier | Aucun score fort | 395 | +0,079 % | +0,052 % | 56,2 % |
| Février | Très positif uniquement | 107 | −0,028 % | +0,014 % | 52,3 % |
| Février | Très négatif uniquement | 125 | +0,013 % | −0,078 % | 43,2 % |
| Février | Aucun score fort | 450 | −0,041 % | +0,021 % | 52,0 % |

Les prix inchangés sont conservés : complément de la proportion de hausse ne
signifie pas automatiquement proportion de baisse.

À 60 minutes : positifs +0,099 % en janvier et −0,070 % en février ; négatifs
−0,047 % et −0,017 %. Moyennes, médianes et taux de hausse ne racontent pas
toujours la même histoire : asymétrie et valeurs extrêmes.

Sur tout le périmètre disponible, et non la cohorte commune, les positifs à
30 minutes sont −0,011 % en janvier et −0,028 % en février ; négatifs +0,044 %
et +0,013 %. Le changement de périmètre modifie sensiblement le résultat.

### Sans autre news scorée dans la fenêtre de 30 minutes

Sur la cohorte commune : positifs +0,104 % (n=112) en janvier, +0,001 % (n=97)
en février ; négatifs +0,087 % (n=83) en janvier, −0,116 % (n=117) en février.
Cette sensibilité donne une orientation différente en février, mais ne confirme
pas une règle stable sur les deux mois. Il ne faut pas sélectionner après coup
uniquement la variante ou le mois favorable.

## News avant ouverture

Sur la cohorte commune, à 60 minutes depuis l'open :

- janvier : positifs +0,292 %, négatifs −0,113 % ;
- février : positifs −0,418 %, négatifs −0,913 %.

La moyenne journalière équipondérée des positifs de janvier est pourtant
**−0,113 %** : la moyenne par événement +0,292 % est donc fragile. Publications
répétées, concentrations et effets marché rendent cette vue secondaire moins
interprétable. Un prix réagit souvent déjà avant ouverture ; cet audit ne mesure
pas ce gap en mélangeant intraday brut et clôture journalière ajustée.

## Disponibilité PIT et limites

**0 événement** possède des métadonnées courantes de news/sentiment disponibles
avant l'entrée simulée. Le diagnostic utilise `GREATEST(updated_at news,
updated_at sentiment)` : ce n'est pas un historique immuable de première
disponibilité. Il ne prouve pas que les news n'existaient pas, mais ne permet pas
de certifier qu'Alpha Trade connaissait ces scores en janvier/février 2025.

L'audit est donc **rétrospectif descriptif**, pas un backtest tradable. Il ne
mesure ni causalité, ni rendement net, ni capacité à sélectionner D1/D10 à H20.
Les news peuvent commenter une variation déjà commencée. Les pré-tendances sont
calculées à titre descriptif, mais aucun contrôle causal n'est effectué.

IEX représente une seule place : volumes partiels, trous et prix propres à ce
flux. Les fenêtres strictes favorisent les titres liquides. Les observations
peuvent se chevaucher ; pas d'intervalle de confiance ou de significativité
indépendante établi ici. Les mouvements les plus élevés à 60 minutes vont
d'environ −11,6 % à +15,0 % ; ils ne constituent pas une qualification des prix.

## Conclusion et prochaine action

**Pas de signal post-publication stable démontré sur ces deux mois.** La forte
association quotidienne sentiment/prix ne se transforme pas ici en hausse
systématique après lecture d'une news positive ni baisse après une négative.
Ce premier audit n'épuise pas la piste : il peut manquer la réaction des toutes
premières minutes, volontairement exclues par le délai conservateur.

Une fois le backfill terminé, relancer un audit sous un **nouveau répertoire**
pour compléter février et les autres mois. Comparer des cohortes cohérentes,
agréger les news pré-ouverture par titre/séance pour éviter les fenêtres répétées,
examiner les pré-tendances, puis les rendements relatifs marché/secteur. Pour
un vrai test d'entrée sur news, il faudra des preuves de disponibilité prospective
et des coûts/quotes ; aucune promotion en production sur ces chiffres.

## Traçabilité

- Script : `scripts/research/us_news_intraday_audit.py` ; trois tests passent.
- Résultats : `artifacts/research/us_news_intraday/jan-feb-2025-20261011-v1/`.
- `protocol.json`, `report.json`, `progress.json` : protocole, résultats, état.
- `news_snapshot.parquet`, `bars_snapshot.parquet` : extraction figée, empreintes
  conservées dans le rapport ; `event_returns.parquet` : événements et fenêtres.

```powershell
python -u -m scripts.research.us_news_intraday_audit --output-dir artifacts/research/us_news_intraday/jan-feb-2025-nouveau-passage
```

Ne pas réutiliser un répertoire de résultats déjà remis pour un autre instantané.
