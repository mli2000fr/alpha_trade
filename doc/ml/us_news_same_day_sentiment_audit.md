# News/sentiment et mouvement du même jour — audit descriptif

Protocole du 11 octobre 2026. Univers actuel :
`config/univers_batch/univers_filtred_tradable.txt`.
Période : 2025 et 2026 jusqu'au 9 octobre, résultats séparés par année.
Pas de sélection Oracle, entraînement, appel fournisseur, ordre ou écriture SQL.

## Question et méthode

Une nouvelle très positive/négative est-elle associée au mouvement du titre
le jour de publication ? Ce test n'est pas une preuve de causalité, ni une
validation de prévision H20 ou de profitabilité.

- Source : `news_raw` joint à `news_ticker_sentiment`, calculs réussis seulement.
- Seuil figé strict : `positive_score > 0.9` ou `negative_score > 0.9`.
- Présence d'au moins un article fort : positif seul, négatif seul, mixte,
  aucun score fort. Aucun article manquant transformé en sentiment neutre.
- Déduplication par symbole, hash de contenu, heure de publication.
- Calendrier US réel, fuseau New York et demi-séances ; pas d'heure Paris fixe.
- Avant ouverture : clôture veille→ouverture, ouverture→clôture et clôture→clôture.
- Pendant séance : association ouverture→clôture seulement. Les cours journaliers
  ne permettent **pas** d'isoler prix juste avant article→clôture.
- Après clôture et jours sans séance : étude séparée à la séance suivante,
  jamais attribution au mouvement d'une séance déjà terminée.
- Horodatages UTC exactement minuit exclus des vues horaires comme
  potentiellement imprécis ; conservés dans le diagnostic global quand admissibles.

Cours actions OHLCV split-adjusted, non remplis, positifs et cohérents. Clôture
précédente exactement à la séance précédente : pas de saut au dernier cours
connu en cas de barre absente. Rendement relatif à SPY clôture→clôture également
mesuré. Moyenne, médiane, fréquence hausse/baisse et moyenne équipondérée par jour.
Baseline univers complet distincte du groupe « articles présents sans score fort ».

## Disponibilité des informations

Vues rétrospectives séparées des vues où news et sentiment étaient disponibles
avant ouverture/clôture. Disponibilité conservatrice = maximum des `updated_at`
actuels news/sentiment. Ces valeurs ne sont pas des vintages immuables : une
mise à jour tardive peut exclure un score pourtant anciennement disponible.
Un sentiment recalculé après la journée n'est pas présenté comme exploitable
en temps réel. Les probabilités du classifieur expriment le ton, pas la probabilité
que le titre monte.

## Limites et suivi

Une news peut décrire une hausse déjà produite ; publication et mouvement
peuvent aussi partager une cause commune (résultats, marché). Biais d'univers
actuel, de couverture médiatique, répétitions de titres et absence de contrôle
secteur/taille restent à considérer. Pas de frais ou portefeuille simulés.

Script : `scripts/research/us_news_same_day_audit.py`. Trois tests de frontières
de séance, clôture anticipée, groupes mixtes, seuil strict et groupe vide passent.
Cache mensuel repris sans retéléchargement ; aucune modification des batchs actifs.

Artefacts : `artifacts/research/us_news_same_day/audit-202510-20261011-v1/`
(le nom technique du dossier ne restreint pas la période, qui commence janvier 2025).
`progress.json` indique la progression ; `report.json` confirme l'achèvement.

## Résultat terminé

367 851 observations article/titre réussies, scores valides ; aucune ligne retirée
par la déduplication choisie. 126 790 avant ouverture, 119 569 en séance,
80 333 après clôture, 41 159 un jour sans séance. 688 timestamps UTC exactement
minuit sont marqués ambigus. Les groupes sont des observations **titre/jour**,
pas des articles ni des transactions. Les résultats excluent les rendements
indisponibles, avec compteurs distincts dans le rapport.

### Sentiment du jour et clôture veille → clôture du jour

Articles publiés avant ouverture ou pendant la séance. Les articles après
clôture sont exclus de cette comparaison.

