# Étude d’opportunité — Extension d’α-Trade au marché actions chinois

**Objet :** Évaluer l’intérêt de développer une déclinaison d’α-Trade sur le marché chinois et déterminer les fournisseurs de données adaptés à un POC.  
**Marché cible :** Actions A chinoises — Shanghai, Shenzhen et Beijing.  
**Horizon :** Swing trading — principalement H5 / H10 / H15 / H20.  
**Besoin temps réel :** Non prioritaire.  
**Architecture actuelle :** Oracle Extreme → modèle LONG dédié → modèle SHORT dédié.  
**Recommandation initiale :** Tushare Pro pour le POC, puis évaluation de RQData en complément si les premiers résultats valident l’intérêt des nouvelles données directionnelles.

---

# 1. Executive Summary

α-Trade est actuellement un système quantitatif/ML développé principalement sur les actions américaines.

L’architecture actuelle ne repose plus sur un modèle global de ranking directionnel. Elle est désormais spécialisée en plusieurs étapes :

```text
                         UNIVERS ACTIONS
                                │
                                ▼
                    ┌───────────────────────┐
                    │   ORACLE EXTREME      │
                    │                       │
                    │ P(mouvement extrême)  │
                    └───────────┬───────────┘
                                │
                                ▼
                     CANDIDATS EXTRÊMES
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
          ┌─────────────────┐     ┌─────────────────┐
          │  MODÈLE LONG    │     │  MODÈLE SHORT   │
          │    dédié        │     │     dédié       │
          └────────┬────────┘     └────────┬────────┘
                   │                       │
                   ▼                       ▼
               P(LONG)                 P(SHORT)
                   │                       │
                   └───────────┬───────────┘
                               ▼
                        Portfolio Engine
```

L’Oracle Extreme a pour rôle de détecter les actions susceptibles de connaître un mouvement important, indépendamment de la direction.

Conceptuellement :

```text
P(extreme) = P(D1 ∪ D10)
```

avec :

```text
D1  = bottom 10 % des rendements futurs
D10 = top 10 % des rendements futurs
```

Les modèles LONG et SHORT tentent ensuite de répondre respectivement à :

```text
P(D10 | extreme)

et

P(D1 | extreme)
```

La problématique actuelle est donc précise :

> **L’Oracle Extreme identifie relativement bien les futurs mouvements importants, mais les modèles LONG et SHORT ont encore du mal à séparer suffisamment les futurs D10 des futurs D1.**

Les analyses réalisées montrent notamment que la population ayant une forte `proba_extreme` contient simultanément une proportion importante de futurs TOP performers et de futurs BOTTOM performers.

Le modèle sait donc relativement bien répondre à :

> « cette action va probablement beaucoup bouger »

mais moins bien à :

> « cette action va beaucoup monter »

ou :

> « cette action va beaucoup baisser ».

L’hypothèse principale étudiée ici est que cette difficulté n’est pas nécessairement due uniquement au choix de l’algorithme ML, mais potentiellement à un manque d’informations réellement directionnelles dans les données utilisées.

Les données actuellement disponibles décrivent déjà bien :

- le prix ;
- le volume ;
- le momentum ;
- la volatilité ;
- la valorisation ;
- les fondamentaux ;
- les facteurs de marché ;
- les relations cross-sectionnelles ;
- le beta/CAPM ;
- les régimes de marché.

En revanche, elles décrivent moins directement :

- qui achète ;
- qui vend ;
- l’évolution des gros flux ;
- l’utilisation du levier ;
- l’activité de short/lending ;
- les changements d’anticipations ;
- les révisions de bénéfices ;
- les changements de consensus ;
- les changements de rating et de target price.

Ces familles d’informations sont précisément celles qui pourraient enrichir les modèles LONG et SHORT.

Le marché chinois est intéressant car plusieurs fournisseurs locaux mettent à disposition des données de ce type à un coût souvent beaucoup plus accessible que les fournisseurs institutionnels équivalents sur le marché américain.

La recommandation est donc progressive :

```text
PHASE 1
Tushare Pro
      │
      ▼
POC A-shares
      │
      ▼
Tester l’apport des nouvelles
données directionnelles
      │
      ├── échec ─────► ne pas investir davantage
      │
      ▼
    succès
      │
      ▼
PHASE 2
Évaluer RQData
      │
      ▼
Consensus / analystes /
PIT supplémentaires
      │
      ▼
α-Trade China V2
```

L’objectif du POC est de répondre à une question simple :

> **En conservant l’architecture Oracle Extreme → LONG Model / SHORT Model, l’ajout de données de flux, de positionnement et d’anticipations améliore-t-il significativement la purification directionnelle des candidats extrêmes ?**

---

# 2. Architecture actuelle d’α-Trade

## 2.1 Univers actuel

α-Trade travaille aujourd’hui principalement sur plusieurs centaines d’actions américaines.

Les horizons utilisés sont notamment :

```text
H3
H5
H10
H15
H20
```

Pour le swing trading, les horizons les plus importants sont :

```text
H5  ≈ 1 semaine
H10 ≈ 2 semaines
H15 ≈ 3 semaines
H20 ≈ 1 mois
```

Cette caractéristique a une conséquence importante :

> **le système n’a pas besoin en priorité de tick data, de Level 2 ou de temps réel à la milliseconde.**

Pour le POC Chine, il est donc préférable d’investir dans des données historiques daily plus riches.

---

# 3. Architecture ML actuelle réelle

L’architecture peut être simplifiée ainsi :

```text
                    DONNÉES DISPONIBLES
                            │
                            ▼
                       Feature Store
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
        OHLCV          Fundamentals       Market /
                                           Technical
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                            ▼
                   ┌───────────────────┐
                   │  ORACLE EXTREME   │
                   └─────────┬─────────┘
                             │
                      Extreme Candidates
                             │
                 ┌───────────┴───────────┐
                 │                       │
                 ▼                       ▼
           LONG MODEL               SHORT MODEL
                 │                       │
                 ▼                       ▼
             P(LONG)                  P(SHORT)
                 │                       │
                 └───────────┬───────────┘
                             ▼
                       Trade Selection
```

Le système sépare donc déjà deux problèmes :

```text
1. Détection d’un mouvement extrême
2. Détermination de la direction
```

C’est un point essentiel.

---

# 4. Rôle de l’Oracle Extreme

L’Oracle Extreme ne cherche pas directement la direction.

Il cherche les actions ayant une forte probabilité de finir dans un décile extrême de rendement futur.

Conceptuellement :

```text
                   Toutes les actions
                          │
                          ▼
                   ORACLE EXTREME
                          │
                          ▼
                P(D1 ou D10 élevé)
                          │
                          ▼
                 candidats extrêmes
```

Sa fonction est donc proche de :

```text
P(extreme)
```

et non :

```text
P(up)
```

ou :

```text
P(down)
```

L’Oracle Extreme agit comme un détecteur de situations intéressantes.

---

# 5. Problématique actuelle : Extreme ≠ Direction

Une analyse sur environ **28 921 picks top 10 % de `proba_extreme`** avait donné approximativement :

| Décile réalisé | Part des picks | Rendement moyen si LONG |
|---|---:|---:|
| D1 — bottom 10 % | 22,8 % | -19,44 % |
| D2–D9 | 53,4 % | ≈ 0 % |
| D10 — top 10 % | 23,8 % | +28,32 % |
| D1 + D10 | 46,6 % | mouvement extrême |

