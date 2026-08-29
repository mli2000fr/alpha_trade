# α-Trade — Guide complet de recalibration après changement majeur de modèle ou d’univers

**Objectif du document**  
Ce document sert de guide de maintenance et de passation pour une personne qui reprend l’application sans connaître tout l’historique des recherches. Il décrit **quoi revalider, quoi recalibrer, dans quel ordre, avec quels garde-fous et pourquoi** lorsqu’un changement important affecte le modèle ML, l’univers de symboles, la structure du portefeuille ou les hypothèses de trading.

> Principe directeur : **un nouveau modèle ou un nouvel univers ne doit jamais hériter automatiquement du budget de risque, du levier, du nombre de positions, des paramètres CP/B4 ou des paramètres de lifecycle du modèle précédent.**  
> Les règles de sécurité peuvent rester communes, mais les paramètres calibrés doivent être requalifiés.

---

## 0. Définitions et principe de séparation

### 0.1 Changement mineur vs changement majeur

On distingue trois niveaux de changement :

| Niveau | Exemple | Action recommandée |
|---|---|---|
| **Niveau 1 — Retrain mineur** | même architecture, même univers, même target, même features, nouvelle date de cutoff | revalidation rapide |
| **Niveau 2 — Nouveau batch sensiblement différent** | mêmes grandes briques mais nouvelles features, nouvel horizon champion, changement de distribution du score, nouvel algo champion | recalibrage portefeuille + risque |
| **Niveau 3 — Changement majeur** | nouvel univers, nouvelle famille de modèle, nouvelle target, nouveau comportement long/short, nouvelle fréquence, nouveau lifecycle | certification complète |

### 0.2 Ce qui appartient au modèle / univers

Les éléments suivants dépendent directement ou indirectement du modèle et/ou de l’univers :

- distribution des scores et des ranks ;
- qualité du TOP/BOTTOM ;
- stabilité temporelle ;
- fréquence des signaux ;
- long/short asymétrie ;
- turnover ;
- volatilité des titres sélectionnés ;
- liquidité ;
- corrélation intra-book ;
- concentration sectorielle ;
- efficacité des stops/TP/trailing ;
- drawdowns ;
- vitesse de recovery ;
- gross/net exposure optimal ;
- besoin réel de levier ;
- fréquence d’activation de CP ;
- fréquence de trip B4 ;
- valeur du force-close.

### 0.3 Ce qui doit rester invariant autant que possible

Les éléments ci-dessous doivent être vus comme **garde-fous structurels**, pas comme variables à tuner à chaque batch :

- PIT / no-lookahead ;
- séparation train / validation / OOS ;
- calculs de features strictement causaux ;
- coûts réalistes ;
- contraintes de marge ;
- contrôles de liquidité ;
- audit logs ;
- parité backtest ↔ prod ;
- fail-safe si données manquantes ;
- limite absolue de levier broker ;
- principe de rollback ;
- principe « aucun nouveau modèle ne récupère automatiquement le risk budget de l’ancien ».

---

# 1. Gate 1 — Revalider l’alpha du nouveau modèle

Aucun travail de sizing / CP / B4 ne doit commencer tant que le modèle ne prouve pas qu’il possède encore un signal exploitable.

## 1.1 Vérifier la qualité du ranking

Pour chaque horizon disponible (par ex. H3/H5/H10/H15/H20) :

- IC rank moyen ;
- IC médian ;
- ICIR ;
- t-stat de l’IC ;
- distribution de l’IC par date ;
- % de dates avec IC > 0 ;
- rolling IC 63j / 126j / 252j ;
- TOP decile vs univers ;
- TOP vs random ;
- TOP vs BOTTOM ;
- monotonicité par bucket / décile ;
- sector-matched random ;
- placebo par permutation intra-date.

### Gate minimum recommandé

Ne pas se contenter d’un IC global positif. Le modèle doit montrer :

1. un spread TOP−random positif ;
2. un spread TOP−BOTTOM positif ;
3. une significativité raisonnable ;
4. une stabilité temporelle acceptable ;
5. pas d’inversion persistante sur la vraie période OOS.

## 1.2 Distinguer rendement absolu et alpha relatif

