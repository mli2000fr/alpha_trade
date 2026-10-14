# News après entrée : confirmation et sortie au prochain open

GO utilisateur et calcul achevé le **14 octobre 2026**.
Référence : `artifacts/research/us_news_post_entry_exit/20261014-v1/report.json`.
**12 cas terminés, sources vérifiées, aucune promotion.**

## Question et verdict

Les news reçues après l'achat peuvent-elles confirmer la conservation d'un
LONG ou aider à sortir avant une perte ? On teste une hypothèse distincte de
l'ancienne association sentiment J / excursion H0…H20.

La règle de sortie négative **ne démontre pas de gain stable** : elle dégrade
tous les TOPs en 2025, améliore modestement TOP20/TOP50 en 2026 mais pas TOP10.
Les news positives ne confirment pas non plus régulièrement qu'il vaut mieux
conserver : les petits effets changent entre les deux années.
Ces données sont des versions actuelles de sentiments historiques, non des
preuves immuables de scores connus à l'époque. Aucun modèle de sortie entraîné.

## Baseline et comparaison

Baseline : dernier Oracle **parcours d'amplitude LightGBM**, campagne économique
`us_oracle_path_economic/20261013-v1`, pas l'ancien Oracle terminal ou LONG/SHORT.
Les modèles, scores et classements ne sont pas recalculés.

- TOP10 primaire ; TOP20/TOP50 secondaires, LONG uniquement.
- Années de décision 2025 et 2026 jusqu'au **2 septembre** ; queues de sortie
  jusqu'au 2 février 2026 / 2 octobre 2026. Capital initial **4 000 USD** par cas.
- **Mêmes entrées effectivement exécutées, mêmes dates, fills, quantités et
  coûts d'entrée**. Pas de nouvelle sélection ou de sizing après les news.
- TP20 %, SL10 % dur, sans trailing, expiration native après vingt séances.
- Capital libéré **non réinvesti**. C'est un test marginal à entrées figées,
  **pas un rerun du risque/circuit breaker après modification de l'equity**,
  ni une stratégie de réentrées exploitant les slots libérés.

Les six courbes sans modification reproduisent intégralement l'equity du moteur
archivé. Les coûts de sortie reproduisent les proceeds de chaque trade natif,
puis sont recalculés au nouvel open avec le même modèle commission/slippage/
spread et ADV20 connu la veille. Pas de coût inféré d'un futur fill.
Tous les comptes restent en cash positif : pas de financement supplémentaire
inventé. Les cas avec fractions/conversion/financement ou legs multiples non
adaptés auraient été bloqués, pas exclus silencieusement ; les six cas n'en ont pas.

## Information disponible et règle figée

367 851 observations article/titre locales dédupliquées. Aucun téléchargement,
SQL, API LLM ou ordre courtier. Source : `news_raw` / `news_ticker_sentiment`
archivées lors du précédent audit, univers de la baseline de 1 790 titres.

À chaque clôture sur une position survivante :

1. Retenir uniquement les nouvelles publications depuis la précédente clôture,
   **postérieures ou égales à l'ouverture effective de l'entrée**. Les articles
   avant l'achat ne sont pas une confirmation post-entrée.
2. Tous les articles scorés de cette fenêtre doivent avoir `negative_score >0,9`
   pour une décision de sortie ; au moins un article. Pas de maximum parmi une
   journée d'articles contradictoires. Seuil 0,9 et scores invalides exclus.
3. Tous positifs >0,9 : signal de conservation ; mixte/autre/aucun : pas de
   nouvelle décision. Un positif **ne repousse ni n'annule le stop**.
4. Une publication après clôture ou le week-end attend la clôture suivante.
   Exactement à l'heure de clôture : décision suivante, pas connaissance anticipée.
   Les 688 publications minuit ambiguës sont exclues des vues horodatées.
5. Première fenêtre négative admissible : liquidation complète **au prochain
   open**, pas au prix historique favorable choisi dans la séance.

Priorités : stop/TP déjà consommés intraday → position absente ; à l'open suivant,
expiration, liquidation de régime et protections gap sont prioritaires. Si ces
protections clôturent déjà le lot, la news ne crée pas une deuxième vente.
Une news négative peut sortir à l'open avant un stop intraday **ultérieur**, jamais
révoquer un stop déclenché avant réception. Le cas réel n'a aucun conflit de
priorité à l'open ; les tests synthétiques couvrent les courses.

## Comparaison économique exploratoire, coûts inclus

Les rendements portent sur les cohortes closes, pas seulement l'année civile.

