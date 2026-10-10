# Oracle H20 corrigé — backtests annuels TOP10, 2020–2026

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## Objet et statut

Expérience lancée le 7 octobre 2026 à la demande de l'utilisateur : mesurer le
rendement du portefeuille pour chaque année, en achetant les dix premiers
**scores prédits** Oracle. Il ne s'agit ni des dix plus grands rendements futurs,
ni des seuls gagnants, ni d'un TOP10 %.

Le contrôle court a terminé les sept années, trois séances par année, sans
échec. Ce contrôle ne fournit **aucun rendement annuel**. Le calcul complet,
distinct, comporte 28 simulations : sept années × quatre sorties.

Artefacts complets :
`artifacts/research/us_concentrated_replay/oracle-top10-annual-20261007-v1/`.
Le statut et les résultats effectivement terminés font foi dans `progress.json`
et `report.json`. Aucun résultat annuel n'est affirmé dans cette documentation
avant la fin du run correspondant.

## Périmètre et comparaison

- 2020–2025 : années civiles complètes, sur le calendrier local SPY.
- 2026 : du 1er janvier au **3 septembre 2026**, dernière date commune des scores
  externes archivés ; ce n'est pas un rendement annuel ni un rendement annualisé.
- 1 677 séances et 16 770 candidats, exactement dix par séance.
- Univers de calcul des scores : 1 790 titres de l'audit corrigé ; 331 titres
  différents apparaissent au moins une fois parmi les dix premiers sur la période.
- Capital initial **4 000 USD pour chaque année**, remise à zéro du portefeuille,
  du circuit breaker et de son historique de risque chaque année.
- Liquidation des positions à la clôture de la dernière séance de chaque année.
  Le prochain signal de fin d'année ne devient pas une position reportée sur
  l'année suivante. Ce protocole n'est donc pas un portefeuille continu sur sept ans.

Les limites de portefeuille peuvent empêcher l'achat des dix candidats : huit
positions au maximum, capital, sizing, exposition sectorielle, régime, gaps et
autres contrôles natifs demeurent actifs. Il ne faut pas confondre dix candidats
avec dix ordres obligatoirement exécutés. Un ordre incompatible avec les
contraintes de portefeuille est explicitement rejeté, jamais redimensionné
silencieusement pour forcer son passage.

## Scores, correction et absence de sélection future

