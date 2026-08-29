# Expériences Oracle — synthèse durable

Retour : [dossier technique Oracle](../ml/oracle/README.md)

## Sources historiques regroupées

Cette synthèse couvre notamment `ml_oracle.md`, `ml_oracle_sprint.md`, `oracle_extreme.md`, `model_extreme_mode.md`, `calibration_oracle_exterme.md`, `mode_cascade.md`, `controle_couverture.md`, `e17_synthese_gpt.md` et `synthese_e6_e13_2026-08-20.md`.

## Question initiale

Le Global Ranking capturait imparfaitement les futurs extrêmes. L’hypothèse était qu’un second modèle pouvait apprendre où B25 réussissait ou échouait, d’abord avec des cibles TOP/BOTTOM séparées.

## Résultat conceptuel

Les modèles amélioraient parfois une métrique de capture mais les scores TOP/BOTTOM restaient fortement liés et distinguaient mal la direction. Les diagnostics de hard negatives, sévérité, features signées, fondamentaux et confounders n’ont pas établi un signal directionnel robuste.

Le code a donc évolué vers une cible commune de magnitude : `oracle_extreme10`. Le composant officiel produit `proba_extreme`, puis un gate percentile quotidien. La direction est externe.

## Enseignements

- Une capture ML supérieure peut dégrader les trades ajoutés.
- Filtrer des candidats peut libérer de la capacité et augmenter le turnover.
- Un reranking est un no-op si l’aval retrie sur une autre colonne.
- Couverture faible et multiple testing créent des faux signaux.
- Une calibration ne crée pas la direction absente.
- Le batch doit être filtré strictement dans la table cumulant les campagnes.
- Le lifecycle exact doit être identique pour comparer le trading.

## Statut

Oracle reste un composant de recherche/gate présent dans le code, pas une autorité directionnelle générale. Son activation effective se vérifie dans la commande, le batch, les champions, les prédictions et le mode cascade.

Les détails chiffrés des campagnes ne sont pas repris car ils ne décrivent pas l’état runtime actuel.