Un portefeuille long peut gagner simplement parce que le marché monte.

Toujours comparer :

- TOP modèle ;
- random same-day ;
- univers equal-weight ;
- sector-matched random ;
- SPY / benchmark ;
- éventuellement momentum naïf.

Un bon modèle doit battre les comparateurs **avec les mêmes contraintes d’exécution**.

## 1.3 Test portefeuille random

Rejouer le pipeline complet avec :

- mêmes coûts ;
- mêmes exits ;
- mêmes CP/B4 ;
- même sizing ;
- même nombre de positions ;
- seule différence = sélection des noms aléatoire.

Mesurer percentile du modèle vs 500/1000 randoms sur :

- Return ;
- Sharpe ;
- Sortino ;
- PF ;
- MaxDD ;
- worst 3m / 6m / 12m.

## 1.4 Validation temporelle correcte

Un modèle entraîné jusqu’à 2024 ne peut pas utiliser 2022 comme vrai OOS.

Utiliser :

- vrai OOS futur disponible ;
- walk-forward historique avec cutoff :
  - train ≤ 2019 → test 2020 ;
  - train ≤ 2020 → test 2021 ;
  - train ≤ 2021 → test 2022 ;
  - etc.
- univers holdout comme validation complémentaire, jamais comme remplacement de l’OOS temporel.

---

# 2. Gate 2 — Recalibrer l’horizon et la sélection

## 2.1 Horizon

Ne pas supposer que H20 reste optimal.

Pour H5/H10/H15/H20 :

- forward return net ;
- IC ;
- spread TOP−BOTTOM ;
- turnover ;
- coûts ;
- durée effective des trades ;
- cohérence avec time stop / TP / stop.

Sélectionner un horizon qui maximise **l’edge net et stable**, pas le meilleur backtest isolé.

## 2.2 Taille du TOP / BOTTOM

Tester une petite grille pré-enregistrée, par exemple :

- top 1 % ;
- top 5 % ;
- top 10 % ;
- top 20 %.

Mais limiter le nombre de variantes pour éviter l’overfit.

Mesurer :

- hit rate ;
- expectancy ;
- dispersion ;
- concentration ;
- capacité ;
- turnover.

## 2.3 Seuils de probabilité

Si un modèle directionnel / probabilité est utilisé :

- vérifier calibration ;
- vérifier coverage ;
- vérifier gradient ;
- comparer ranking vs veto ;
- placebo du score secondaire.

Ne pas réutiliser automatiquement `min_prob` de l’ancien modèle.

---

# 3. Gate 3 — Revalider LONG et SHORT séparément

Le long et le short sont deux problèmes différents.

## 3.1 Long

Mesurer :

- P(up) ;
- forward returns ;
- MFE / MAE ;
- TP hit ;
- stop hit ;
- expectancy ;
- stabilité par régime ;
- performance relative au marché.

## 3.2 Short

Ne jamais supposer que `1-rank` est un bon modèle short.

Mesurer :

- P(down) ;
- MFE short / MAE short ;
- squeeze avant baisse ;
- borrow / contraintes si disponibles ;
- performance par régime ;
- lifecycle réel.

## 3.3 Structure du book

Revalider :

- long-only ;
- 7L/1S ;
- 6L/2S ;
- éventuellement autre ratio si justifié.

Ne pas tuner 10 variantes. Pré-enregistrer 2–3 architectures seulement.

---

# 4. Gate 4 — Nombre de positions et dilution de l’alpha

Le nombre de positions modifie :

- diversification ;
- concentration ;
- turnover ;
- capacité ;
- alpha moyen par trade ;
- gross réel ;
- réaction du breaker.

Tester par exemple m4 / m8 / m12 uniquement si pertinent.

Mesures :

- return ;
- Sharpe ;
- DD ;
- nombre de trades ;
- gross ;
- concentration ;
- PnL marginal des derniers slots.

Le bon nombre de positions est le point où la diversification ajoute encore de la robustesse sans trop diluer le signal.

---

# 5. Gate 5 — Recalibrer le sizing

## 5.1 Sizing ATR

Revalider :

