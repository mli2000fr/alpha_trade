# P0k — Revalidation directionnelle ciblée sur l'univers Oracle dynamique

## Pourquoi une revalidation est nécessaire

Les expériences directionnelles historiques ont majoritairement utilisé un
univers statique d'environ 400 symboles. P0f remplace ce contrat par une
admission quotidienne PIT issue de l'univers large : environ 1 550 titres par
jour en médiane et 2,91 millions de prédictions OOF sur quatorze folds.

Changer la population peut modifier :

- les déciles D1/D10 calculés chaque jour ;
- la composition du TOP20 Oracle ;
- les rangs cross-sectionnels et les distributions de features ;
- la diversité sectorielle, de volatilité et de régimes ;
- le nombre d'exemples disponibles pour un modèle mutualisé.

Il serait donc excessif de considérer que chaque ancien `NO_GO` est prouvé à
l'identique sur P0f. À l'inverse, rejouer toutes les variantes créerait une
campagne coûteuse et un risque d'optimisation a posteriori.

## Ce qui est déjà revalidé

P0g a réentraîné le témoin mutualisé D1/D10 sur les événements TOP20 OOF du
batch P0f `model-factory-20260909051302-323684`. Le résultat est inférieur au
hasard : AUC 0,4904, IC quotidien -0,0147 et branche SHORT signée négative.

Ce résultat montre que l'élargissement de l'univers ne suffit pas, à lui seul,
à créer une direction exploitable. Il ne couvre toutefois qu'une formulation :
la classification directe D1 contre D10.

## Expériences sensibles à l'univers à recontrôler

### Écran 1 — trois familles indépendantes

1. **E2 — deux probabilités indépendantes** : estimer séparément
   `P(rendement >= +3 %)` et `P(rendement <= -3 %)`, aux horizons H3/H10/H20.
   Cette cible peut bénéficier du nombre d'événements et d'une prévalence plus
   représentative que le D1/D10 forcé.
2. **R1 — ranker conditionnel Oracle** : classer les rendements uniquement dans
   le TOP20 P0f, aux horizons H3/H10/H20. C'est la famille la plus directement
   sensible à la taille et à la diversité du cross-section quotidien.
3. **E5 — régime quotidien** : prédire un côté commun au panier Oracle du jour.
   L'agrégation quotidienne change lorsque le pool passe de 400 titres fixes à
   une admission dynamique large.

Les paramètres, features et seuils restent ceux des expériences originales.
Aucune recherche d'hyperparamètres n'est autorisée dans cet écran.

### Écran 2 — conditionnel

E4-B (première barrière binaire) ne sera rejoué que si au moins une famille de
l'écran 1 satisfait ses gates de stabilité. Temporal V2, consensus, réseaux
séquentiels et variantes de contexte restent fermés tant que cet écran simple
ne montre pas de signal.

Les expériences fondées sur des données Eroya collectées seulement pour les
anciens 400 ne peuvent pas être déclarées revalidées sur P0f. Elles restent
`NO_GO` dans leur population testée et exigeraient une nouvelle collecte PIT
comparable avant tout nouveau verdict.

## Contrat commun

- Oracle : `model-factory-20260909051302-323684` ;
- données : uniquement les historiques locaux disponibles, avec cutoff
  `stock_bars_daily` au 10 juillet 2026 ;
- apprentissage/validation : OOF Walk-Forward du batch, sans utiliser P0i ni
  2026H1 pour choisir une variante ;
- fenêtres : `min_train=504`, validation 126, test 126, pas 126, maximum 12
  splits lorsque l'outil concerné le permet ;
- contexte : `none` pour rester comparable aux témoins les moins mauvais ;
- aucun changement des exits, du portefeuille ou du backtest ;
- résultats rapportés globalement, par fold et par semestre.

## Gates préfixés

Une famille n'est rouverte que si elle satisfait simultanément :

1. AUC ou IC de signe favorable en agrégé ;
2. au moins 8 folds favorables sur 12, ou 75 % des folds réellement disponibles ;
3. lift du décile sélectionné favorable et économiquement cohérent ;
4. aucun côté promu avec une couverture artificiellement faible ;
5. stabilité sur plusieurs semestres, sans dépendre uniquement de 2025 ;
6. confirmation ultérieure sur une période tenue à l'écart avant toute
   intégration au backtest.

Un simple passage de 0,50 à 0,51 sur l'AUC globale ne suffit pas. Si aucun des
trois écrans ne passe, le rejet directionnel est considéré robuste au changement
d'univers et la recherche revient à la monétisation de l'amplitude ou à une
source PIT réellement nouvelle.

## Séquence de décision

```text
P0f amplitude validée
        |
        v
E2 + R1 + E5 sur TOP20 OOF dynamique
        |
        +-- aucun gate --> direction rejetée sur nouvel univers
        |
        +-- signal stable --> E4-B ciblé puis confirmation tenue à l'écart
                                      |
                                      +-- confirmation --> backtest dédié
                                      +-- échec --------> fermeture de la piste
```

## Statut

`EN_COURS_PROTOCOL_PREEnREGISTRE` — protocole défini avant lecture des nouveaux
résultats. P0g reste un `NO_GO` acquis ; P0k mesure seulement si d'autres cibles
réagissent différemment à l'univers dynamique.

L'écran 1 a été lancé le 9 septembre 2026 à 14 h 28, avec quatre threads par
processus et des sorties séparées :

```text
log/batch/p0k-20260909-142850/
├── e2.stdout.log / e2.stderr.log
├── r1.stdout.log / r1.stderr.log
└── e5.stdout.log / e5.stderr.log
```

Les trois avertissements `triton not found` au démarrage concernent uniquement
le comptage de FLOPs PyTorch. Ils ne bloquent ni CatBoost ni les expériences et
ne changent pas leurs métriques.
