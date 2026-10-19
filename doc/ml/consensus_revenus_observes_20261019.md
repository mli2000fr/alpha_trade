# Consensus de revenus seuls — pilote figé, 19 octobre 2026

## Conclusion

**Pilote exécuté et audité ; efficacité H10 pas encore mesurable.**
Les observations archivées permettent de calculer des variations de consensus
de revenus, sans utiliser l'EPS ni ses conventions inconnues. Le TOP10 récent
ne dispose toutefois que d'une seule cohorte exploitable. Deux motifs ont un
appui documentaire devise/période : DOCN en hausse et FUN en baisse.

**Aucun horizon H10 n'est arrivé à maturité au moment du protocole.**
Les deux cas TOP10 atteindront leur dixième séance le **30 octobre 2026 après
clôture NYSE, 20 h UTC / 21 h Paris**, sous réserve de prix qualifiés.
Ce n'est ni un échec de la piste, ni un résultat favorable, ni un taux de réussite.
Deux cas ne suffiront pas à valider la stratégie, même une fois terminés.

Pas de prix futurs, résultat TP/SL, PnL, fit, appel fournisseur/LLM, commande
broker ou entraînement. Aucune table, configuration, modèle ou collecte de
production modifié. La seule lecture SQL supplémentaire porte sur des
enveloppes de consensus **déjà archivées**, en READ ONLY / REPEATABLE READ,
session UTC, puis ROLLBACK.

## Pourquoi c'est un test distinct

La règle précédente demandait des variations concordantes d'EPS **et** de
revenus. Cette variante ignore complètement l'EPS : une incohérence d'EPS
ne bloque pas une ligne de revenus cohérente, et une hausse d'EPS ne transforme
pas un revenu inchangé en signal positif.

Le [retour du support EODHD](consensus_eodhd_precisions_support_20261019.md)
confirme les unités complètes, USD pour DOCN/FUN et le rôle de `0q`. Il ne
fournit ni de vintages historiques supplémentaires ni l'identité des analystes.

## Contrat figé avant tout résultat H10

Protocole :
`artifacts/research/us_consensus_revenue_only/20261019-v1/protocol.json`,
créé le **19 octobre 2026 à 21:00:55 UTC / 23:00:55 Paris**.

- **Revenus en hausse → motif LONG ; en baisse → motif SHORT ; stables,
  absents ou non comparables → abstention.** Pas de seuil optimisé sur les pertes.
- Même fournisseur, symbole, ancrage fiscal et horizon **`0q`** aux deux bornes.
  Jamais `+1q` contre `0q`, année contre trimestre ou trimestre contre suivant.
- Entre deux ouvertures NYSE successives : comparer le dernier état réellement
  disponible **avant chaque ouverture**. Cela capture la variation entre
  décisions de trading, sans traiter deux copies samedi/dimanche identiques
  comme deux nouvelles occasions indépendantes.
- Disponibilité = maximum observation, disponibilité enregistrée, insertion et
  fin du run terminé. Ce maximum doit précéder strictement le cutoff.
- Au moins trois analystes revenus à chaque borne. **Nombre inchangé pour le
  groupe primaire** ; changements conservés dans un diagnostic séparé.
  Nombre inchangé ne signifie pas forcément mêmes analystes.
- Vérification du hash de l'item, des valeurs normalisées de revenus et de leur
  intervalle ; absence de preuve brute conservée, pas remplacée par une supposition.
- L'ancrage le plus récent parmi les `0q` disponibles sert de **candidat** au
  trimestre courant. Il ne qualifie pas automatiquement l'identité fiscale ou
  le statut non encore publié de toutes les sociétés.

Devise et trimestre documentairement appuyés uniquement pour DOCN/FUN,
Q3 2026 ancré au 30 septembre, sur ce périmètre borné. Pas de USD présumé pour
tout l'univers. Le jour fiscal réel de clôture FUN reste distinct de cet ancrage.
Les faux marqueurs du collecteur ne sont pas modifiés globalement en base.

### Classement Oracle et cible d'évaluation

Préfiltre : modèle courant **Oracle parcours H20**,
`model-factory-20261016180250-3b0515`. Classement de la séance précédente,
scores créés avant l'entrée, modèle disponible avant sa prédiction, score
décroissant et symbole croissant en cas d'égalité ; pas de remplacement.

La seule date de score récente dans le dossier est le **16 octobre**,
1 743 scores créés le 17 : elle autorise le diagnostic de la cohorte entrant le
**19 octobre**, pas une sélection rétrospective des 13–16 octobre et pas une
réutilisation automatique pour le 20 octobre.

Cible future prévue, différente de l'horizon de l'Oracle : **TP10 avant SL5
sur dix séances depuis l'open d'entrée**, expiration à la dixième clôture,
gaps conservés et perte d'abord en cas d'ambiguïté OHLC. Pas d'optimisation
TP/SL, ni de performance exécutée dans ce pilote immature. Les coûts et
références devront être identiques entre les bras lors d'une future comparaison.

### Limite de pré-enregistrement

Les features de cette semaine ont déjà été examinées lors de précédents
diagnostics. Le nouveau protocole est fixé **après les dates d'entrée de ce
petit dossier**, même si les résultats H10 sont encore futurs. Le pilote est
donc exploratoire : aucune affirmation de décision opérationnelle prise en
temps réel le 19 ou de confirmation indépendante.

La confirmation demandera de nouvelles dates après le protocole, des scores
Oracle contemporains, au moins 50 séances d'entrée et 100 épisodes TOP10
sans chevauchement. Davantage de lignes anciennes ne crée pas cette durée.

## Périmètre réellement calculé

