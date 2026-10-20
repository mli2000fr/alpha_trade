# Retour à la moyenne dans la même séance — protocole du 20 octobre 2026

## Objet et statut

Expérience distincte des retours à la moyenne H10/H20 et des features intraday
utilisées pour prédire plusieurs jours. **Ni modèle entraîné, ni recommandation
de trading, ni reproduction d'une stratégie institutionnelle.**

GO utilisateur pour préparer et tester sur les données existantes. La première
version a été rédigée avant les résultats ; voir le bilan daté en fin de document.

## Données et population figées avant les résultats

- Univers actuel `config/univers_batch/univers_filtred_tradable.txt` : biais de
  survivants conservé, pas univers historique complet.
- Séances du 3 janvier 2024 au 2 septembre 2026 ; les rangs Oracle archivés
  s'arrêtent au 1er septembre, utilisés uniquement **la séance suivante**.
- Chaque jour : 100 candidats au plus, classés par médiane des vingt séances
  précédentes de `close × volume`, proxy supérieur à 20 M USD et prix précédent
  au moins 5 USD. Vingt séances valides et métadonnées stables requises.
- Les séries daily peuvent être retraitées par le fournisseur : ce proxy n'est
  pas une certification du véritable montant négocié connu à l'époque.
- Préparation : **66 900 couples titre/séance, 234 titres distincts, 669 séances**.
- Barres existantes SQL `stock_bars_intraday`, exclusivement `alpaca_sip`,
  fournisseur Alpaca, `5m`, `raw`, `regular`, `US_EQ`. Aucun IEX ni remplissage.
- Extraction terminée en une transaction, 539 parties symbole/année,
  **3 238 954 barres**, du 20 octobre 18:30:39 au 18:32:20 UTC.
  Aucun téléchargement, compte/API payant ou quota fournisseur consommé.
- Contrôle de faisabilité : aucune barre SPY ou des onze ETF sectoriels dans
  cette table. La référence retenue **avant résultats** est donc la médiane des
  rendements depuis l'ouverture du panier liquide, pas une neutralité sectorielle.
- Médiane calculée à chaque instant sur les seuls préfixes complets et valides :
  au moins 80 % du panier et 50 titres. Un trou futur ne supprime pas un pair
  du calcul passé. Le titre lui-même est inclus dans la médiane.

## Règle unique

De trente minutes après l'ouverture à une heure avant la clôture, chercher le
premier excès relatif d'au moins 2 %, puis un début de retournement :

- LONG : sous-performance d'au moins 2 points, clôture 5m supérieure à la
  précédente, plus bas non inférieur au précédent, prix sous le VWAP proxy ;
- SHORT symétrique, **diagnostic uniquement**, sans preuve de locates historiques.

Le VWAP utilisé est une approximation cumulée
`somme(((high + low + close) / 3) × volume) / somme(volume)`, non le véritable
VWAP des transactions. Seules les barres déjà terminées sont utilisées.

Entrée à l'ouverture de la barre suivante, jamais dans celle qui donne le
signal. Une seule occasion par titre/jour ; si cette ouverture a déjà dépassé
l'objectif, abstention, sans rechercher une seconde entrée plus favorable.

Protections : **stop 1 %**, objectif = VWAP proxy figé au signal, sortie maximale
à l'**ouverture de la dernière barre 5m** (15:55 New York en séance ordinaire,
12:55 en demi-séance). Pas de détention H20, trailing ou moyenne à la baisse.
Calendrier NYSE, fuseaux et changements d'heure réels.

Gaps défavorables au prix d'ouverture, non plafonnés au stop ; gaps favorables
vers objectif plafonnés à ce dernier. Si les deux barrières sont touchées dans
la même barre, stop d'abord. Les barres ne prouvent pas l'ordre réel des ticks.

## Comparaisons et coûts

Périmètre principal : panier liquide sans Oracle. Deux sous-ensembles secondaires
figés : TOP20 % et TOP10 Oracle **de la veille**. Rangs de recherche PATH_H20
CatBoost OOS archivés, pas nouveau scoring du champion LightGBM live.

Sur chaque signal, comparer la direction proposée à son inverse et aux sens
toujours LONG/SHORT, au même instant et avec même distance d'objectif. Sur le
sous-groupe LONG, « toujours LONG » est identique : ce témoin ne prouve donc
aucun avantage supplémentaire de sélection.