L'expérience réutilise les artefacts corrigés de
[l'audit numérique H20](oracle_h20_numeric_effect.md) et de
[l'audit TOP10](oracle_h20_corrected_top10_audit.md), liés au profil du batch
`model-factory-20261003082853-e98332`. Elle ne remplace pas les modèles de serving.

| Période | Source du score |
| --- | --- |
| 2020 → 9 juillet 2024 | Prédictions OOF des folds corrigés déjà entraînés |
| 10 juillet → 31 décembre 2024 | Dernier modèle corrigé, fold du 8 janvier 2024, appliqué aux features déjà archivées |
| 2025 → 3 septembre 2026 | Confirmation externe déjà calculée avec le même dernier modèle figé |

Pour le raccordement 2024, les dernières disponibilités de labels utilisées
pour entraîner et sélectionner le modèle précèdent la période prédite. Les
features sont calculées sur l'ensemble observable et les rangs transversaux
restaurés avant de sélectionner dix titres. Aucun nouveau modèle n'est entraîné.
Le second semestre n'est pas rempli avec des scores d'un modèle entraîné après coup.

À chaque date : score décroissant, symbole croissant pour départager les
égalités. La frontière de sélection ne conserve que `date`, `symbol`, `score`,
`fold_start`, puis produit `oracle_rank` et `ORACLE_TOP10`. Les labels, déciles
réels et rendements futurs ne sont jamais transmis au moteur de décision.
**Pas de filtre ATR, de modèle directionnel, ni de filtre positif/négatif.**

## Exécution, risque et quatre variantes

Signal après observation de J ; entrée éventuelle à l'ouverture suivante.
Le moteur partagé applique la chronologie des gaps, les contrôles d'exécution,
les protections et le suivi du portefeuille. SL initial fixe à **7 % du prix
réellement simulé d'entrée**. Le sizing natif fondé sur l'ATR reste inchangé :
ce n'est pas une expérience de sizing à risque fixe exactement égal à 7 %.
Un gap peut provoquer une perte supérieure à 7 %.

| Variante | TP | Trailing | Échéance |
| --- | --- | --- | --- |
| `CURRENT_NO_EXPIRY` | Oui | Oui | Pas de sortie temporelle, sauf liquidation annuelle |
| `REFERENCE_20_AFTER_ENTRY` | Oui | Oui | 20 séances après l'entrée |
| `NO_TP_FIXED_SL_20_AFTER_ENTRY` | Non | Non | 20 séances après l'entrée |
| `NO_TP_TRAILING_20_AFTER_ENTRY` | Non | Oui | 20 séances après l'entrée |

« 20 séances après l'entrée » signifie indice de séance d'entrée + 20, et non
J+20 depuis le signal. TP natif : ATR × 3, plafonné à 7 %. Le trailing peut
modifier le niveau de protection après l'entrée dans les variantes concernées.

Régimes, sizing et risque sont figés dans `protocol.json`. Coûts canoniques :
commission 1 bp par jambe, slippage 2 bps, demi-spread hypothétique 5 bps,
intérêt de marge annuel 7,5 % sur l'emprunt effectif. Ces hypothèses ne sont pas
des quotes/fills historiques de courtier. Les coûts sont appliqués dans le moteur,
pas retranchés approximativement une seconde fois au rendement final.

## Contrôles et limites

Chaque séance doit posséder exactement dix candidats ; un trou de scores ne
devient pas artificiellement une journée en cash. La couverture macro contient
toutes les dates du calendrier, sans que cela certifie chaque valeur ou sa
publication PIT. Les données manquantes par champ conservent le traitement
natif du régime, sans reconstitution depuis le futur.

Les barres nulles, volumes de positions détenues non qualifiés et incohérences
d'identité peuvent arrêter une variante. Un échec reste visible et les autres
simulations annuelles indépendantes continuent. Un run échoué n'est jamais
présenté comme une performance annuelle complète. Les résultats partiels et
le motif sont conservés pour diagnostic.

Limites : univers actuel/reconstruit et risque de survivance, secteurs actuels
NON-PIT explicitement acceptés, archive macro quotidienne sans preuve exhaustive
des vintages, prix locaux non tous certifiés indépendamment, exécutions OHLC
simulées, périodes déjà observées. Le vieillissement du modèle est aussi présent :
le modèle reste figé après janvier 2024, sans réentraînement annuel automatique.

Il ne s'agit pas d'une garantie de parité avec de vrais fills live. Aucun batch
existant, modèle de production ou donnée SQL n'est modifié. Les accès SQL de
préparation sont limités aux lectures, les entrées sont archivées et empreintées.

## Suivre et reprendre

```powershell
Get-Content F:\projets\artifacts\research\us_concentrated_replay\oracle-top10-annual-20261007-v1\progress.json
Get-Content F:\projets\log\batch\oracle-top10-annual-20261007-v1\stderr.log -Tail 15 -Wait
```

Le progress global précise l'année, la variante active et les runs terminés.
Chaque sous-dossier `année/variante/progress.json` indique les séances traitées.
`report.json` est enrichi après chaque variante ; seuls les résultats de statut
`COMPLETED` sont des simulations complètes. `PARTIAL_FAILED` indique des variantes
en échec, même si d'autres ont terminé.

Reprise avec le protocole identique, après vérification de l'absence d'un processus
déjà actif :

```powershell
python -u -m scripts.research.us_oracle_top10_annual --output artifacts/research/us_concentrated_replay/oracle-top10-annual-20261007-v1
```

Les variantes terminées sont conservées ; une variante échouée est recalculée
depuis le début de son année sur les entrées archivées. La reprise n'est pas
une restauration de l'état intermédiaire des positions. Ne pas lancer deux
processus sur le même répertoire.

Pour chaque année et sortie : rendement net `return_pct` (fraction, multiplier
par 100), drawdown maximum, Sharpe, positions clôturées, taux de réussite,
exposition brute moyenne rapportée aux fonds propres, intérêts de marge et
réconciliation de trésorerie. Comparer toutes les variantes, sans promouvoir
après coup la meilleure comme une stratégie validée indépendamment.
