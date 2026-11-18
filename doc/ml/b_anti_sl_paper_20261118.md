# B témoin / B + anti-SL : paramétrage du batch quotidien PAPER

18 novembre2026. Configuration et raccordement hors ligne terminés. Aucun ordre, appel fournisseur, écritureSQL, entraînement ou redémarrage de watcher lancé pour cette modification. Le batch de modèles fourni par l’utilisateur est encore en entraînement ; sa consommation est bloquée jusqu’à publication de tous les artefacts.

## Réglage principal dans config.yaml

```yaml
us_pipeline:
  q051_vol20_regime:
    enabled: false
  b_anti_sl_reference:
    enabled: true
    model_batch_id: model-factory-20261118172104-2f6a31
    artifacts_dir: artifacts/models
    apply_anti_sl: true
```

- `enabled: true` : parcours B dédié pour les étapes10/11/12 du batchUS, PAPER uniquement.
- `apply_anti_sl: true` : B + veto anti-SL, profil `q051_b_anti_sl_witness_v1`.
- `apply_anti_sl: false` : B sans veto, profil `q051_b_witness_v1`. Les variables/probabilités anti-SL déclarées restent vérifiées ; désactiver le veto ne rend pas un artefact corrompu acceptable et ne réentraîne aucun modèle.
- Deux parcours quotidiens ne peuvent pas être activés simultanément. Pour revenir au profil historique vol20/régime, désactiver B puis réactiver l’ancien bloc.

Le choix est figé dans le profil de la sélection et transmis dans les commandes des étapes10/11/12 de chaque compte. Changer le YAML ne transforme pas une sélection déjà publiée. Pour changer son filtre, lancer une nouvelle étape10 ; les profils exacts restent attachés aux campagnes existantes.

## Parcours appliqué

Oracle parcoursH10 du batch → TOP10% de l’univers complet du modèle → TOP10 LONG B29 → score strictement>0,50 et AUC de calibration≥0,50 → veto optionnel anti-SL → risque → Winner.

Avec1790titres dans le contrat :179candidats Oracle. Le classement est fait avant les rejets de score/AUC/anti-SL ; aucune substitution par le11eLONG ou un titre hors pool. Le nombre effectivement acheté peut donc être inférieur à10. La liste de trading conserve les lignes/rangs et les motifs de rejet. Les SHORT entraînés restent archivés ; aucune vente à découvert n’est sélectionnée par ce profil.

Le profil impose H10 et `compact_volatility` (B29). Le mode avec anti-SL exige aussi la déclaration et le manifeste anti-SL du batch. Tant que `oracle_path/report.json` n’existe pas, l’étape10 explique que l’entraînement doit finir ; elle ne substitue ni l’ancien batch ni un modèle de recherche.

Les poids ne sont pas ceux de la recherche historique ; ce nouveau raccordement ne reproduit pas automatiquement les rendements2021–2026.

## Portefeuille et protections

Les deux nouveaux profils reprennent exactement le `risk_config` et Winner archivés dans `us_q051_b_early_sl/20261116-v1/cases/SL10/result/configuration.json`. Empreinte de source et empreinte du risque incluses dans les nouveaux profilsJSON. La référence vol20/régime d’origine est conservée sans modification.

| Paramètre | B / B + anti-SL |
| --- | --- |
| Quantité | Position complète, actions entières |
| Entrée | Ouverture deJ+1, ordrePAPER à l’enchère d’ouverture ; aucune confirmation5m |
| Validité du signal | J+1 uniquement |
| SL | 5%depuis le prix exécuté |
| TP / trailing / renforcement | Désactivés |
| Échéance | Dix séances de détention, entrée incluse ; sortie ouverture11 |
| Risque budgété par entrée | 1,25%du capital du compte |
| Poids maximal par titre | 20% |
| Nombre maximal de positions | 20 |
| Notionnel minimum | 50$ |
| Plafond nouvelles entrées | 1×le capital ; capacité du compte margin bornée à2× |
| Réserve de dimensionnement | 25bps par opération, distincte des frais réels |
| Concentration par symbole | Champs de risque archivés :10entrées/90jours, pause90jours après3pertes consécutives |
| Volatilité20% / régimeSPY / B4/DD15 | Non appliqués |
| Facteurs / corrélation / plafonds sectoriels | Non appliqués |
| Options / GPT | Non ajoutés |

