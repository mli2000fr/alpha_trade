# Marge d’action d’une sortie quotidienne — Oracle × ATR LONG

## Protocole figé, 11 octobre 2026

Étape préalable au modèle global « conserver/sortir ». Aucun entraînement,
aucune nouvelle lecture SQL, aucune écriture SQL ou modification de production.
Réutiliser les snapshots corrigés de l’audit d’excursions après vérification
des empreintes. Univers archivé nettoyé de 1 790 titres, mêmes périodes 2020–
9 juillet 2024 et 2025–3 septembre 2026 ; second semestre 2024 absent.

Sélections imbriquées TOP10/TOP20/TOP50 en ordre Oracle dans Oracle TOP20 % ∩
ATR TOP20 %, avant de consulter les résultats. Tous les scénarios sont LONG,
pas une sélection rétrospective du bon sens. Aucun symbole réservé remplacé.

## Convention de gestion

Entrée ouverture ajustée J+1, SL fixe 7 % actif en permanence, sans TP.
Échéance à la clôture de la vingtième séance observée, entrée comprise, J+20.
C’est un diagnostic cohérent avec les vingt barres de l’audit précédent,
**pas la parité live avec une vente à l’ouverture J+21**.

Décision à la clôture connue, vente à l’ouverture suivante. Si cette ouverture
franchit le stop, le gap stop reste prioritaire et peut dépasser 7 % de perte.
Le stop intraday est supposé exécuté au seuil hors gaps, sans certification de
liquidité/slippage. Aucune vente à une clôture déjà utilisée pour décider.

Règles fixes, sans choix du meilleur paramètre après résultats :

- HOLD20_SL7 : référence ;
- EXIT_AFTER3/5/10 : vente après 3/5/10 clôtures, à l’ouverture suivante ;
- LOSS_AFTER3 : dès la 3e clôture, sortir si clôture sous le prix d’entrée ;
- WEAKNESS_2_CLOSES : sous l’entrée et deux baisses consécutives de clôture ;
- TRAILING_CLOSE20 : clôture <=80 % du plus haut observé depuis l’entrée,
  sortie suivante ; le SL initial n’est jamais déplacé vers le bas.

## Mesurer la marge et les concessions

Nombre de stops de référence précédés d’au moins une possibilité de vente
après une clôture et avant le stop, à une ouverture supérieure au seuil SL.
Un stop dans la séance d’entrée ne peut pas être évité par une décision quotidienne.
Un stop par gap dès la deuxième séance peut également être trop précoce.

Borne idéale séparée : meilleure ouverture réalisable après une clôture et
avant le stop de référence, ou référence si elle est meilleure. Ce choix utilise
le futur et **ne constitue jamais une stratégie**, seulement une borne de marge.

Pour chaque règle et année : couverture, rendement moyen/médian par observation,
variation face à la référence, proportion de stops évités, amélioration parmi
les stops de référence et gains sacrifiés. « Grand gagnant » : référence >=20 % ;
« conservé » : au moins 80 % de son rendement de référence conservé.

Coûts illustratifs : 10 et 25 bps aller-retour par notionnel. Ni commission de
courtier qualifiée, ni spread/slippage historique. Les mêmes coûts fixes sont
appliqués aux règles : ils ne changent donc pas le delta entre règles. Aucun
capital, sizing, contrainte de positions chevauchantes ou PnL de portefeuille.

Sensibilité séparée sans plages `high/low>=1.5`, exploratoire comme auparavant.
Univers historique et ajustements non entièrement PIT certifiés ; 2026 déjà
examiné. Ces retours unitaires ne démontrent pas la performance live.

```powershell
python -u -m scripts.research.us_oracle_daily_exit_audit --output artifacts/research/us_amplitude_rerank/daily-exit-opportunity-h20-20261011-v1
```

`progress.json` suit les lots ; reprise avec empreintes dans `done.json`.
Rapport `report.json`, `annual.parquet`, `annual_range_sensitivity.parquet`,
`decisions.parquet`. Ne pas lancer deux instances dans le même dossier.

Un modèle de sortie ne sera pas entraîné automatiquement ici. Ensuite il faudra
qualifier les features disponibles chaque jour — titre, état de position et
macro —, la disponibilité des cibles, la purge temporelle et la comparaison
hors échantillon. Une borne élevée ne signifie pas qu’un modèle pourrait la capter.

## Résultats terminés — 11 octobre 2026

