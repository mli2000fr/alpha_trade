# Écart Winner 2019 / 2020 : premier mécanisme établi

Complément d'investigation du 25 octobre 2026. Ne modifie pas le protocole
scellé ni les règles des replays en cours.

## Allocation B4 et minimum notionnel : interaction déterministe

Le contrat historique utilise un risque de 1,25 % du capital courant par
entrée, un multiplicateur 1, un SL5 %, une réserve de sizing de 25 pb par
jambe et un minimum de position de 155 $. En allocation B4 réduite à 6 %,
avant même les contraintes de cash, poids, corrélation ou actions entières :

`notionnel maximal théorique = equity × 0,0125 × 0,06 / (0,05 + 2,05 × 0,0025)`

| Capital courant | Plafond théorique de notionnel à allocation 6 % |
| --- | ---: |
| 4 000 $ | 54,42 $ |
| 6 000 $ | 81,63 $ |
| 7 980,17 $ | 108,57 $ |
| 19 011,91 $ | 258,67 $ |
| 24 093,39 $ | 327,80 $ |

En dessous de **11 392,50 $**, ce plafond reste inférieur à 155 $ : aucune
nouvelle entrée ne peut passer dans cet état dégradé à 6 %, même avec du cash
disponible. Ce seuil est une borne continue nécessaire, pas une garantie
d'entrée au-dessus : actions entières, budget figé de la campagne, volatilité
ou autres contraintes peuvent réduire davantage la quantité admise.

Le compte neuf commence 2022 à environ 6 180 $, celui hérité à 19 012 $.
Ce mécanisme est donc capable de bloquer le premier tout en laissant
le second entrer. Il ne prouve pas encore quelles séances se trouvent
effectivement à 6 %, ni quelle fraction de l'écart final il explique.
Les allocations supérieures issues de la récupération B4 changent ce seuil.

La réserve de 25 pb sert au dimensionnement ; les frais comptabilisés restent
8 pb par jambe. Ne pas confondre ces deux valeurs.

## Ce que cela dit — et ne dit pas

- L'explication ne se réduit pas à multiplier le rendement par le capital
  gagné en 2019. Les seuils rendent les trajectoires non proportionnelles.
- Ce n'est pas une preuve de bug : les contraintes sont appliquées conformément
  aux calculs lus. Leur interaction peut néanmoins laisser un petit compte
  presque sans nouvelles entrées en régime dégradé.
- Les positions, plans, séquences de pertes et pics de risque hérités changent
  aussi le chemin suivi. Les trois replays contrôlés doivent en mesurer l'effet.
- Aucun seuil n'a été desserré et aucune règle de production n'a été modifiée.

Protocole : [investigation et replays](winner_ecart_dates_depart_audit_20261025.md).
Suivi : `artifacts/research/us_winner_start_state_audit/20261025-v1/progress.json`.
Les résultats ne sont complets que lorsque la racine contient `report.json`
avec `COMPLETED_AUDITED_EXPLORATORY` et les trois comptes audités.