| Année | TOP | Capital baseline $ | Capital sortie news $ | Rendement baseline → news | Écart net $ | Sorties modifiées |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| 2025 | 10 | 3 778,27 | 3 732,30 | −5,54 % → −6,69 % | −45,96 | 24 |
| 2025 | 20 | 3 820,51 | 3 748,07 | −4,49 % → −6,30 % | −72,45 | 20 |
| 2025 | 50 | 3 880,77 | 3 648,05 | −2,98 % → −8,80 % | −232,72 | 27 |
| 2026 partiel | 10 | 4 369,39 | 4 359,77 | +9,23 % → +8,99 % | −9,63 | 26 |
| 2026 partiel | 20 | 4 417,79 | 4 473,11 | +10,44 % → +11,83 % | +55,32 | 31 |
| 2026 partiel | 50 | 4 360,50 | 4 417,39 | +9,01 % → +10,43 % | +56,88 | 32 |

TOP10 : gagnants **38,17 % → 39,69 %** en 2025 et **38,00 % → 40,00 %** en
2026, mais le capital final baisse dans les deux cas. Un meilleur taux gagnant
ne suffit donc pas. DD maximal TOP10 **−18,26 % → −18,60 %** en 2025,
**−9,99 % → −9,75 %** en 2026. Les gains sacrifiés compensent ou dépassent
les pertes évitées. Les gains/pertes en dollars, gagnants/perdants et courbes
quotidiennes sont conservés pour les six scénarios.

## Les news confirment-elles de conserver ?

Diagnostic : avantage net de conserver jusqu'à la **sortie native réelle**,
comparé à sortir au prochain open. Ce n'est ni P(D10), ni P(hausse à H20),
ni une cible illimitée permettant un rebond après SL.

Tous les états quotidiens sont ceux des **positions de la baseline**. Pour la
vue descriptive, ils peuvent continuer après la date où le scénario news aurait
vendu ; ils ne sont pas utilisés comme nouvelles décisions de ce scénario.
Les répétitions ne comptent pas comme autant de trades indépendants. Vue primaire :
**premier signal fort, positif ou négatif, par trade**, choisi sans son résultat futur.

| TOP10 / premier signal fort | N 2025 | Conserver mieux, 2025 | N 2026 | Conserver mieux, 2026 |
| --- | ---: | ---: | ---: | ---: |
| Positif | 12 | 41,67 % | 15 | 53,33 % |
| Négatif | 22 | 40,91 % | 24 | 45,83 % |

Les corpus sont petits et chevauchants. L'avantage moyen de conserver après
première news positive vaut **−0,97 point** en 2025 et **+0,56 point** en 2026.
Après news négative, quelques grands gagnants conservés font que la moyenne
peut rester positive malgré une médiane négative : ne pas confondre fréquence
d'éviction utile et montant net gagné.

Contrôle descriptif de l'état déjà visible : témoins sans signal fort dans le
même **mois × tranche de PnL courant × tranche d'âge**, au moins cinq états
témoins. Tranches PnL [−∞,−5,0,5,10,+∞), âges 0–4/5–9/10–19, fixées avant
résultats. Pour TOP10/positif, l'écart moyen contre ces témoins passe de
**−3,08 points sur sept événements** en 2025 à **+0,74 point sur quatorze** en
2026. Pas de stabilité démontrée ; appariement grossier, pas preuve causale,
pas de p-value ou intervalle fabriqué sur de nombreuses lignes dépendantes.

## Réserve de disponibilité

Deuxième scénario séparé : une news n'entre dans la décision qu'après le maximum
de publication et dernières mises à jour archivées, au plus tard avant la clôture.
**Zéro signal fort sur les états détenus 2025–2026 ; zéro sortie modifiée** : les
six courbes reproduisent la baseline. Ce diagnostic ne prouve pas que les articles
n'existaient pas ; il ne permet pas de certifier les scores historiques comme PIT.
On ne rétrodate pas le scoring et on ne remplace pas les dates par des heures supposées.

Source de survivorship actuelle, ajustements prix rétrospectifs, secteurs actuels
et macro non certifiés hérités de la baseline. Univers pas intégralement tradable
historiquement démontré. Données news partielles, biais prix→commentaire et
années déjà explorées ; aucun holdout vierge ni garantie d'exécution broker.

## Reproduction et suites

```powershell
python -u -m scripts.research.us_news_post_entry_exit_audit --output artifacts/research/us_news_post_entry_exit/NOUVEL-ID
```

Fichiers : `protocol.json`, `input-manifest.json`, `report.json`, `progress.json` ;
par cas `states.parquet`, `daily.parquet`, `orders.json`, `report.json`.
Lock exclusif et refus d'écraser un protocole ; hashes vérifiés avant/après.
Les décisions de vente, performances et données de diagnostic restent auditablement
séparées. Aucun modèle, batch, table SQL ou service de production modifié.

**Clôture bornée : pas de promotion de cette règle et pas de recherche de seuil
optimal sur ces mêmes pertes.** Une prochaine validation exploitable demanderait
des news/scores prospectifs versionnés et réellement disponibles avant décision,
puis une nouvelle période et un replay complet des risques/entrées si la règle passe.