| Année | Groupe | Observations avec rendement | Rendement moyen | Médiane | Fréquence de hausse | Excès moyen contre SPY |
|---|---|---:|---:|---:|---:|---:|
| 2025 | Positif seul >0,9 | 16 745 | +0,611 % | +0,258 % | 56,09 % | +0,505 point |
| 2025 | Négatif seul >0,9 | 11 794 | −0,547 % | −0,213 % | 45,18 % | −0,591 point |
| 2025 | Articles présents sans score fort | 48 830 | +0,105 % | +0,076 % | 51,77 % | +0,022 point |
| 2026 | Positif seul >0,9 | 14 598 | +0,535 % | +0,203 % | 53,89 % | +0,440 point |
| 2026 | Négatif seul >0,9 | 8 610 | −0,569 % | −0,261 % | 45,20 % | −0,608 point |
| 2026 | Articles présents sans score fort | 36 479 | +0,096 % | +0,052 % | 50,95 % | +0,014 point |

Le groupe mixte est distinct : rendement moyen −0,551 % en 2025, −0,767 % en
2026. Baseline univers complet : +0,046 % et +0,065 % respectivement.
Ces groupes n'ont pas une composition sectorielle ni une couverture comparables.
Les moyennes sont en pourcentage de variation, pas une performance cumulable.

La moyenne clôture→clôture du groupe positif est positive dans 22/22 mois,
celle du négatif négative dans 21/22 mois (octobre 2026 partiel). Cela renforce
le constat d'association, **pas** une interprétation causale ou exploitable.

### News avant ouverture : où se trouve le mouvement ?

| Année | Groupe | Clôture veille→ouverture | Ouverture→clôture | Clôture veille→clôture |
|---|---|---:|---:|---:|
| 2025 | Positif seul | +0,446 % | −0,053 % | +0,389 % |
| 2025 | Négatif seul | −0,262 % | +0,026 % | −0,237 % |
| 2026 | Positif seul | +0,502 % | +0,052 % | +0,552 % |
| 2026 | Négatif seul | −0,328 % | −0,034 % | −0,367 % |

La relation est surtout présente **dans le gap, avant une entrée à l'ouverture**.
Après ouverture, le sens est faible et change selon l'année. Les moyennes
mensuelles ouverture→clôture des groupes positif et négatif sont chacune
positives dans 12/22 mois : pas de persistance directionnelle démontrée.
Les composantes ne s'additionnent pas exactement (rendements composés).

### News en séance et après clôture

En séance, ouverture→clôture : positif +0,353 % / +0,172 % (2025/2026),
négatif −0,519 % / −0,355 %. Mais ce mouvement peut **précéder l'article** :
il faut des prix horodatés avant/après chaque publication pour tester une entrée.

Après clôture ou jour non tradé, séance suivante : positif clôture→clôture
+0,330 % / +0,280 %, négatif −0,079 % / −0,085 %. Les mouvements positifs
se concentrent encore dans le gap (+0,336 % / +0,262 %), avec un mouvement
ouverture→clôture −0,001 % / +0,025 %. Le regroupement jours non tradés/post-close
est explicite et peut être affiné dans un protocole distinct.

### Réserve PIT déterminante

**Zéro observation admissible** dans les vues où les `updated_at` actuels
news/sentiment précèdent l'ouverture ou la clôture. Cela interdit de déclarer
ce test exploitable historiquement en live. Ce n'est pas la preuve que tous
les articles étaient indisponibles : les dernières mises à jour ne prouvent
pas leur première disponibilité. Il manque des vintages immuables de scoring.

## Conclusion

**Oui, le sentiment fort est associé au mouvement du même jour dans les deux
années.** La mesure demandée répond donc positivement à la question descriptive.
En revanche, acheter à l'ouverture après une news positive n'est pas validé :
le gap a déjà absorbé l'essentiel de la relation. Les articles en séance peuvent
relater le mouvement plutôt que le prévoir.

Suite éventuelle sur nouveau GO : aligner les cours intraday autour de l'heure
de publication et archiver prospectivement réception/scoring, puis mesurer
uniquement le rendement après une décision réellement possible. Aucun changement
de modèle, filtre de trading ou test économique lancé dans cet audit.