- `risk_per_trade` ;
- ATR lookback ;
- ATR multiple ;
- position min/max ;
- min notional ;
- cap symbol ;
- cap secteur.

## 5.2 Equal-weight vs risk-weight

Comparer au moins :

- equal weight ;
- ATR risk ;
- éventuellement rank-weighted si déjà justifié.

## 5.3 Analyse de concentration

Mesurer :

- max poids symbole ;
- max trades simultanés par symbole ;
- top-5 / top-10 contribution au DD ;
- concentration secteur ;
- beta concentration ;
- factor concentration.

Un nouvel univers peut rendre un cap historiquement correct totalement inadapté.

---

# 6. Gate 6 — Recalibrer gross exposure et levier

C’est une étape séparée du modèle.

## 6.1 Construire la frontière efficiente

Tester plusieurs niveaux de gross de manière pré-spécifiée :

- faible ;
- intermédiaire ;
- élevé.

Exemple : 60 / 75 / 90 / 105 / 120 %, puis seulement pousser plus haut si la courbe reste saine.

Mesurer :

- Return ;
- CAGR ;
- MaxDD ;
- Return/MaxDD ;
- Sharpe ;
- Sortino ;
- worst 3m/6m ;
- recovery ;
- trips B4 ;
- jours CP ;
- margin usage.

## 6.2 Max leverage ≠ leverage optimal

`max_leverage=2.0` est une limite, pas une cible.

Le nouveau modèle doit obtenir un **gross certifié**.

## 6.3 Gate

Rejeter un niveau d’exposition si :

- DD augmente beaucoup plus vite que le rendement ;
- Sharpe se dégrade ;
- B4 devient fréquent ;
- force-close devient partie du fonctionnement normal ;
- coûts/slippage deviennent trop importants.

---

# 7. Gate 7 — Recalibrer stop initial / TP / trailing / time stop

## 7.1 Stop initial

Revalider :

- ATR multiple ;
- distance moyenne ;
- distribution ;
- pertes extrêmes ;
- gaps ;
- stop theoretical vs realized.

Un univers plus volatil rend les stops ATR beaucoup plus larges.

## 7.2 Take-profit

Revalider :

- TP ATR multiple ;
- TP max % ;
- hit rate ;
- expectancy ;
- opportunity cost ;
- ancrage au fill vs close décision.

## 7.3 Trailing

Le trailing est extrêmement dépendant de l’univers.

Mesurer :

- % exits trailing ;
- recovery après trailing ;
- comportement par régime ;
- trailing fixe vs risk-based.

## 7.4 Time stop

Revalider `max_business_days`.

Un H10 n’a pas forcément le même time stop qu’un H20.

---

# 8. Gate 8 — Recalibrer coûts et liquidité

Obligatoire si univers change.

## 8.1 Coûts

Mettre à jour :

- commission ;
- slippage ;
- spread ;
- borrow cost short ;
- margin cost ;
- turnover.

## 8.2 Liquidité

Mesurer :

- ADV ;
- dollar volume ;
- spread médian / p90 ;
- impact selon taille ;
- fill rate ;
- overnight gaps ;
- hard-to-borrow si short.

## 8.3 Stress

Tester au minimum :

- coûts ×1.5 ;
- coûts ×2 ;
- slippage dégradé ;
- signaux manqués ;
- retard d’exécution.

---

# 9. Gate 9 — Revalider les régimes de marché

Ne pas supposer que les régimes restent utiles.

Pour BULL / CORRECTION / SLIDE / REBOUND :

- fréquence ;
- returns du book ;
- long PnL ;
- short PnL ;
- DD ;
- gross ;
- transition ;
- faux flips.

Vérifier également les overlays macro / VIX / yields si utilisés.

---

# 10. Gate 10 — Revalider CP / CP-V2

## 10.1 Ce qui peut rester structurel

Le principe :

- de-risk en stress ;
- asymétrie long/short ;
- release contrôlée ;
- fail-safe.

## 10.2 Ce qu’il faut requalifier

Selon nouveau modèle/univers :

- gross cap CP ;
- long budget ;
- short budget ;
- nombre de slots short ;
- release sessions ;
- hystérésis ;
- comportement post-CP.

## 10.3 Attribution causale obligatoire