46 lots terminés ; règles évaluées sur les TOP10, TOP20 et TOP50 imbriqués.
Sept tests ciblés valident la causalité des sorties et la priorité du gap stop.
Le modèle de sortie n’a pas été entraîné et aucune donnée SQL n’a été modifiée.

### Il existe une marge quotidienne, mais elle nécessite une prédiction

Sur les stops LONG de référence du TOP10 : 84,14 % en 2025 et 79,75 % en 2026
étaient précédés d’au moins une clôture permettant une sortie à une ouverture
ultérieure supérieure au stop, avant que le stop ne soit déclenché.
Ces pourcentages mesurent une **possibilité rétrospective**, pas la capacité
d’un modèle à identifier les pertes à temps. Les autres stops arrivent trop
tôt, ou par un gap ne laissant aucune ouverture protégée accessible après
la première décision quotidienne.

La borne idéale améliore la moyenne de +9,29 points en 2025 et +9,54 points
en 2026. Elle choisit les sorties grâce au futur : ne jamais la présenter
comme une performance réalisable ou comme une cible de gain promise.

### Sortir systématiquement plus tôt sacrifie les gagnants

TOP10, mêmes chemins qualifiés par année, moyenne **par observation unitaire**
avant coûts, pas performance annualisée ni portefeuille :

| Règle | Moyenne 2025 | Moyenne 2026 | Stops de référence évités 2025 / 2026 |
|---|---:|---:|---:|
| SL7, sans TP, échéance 20 | +1,49 % | +0,96 % | référence |
| Sortie après 3 clôtures | +0,46 % | +0,35 % | 51,76 % / 48,37 % |
| Sortie après 5 clôtures | +0,63 % | +0,38 % | 35,97 % / 31,06 % |
| Sortie après 10 clôtures | +0,99 % | +0,48 % | 16,59 % / 12,63 % |
| Perte après la 3e clôture | +0,94 % | +0,69 % | 44,05 % / 37,17 % |
| Deux clôtures en baisse et sous l’entrée | +1,23 % | +1,02 % | 31,77 % / 25,18 % |
| Trailing sur clôture à 20 % | +1,65 % | +1,08 % | 3,89 % / 3,26 % |

La sortie après trois clôtures réduit fortement les stops, mais ne conserve
au moins 80 % du rendement que de 2,88 % des grands gagnants de référence
en 2025 et 6,22 % en 2026. Même la règle perte après trois clôtures dégrade
la moyenne, malgré moins de stops.

La faiblesse sur deux clôtures donne un petit avantage en 2026 (+0,057 point),
mais perd 0,26 point en 2025 et est également défavorable plusieurs années
historiques. Le trailing 20 % progresse en 2025/2026, mais recule nettement
en 2020, 2021 et 2022 : aucun avantage stable à promouvoir.

### TOP20, TOP50 et réserves

Sur TOP20 et TOP50, les sorties temporelles et la règle perte après trois
clôtures restent en dessous de la référence en 2025 et 2026. La faiblesse sur
deux clôtures n’améliore pas simultanément les deux années. La conclusion
« moins de stops ne signifie pas meilleure moyenne » n’est pas spécifique au TOP10.

La sensibilité sans plages intraday `high/low >=1.5` confirme cette lecture.
Le petit avantage trailing TOP10 devient +0,055 point en 2025 et −0,017 point
en 2026 : une partie du résultat dépend de quelques chemins réservés pour revue.

Les coûts illustratifs fixes de 10 ou 25 bps diminuent chaque moyenne de
0,10 ou 0,25 point ; ils ne modifient pas les deltas entre politiques.
Ils ne représentent pas des coûts complets de portefeuille et ne permettent
pas de déduire le rendement avec capital disponible et positions simultanées.

La référence ici est **sans TP** ; son nombre de stops diffère du précédent
audit « +20 % avant −7 % », car certains gagnants y étaient sortis au TP avant
une baisse ultérieure. Ce n’est pas une contradiction entre rapports.

**Conclusion : marge d’action réelle, mais aucune règle simple gagnante stable.**
L’idée d’un modèle global de sortie reste une hypothèse légitime à tester,
pas une amélioration démontrée. Il devra éviter certaines pertes sans sacrifier
les grands gagnants, sur des features quotidiennes réellement disponibles à la
décision. La qualification PIT des features/macro et la validation chronologique
constituent la prochaine étape avant entraînement ; pas d’activation automatique.
