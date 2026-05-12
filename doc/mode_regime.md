# FAQ et Explications — Mode régime Market-Aware

## 1) Est-ce normal d’avoir `Mode régime : capital_preservation` peu importe la date ?

**Non, pas avec une config saine.**

Avec la config corrigée, le comportement normal est :
- certaines dates → `capital_preservation`
- d’autres dates → `normal`

### Cause trouvée
Le provider EODHD pour la “courbe VIX courte” utilisait par défaut :
- `VIX.INDX` pour le VIX principal
- **`VXN.INDX`** comme “VIX court terme” (ce qui est faux, c’est le Nasdaq-100)

Résultat : `VXN` est souvent supérieur à `VIX` ⇒ la logique `short > vix => vix_curve_inverted` déclenchait `capital_preservation` trop souvent.

### Correctif appliqué
On utilise maintenant :
- `VIX.INDX`
- **`VIX9D.INDX`** pour le court terme

et la config YAML explicite :

```yaml
vix:
  enabled: true
  symbol: "VIX.INDX"
  short_symbol: "VIX9D.INDX"
  high_threshold: 25.0
  inverted_curve_mode: capital_preservation
```

## 2) Vérification réelle après correctif

Exemples obtenus :
- **2025-04-15** → `capital_preservation` (`vix = 30.12`)
- **2025-05-15** → `normal` (`vix = 17.83`)
- **2025-07-15** → `normal` (`vix = 17.38`)
- **2025-12-15** → `normal` (`vix = 16.5`)
- **2026-03-15** → `capital_preservation` (`vix = 27.19`)

## 3) Quelles sont les valeurs possibles du mode ?

- `normal` : mode nominal, tout est autorisé
- `capital_preservation` : mode défensif, on réduit le risque mais on continue à entrer
- `close_only` : plus de nouvelles entrées, on gère les sorties
- `cash_only` : tout est bloqué, typiquement pour le backtest

## 4) À quoi sert chaque mode concrètement ?

- `normal` : pipeline standard
- `capital_preservation` : protection du capital (VIX élevé, sentiment warning…)
- `close_only` : on n’ouvre plus rien, on gère les sorties (live)
- `cash_only` : on reste en cash, surtout en backtest

## 5) Est-ce appliqué en live et en backtest ?

Oui, la logique est partagée :
- en live : impacte l’exécution, les entrées, le risk config
- en backtest : même logique, même impact

## 6) “Le `sentiment_score_provider` n’est pas encore branché dans le flux live/IHM standard”, ça veut dire quoi ?

- La logique existe, mais la source réelle du score n’était pas encore branchée automatiquement dans le calcul standard (IHM, run live).
- Le moteur sait quoi faire avec un score, mais il lui fallait une vraie source branchée pour fournir ce score en prod.

## 7) À quoi sert ce `sentiment_score_provider` ?

- Fonction injectée qui donne un score de sentiment agrégé sur N jours.
- Si score <= warning threshold → `capital_preservation`
- Si score <= critical threshold : en live → `close_only`, en backtest → `cash_only`

## 8) Faut-il le brancher ?

- **Pas obligatoire** pour le régime macro réel.
- **Nécessaire** si tu veux exploiter la partie “sentiment breaker” (passage automatique en mode défensif via le sentiment).

## 9) Aujourd’hui, dans ta config, qu’est-ce qui sert vraiment ?

- **VIX** (et courbe VIX courte)
- `enforce_min_notional`, `allowed_slots`
- Ce qui ne sert pas encore ou reste désactivé : `yields`, `sentiment_circuit_breaker`, `patterns.*`, `earnings_shield`, `buyback_blackout`

## 10) Ce que j’ai corrigé

- Correction du mapping court-terme VIX (VIX9D au lieu de VXN)
- Correction du YAML
- Correction des tests et de la doc
- Branchement réel du `sentiment_score_provider` dans le flux live + IHM
- Ajout d’une explication IHM plus explicite du type “pourquoi ce mode ?” avec la source déclenchante

## 11) Validation

- Tests ciblés verts
- Comportement réel validé sur plusieurs dates

## 12) Conseils

- Pour vérifier dans l’IHM : 2025-05-15 → `normal`, 2025-04-15 → `capital_preservation`
- Pour la suite : brancher le sentiment si tu veux la fonctionnalité complète, sinon tu as déjà un régime macro fiable.

## 13) Différence avec le “Régime de marché” des presets Alpha Scanner

**Non, ce n’est pas la même chose.**

Le “Régime de marché” visible dans **Paramètres / Santé** pour les presets :
- sert uniquement à choisir à quel point les presets de diagnostic Alpha Scanner sont permissifs ou stricts ;
- ajuste les seuils de **fraîcheur / couverture** des quotes et du calendrier earnings ;
- n’active pas directement `capital_preservation`, `close_only` ou `cash_only`.

En pratique :
- **modes régime market-aware** = logique métier d’exécution / backtest ;
- **presets Alpha Scanner** = logique IHM/opérateur pour le diagnostic de qualité des dépendances.

### Est-ce redondant ?

- **Fonctionnellement : non**, car ils ne pilotent pas la même couche.
- **En UX : partiellement oui**, parce que le mot “régime” peut faire croire que c’est le même objet.

### Mon avis

- Je **ne le retirerais pas** tout de suite s’il est utile pour calibrer rapidement la sélectivité des presets Alpha Scanner.
- En revanche, je le **renommerais / clarifierais** dans l’IHM (par exemple “Contexte marché pour les presets Alpha Scanner”) pour éviter la confusion avec le vrai mode régime market-aware.

### À quoi sert donc ce preset aujourd’hui ?

Il sert à rendre plus ou moins stricts les seuils du diagnostic Alpha Scanner, par exemple :
- en marché `normal` → seuils standards,
- en marché `weak` → seuils un peu plus stricts,
- en marché `very_selective` → seuils encore plus stricts.

Donc il sert bien, mais **pas** pour décider du mode `normal` / `capital_preservation` / `close_only` / `cash_only`.