Cela montre que l’Oracle Extreme trouve réellement une concentration élevée de mouvements importants.

Mais ces mouvements sont presque symétriquement répartis entre :

```text
D1  ≈ forte baisse
D10 ≈ forte hausse
```

La vraie difficulté devient donc :

```text
                     Oracle Extreme
                          efficace
                             │
                             ▼
                 candidats extrêmes
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
               D1                        D10
         forte baisse               forte hausse
                │                         │
                └────────────┬────────────┘
                             │
                      difficulté actuelle
                             │
                             ▼
                   LONG / SHORT models
```

L’enjeu n’est plus d’inventer une séparation Extreme/Direction : elle existe déjà.

L’enjeu est de rendre les deux modèles directionnels suffisamment discriminants.

---

# 6. Modèle LONG dédié

Le modèle LONG tente de répondre à :

```text
P(D10 | extreme)
```

Son objectif est de conserver le maximum de futurs D10 tout en éliminant les futurs D1.

Conceptuellement :

```text
Oracle Extreme élevé
        +
Directional LONG evidence
        │
        ▼
      LONG
```

Le modèle LONG doit donc apprendre les configurations qui annoncent un mouvement extrême vers le haut.

---

# 7. Modèle SHORT dédié

Le modèle SHORT tente de répondre à :

```text
P(D1 | extreme)
```

Il doit identifier les configurations qui annoncent un mouvement extrême vers le bas.

Conceptuellement :

```text
Oracle Extreme élevé
        +
Directional SHORT evidence
        │
        ▼
      SHORT
```

Il est pertinent de conserver deux modèles distincts car les mécanismes haussiers et baissiers peuvent être asymétriques.

---

# 8. Pourquoi les données actuelles peuvent atteindre une limite

Une part importante des features disponibles reste dérivée directement ou indirectement du prix.

Exemples :

```text
Prix
 │
 ├── RSI
 ├── MACD
 ├── EMA20
 ├── EMA50
 ├── momentum
 ├── ATR
 ├── volatility
 └── relative strength
```

Ces variables sont utiles, mais elles ne représentent pas nécessairement autant de sources d’information indépendantes qu’il y a de colonnes.

Le modèle peut disposer de beaucoup de features sans pour autant disposer de beaucoup de nouvelles informations économiques.

Le ML peut exploiter l’information présente.

Il ne peut pas créer une information qui n’existe pas dans les données.

---

# 9. Hypothèse : manque de données réellement directionnelles

Les modèles LONG et SHORT gagneraient potentiellement à connaître davantage d’informations sur :

```text
QUI achète ?
QUI vend ?

les gros investisseurs accumulent-ils ?

les gros investisseurs distribuent-ils ?

le levier long augmente-t-il ?

l’activité short augmente-t-elle ?

les analystes révisent-ils leurs estimations ?

les prévisions de bénéfices progressent-elles ?

le consensus se dégrade-t-il ?

les target prices montent-ils ou baissent-ils ?
```

Ces informations sont beaucoup plus proches du mécanisme économique qui précède un mouvement de prix.

Schématiquement :

```text
           INFORMATION NOUVELLE
                    │
                    ▼
            changement d’attente
                    │
                    ▼
             décision investisseur
                    │
                    ▼
               achat / vente
                    │
                    ▼
               mouvement prix
```

Alors que beaucoup d’indicateurs techniques interviennent plutôt après :

```text
mouvement prix
      │
      ▼
RSI / MACD / Momentum
```

---

# 10. Pourquoi tester cette hypothèse en Chine

Sur le marché américain, plusieurs données directionnelles intéressantes sont disponibles chez :

```text
FactSet
LSEG
Zacks
Intrinio
CBOE
Nasdaq
RavenPack
etc.
```

Mais leur coût peut devenir rapidement important.

Le marché chinois constitue donc un laboratoire intéressant car plusieurs fournisseurs quant locaux donnent accès à :

- Money Flow ;
- flux par taille d’ordre ;
- margin financing ;
- securities lending ;
- fondamentaux ;
- événements ;
- earnings forecasts ;
- analyst consensus ;
- target prices ;
- ratings ;
- données PIT.

Cela permet de tester l’hypothèse à moindre coût avant d’envisager éventuellement des achats de données similaires sur le marché US.

---

# 11. Fournisseurs chinois à considérer

Les deux fournisseurs principaux à examiner sont :

```text
1. Tushare Pro

2. Ricequant / RQData
```

Wind peut également être considéré dans un contexte institutionnel plus avancé, mais il est probablement surdimensionné pour le POC.

---

# 12. Recommandation initiale : Tushare Pro

Tushare est recommandé pour la Phase 1 car il permet d’accéder à plusieurs familles de données intéressantes avec un coût relativement faible.

Son intérêt principal est le rapport :

```text
couverture
+
historique
+
API Python
+
datasets spécifiques Chine
+
coût
```

---

# 13. Marchés couverts

Pour le POC :

```text
Shanghai Stock Exchange
Shenzhen Stock Exchange
Beijing Stock Exchange
```

L’univers recommandé au départ est principalement celui des A-shares liquides de Shanghai et Shenzhen.

---

# 14. Données OHLCV

Tushare permet de récupérer notamment :

```text
open
high
low
close
pre_close
change
pct_change
volume
amount
```

Ces données permettent de reconstruire la majorité des indicateurs techniques déjà utilisés par α-Trade.

---

# 15. Corporate Actions

Il faut également récupérer :

```text
adjustment factors
dividendes
splits
changements de capital
droits
```

afin d’éviter les erreurs de backtest sur les séries historiques.

---

# 16. Money Flow

C’est probablement l’une des familles les plus intéressantes pour le POC.

Tushare fournit des flux ventilés par taille d’ordre :

```text
BUY
 │
 ├── Small
 ├── Medium
 ├── Large
 └── Extra Large

SELL
 │
 ├── Small
 ├── Medium
 ├── Large
 └── Extra Large
```

Cela permet de mesurer les différences entre petits investisseurs et gros ordres.

---

# 17. Features Money Flow envisageables

Exemples :

```text
large_buy_ratio
large_sell_ratio

large_net_flow
extra_large_net_flow

large_flow_acceleration_5d
large_flow_acceleration_20d

small_net_flow
medium_net_flow

large_vs_small_flow

net_flow_1d
net_flow_5d
net_flow_10d
net_flow_20d
```

Normalisation utile :

```text
large_flow / market_cap

large_flow / volume

net_flow / turnover
```

---

# 18. Divergence prix / flux

Une feature particulièrement intéressante :

```text
                PRICE
                  │
           ┌──────┴──────┐
           ↓             ↓
          UP            DOWN

FLOW ↑  confirmation   accumulation ?

FLOW ↓  distribution ? confirmation
```

Exemple :

```text
Price 5d = -6 %
Large order net flow = fortement positif
```

peut représenter une accumulation.

Alors que :

```text
Price 5d = -6 %
Large order net flow = fortement négatif
```

peut confirmer une pression vendeuse.

---

# 19. Intérêt pour le modèle LONG

Les features potentielles pour LONG pourraient inclure :