Pas de preset choisi selon le capital : les mêmes limites sont appliquées à l’equity réelle de chaque compte. Les contrôles broker, capacité disponible, prixJ, positions/ordres en cours, quantités, réservations, identité du compte, verrous, doublons et watcher restent requis. Les refus de données sont conservés.

Le profil B n’exige ni200clôturesSPY ni61cours pour une covariance désactivée ; il exige la clôtureJ canonique des titres nécessaires. Les appels prix de contexte utilisent toujours la préférence des fournisseurs configurée. La quantité est calculée depuis le prix de référenceJ ; le cours d’ouverture réellement exécuté peut différer. Le stop est posé depuis le fill réel. Pas de certification de parité intégrale avec le backtest.

## Réglages partagés et entraînement déjà lancé

Winner dans le YAML est aligné sur le témoin : confirmation0, position1, SL0,05, TP/trailing null, horizon10, validité1, délai de données0. Les positions déjà ouvertes conservent leur contrat figé.

Pour les **prochains entraînements**, `oracle_path.directional.oracle_top_fraction: 0.10` est résolu depuis l’univers complet, puis le nombre est figé dans le contrat ; `selected_n: 10`. Le nombre20 conservé dans `oracle_top_n` est uniquement un fallback si la fraction est absente/null. Un pool trop petit pour le TOP final est refusé. Le formulaire peut lire l’activation avant de connaître la taille de l’univers ; la résolution finale a lieu à l’entraînement.

Le batch `model-factory-20261118172104-2f6a31` a déjà figé TOP20→TOP5 avant cette modification. **Son contrat n’est pas réécrit et son entraînement n’est pas interrompu.** Le parcours PAPER utilise les probabilités de tout l’univers pour refaire le classement179→TOP10 avec ses propres seuils, puis le veto. C’est aussi ce qui permet au backtest de choisir un classement différent sans réentraîner.

Les valeurs globales B4/facteurs/régime présentes ailleurs dans le YAML restent les réglages des autres parcours. Le profil B les isole explicitement ; ne pas les désactiver globalement pour obtenir le témoin. Les anciens lancements/campagnes vol20/régime continuent à relire leur propre profil figé, même après activation de B.

Le bandeau de la page Pipeline décrit le profil quotidien actif. Les lancements manuels de la page conservent leurs propres réglages, comme avant.

## Validation

263tests ciblés distincts passent : profilsQ051, couverture93%, bundle directionnel, anti-SL, batchUS/multi-comptes, démarrage watcher, runtime/ordresstandard/broker et groupeB. Le nouveau groupe vérifie notamment :

- profils statiques distincts ON/OFF, refus des configurations ambiguës et valeurs non booléennes ;
- sélection TOP10 identique avant veto, suppression sans remplacement, données corrompues encore refusées enOFF ;
- passage du profil exact aux trois étapes et aux trois comptes ;
- taille native sans SPY/covariance, plafonds de capital maintenus ;
- revalidation réelle par le watcher sous le profil figé de la campagne, sans fuite de contexte vers une autre campagne ;
- soumissionPAPER OPG sur broker simulé, SL5 après fill et échéanceopen11 ;
- anciens profils lisibles et non altérés, entraînement incomplet refusé avant tout appel broker.

Prévol local : `artifacts/operations/b_anti_sl_profile_setup/20261118-v1/validation.json`. Il confirme la configuration, les déclarations B/anti-SL du modèle et le statut d’entraînement en cours, sans requêteSQL ni fournisseur. La mise en service effective requiert la fin de l’entraînement et un prochain lancement quotidien avec ses données fraîches.