Rendement par occasion, base hypothétique 1 000 USD : 10 bps/jambe + 1 USD par
ordre, stress à 25 bps/jambe. Frais de sortie proportionnels à sa valeur ; short
avec un jour d'emprunt hypothétique à 0,3 % annuel, **pas tarif/locate garanti**.
Pas de capital partagé, levier, réinvestissement, rendement annuel composé ou
drawdown portefeuille revendiqué.

Incertitude : bootstrap par blocs de vingt séances, 1 999 tirages, seed figée.
Gate LONG exploratoire : au moins 100 trades et 50 dates par année, borne basse
du net stress et de l'avantage sur SHORT apparié positive en 2025 **et** 2026.
2024 descriptif. Ces années ont déjà servi dans d'autres recherches : elles ne
constituent pas un véritable nouvel échantillon vierge.

Un chemin d'exécution incomplet reste **UNKNOWN**, même si un TP antérieur
paraît suffisant. Aucun remplacement par un autre titre, ni inconnu devenu perte.
La sélection par couverture complète reste un biais à mesurer et à signaler.

## Reproduction et archives

Racine : `artifacts/research/us_intraday_mean_reversion/20261020-v1/`.
`protocol.json` scelle les règles et hashes des scripts, tests, univers, scores
et prix. `pool.parquet` conserve la sélection antérieure ; `sessions.parquet`
le calendrier ; `snapshot-ready.json` les parties SQL lues dans une transaction
`REPEATABLE READ / READ ONLY`, terminée par `ROLLBACK`.

```powershell
python -u -m scripts.research.us_intraday_mean_reversion --phase prepare --output artifacts/research/us_intraday_mean_reversion/20261020-v1
python -u -m scripts.research.us_intraday_mean_reversion --phase snapshot --output artifacts/research/us_intraday_mean_reversion/20261020-v1
python -u -m scripts.research.us_intraday_mean_reversion --phase replay --output artifacts/research/us_intraday_mean_reversion/20261020-v1
python -u -m scripts.research.us_intraday_mean_reversion_audit --output artifacts/research/us_intraday_mean_reversion/20261020-v1
python -u -m scripts.research.us_intraday_mean_reversion_quality --root artifacts/research/us_intraday_mean_reversion/20261020-v1 --output artifacts/research/us_intraday_mean_reversion/20261020-v1/qualification-v1
```

Ne pas relancer deux instances dans le même dossier. Les résultats sont
immuables ; une extraction SQL interrompue demande un dossier neuf, pas une
fusion silencieuse d'états différents de la base.

`coverage.parquet`, `basket.parquet`, `signals.parquet`, `trades.parquet`,
`summary.csv`, `comparisons.csv`, `monthly.csv`, `report.json`, `final-audit.json`
constituent les sorties. Le contrôle est une autre implémentation du même
assistant, **pas une revue humaine indépendante**.

Tests : 19 cas ciblés passent avant préparation ; trois contrôles supplémentaires
sur le rapprochement des prix, les préfixes et les gaps à l'expiration portent le
total à **22**.
Lancement limité, sans le seuil
de couverture global du projet ; cela ne signifie pas que toute la suite passe.

Le supplément `qualification-v1` dispose de son propre protocole scellé, sans
modifier celui du premier rejeu. Il reconstruit les signaux et la médiane par
une autre implémentation puis compare, pour les issues initialement évaluables,
les quatre OHLC agrégés de la séance à la référence quotidienne. Une échelle
constante est permise entre raw SIP et daily retraité ; la dispersion des quatre
ratios ne doit pas dépasser **1 %**, tolérance de qualité déjà utilisée dans
les anciens tests intraday, pas sélectionnée ici sur les gains. Les cas en
désaccord restent inconnus pour l'analyse qualifiée, pas réparés ou remplacés.
Ce contrôle après coup des prix n'est jamais utilisé comme feature de décision.
Les deux bilans, brut et qualifié, restent conservés.

Une correction technique explicite du supplément applique aussi le plafonnement
au TP lorsqu'un gap favorable apparaît à l'ouverture de la dernière barre : le
premier rejeu utilisait alors le prix d'expiration sans plafonnement. Cela ne peut
que réduire le rendement, jamais améliorer un résultat. Les sorties d'origine
restent conservées ; les tableaux définitifs utilisent les résultats corrigés.

## Sources d'inspiration, pas preuve de rentabilité de cette règle