```text
large_buy_net_flow
extra_large_buy_net_flow

large_flow_acceleration_5d
large_flow_acceleration_20d

large_vs_small_flow

margin_purchase_change

margin_balance_change

positive_earnings_revision

positive_forecast_change

positive_profit_revision

positive_revenue_revision
```

L’objectif est de détecter :

```text
accumulation
+
amélioration des anticipations
+
augmentation du financement long
+
Oracle Extreme élevé
```

---

# 20. Intérêt pour le modèle SHORT

Les features SHORT peuvent être différentes :

```text
large_sell_net_flow
extra_large_sell_net_flow

large_outflow_acceleration

distribution_vs_small_buying

securities_lending_change

short_activity_change

negative_earnings_revision

negative_profit_forecast

negative_revenue_revision
```

Cela permet de conserver l’asymétrie LONG/SHORT.

---

# 21. Margin Financing

Exemples de données :

```text
margin_balance
margin_purchase
margin_repayment
```

Features possibles :

```text
margin_balance_change_1d
margin_balance_change_5d
margin_balance_change_20d

margin_purchase_acceleration
```

Ces variables peuvent servir de proxy de l’évolution du levier long.

---

# 22. Securities Lending / Short Activity

Selon les titres et la couverture :

```text
short_balance
short_quantity
short_sell_change
short_repayment
```

Features :

```text
short_balance_change_5d
short_balance_change_20d

short_sell_acceleration
```

---

# 23. Fondamentaux

Il faut également conserver les familles déjà présentes dans α-Trade :

```text
Income Statement
Balance Sheet
Cash Flow Statement
```

ainsi que :

```text
ROE
ROA
gross margin
net margin

revenue growth
profit growth

debt ratios
cash flow

PE
PB
PS
market cap
```

---

# 24. Données d’événements

À intégrer :

```text
earnings announcements
earnings forecasts
dividend announcements
financial publication dates
```

Le moment où l’information devient disponible est aussi important que la valeur elle-même.

---

# 25. Importance du Point-In-Time

Exemple :

```text
résultat Q1 connu économiquement au 31 mars
mais publié le 30 avril
```

Un modèle au 15 avril ne doit pas voir cette information.

Il faut donc stocker autant que possible :

```text
effective_date
publication_date
available_at
```

L’architecture doit raisonner en information disponible à la date D.

---

# 26. Risque de look-ahead bias

Sans gestion PIT :

```text
backtest
  │
  ▼
utilise une information future
  │
  ▼
performance artificiellement élevée
```

C’est particulièrement critique pour :

```text
financials
forecasts
consensus
ratings
corporate events
```

---

# 27. Deuxième fournisseur potentiel : RQData

RQData est particulièrement intéressant si le POC Tushare confirme que les données directionnelles apportent de la valeur.

Ses avantages principaux concernent notamment :

```text
PIT financials

analyst consensus

earnings estimates

target prices

ratings

options data

alternative datasets
```

---

# 28. Pourquoi ne pas prendre RQData immédiatement

Parce que le premier objectif n’est pas de maximiser immédiatement la couverture.

Il faut d’abord répondre à :

> Les nouvelles familles de données apportent-elles réellement une information directionnelle ?

La démarche est donc :

```text
Tushare
   │
   ▼
Flow
Margin
Lending
Events
   │
   ▼
Ablation tests
   │
   ▼
Gain directionnel ?
   │
 ┌─┴───────────────┐
 │                 │
NON               OUI
 │                 │
 ▼                 ▼
STOP / revoir      tester RQData
                   │
                   ▼
          Consensus / revisions
```

---

# 29. Intérêt des données analystes

Si Phase 1 réussit, RQData peut permettre de construire :

```text
EPS consensus
revenue consensus
net income consensus

target price
analyst rating
```

mais surtout leurs variations :

```text
EPS_revision_7d
EPS_revision_30d
EPS_revision_90d

target_price_revision

rating_upgrade
rating_downgrade

positive_revision_count
negative_revision_count

revision_breadth
```

---

# 30. Pourquoi la variation est souvent plus intéressante que le niveau

Exemple :

```text
Consensus EPS = 10
```

est moins informatif que :

```text
J-30 = 8.5
J-20 = 9.0
J-10 = 9.6
J0   = 10.0
```

qui traduit :

```text
révisions positives persistantes
```

À l’inverse :

```text
10.0 → 9.5 → 8.7 → 7.9
```

indique une détérioration des attentes.

---

# 31. Architecture cible α-Trade China V1

```text
                           TUSHARE
                              │
       ┌──────────────────────┼────────────────────────┐
       │                      │                        │
       ▼                      ▼                        ▼
     OHLCV                 Money Flow              Margin
       │             Small / Medium / Large           │
       │                    / XL                      │
       │                      │                        │
       ├──────────────────────┼────────────────────────┤
       │                      │                        │
       ▼                      ▼                        ▼
 Fundamentals            Lending / Short             Events
       │                      │                        │
       └──────────────────────┼────────────────────────┘
                              │
                              ▼
                        PIT Feature Store
                              │
                              ▼
                     ┌──────────────────┐
                     │  ORACLE EXTREME  │
                     └────────┬─────────┘
                              │
                      Extreme Candidates
                              │
                  ┌───────────┴───────────┐
                  │                       │
                  ▼                       ▼
          ┌───────────────┐       ┌───────────────┐
          │  LONG MODEL   │       │  SHORT MODEL  │
          │               │       │               │
          │ P(D10|extreme)│       │ P(D1|extreme) │
          └───────┬───────┘       └───────┬───────┘
                  │                       │
                  ▼                       ▼
              LONG score             SHORT score
                  │                       │
                  └───────────┬───────────┘
                              ▼
                         Trade Engine
```

---

# 32. Architecture cible V2 avec RQData

```text
                         α-TRADE CHINA
                               │
             ┌─────────────────┴─────────────────┐
             │                                   │
          TUSHARE                             RQDATA
             │                                   │
     ┌───────┼────────┐                ┌─────────┼─────────┐
     │       │        │                │         │         │
   OHLCV   FLOW    MARGIN           Consensus   EPS     Ratings
     │       │        │                │         │         │
     └───────┴────────┘                └─────────┴─────────┘
             │                                   │
             └─────────────────┬─────────────────┘
                               │
                               ▼
                         PIT Feature Store
                               │
                               ▼
                         Oracle Extreme
                               │
                               ▼
                      Extreme Candidates
                               │
                   ┌───────────┴───────────┐
                   │                       │
                   ▼                       ▼
             LONG Model              SHORT Model
```

---

# 33. Univers recommandé pour le POC

Ne pas commencer avec toutes les A-shares.

Univers conseillé :

```text
500 à 1 000 actions
```

sélectionnées sur des critères PIT de :

```text
liquidité
volume
turnover
market cap
ancienneté de cotation
tradabilité
```

---

# 34. Survivorship Bias

Il ne faut pas construire l’univers historique à partir des titres actuels.

Erreur typique :

```text
prendre les 1000 plus grosses actions de 2026
et les backtester depuis 2015
```

Cela introduit un biais de survivants.

Il faut reconstruire :

```text
Universe(t)
```

pour chaque date historique.

---

# 35. Titres délistés et suspensions

Le dataset doit idéalement conserver :

```text
actions délistées
actions suspendues
ST
*ST
IPO récentes
```

Sinon le backtest sous-estime les situations défavorables.