Réutilisation immuable du dossier du pilote précédent : collectes **11–18
octobre**, export proche-période de 98 600 lignes pour 1 760 émetteurs.
Ce n'est pas un nouvel inventaire de tout ce qui a pu être collecté depuis.
Le fichier d'univers comporte 1 790 titres ; les manques ne sont pas masqués.

Après passage en `0q` et appariement aux ouvertures : **8 570 comparaisons,
1 724 titres, cinq dates d'entrée** (13, 14, 15, 16 et 19 octobre).
Ces comparaisons ne sont pas 8 570 trades indépendants.

Parmi les comparaisons techniquement cohérentes :

| Nombre d'analystes revenus | Hausses | Baisses | Stables |
|---|---:|---:|---:|
| Inchangé, ≥3 aux deux bornes | **479** | **488** | 6 015 |
| Changé, ≥3 aux deux bornes | 281 | 222 | 0 |
| Absent ou <3 | 29 | 35 | 884 |

Les **967 variations à nombre inchangé** ne sont pas autant de signaux
qualifiés : devise et trimestre ne sont pas certifiés pour tout cet univers,
et les mêmes sociétés peuvent apparaître plusieurs jours.
Les 503 variations avec changement du nombre sont séparées, pas ajoutées au
résultat primaire. Les autres manques/erreurs restent dans les exclusions.

Échantillon fixé sans rendements : dix paires TOP10, vingt émetteurs avec
variation et dix témoins stables. **40 paires / 80 lignes**, vérifiées contre
**58 enveloppes** existantes : 80/80 retrouvées, zéro enveloppe invalide.
Cela ne certifie pas les enveloppes de toutes les 8 570 comparaisons.

## TOP10 : résultats de features seulement

Comparaison des derniers états disponibles avant les ouvertures du 16 et du
19 octobre : snapshots du **15 et du 18 octobre** pour les deux cas ci-dessous.

| Titre | Rang Oracle | Revenus moyens avant → après | Variation relative | Analystes revenus | Motif de recherche |
|---|---:|---:|---:|---:|---|
| DOCN | 10 | 306 657 240 → 306 723 910 USD | **+0,0217 %** | 15 → 15 | LONG |
| FUN | 4 | 1 170 267 190 → 1 168 235 510 USD | **−0,1736 %** | 13 → 13 | SHORT |

Ce sont de **petites variations de prévisions**, ni la croissance du chiffre
d'affaires réalisé, ni une probabilité de hausse/baisse du titre.

Autres cas du TOP10 :

- CCOI : variation brute −0,0158 %, nombre inchangé ; devise et période restent
  non vérifiées dans ce dossier. Abstention du groupe documenté, pas signal rejeté
  par une mesure d'efficacité.
- FMC : −58,28 %, avec analystes revenus **10 → 5** ; exclu du groupe à nombre
  inchangé. Ne pas présenter cela comme une baisse de ventes annoncée par FMC.
- BAND, COHR, ICHR, MXL, TXG et UCTT : revenu moyen inchangé sur ces bornes.

Les deux motifs appuyés restent des **features de recherche**, pas des
recommandations ou une admission live. Les règles de production n'ont pas été
touchées.

## Maturité et suite utile

À l'instant du protocole : **zéro H10 mature**, donc aucun win-rate, AUC,
rendement moyen, PnL ou avantage économique calculable à communiquer.

- Première maturité H10 parmi toutes les comparaisons de l'univers :
  **26 octobre à 20 h UTC / 21 h Paris**, pour les entrées du 13.
- Maturité des deux cas TOP10 du 19 : **30 octobre à 20 h UTC / 21 h Paris**.
- Une date de maturité ne remplace pas des prix qualifiés ni un échantillon
  de confirmation. Le fichier actuel n'est pas un backtest historique 2024–2025.

Travail ultérieur, sans modifier le résultat figé :

1. Qualifier devise et trimestre des autres candidats, en priorité CCOI ;
   ne pas acheter un produit ni supposer USD sans preuve.
2. Conserver de nouveaux snapshots **et scores Oracle quotidiens** pour les
   mêmes dates d'entrée ; pas de score futur ou ancien repris par commodité.
3. À maturité, exporter les prix qualifiés et évaluer la cible figée, en
   gardant les absences et les coûts. Ne pas supprimer les perdants a posteriori.
4. Maintenir les groupes analystes inchangés/changés séparés, puis comparer sur
   un support commun à des références directionnelles simples. Aucun poids,
   seuil ou modèle ne doit être choisi sur ces deux cas.

Aucune automation de suivi ni nouveau batch créé ici. Aucun entraînement à
lancer sur huit dates de collecte.

## Livrables et vérification

Dossier : `artifacts/research/us_consensus_revenue_only/20261019-v1/`.
Protocole, features, sélection de preuves, enveloppes, rapport et audit scellés.

- `scripts/research/us_consensus_revenue_only.py` : phases `prepare`, `build`,
  `proofs`, `finalize`, vers un dossier neuf ; pas d'écrasement de phase terminée.
- `scripts/research/us_consensus_revenue_only_audit.py` : vérification scalaire
  des 8 570 comparaisons, timestamps, motifs, rangs et maturités.
- Les tests vérifient notamment qu'un EPS invalide n'affecte pas le test revenus,
  qu'aucun horizon fiscal n'est mélangé et que les scores du 16 ne sont pas
  utilisés pour des entrées sans classement contemporain.
- **211 tests ciblés passent**, dont 22 nouveaux sur ce pilote et son audit.
  Ce total porte sur les quatorze fichiers du groupe de régression, pas sur
  toute l'application.

Cette vérification est faite par le même assistant, pas une seconde revue
humaine indépendante. Aucun calcul de ce dossier ne reste en cours.
