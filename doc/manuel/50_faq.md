# 50. FAQ — questions fréquentes des débutants

## Démarrage

### ❓ Combien de temps avant de pouvoir gagner de l'argent ?

Comptez **6 mois minimum** : 2 mois en simulate + 3 mois en paper +
1er trade live à petite échelle. Tout ce qui va plus vite est dangereux.

### ❓ Combien faut-il pour démarrer ?

Techniquement 100 USD suffisent (Alpaca permet les fractional shares).
Réellement, 1 000 → 2 000 € est un bon point de départ pour amortir les
frais et constituer 3 lignes diversifiées.

### ❓ Faut-il connaître le code Python ?

Non pour utiliser l'IHM. Oui pour modifier des paramètres avancés
(`config.yaml`).

### ❓ L'application fonctionne-t-elle sur Mac / Linux ?

Possible mais non testé. La doc cible Windows.

## Fonctionnement

### ❓ Pourquoi 0 candidat retenu aujourd'hui ?

Plusieurs causes :
1. Marché baissier généralisé (RSI < 90 partout).
2. Filtres trop stricts pour votre preset.
3. Pipeline pas exécuté aujourd'hui (vérifiez page Vue d'ensemble).
4. Données pas à jour (step 2 a échoué).

Voir [05_page_screening.md §5](05_page_screening.md).

### ❓ Pourquoi ma page est vide ?

Voir [51_depannage.md §1](51_depannage.md).

### ❓ Le ML peut-il prédire l'avenir ?

**Non.** Il estime une probabilité conditionnelle basée sur des patterns
historiques. La probabilité 0.65 signifie « historiquement, dans des
conditions similaires, le cours a monté de +2 % en 5 jours dans 65 % des
cas ». Ce n'est pas une garantie.

### ❓ Combien de trades par mois sur 2 000 € ?

Avec preset `capital_0_2000_eur` et 3 positions max : ~10-30
trades/mois (rotation tous les 5-10 jours en moyenne).

## Argent et performance

### ❓ Combien je peux gagner par mois avec 2 000 € ?

En espérance long terme : 1-2 % / mois (~20-50 €). En réalité : très
volatil, des mois à -200 €, d'autres à +500 €.

### ❓ Et si je perds tout ?

C'est possible. C'est pourquoi vous ne devez investir que de l'argent que
vous pouvez perdre **intégralement** sans impact sur votre vie.

### ❓ Puis-je faire du levier (margin) ?

**Non, pas avant 25 000 USD.** Le levier multiplie les pertes. Le preset
`capital_0_2000_eur` impose `cash` automatiquement.

### ❓ Faut-il déclarer aux impôts ?

**Oui.** Voir [20_gestion_petit_capital_2000eur.md §6](20_gestion_petit_capital_2000eur.md).

## Erreurs fréquentes

### ❓ « Insufficient buying power » lors d'un ordre

Le compte n'a plus assez de cash. Causes :
- positions ouvertes immobilisent le cash,
- ordres limit en attente immobilisent le cash en `pending`,
- erreur de calcul `target_quantity` (rare).

### ❓ « Order rejected: PDT »

Vous avez fait > 3 day-trades / 5 jours sur compte margin < 25k$.
Solution : passez en cash.

### ❓ Watcher rouge

Le processus est tombé. Relancez :
```powershell
python run_execution_protection_watch.py
```

### ❓ « DB indisponible »

Voir [51_depannage.md §2](51_depannage.md).

### ❓ Pipeline bloqué « En cours » depuis 2h

Probablement le step 2 (import bars) coincé. Solution :
1. Page **🛟 Supervision Ops** → kill le PID concerné.
2. Relancez juste ce step.

## Stratégie

### ❓ Quelle est la stratégie sous-jacente ?

**Momentum swing trade long-only** : on achète les actions qui montent
fort (force relative > 90), proches de leur plus haut 52 semaines, avec
un boost de sentiment news positif et une probabilité ML > 55 %.

### ❓ Puis-je faire du short ?

Non actuellement supporté.

### ❓ Puis-je trader des cryptos / forex / options ?

Non, l'app est conçue pour **US stocks** uniquement.

### ❓ Pourquoi pas de buy & hold long-terme ?

Le moteur est calibré pour des horizons 2-10 jours. Pour du long-terme,
préférez un ETF MSCI World en DCA.

### ❓ Puis-je modifier la stratégie ?

Oui via les paramètres (page Settings) et le code Python. Mais cela
demande une bonne compréhension. Lisez d'abord
[doc/selector.md](../selector.md) et [doc/risk_management.md](../risk_management.md).

## Pour aller plus loin

- Dépannage : [51_depannage.md](51_depannage.md)
- Sécurité : [52_securite_et_argent_reel.md](52_securite_et_argent_reel.md)
- Glossaire : [30_glossaire_financier.md](30_glossaire_financier.md)