---

# 36. Spécificités du marché chinois

Le moteur US ne peut pas être copié sans adaptation.

Il faut intégrer notamment :

```text
T+1
limit-up
limit-down
suspensions
ST / *ST
règles IPO
règles différentes selon les segments
```

---

# 37. T+1

En Chine A-share, une action achetée aujourd’hui ne peut généralement pas être revendue dans la même séance.

Pour H5/H10/H15/H20, ce n’est pas une contrainte majeure, mais elle doit être respectée dans le moteur d’exécution.

---

# 38. Limit-Up / Limit-Down

Cas critique :

```text
modèle décide BUY
      │
      ▼
action au limit-up
      │
      ▼
ordre potentiellement non exécutable
```

Un backtest naïf ne doit pas supposer :

```text
BUY @ open
```

si l’action n’était pas réellement achetable.

---

# 39. Pourquoi le temps réel n’est pas prioritaire

Pour une stratégie H5–H20 :

```text
tick data        ❌
Level 2          ❌
millisecond      ❌
real-time feed   ❌
```

ne sont pas prioritaires.

Les données :

```text
Daily EOD
```

sont suffisantes pour tester l’hypothèse ML.

---

# 40. Protocole expérimental

Il faut éviter de simplement ajouter toutes les nouvelles features et regarder le P&L.

Une ablation study est nécessaire.

---

# 41. Baseline

Reproduire l’architecture actuelle sur le marché chinois :

```text
Oracle Extreme
+
LONG actuel
+
SHORT actuel
```

avec les features disponibles actuellement.

---

# 42. Test Money Flow

Séparément :

```text
LONG actuel
+
Money Flow
```

et :

```text
SHORT actuel
+
Money Flow
```

---

# 43. Test Margin / Lending

LONG :

```text
LONG actuel
+
Margin Financing
```

SHORT :

```text
SHORT actuel
+
Lending / Short Activity
```

---

# 44. Test Events

LONG :

```text
positive forecast changes
positive earnings signals
positive revisions
```

SHORT :

```text
negative forecast changes
negative earnings signals
negative revisions
```

---

# 45. Test combinaison

Architecture finale de test :

```text
Oracle Extreme
        │
        ├──── LONG V2
        │       ├─ existing features
        │       ├─ flow
        │       ├─ margin
        │       ├─ positive revisions
        │       └─ events
        │
        └──── SHORT V2
                ├─ existing features
                ├─ flow
                ├─ lending
                ├─ negative revisions
                └─ events
```

---

# 46. KPI à mesurer

Ne pas regarder uniquement le rendement.

Mesurer au minimum :

```text
IC
Rank IC

AUC
Precision
Recall

D10 precision
D1 precision

D10 recall
D1 recall

TOP/BOTTOM spread

P(D10 | selected LONG)
P(D1 | selected LONG)

P(D1 | selected SHORT)
P(D10 | selected SHORT)
```

---

# 47. KPI principal : purification directionnelle

Le KPI principal est la capacité à transformer une population Extreme presque symétrique en une population directionnellement pure.

Exemple illustratif pour LONG :

```text
              Oracle population       Après LONG model

D10                 24 %                     45 %
D1                  23 %                     10 %
```

Pour SHORT :

```text
              Oracle population       Après SHORT model

D1                  23 %                     44 %
D10                 24 %                      9 %
```

Ces chiffres sont uniquement illustratifs.

L’objectif conceptuel est :

```text
LONG :
augmenter D10
réduire D1

SHORT :
augmenter D1
réduire D10
```

---

# 48. Walk-Forward

Comme pour le système US :

```text
TRAIN
  │
  ▼
VALIDATION
  │
  ▼
PURGE
  │
  ▼
OOS
```

Il faut éviter tout split randomisé.

---

# 49. Test économique

Une amélioration statistique ne suffit pas.

Il faut ensuite intégrer :

```text
signal
  │
  ▼
portfolio
  │
  ▼
execution rules
  │
  ▼
transaction costs
  │
  ▼
slippage
  │
  ▼
limit-up/down
  │
  ▼
suspensions
  │
  ▼
NET PERFORMANCE
```

---

# 50. Critères GO

Continuer vers RQData si :

```text
amélioration D1/D10 stable

IC directionnel positif

amélioration sur majorité des folds

gain OOS

TOP/BOTTOM spread positif

gain après coûts

pas de dépendance à une seule année

pas de dépendance à quelques titres
```

---

# 51. Critères NO-GO

Revoir ou arrêter si :

```text
gain uniquement in-sample

IC instable

aucune purification D1/D10

gain disparaissant OOS

alpha < coûts

forte sensibilité aux paramètres

gain concentré sur quelques périodes
```

---

# 52. Budget et stratégie fournisseurs

## Phase 1 — Tushare Pro

Prendre uniquement ce qui sert au POC :

```text
daily OHLCV
adjustment factors
stock master

money flow
large / extra-large orders

margin financing
securities lending

fundamentals
events
earnings forecasts

suspension / trading status
```

Pas besoin au départ de :

```text
real-time
minute
tick
Level 2
```

---

# 53. Pourquoi Tushare d’abord

Parce que Tushare permet de tester rapidement la question principale :

> Les données de flux et de positionnement apportent-elles une vraie information directionnelle supplémentaire ?

C’est le meilleur compromis POC entre coût, richesse des données et facilité d’intégration.

---

# 54. Phase 2 — RQData

À envisager uniquement si Phase 1 est concluante.

Datasets prioritaires :

```text
analyst consensus

EPS estimates
revenue estimates

target prices
ratings

estimate revisions

PIT financials
```

---

# 55. Wind

Wind peut être pertinent plus tard pour :

```text
usage institutionnel
production commerciale
multi-market
support contractuel
exigences fortes de qualité/data governance
```

Mais il est probablement surdimensionné pour le POC.

---

# 56. Comparaison décisionnelle

| Critère | Tushare | RQData | Wind |
|---|---:|---:|---:|
| A-shares | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Daily OHLCV | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Fundamentals | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Money Flow | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Margin/Lending | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Consensus | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| PIT | ⭐⭐⭐ avec contrôles | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Python/API | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Coût POC | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| Adapté au POC | **⭐⭐⭐⭐⭐** | ⭐⭐⭐⭐ | ⭐⭐ |

---

# 57. Roadmap proposée

## Phase 0 — Validation Data

Objectifs :

```text
ouvrir compte Tushare

tester API

vérifier historique

vérifier droits sur les endpoints

vérifier publication dates

vérifier délistés / suspensions

vérifier données Money Flow

vérifier Margin / Lending
```

---

# 58. Phase 1 — Data Lake Chine

Tables envisageables :

```text
china_stock_master

china_daily_bars

china_adj_factors

china_fundamentals

china_money_flow

china_margin

china_lending

china_events

china_trading_status
```

---

# 59. Phase 2 — Feature Engine

Créer les nouvelles familles :

```text
FLOW FEATURES

MARGIN FEATURES

LENDING FEATURES

EVENT FEATURES

PIT FUNDAMENTAL FEATURES
```

---

# 60. Phase 3 — Baseline

Porter l’architecture actuelle :

```text
Oracle Extreme
+
LONG
+
SHORT
```

sans nouvelles données.

Cette baseline est indispensable pour mesurer l’effet des datasets supplémentaires.