Comparer CP ON vs OFF / nouvelle variante.

Buckets :

- entrées empêchées ;
- sizing ;
- composition ;
- lifecycle ;
- effet 1–3j / 4–10j / >10j.

Le CP ne doit pas être jugé uniquement sur Return ou MaxDD.

---

# 11. Gate 11 — Revalider B4 / drawdown breaker

Le seuil DD n’est pas universel.

## 11.1 Seuil

Revalider selon gross et distribution de DD :

- 15 % ;
- 18 % ;
- 20 % ;
- 25 % uniquement comme stress si justifié.

## 11.2 Rôle

B4 doit rester :

- rare ;
- catastrophe ;
- jamais un composant quotidien.

Si B4 trippe souvent, le sizing est probablement trop agressif.

## 11.3 Recovery

Revalider :

- RecoveryRatio ;
- hystérésis ;
- relapse ;
- temps de retour à 100 % ;
- dépendance au régime.

## 11.4 Force-close

Ne pas transférer automatiquement `50 % des pires PnL`.

Comparer si données suffisantes :

- KEEP ;
- WORST_50 ;
- ALL.

Nouveau modèle = nouvelle distribution de recovery des positions.

---

# 12. Gate 12 — Revalider B4 staged si utilisé plus tard

Si architecture progressive adoptée :

- palier 1 : DD X → expo Y ;
- palier 2 ;
- palier 3 ;
- hard kill.

Chaque palier doit être évalué sur :

- ADD après palier ;
- recovery ;
- coût du rebound ;
- fréquence ;
- interaction CP.

---

# 13. Gate 13 — Revalider long-only séparément

Un compte long-only est une stratégie de risque différente.

Ne pas réutiliser automatiquement :

- budgets CP 6L/2S ;
- short reserve ;
- DD behavior ;
- recovery.

Certification séparée.

---

# 14. Gate 14 — Stress tests obligatoires

Pour chaque nouveau modèle/univers :

## Bear lent
Exemple type 2022.

## Crash + V recovery
Exemple type 2025 / 2020 si PIT valide.

## Choc coûts
Spreads/slippage plus élevés.

## Exposition élevée
Vérifier la marge de sécurité.

## CP OFF
Diagnostic uniquement.

## Signaux manqués
10–20 % de sélections non exécutées.

## Execution delay
Entrée retardée.

---

# 15. Gate 15 — Parité backtest ↔ production

Une configuration n’est pas promouvable sans parité.

Comparer :

- sélection ;
- risk decisions ;
- budgets ;
- allocation ;
- CP state ;
- B4 state ;
- TP / SL / trailing ;
- positions ;
- force-close ;
- release ;
- gross/net.

Les décisions discrètes doivent être identiques.  
Les floats doivent être dans une tolérance minuscule documentée.

---

# 16. Gate 16 — Promotion / rollback

Chaque modèle doit avoir une certification versionnée.

Exemple :

```text
model_batch = B50
universe = U2
risk_certification = R50
book = 6L/2S
gross_target = 0.90
cp_policy = cp_v2
b4_policy = b4
force_close = 0.5
```

Conserver :

- ancienne config ;
- rollback ;
- date de promotion ;
- artefacts ;
- rapports ;
- hashes de config/code.

---

# 17. Matrice complète des paramètres à requalifier

| Domaine | Paramètre / question | Priorité |
|---|---|---|
| Alpha | IC / ICIR | critique |
| Alpha | TOP vs random | critique |
| Alpha | TOP vs BOTTOM | critique |
| Alpha | placebo | critique |
| Alpha | stabilité année/régime | critique |
| Horizon | H5/H10/H15/H20 | critique |
| Sélection | top_pct | haute |
| Sélection | min_prob | haute |
| Book | long-only / 6L2S / autre | critique |
| Book | nombre de positions | critique |
| Sizing | ATR risk | critique |
| Sizing | min/max notional | haute |
| Exposure | gross cible | critique |
| Exposure | net cible | critique |
| Leverage | leverage effectif | critique |
| Concentration | symbole | haute |
| Concentration | secteur | haute |
| Lifecycle | stop ATR | haute |
| Lifecycle | TP | haute |
| Lifecycle | trailing | haute |
| Lifecycle | time stop | haute |
| Costs | spread | critique si nouvel univers |
| Costs | slippage | critique |
| Costs | commission | moyenne |
| Costs | borrow | critique si short |
| Liquidity | ADV | critique |
| Regime | définition / fréquence | haute |
| CP | gross cap | critique |
| CP | budget long | critique |
| CP | budget short | critique |
| CP | release | haute |
| CP | hystérésis | haute |
| B4 | DD threshold | critique |
| B4 | allocation/recovery | haute |
| B4 | force close | haute |
| Stress | crash / bear / V | critique |
| Prod | parity | critique |
| Prod | rollback | critique |

