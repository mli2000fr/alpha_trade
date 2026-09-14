# E20-D — Replay économique de la confirmation price-only

## Objectif

E20-D vérifie si le signal directionnel statistique d’E20-B reste exploitable
après une entrée réellement possible à 10:00 New York. L’expérience est
research-only et ne modifie aucun chemin de production.

## Politique figée

Le signal Oracle H20 est calculé à la clôture J. À la séance suivante :

```text
variation open → 10:00 > +0,50 % → LONG à 10:00
variation open → 10:00 < -0,50 % → SHORT à 10:00
sinon                         → abstention
```

Le prix d’entrée est le close de la dernière barre minute terminée au checkpoint
30 minutes, remis sur l’échelle ajustée des barres quotidiennes.

## Filtres et lifecycle

- gap absolu open contre clôture précédente <= 3 % ;
- prix d’entrée >= 10 USD ;
- ADV20 >= 1 million USD ;
- huit positions LONG/SHORT partagées, priorité au score Oracle ;
- stop initial 2,5×ATR20 PIT ;
- trailing risk-based 2,5×ATR à partir de la deuxième séance ;
- TP `min(3×ATR, 7 %)` ;
- résolution intrabar conservative ;
- échéance maximale H20, sortie au prochain open ;
- commission 1 bp et slippage 2 bp par sens ;
- coût d’emprunt SHORT 0,3 % annualisé.

## Incertitude de la séance d’entrée

Le backfill Opening Window s’arrête à 10:30 et ne contient pas la trajectoire
complète après 10:00. L’OHLC journalier du jour d’entrée inclut en outre les
trente minutes antérieures à l’entrée. Deux bornes sont donc pré-enregistrées :

1. `full_day_conservative`, politique primaire : applique l’OHLC complet du jour
   d’entrée, avec le risque de faux déclenchements antérieurs à 10:00 ;
2. `next_session_protection`, sensibilité optimiste : ignore les barrières du
   jour d’entrée et les active à la séance suivante.

Une conclusion qui ne survit pas aux deux bornes est déclarée bloquée. Un GO ne
constitue pas une promotion : il autorise seulement l’acquisition/reconstruction
de la trajectoire intraday postérieure à 10:00.

## Gates pré-enregistrés

- au moins 500 trades après capacité ;
- borne basse bootstrap 95 % du rendement net moyen par date > 0 pour la borne
  pessimiste ;
- même gate pour la borne optimiste ;
- au moins 60 % des semestres positifs dans chacune des deux bornes.

Le verdict possible est `GO_EXACT_INTRADAY_CONFIRMATION` ou
`NO_GO_OR_BLOCKED_ECONOMIC_REPLAY`.

La contribution normalisée `sum(net_return)/8` est un diagnostic de capacité,
pas une courbe de capital ni un rendement de portefeuille composé.

## Reproduction

```powershell
python -u -m modelFactory.oracle_opening_price_economic_replay --events-path artifacts/research/oracle_opening_price_confirmation/e20b-opening-price-only-20260914051444/oracle_price_only_events.parquet --bootstrap-samples 2000 --log-level INFO
```

Voir [E20-B](oracle_opening_price_confirmation_e20b.md),
[E20-C](oracle_opening_volume_ablation_e20c.md) et le
[registre](experiences_done.md).

## Résultat canonique du 14 septembre 2026

Artefact :

```text
artifacts/research/oracle_opening_price_economic_replay/e20d-opening-price-economic-20260914175418
```

Le verdict est `NO_GO_OR_BLOCKED_ECONOMIC_REPLAY`, avec 2 259 trades après
capacité sur 1 232 dates. La politique symétrique avec lifecycle produit
-0,120 % par trade et -0,112 % par date, IC95 [-0,628 % ; +0,383 %]. Seulement
7 semestres sur 15 sont positifs. La sensibilité sans protection le jour
d'entrée reste négative : -0,406 % par trade, IC95 journalier
[-0,775 % ; +0,229 %]. Tous les gates de performance et de stabilité échouent.

### Attribution open, entrée retardée et lifecycle

Sur le portefeuille primaire :

| Mesure | Rendement moyen |
|---|---:|
| H20 contrefactuel depuis l'open | +1,697 % |
| H20 fixe depuis l'entrée réalisable à 10:00 | -0,689 % |
| Impact pur du retard open → 10:00 | -2,386 points |
| Lifecycle PROD depuis 10:00 | -0,120 % |

L'impact du retard est statistiquement robuste : moyenne par date -2,328
points, IC95 [-2,487 ; -2,184]. E20-B capturait donc en grande partie un
mouvement déjà réalisé au moment où la direction devenait observable. Le
lifecycle réduit la perte par rapport au maintien H20 fixe ; il n'est pas la
cause principale du NO-GO agrégé.

### Décomposition LONG/SHORT diagnostique

La branche SHORT est rejetée : -4,015 % en maintien H20 depuis 10:00, IC95
par date [-6,607 % ; -1,327 %], et seulement 2 semestres positifs sur 15. Le
lifecycle limite cette perte à -0,596 % par trade sans la rendre robuste.

La branche LONG, découverte après lecture du résultat, conserve +2,822 % par
trade en maintien H20 depuis 10:00 et 10 semestres positifs sur 15. Sa moyenne
par date de +2,307 % reste toutefois non significative, IC95
[-0,329 % ; +4,774 %]. Avec le lifecycle PROD, elle tombe à +0,382 % par trade,
IC95 journalier [-0,502 % ; +1,013 %]. Cette découpe post-hoc n'est pas une
validation et ne peut pas être promue.

### Conclusion

- fermer la politique LONG/SHORT symétrique E20-D ;
- ne pas modifier le lifecycle à partir de ce résultat ;
- ne jamais interpréter le rendement contrefactuel à l'open comme tradable,
  puisque la direction n'est connue qu'à 10:00 ;
- une éventuelle suite doit pré-enregistrer une hypothèse LONG-only et la tester
  sur une population indépendante, avec capacité recalculée sur son propre
  horizon de sortie.