---

# 61. Phase 4 — Ablation Tests

Tester successivement :

```text
Baseline

Baseline + Flow

Baseline + Margin/Lending

Baseline + Events

Baseline + Flow + Margin

Baseline + toutes les nouvelles features
```

LONG et SHORT doivent être évalués séparément.

---

# 62. Phase 5 — Walk-Forward / OOS

Chaque expérimentation doit conserver :

```text
mêmes dates

mêmes folds

mêmes purges

même univers

mêmes coûts

mêmes règles d’exécution
```

pour rendre les comparaisons valides.

---

# 63. Phase 6 — Décision RQData

Si la Phase 1 démontre clairement que l’ajout d’information indépendante améliore les modèles directionnels :

```text
Tushare
   │
   ▼
preuve d’amélioration
   │
   ▼
RQData
   │
   ▼
Consensus / Estimates / Ratings
```

---

# 64. Ce qu’il ne faut pas faire

Ne pas :

```text
acheter immédiatement plusieurs fournisseurs

prendre du Level 2 pour un problème H5-H20

télécharger du tick historique sans justification

changer en même temps données + modèle + target

utiliser un univers survivorship-biased

ignorer les dates de publication

ignorer les limit-up/down

ignorer les suspensions
```

---

# 65. Recommandation finale

La stratégie recommandée est :

**1. Conserver l’architecture actuelle Oracle Extreme → LONG / SHORT.**

**2. Ne pas remplacer l’Oracle Extreme.**

**3. Utiliser le marché chinois comme laboratoire de données directionnelles.**

**4. Commencer avec Tushare Pro.**

**5. Utiliser uniquement des données daily pour le POC.**

**6. Construire un univers PIT de 500 à 1 000 A-shares liquides.**

**7. Ajouter d’abord Money Flow, Margin, Lending et Events.**

**8. Mesurer spécifiquement la purification D1/D10 des modèles LONG et SHORT.**

**9. N’évaluer RQData que si Tushare montre un gain clair.**

**10. Utiliser ensuite RQData pour consensus, estimates, ratings et révisions.**

**11. Ne considérer Wind qu’à un stade institutionnel ou commercial plus avancé.**

---

# 66. Question décisionnelle pour le POC

La question centrale du projet doit être formulée ainsi :

> **En conservant notre architecture actuelle Oracle Extreme → modèle LONG dédié / modèle SHORT dédié, l’ajout de données de flux, de positionnement, de financement et d’anticipations permet-il d’améliorer significativement et de manière stable la capacité à distinguer les futurs D10 des futurs D1 parmi les candidats extrêmes ?**

Cette formulation permet de garder un objectif clair, mesurable et directement lié au problème actuel d’α-Trade.

---

# 67. Valeur stratégique du POC

Le POC Chine peut avoir une double valeur.

Premièrement :

> déterminer si une version α-Trade China possède un potentiel économique propre.

Deuxièmement, et probablement plus important :

> identifier empiriquement quelles catégories de données directionnelles valent réellement la peine d’être achetées plus tard pour α-Trade US.

Si Money Flow, Margin, Lending ou Analyst Revisions améliorent nettement la discrimination D1/D10 en Chine, cela fournira une preuve forte que la faiblesse directionnelle du système US est au moins partiellement liée au dataset, et pas uniquement au modèle.

La Chine devient donc un laboratoire de validation de l’hypothèse :

```text
Plus de features
≠
plus d’information

mais

nouvelles sources d’information
→
potentiellement meilleure direction
```

C’est précisément cette distinction que le POC doit valider.

---

# 68. Audit d’intégration dans l’application actuelle

## 68.1 Verdict de faisabilité

La coexistence des marchés US et chinois est techniquement possible, mais elle ne peut pas être obtenue de manière sûre avec un simple interrupteur visuel et une colonne ajoutée à quelques tables.

L’application actuelle possède déjà de bons points d’extension :

- séparation entre ingestion, feature engineering, ML, risque et exécution ;
- provenance des barres via `data_source` ;
- univers configurables ;
- batches et runs ML identifiés ;
- modèles Oracle et directionnels séparés ;
- début de gestion pays/devise dans les contrôles de concentration ;
- restriction de sortie le jour de l’entrée déjà simulable ;
- clients de brokers isolés dans `service/`.

Mais le contrat dominant reste implicitement américain :

```text
symbol seul
    + calendrier NYSE
    + timezone America/New_York
    + cutoff EOD vers 21:00 UTC
    + benchmark SPY
    + liquidité et notionnels en USD
    + métadonnée asset_class = us_equity
    + exécution nominale Alpaca
```

La bonne cible est donc une application **market-aware**, dans laquelle le marché est un attribut persistant de chaque donnée et de chaque run, et non une variable globale cachée.

## 68.2 Correction de l’architecture proposée initialement

La première version du document proposait des tables parallèles :

```text
china_stock_master
china_daily_bars
china_fundamentals
...
```

Cette solution convient éventuellement à une zone brute de staging propre à Tushare, mais elle est déconseillée pour les tables métier canoniques. Dupliquer toutes les tables créerait deux implémentations du screener, du ML, du risque et du backtest, avec un risque important de divergence.

Architecture recommandée :

```text
Sources US                         Sources CN
EODHD / Alpaca / Finnhub          Tushare / RQData
          │                              │
          ▼                              ▼
staging provider US                staging provider CN
          │                              │
          └──────────────┬───────────────┘
                         ▼
               modèle canonique commun
           instrument_id + market_code + MIC
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
            ML        backtest     risque
             │                       │
             └───────────┬───────────┘
                         ▼
                routeur d’exécution
                 US broker / CN broker
```

Les tables brutes peuvent rester spécifiques au fournisseur. Les tables consommées par le reste de l’application doivent être communes et explicitement scopées par marché.

# 69. Le switch US/CN dans l’IHM

## 69.1 Comportement attendu

Le switch peut proposer :

```text
US — Actions américaines
CN — A-shares chinoises
ALL — Vue consolidée, uniquement lorsque le traitement le permet
```

`US` doit rester la valeur par défaut durant toute la migration afin de préserver le comportement actuel.

Le choix doit filtrer :

- les fichiers et publications d’univers ;
- les fournisseurs disponibles ;
- les benchmarks ;
- les batches ML affichés ;
- les prédictions ;
- les backtests ;
- les comptes et brokers compatibles ;
- les positions, ordres et rapports ;
- le monitoring de fraîcheur.

## 69.2 Le switch ne doit pas être une variable globale

Un état global `current_market = CN` serait dangereux : deux utilisateurs, deux onglets ou deux batches parallèles pourraient se contaminer.

Le marché doit être transporté dans chaque commande et persisté :

```text
IHM
 │
 ├── market_code=US
 └── market_code=CN
        │
        ▼
PipelineOptions / CLI / config effective
        │
        ▼
run et batch persistés avec market_code
        │
        ▼
chaque repository applique le scope
```

Pour les opérations cross-sectionnelles — Oracle, ranking, sector neutralization — `ALL` doit être interdit dans un premier temps. Un rang calculé dans un mélange US/CN serait affecté par les différences de calendrier, devise, microstructure et distribution. Les modèles doivent être entraînés séparément par marché, même si le code et les familles de features sont partagés.

## 69.3 Univers de fichiers

