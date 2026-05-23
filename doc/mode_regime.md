# FAQ opérateur — Mode régime Market-Aware

Cette note répond aux questions fréquentes côté opérateur.

Pour l'explication détaillée de la couche macro/régime (sources Stooq/EODHD, impact sur le backtest et le live, `data_quality=missing`, mode strict vs tolérant), voir :

- [`doc/macro_regime.md`](macro_regime.md)

---

## 1) Est-ce normal d’avoir `Mode régime : capital_preservation` peu importe la date ?

**Non, pas avec une config saine.**

En fonctionnement normal :
- certaines dates doivent rester en `normal` ;
- d'autres peuvent passer en `capital_preservation` quand la macro le justifie.

### Cause historique déjà corrigée
Le provider EODHD pour la courbe VIX courte utilisait autrefois :
- `VIX.INDX` pour le VIX principal ;
- **`VXN.INDX`** comme “VIX court terme”, ce qui était faux.

Résultat : `VXN > VIX` déclenchait trop souvent une pseudo inversion de courbe, donc `capital_preservation` devenait anormalement fréquent.

### Correctif retenu
Le mapping correct est :
- `VIX.INDX`
- `VIX9D.INDX`

Exemple YAML explicite :

```yaml
vix:
  enabled: true
  symbol: "VIX.INDX"
  short_symbol: "VIX9D.INDX"
  high_threshold: 25.0
  inverted_curve_mode: capital_preservation
```

---

## 2) Quelles sont les valeurs possibles du mode ?

- `normal` : fonctionnement nominal
- `capital_preservation` : mode défensif, on continue à opérer mais avec prudence
- `close_only` : plus de nouvelles entrées, on gère surtout les sorties
- `cash_only` : blocage complet des nouvelles entrées

Pour l'impact exact de ces modes sur le moteur de risque, voir `macro_regime.md`.

---

## 3) À quoi sert chaque mode concrètement ?

- `normal` : pas de restriction additionnelle liée au régime
- `capital_preservation` : réduction du risque et du niveau d'agressivité
- `close_only` : on n'ouvre plus de nouvelles positions
- `cash_only` : posture maximale de prudence / blocage des nouvelles entrées

La manière précise dont cela affecte le backtest et le live est décrite dans `macro_regime.md`.

---

## 4) Est-ce appliqué en live et en backtest ?

**Oui.**

La logique de snapshot régime est partagée :
- en **live**, elle ajuste la configuration de risque avant construction du portefeuille cible ;
- en **backtest**, elle ajuste le replay et les diagnostics.

Voir `macro_regime.md` pour le détail des points d'intégration.

---

## 5) Si la macro est absente, que se passe-t-il ?

Deux politiques existent :

- **tolérante** : le run continue et la séance est marquée `data_quality=missing`
- **stricte** : le run échoue explicitement si la macro requise manque

Voir `macro_regime.md` pour les détails sur `allow_neutral_fallback_on_missing_macro_data` et `MacroDataUnavailableError`.

---

## 6) Qu’est-ce qui sert vraiment aujourd’hui ?

En pratique, les briques les plus utiles / visibles aujourd'hui sont :

- **VIX**
- **courbe VIX courte**
- **10Y US** si la brique `yields` est activée
- les garde-fous de capacité (`enforce_min_notional`, `allowed_slots`)

Les autres composantes (ex. sentiment breaker, earnings shield, buyback blackout) dépendent de leur activation et de leur branchement effectif.

---

## 7) Vérification rapide côté IHM

Si tu veux simplement vérifier que le régime n'est pas “bloqué” sur une seule valeur, regarde quelques dates contrastées.

Exemples historiques observés :
- **2025-04-15** → `capital_preservation`
- **2025-05-15** → `normal`
- **2025-07-15** → `normal`

Le but n'est pas de figer ces valeurs comme vérité éternelle, mais de confirmer que le moteur n'est pas coincé artificiellement dans un seul mode.

---

## 8) Différence avec le “Régime de marché” des presets Alpha Scanner

**Ce n'est pas la même chose.**

Le “Régime de marché” visible dans **Paramètres / Santé** pour les presets Alpha Scanner :
- sert à ajuster la sévérité des seuils de diagnostic ;
- agit sur des contrôles de fraîcheur / couverture / qualité ;
- ne pilote pas directement `capital_preservation`, `close_only` ou `cash_only`.

En pratique :
- **mode régime market-aware** = logique métier de risque / exécution / backtest ;
- **presets Alpha Scanner** = logique IHM/opérateur de diagnostic.

### Est-ce redondant ?
- **fonctionnellement : non** ;
- **en UX : partiellement oui**, parce que le mot “régime” prête à confusion.

Une clarification de libellé côté IHM peut être utile pour éviter l'ambiguïté.

---

## 9) Référence détaillée

Pour tout ce qui suit, il faut désormais se référer à la doc détaillée unique :

- [`doc/macro_regime.md`](macro_regime.md)

Cette doc centralise :
- les sources macro ;
- les logs Stooq ;
- l'impact sur le backtest ;
- l'impact sur le live ;
- les diagnostics `macro_missing_dates_count` ;
- la politique strict/tolérant ;
- la signification de `data_quality=missing`.