- [Huaan — sélection multifactorielle et gestion des expositions](https://www.huaan.com.cn/news/2025-07-14/229590_1.shtml).
- [Campbell — arbitrage statistique, momentum et fondamentaux diversifiés](https://www.campbell.com/institutional-investors/).
- [CFM — combinaison de moteurs directionnels, statistiques et de volatilité](https://www.cfm.com/cfm-50-giants-in-hedge-funds/).

Ces sources ne publient pas notre règle « excès 2 % / stop 1 % / VWAP ». Celle-ci
est notre hypothèse de recherche, pas une recette attribuée à ces sociétés.
Un résultat historique ne qualifierait pas à lui seul l'exécution réelle : NBBO,
profondeur, haltes, frais et disponibilité du courtier restent à contrôler.
Une mise en service intraday demanderait également un ordinateur/service actif
pendant les heures d'entrée ; aucun horaire de batch n'est modifié ici.

## Bilan

### Couverture et premier rejeu

| Année | Couples sélectionnés avant données intraday | Au moins une barre | Séance complète valide | Signaux | Chemin initialement évaluable |
|---|---:|---:|---:|---:|---:|
| 2024 | 25 100 | 0 | 0 | 0 | 0 |
| 2025 | 25 000 | 24 981 | 24 425 | 5 389 | 5 343 |
| 2026, jusqu'au 2 septembre | 16 800 | 16 792 | 16 786 | 6 364 | 6 344 |

La couverture en 2024 est **absente**, pas un résultat nul de stratégie. Il n'a
pas été tenté de télécharger cette année. Les 11 753 signaux comprennent :
11 687 issues initialement évaluables, 30 chemins d'exécution incomplets,
33 abstentions car l'ouverture suivante dépasse déjà le VWAP cible, trois cas
réservés pour base de prix. Les 46 748 lignes de trades incluent les quatre
politiques appariées, pas autant d'opérations indépendantes.

Premier audit terminé : `PASS_EXPLORATORY_DATA_AND_EXECUTION_CHECKS`, 11 753
préfixes de signaux contrôlés et 46 748 sorties/coûts revérifiés. Le bilan
qualifié ci-dessous ajoute la reconstruction de l'ensemble des candidats et
les réserves de prix ; le premier audit ne certifie pas à lui seul ces réserves.

### Résultat définitif après qualification — NO_GO de cette règle

**Expérience terminée. Aucune promotion ML, PAPER ou LIVE.** Le contrôle
`qualification-v1/report.json` reconstruit les **66 900** couples candidats et
leurs préfixes, les 11 753 premiers signaux, puis vérifie les prix quotidiens.
Statut technique `PASS_OFFLINE_CAUSAL_AND_PRICE_QUALITY_CHECKS`, verdict de la
règle `NO_GO_CURRENT_FROZEN_RULE`. Un PASS de contrôles n'est pas un PASS économique.

- **2025 : 5 338** occasions qualifiées, dont **2 719 LONG / 2 619 SHORT**.
- **2026 : 6 336** occasions qualifiées, dont **3 158 LONG / 3 178 SHORT**.
- **13 réserves de prix** s'ajoutent aux motifs d'origine : cinq en 2025,
  huit en 2026. Elles ne sont ni des pertes, ni des prix corrigés en base.
- Quatre lignes de politiques appariées nécessitaient le plafonnement
  conservateur du gap final au TP. Correction conservée explicitement dans
  `qualified-trades.parquet`, colonne `final_open_target_corrected`.
- Les quatre politiques correspondent à **46 696 lignes**, mais seulement
  **11 674 occasions distinctes** après qualification. Elles ne se cumulent pas.

Résultats **LONG**, rendements moyens par occasion, pas rendement du capital
sur l'année. Les sous-ensembles Oracle restent intersectés au panier liquide ;
ce n'est pas une simulation de tous les membres du TOP10 sans filtre de liquidité.

| Périmètre | Année | Occasions LONG | Dates | Titres distincts | Brut moyen | Net moyen | Gagnants nets |
|---|---|---:|---:|---:|---:|---:|---:|
| Panier liquide sans Oracle | 2025 | 2 719 | 248 | 167 | −0,018 % | **−0,418 %** | 37,07 % |
| Panier liquide sans Oracle | 2026 | 3 158 | 168 | 163 | +0,050 % | **−0,350 %** | 40,22 % |
| Panier liquide ∩ TOP20 % Oracle veille | 2025 | 1 086 | 227 | 50 | −0,048 % | **−0,448 %** | 37,66 % |
| Panier liquide ∩ TOP20 % Oracle veille | 2026 | 1 530 | 164 | 61 | +0,057 % | **−0,343 %** | 41,70 % |
| Panier liquide ∩ TOP10 Oracle veille | 2025 | 70 | 59 | 7 | −0,217 % | **−0,616 %** | 25,71 % |
| Panier liquide ∩ TOP10 Oracle veille | 2026 | 182 | 102 | 12 | +0,314 % | **−0,086 %** | 50,00 % |

Le dernier chiffre, proche de zéro en 2026, n'est pas une réussite transversale :
intervalle net TOP10 LONG [−0,236 % ; +0,139 %], seulement douze titres et 2025
négatif sur sept titres. Le minimum de 100 trades/year n'est pas atteint pour
ce sous-ensemble en 2025. Ces sous-tests ne remplacent pas le critère principal.

Sur le panier principal LONG, intervalles du net [−0,451 % ; −0,371 %] en 2025,
[−0,387 % ; −0,298 %] en 2026. Avec coûts stressés : **−0,718 % / −0,650 %**.
Même en retirant comptablement la commission fixe de 1 USD par ordre, tout en
conservant 10 bps par jambe, le net principal LONG reste **−0,218 % / −0,150 %**.
C'est une décomposition de coûts, pas un nouveau choix de seuil ou tarif Alpaca
réel prouvé. L'échec n'est donc pas seulement causé par cette commission.

Sur 1 000 USD par occasion LONG principale :

- 2025 : 1 008 gains / 1 711 pertes, gain moyen +5,59 USD, perte moyenne −9,94 USD ;
- 2026 : 1 270 gains / 1 888 pertes, gain moyen +6,26 USD, perte moyenne −10,07 USD.

Un TP touché n'est pas automatiquement un gain net : un retour très court au
VWAP peut ne pas payer les frais. Le brut principal est lui-même proche de zéro,
ce qui ne laisse pas de marge économique suffisante.

SHORT principal, diagnostic sans preuve de locates : **−0,418 %** en 2025,
**−0,373 %** en 2026 ; gagnants nets 36,54 % / 40,37 %. Les deux sens regroupés
restent négatifs : **−0,418 % / −0,362 %**. L'inverse apparié et les contrôles
toujours LONG/SHORT sont publiés dans `comparisons.csv` / `summary.csv`, sans
inverser la stratégie après observation pour sélectionner un gagnant.

Les deux gates principaux 2025/2026 échouent : net stress non positivement établi
et avantage LONG sur SHORT apparié non positivement établi. Le TOP20 % n'améliore
pas durablement ; le TOP10 change beaucoup entre les deux années mais ne passe
pas le contrat. Pas d'optimisation a posteriori du seuil 2 %, du stop 1 %, du
créneau horaire, du VWAP ou des coûts pour sauver le résultat.

### Réserves de prix conservées

| Date | Titre | Dispersion des ratios OHLC raw/daily |
|---|---|---:|
| 2025-04-08 | COF | 1,332 % |
| 2025-04-08 | KKR | 1,162 % |
| 2025-04-10 | MRVL | 2,750 % |
| 2025-04-10 | ADI | 1,260 % |
| 2025-11-06 | INTC | 3,493 % |
| 2026-01-15 | WDC | 1,033 % |
| 2026-01-29 | CLS | 1,041 % |
| 2026-03-23 | MU | 3,399 % |
| 2026-03-23 | WDC | 2,831 % |
| 2026-04-17 | EOG | 1,085 % |
| 2026-05-28 | PLTR | 1,109 % |
| 2026-06-10 | ORCL | 1,252 % |
| 2026-07-27 | FTNT | 1,035 % |

Ces dispersions ne désignent pas automatiquement le mauvais fournisseur : elles
signalent un désaccord de périmètre/prix à qualifier. Aucun cours, univers ou
modèle n'est modifié pour ce test.

### Conclusion et clôture

**Règle non retenue, test clos.** Le volume d'observations suffit pour ne pas
attribuer ce résultat à cinq cas isolés, mais ne transforme pas les données
retraitées en preuves PIT ou d'exécution broker. Cela ne réfute pas toutes les
formes de retour à la moyenne ni les stratégies privées des professionnels.
Cela ne mesure pas non plus directement la prédiction D1/D10 à H20 : l'objectif
ici était exclusivement une correction dans la séance.

22 tests ciblés passent, reçus dans `test-results.xml`. Aucun entraînement,
nouveau téléchargement, appel GPT/DeepSeek, écriture SQL, ordre, batch,
modèle ou configuration de trading modifié. Les scripts de recherche et la
documentation seuls sont ajoutés ; `.gitattributes` préserve leurs sources LF.