Les fichiers texte actuels ne contiennent que des symboles. Deux options sont possibles :

```text
config/univers/us/*.txt
config/univers/cn/*.txt
```

ou un manifeste accompagnant chaque fichier :

```json
{
  "market_code": "CN",
  "symbols_file": "a_shares_liquides_800.txt",
  "as_of_date": "2026-09-04",
  "currency": "CNY"
}
```

Le marché ne doit pas être déduit uniquement du nom du fichier. Le batch doit stocker la valeur résolue.

# 70. Identité des instruments et stratégie SQL

## 70.1 Problème actuel

`stock_metadata.symbol` est actuellement la clé primaire. Plusieurs tables utilisent ensuite des clés telles que :

```text
(symbol, date)
(symbol, prediction_date, run_id)
(symbol, date, batch_id)
(account_id, symbol)
```

Ajouter seulement `market_code` sans modifier ces clés ne résout pas le problème : une contrainte unique qui ignore le marché peut toujours écraser ou fusionner deux instruments.

Le suffixe fournisseur (`600000.SH`, `000001.SZ`) limite les collisions, mais il ne doit pas devenir l’identité métier. Les symboles changent, les fournisseurs n’utilisent pas toujours le même format et plusieurs places doivent être distinguées.

## 70.2 Identité recommandée

Créer un identifiant interne immuable :

```text
instrument_id       BIGINT
market_code         US | CN
country_code        US | CN
exchange_mic        XNYS | XNAS | XSHG | XSHE | XBEI | ...
local_symbol        symbole officiel local
display_symbol      symbole présenté à l’utilisateur
currency            USD | CNY
provider_symbol     identifiant propre à chaque fournisseur
```

Clé naturelle de contrôle :

```text
UNIQUE(exchange_mic, local_symbol)
```

Les mappings fournisseur doivent être dans une table fille, par exemple :

```text
instrument_provider_symbols
instrument_id | provider | provider_symbol | valid_from | valid_to
```

Ainsi, les formats Tushare, RQData, EODHD et broker restent des identifiants externes et peuvent évoluer sans casser l’historique.

## 70.3 Migration progressive sans régression US

La migration recommandée se fait en deux temps :

1. ajouter le référentiel marché/instrument et backfiller tous les titres actuels avec `market_code='US'` ;
2. ajouter `instrument_id` aux tables consommatrices, remplir depuis `stock_metadata`, créer les nouvelles contraintes/index, puis rendre la colonne obligatoire ;
3. faire lire et écrire le code par `instrument_id`, tout en conservant temporairement `symbol` comme colonne de présentation ;
4. seulement ensuite charger des instruments CN ;
5. supprimer les anciens contrats d’unicité fondés sur `symbol` seul après validation complète.

Une solution transitoire plus rapide consiste à ajouter `market_code CHAR(2) NOT NULL DEFAULT 'US'` et à reconstruire toutes les clés avec ce champ. Elle est acceptable pour un POC de recherche, mais moins robuste qu’un véritable `instrument_id`.

# 71. Tables potentiellement impactées

## 71.1 Référentiel, données et univers — priorité bloquante

| Table ou famille | Situation actuelle | Adaptation nécessaire |
|---|---|---|
| `stock_metadata` | PK `symbol`, filtre applicatif `asset_class='us_equity'` | `instrument_id`, `market_code`, pays, MIC, devise, timezone, board, statut ST, lot, tick, règles de prix, éligibilité short et fournisseur |
| `stock_bars` | unicité `symbol/timeframe/timestamp`, timestamp documenté New York | clé instrument, timestamps UTC, timezone/session du marché, source et unités normalisées |
| `stock_bars_daily` | PK `symbol/date`, source active unique | PK instrument/date, market scope, statut de séance, suspension et limites de prix |
| `stock_quote_snapshots` | PK `symbol/quote_date` | clé instrument/date, devise, provider et cutoff local |
| `stock_earnings_calendar` | PK `symbol/earnings_date` | clé instrument/date, dates de publication/disponibilité PIT et timezone |
| `stock_fundamentals_daily` | unicité `symbol/trade_date` | clé instrument/date, devise/unité, période fiscale, dates PIT et source |
| historiques analystes | identité par symbole | instrument, marché, devise, publication/available_at, mapping provider |
| `stock_scores` | PK `symbol` | PK instrument ; empêcher qu’un run US remplace un état CN |
| `stock_scores_history` | unicité date/preset/symbol | ajouter marché/instrument ; presets propres au marché |
| `tradable_universe_runs` | aucun marché explicite | `market_code`, calendrier, devise, provider et version de politique |
| `tradable_universe_history` | clé run/symbol | instrument ; causes CN : suspension, ST, limit state, ancienneté, connect eligibility |
| audits de nettoyage | scope symbole | instrument + marché + calendrier/source audités |

Les nouvelles données Money Flow, Margin et Lending doivent avoir leurs propres tables canoniques PIT. Elles ne doivent pas être ajoutées comme colonnes mutables à `stock_metadata`.

## 71.2 ML — priorité bloquante avant tout entraînement CN

| Table ou artefact | Adaptation |
|---|---|
| `model_training_batch` | stocker `market_code`, benchmark, devise, calendrier, source d’univers et fingerprint de l’univers |
| `model_training_run` | hériter du marché du batch et utiliser `instrument_id` pour les modèles per-symbol |
| registry, metrics, diagnostics, governance | rendre le marché consultable ; vérifier la cohérence avec le batch parent |
| `model_predictions` | instrument + marché ; conserver batch/run/role ; aucune lecture sans scope batch et marché |
| `global_rank_history` | instrument + marché ; classement quotidien calculé à l’intérieur d’un seul marché |
| `global_oracle_labels` | instrument + marché ; déciles construits uniquement dans l’univers CN ou US correspondant |
| `oracle_extreme_predictions` | instrument + marché ; PK et index reconstruits sans ambiguïté |
| artefacts disque | manifeste obligatoire avec marché, benchmark, calendrier, devise, univers, features et versions de sources |

Le `batch_id` isole déjà une partie des prédictions, mais il ne suffit pas : les loaders de barres et de features filtrent aujourd’hui souvent seulement sur `symbol`. Un batch CN correctement marqué pourrait donc encore consommer une donnée du mauvais marché si l’identité n’est pas propagée jusqu’aux jointures.

## 71.3 Sentiment et événements

Les tables suivantes contiennent aussi des symboles ou tickers et doivent être scopées :

- `news_ticker_map` ;
- `news_ticker_sentiment` ;
- `ticker_daily_sentiment_features` ;
- checkpoints d’ingestion par symbole ;
- événements macro et sectoriels lorsqu’ils sont rattachés à un marché.

Il faut en plus prévoir :

- langue de la source ;
- modèle NLP et version ;
- fuseau de publication ;
- mapping des noms chinois, codes locaux et symboles fournisseur ;
- contrôle PIT de la traduction et de l’enrichissement.

Un modèle FinBERT anglais ne doit pas être considéré automatiquement valide pour des textes chinois.

## 71.4 Risque, exécution et portefeuille

Les tables `risk_decisions`, `portfolio_targets`, les snapshots, ordres, fills, positions, lots, événements d’exécution et réconciliations transportent aujourd’hui principalement `symbol` et `account_id`. Elles devront transporter au minimum `instrument_id`, et le run parent devra identifier le marché.