---

# 18. Workflow recommandé pour le mainteneur

```text
NOUVEAU MODELE / UNIVERS
        |
        v
[1] Validation alpha
        |
   FAIL -> STOP
        |
        v
[2] Horizon + sélection + long/short
        |
        v
[3] Construction du book
        |
        v
[4] Lifecycle / sizing / coûts
        |
        v
[5] Courbe gross / leverage / DD
        |
        v
[6] CP / B4 sur le portefeuille choisi
        |
        v
[7] Stress tests
        |
        v
[8] Parité backtest-prod
        |
        v
[9] Paper / shadow
        |
        v
[10] Promotion + rollback prêt
```

---

# 19. Règles anti-overfit

1. Pré-enregistrer les variantes avant de voir les résultats.
2. Ne pas lancer 20 seuils si 3 suffisent.
3. Séparer exploration et validation.
4. Ne pas réutiliser 2022 comme OOS si le modèle a été entraîné après 2022.
5. Conserver un vrai OOS futur.
6. Utiliser walk-forward historique avec cutoff propre.
7. Ne jamais choisir un univers holdout après observation des performances.
8. Ne pas choisir un paramètre uniquement sur Return.
9. Toujours regarder DD / Sharpe / recovery / worst windows.
10. Un seul épisode historique ne suffit pas pour optimiser un airbag catastrophe.

---

# 20. Livrables obligatoires pour chaque certification

Créer un dossier versionné contenant :

- `model_summary.md`
- `alpha_validation.md`
- `portfolio_construction.md`
- `lifecycle_validation.md`
- `cost_liquidity_validation.md`
- `risk_scaling.md`
- `cp_validation.md`
- `b4_validation.md`
- `stress_tests.md`
- `prod_parity.md`
- `promotion_decision.md`
- `config_snapshot.yaml`
- hash commit git
- batch ID
- univers exact
- cutoff train
- validation period
- OOS period

---

# 21. Résumé exécutif pour un nouveau mainteneur

Lorsqu’un modèle ou univers change radicalement :

1. **Ne pas hériter du risk budget précédent.**
2. Reprouver l’alpha.
3. Rechoisir horizon / sélection / book.
4. Revalider lifecycle et coûts.
5. Recalibrer gross / leverage.
6. Ensuite seulement revalider CP et B4.
7. Faire les stress tests.
8. Vérifier la parité PROD.
9. Paper/shadow avant live.
10. Versionner la certification et conserver rollback.

> **Le chiffre important n’est pas “max_leverage=2.0”.**  
> Le chiffre important est : **quel gross / levier ce modèle précis, sur cet univers précis, a réellement été certifié à supporter avec un couple rendement/risque acceptable.**

---

# 22. Statut des enseignements historiques à ne pas transférer aveuglément

Les conclusions issues d’un ancien modèle/univers doivent être considérées comme **hypothèses initiales**, pas comme vérités universelles :

- 6L/2S peut être bon aujourd’hui et mauvais demain ;
- CP-V2 peut rester architecturalement pertinent mais ses budgets peuvent changer ;
- release J+6 doit être revalidée ;
- B4 à 15 % doit être requalifié ;
- force-close 50 % est provisoire, pas universel ;
- trailing / TP / stop dépendent fortement du profil des trades ;
- le gross optimal doit être recalibré ;
- l’usage réel du levier doit être requalifié ;
- les caps symbole / secteur doivent être recalibrés si l’univers change.

---

**Fin du guide**