Points particuliers :

- `execution_positions` est unique sur `(account_id, symbol)` : cette contrainte doit utiliser l’instrument ;
- les idempotency keys et business keys des ordres doivent inclure l’identité canonique ;
- un compte doit déclarer broker, marchés autorisés, devise de base et type d’accès ;
- les montants cash doivent porter leur devise ;
- le PnL consolidé exige des taux FX PIT ;
- les corporate actions doivent référencer l’instrument ; leur clé d’idempotence ne doit pas reposer sur le symbole seul ;
- les limites pays/devise existantes dans le module de concentration constituent un bon socle, mais les objets candidats et positions ne leur fournissent pas encore systématiquement ces données.

## 71.5 Tables pouvant hériter du marché au lieu de le dupliquer

Il n’est pas nécessaire d’ajouter aveuglément `market_code` à toutes les tables. Une table strictement fille d’un run immuable peut hériter le marché via une clé étrangère vers ce run.

On peut néanmoins dénormaliser `market_code` lorsqu’il est indispensable pour :

- une requête opérationnelle fréquente ;
- un partitionnement ;
- un contrôle d’unicité ;
- une barrière de sécurité empêchant une jointure cross-market.

Chaque dénormalisation doit avoir une contrainte ou un test garantissant sa cohérence avec le parent.

# 72. Impacts sur le code par module

## 72.1 Couche commune

`common.market_calendar` est aujourd’hui explicitement NYSE et expose des fonctions comme `nyse_session_dates`. Il faut introduire un registre :

```text
MarketContext
├── market_code
├── calendar_name
├── timezone
├── session open/close
├── decision_cutoff
├── settlement policy
├── benchmark_symbol/instrument
├── base_currency
└── execution rules profile
```

Les fonctions génériques deviennent par exemple :

```text
session_dates(market, start, end)
session_bounds(market, date)
next_trading_day(market, date)
```

Les wrappers NYSE peuvent rester temporairement pour la compatibilité US.

Le contrat PIT utilise actuellement `America/New_York` et plusieurs loaders ajoutent conventionnellement 21 heures UTC à une date. Ce cutoff doit devenir une propriété de la source et du marché. Une heure UTC fixe est incorrecte même pour les États-Unis pendant les changements d’heure et ne convient pas à `Asia/Shanghai`.

## 72.2 Ingestion et Data Integrity

Le chemin actuel est centré sur EODHD/Alpaca. Un adaptateur Tushare doit produire le schéma canonique et normaliser explicitement :

- codes échange/symboles ;
- devise CNY ;
- timezone `Asia/Shanghai` et timestamps UTC ;
- unités de volume et de montant ;
- facteurs d’ajustement ;
- calendriers de séances ;
- suspensions ;
- statut ST/*ST ;
- bornes de prix applicables ;
- provenance et dates de disponibilité.

Le sanitizer daily utilise actuellement le calendrier NYSE et un fallback historique fondé sur SPY. Il doit recevoir un `MarketContext`; le fallback CN doit provenir du calendrier de place ou du fournisseur, jamais de SPY.

Une suspension ne doit pas être réduite à une simple barre forward-fillée `is_filled=True`. Pour le ML, une valeur peut être conservée avec un masque. Pour l’exécution et le backtest, elle doit rendre l’instrument non tradable ce jour-là.

## 72.3 Univers, screener et selector

Le filtre d’éligibilité actuel exige explicitement `asset_class='us_equity'`. Sans modification, les titres CN seront exclus même s’ils sont actifs, tradables et disposent de barres.

Les seuils actuels sont libellés en dollars (`liquidity_threshold_usd`, `adv_usd`, market cap en USD). Il faut choisir un contrat unique :

- soit tout convertir dans une devise de référence avec un FX PIT ;
- soit stocker valeur locale + devise et convertir uniquement lors des comparaisons.

La seconde solution est plus audit-able. Les seuils de sélection doivent être définis par marché et leur devise explicite.

Les secteurs chinois doivent être mappés vers une taxonomie stable. Il ne faut pas mélanger directement les libellés sectoriels Yahoo/EODHD US avec ceux d’un fournisseur chinois sans table de correspondance versionnée.

## 72.4 Feature engineering

Plusieurs features expertes dépendent de SPY, VIX, VXN, MOVE ou d’un régime US. Pour CN :

- le benchmark doit devenir un paramètre persistant du batch ;
- les features relatives doivent employer un benchmark CN adapté et disponible PIT ;
- les features macro US doivent être désactivées dans la baseline CN ou explicitement étudiées comme facteurs externes ;
- les features sectorielles et cross-sectionnelles doivent être calculées dans l’univers CN du jour ;
- les nouvelles familles Flow/Margin/Lending doivent conserver valeur, unité, source et `available_at`.

Les noms de colonnes tels que `SPY_SMA_200_slope` devront être généralisés ou accompagnés d’un contrat de benchmark. Changer uniquement la série derrière un nom `SPY_*` rendrait l’artefact trompeur.

## 72.5 Oracle Extreme et modèles directionnels

L’architecture actuelle conditionne désormais les endpoints d’entraînement directionnels sur le TOP20 des prédictions Oracle OOF. Ce contrat peut être réutilisé en Chine, sous quatre conditions :

1. labels D1/D10 calculés uniquement dans l’univers CN de chaque date ;
2. folds construits avec le calendrier CN ;
3. Oracle OOF CN utilisé pour conditionner les branches CN ;
4. aucune réutilisation directe d’un champion US comme modèle CN de production.

Il est possible de tester un transfert US vers CN comme expérience séparée, mais le résultat doit être identifié comme tel et comparé à un entraînement CN natif.

## 72.6 Backtest

Le backtest sait déjà interdire une sortie le jour de l’entrée via `swing_only`, mais un profil CN complet doit ajouter :

- calendrier chinois ;
- absence d’exécution pendant une suspension ;
- impossibilité ou probabilité réduite de fill au limit-up/limit-down ;
- tick size et taille de lot ;
- règles particulières selon board, statut et date ;
- disponibilité réelle du short/lending ;
- frais, taxes, commissions et slippage propres au canal d’accès ;
- settlement cash et FX ;
- corporate actions chinoises ;
- univers PIT incluant délistés et changements de statut.

Le simulateur actuel nomme de nombreuses grandeurs en USD et résout les commissions avec un preset Alpaca. Ces contrats doivent devenir monétaires et dépendants du marché/broker.

## 72.7 Risque

Le module de concentration contient déjà des limites pays, devise et non-USD. C’est une base utile, mais il faut propager pays/devise depuis le référentiel jusqu’aux candidats et holdings.

À ajouter ou paramétrer :

- enveloppe de risque US et CN ;
- exposition CNY et risque FX ;
- corrélations calculées sur calendriers alignés sans forward-fill abusif ;
- limites par marché, place et board ;
- haircut de liquidité CN ;
- politique `SHORT_SIGNAL_ONLY` lorsque la vente à découvert n’est pas exécutable ;
- taille arrondie au lot autorisé ;
- contrôle du cash disponible par devise.

## 72.8 Exécution

Le moteur possède une classe appelée `BrokerAdapter`, mais son implémentation nominale adapte actuellement `AlpacaTradingClient` et les CLI/watchers instancient Alpaca directement. Le client IBKR présent dans `service/ibkr` ne signifie donc pas que le chemin de production est déjà multi-broker.

Il faut d’abord définir un protocole broker générique :

```text
submit / cancel / replace
orders / fills / positions / account
asset metadata
market clock
borrow or short eligibility
corporate actions / statements
```

Puis créer un routeur compte + marché. L’éligibilité réelle aux A-shares dépendra du broker et du canal d’accès retenu ; elle doit être contrôlée avant l’ordre, pas supposée à partir du signal ML.

## 72.9 IHM, rapports et monitoring

Toutes les pages listant univers, batches, prédictions, backtests, positions ou runs doivent afficher le marché. Les identifiants visuels recommandés sont :

```text
US · AAPL
CN · XSHG · 600000
CN · XSHE · 000001
```

Les diagnostics doivent détecter :

- batch sans marché ;
- univers mélangeant plusieurs marchés ;
- benchmark incompatible ;
- calendrier ou devise incohérents ;
- prédictions sans données du marché attendu ;
- fraîcheur par marché ;
- couverture des suspensions et limites de prix ;
- modèle US utilisé pour une prédiction CN sans mode transfert explicite.

# 73. Règles chinoises à modéliser comme données versionnées

Les règles de marché ne doivent pas être codées sous forme de constantes éternelles. Elles peuvent varier selon la place, le board, le statut du titre et la période.

Créer une politique versionnée comportant au minimum :

```text
exchange_mic
board_code
effective_from / effective_to
buy_lot_size
sell_odd_lot_policy
tick_size
same_day_sell_allowed
price_limit_up_pct / price_limit_down_pct
ipo_special_window
short_allowed
settlement_days
```

Avant une utilisation réelle, les règles d’accès, de vente à découvert, de lots, de limites, de frais et de fiscalité doivent être confirmées auprès du broker et des sources officielles pour le canal exact choisi. Les hypothèses de la présente étude suffisent pour cadrer un POC, pas pour autoriser une exécution réelle.

# 74. Point essentiel : modèle SHORT ne signifie pas nécessairement vente à découvert

Le modèle SHORT peut avoir trois usages :

```text
1. exécuter une position short si le titre et le compte sont éligibles ;
2. bloquer un candidat LONG détecté comme baissier ;
3. classer le risque directionnel sans générer d’ordre.
```

Pour le premier POC Chine, la recommandation est :

```text
Oracle Extreme
      │
      ├── branche LONG → candidat achetable
      └── branche SHORT → veto / mesure de qualité
```

Le short exécutable doit rester désactivé tant que disponibilité de prêt, canal broker, coûts et règles PIT ne sont pas modélisés et testés.

# 75. Roadmap d’intégration révisée

## Phase A — Fondation multi-marché, sans données CN

- créer `MarketContext` et registre des marchés ;
- créer le référentiel instrument ;
- backfiller `US` et vérifier une parité bit-for-bit des résultats existants ;
- rendre calendrier, timezone, benchmark et devise explicites ;
- ajouter le filtre IHM US/CN, avec CN désactivé tant que le socle n’est pas prêt.

Gate : tous les tests actuels passent et les runs US de référence sont inchangés.

## Phase B — POC données CN isolé

- connecter Tushare dans une zone de staging ;
- charger master, calendrier, OHLCV, ajustements, statuts et suspensions ;
- normaliser vers les tables canoniques ;
- publier un univers PIT CN de 500 à 1 000 instruments ;
- interdire encore l’exécution réelle.

Gate : absence de collision, couverture et unités validées, audits PIT verts.

## Phase C — Baseline ML CN

- profil de features de prix compatible CN ;
- benchmark et secteurs CN ;
- Oracle CN ;
- modèles directionnels conditionnels CN ;
- artefacts et diagnostics filtrés par marché.

Gate : folds valides, stabilité OOS, aucune donnée US injectée involontairement.

## Phase D — Nouvelles données directionnelles

- Flow ;
- Margin ;
- Lending ;
- événements et prévisions ;
- ablations séparées LONG/SHORT sur protocole gelé.

Gate : purification directionnelle stable et amélioration après correction des comparaisons multiples.

## Phase E — Backtest économique CN

- règles de marché versionnées ;
- lots, limites, suspensions, coûts et FX ;
- short utilisé d’abord comme veto ;
- stress tests par année, régime, board et liquidité.

## Phase F — Exécution, uniquement après validation séparée

- broker/canal d’accès ;
- paper ou shadow mode ;
- rapprochement positions/ordres/cash multi-devise ;
- preflight spécifique CN ;
- activation graduelle avec kill switch par marché.

# 76. Tests de non-régression et critères d’acceptation

## 76.1 Isolation

- une requête US ne retourne aucune ligne CN ;
- une requête CN ne retourne aucune ligne US ;
- deux instruments ayant le même `local_symbol` sur deux MIC restent distincts ;
- aucun upsert CN ne remplace une ligne US ;
- un batch et ses prédictions ont toujours le même marché.

## 76.2 Temps et PIT

- jours fériés US et CN indépendants ;
- cutoffs calculés dans la bonne timezone puis comparés en UTC ;
- aucun forward-fill inter-séance ne rend une suspension tradable ;
- publications fondamentales/analystes filtrées par `available_at` ;
- folds et horizons avancent en séances du marché concerné.

## 76.3 ML

- rangs et déciles ne mélangent jamais US/CN ;
- benchmark compatible avec le marché ;
- manifeste d’artefact complet et contrôlé au serving ;
- erreur bloquante si marché, univers ou features diffèrent de l’entraînement.

## 76.4 Backtest/exécution

- T+1 appliqué selon la politique effective ;
- ordres non exécutés sur suspension ;
- scénarios limit-up/limit-down conservateurs ;
- arrondi de quantité conforme au lot ;
- coûts en devise locale puis conversion FX PIT ;
- short bloqué sans éligibilité et disponibilité de prêt ;
- idempotence des ordres et corporate actions avec `instrument_id`.

# 77. Synthèse des impacts et ordre de priorité

| Priorité | Impact | Pourquoi |
|---|---|---|
| P0 | identité `instrument_id` + marché/MIC | empêche collisions et jointures erronées |
| P0 | calendrier/timezone/cutoff génériques | garantit PIT, sessions et horizons corrects |
| P0 | scope marché dans univers, batches, labels et prédictions | empêche la contamination ML cross-market |
| P0 | normalisation Tushare et unités | évite prix/volume/liquidité faux |
| P1 | benchmark, secteurs et features par marché | rend le modèle CN économiquement cohérent |
| P1 | backtest suspensions/limites/lots/T+1 | évite une performance non exécutable |
| P1 | devise, FX, frais et cash | rend PnL et risque comparables |
| P1 | IHM et monitoring market-aware | rend les erreurs visibles et auditables |
| P2 | broker générique et routeur | nécessaire seulement pour passer du POC à l’exécution |
| P2 | sentiment chinois et NLP local | nouvelle source alpha, non nécessaire à la baseline |

Conclusion d’architecture :

> **Oui, α-Trade peut faire coexister US et CN. Le switch IHM est la façade ; la vraie évolution est l’introduction d’une identité instrument, d’un contexte marché propagé de bout en bout et de politiques de calendrier, devise, données, ML et exécution propres à chaque marché.**
