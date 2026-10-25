# TOP20 continu : demi-position contre témoin complet SL5 — protocole figé

GO du25 octobre2026. Objectif : mesurer le compromis rendement/DD en ne changeant
que la fraction initiale de la campagne,100% vers50%. Pas de nouvelle recherche
de TP/SL, ni sélection mensuelle. Aucun résultat supposé linéaire.

## Référence et conditions communes

Témoin audité `us_winner_monthly_selector/20261024-v1/cases/SHADOW_SL5_TROFF_H20_TPOFF` :
4000USD le1er juillet2019, compte continu jusqu'au31 décembre2024, sans reset
annuel. TOP20 d'origine, positions LONG, pas de remplacement de rang après
exclusion. Résultat déjà observé :23810,29USD,+495,26%,DD−39,88%.

SL fixe5%, aucunTP/trailing, détention20 séances depuis fill, sortie open21.
Deux confirmations5min au-dessus du plus haut de la séance précédente, attente
maximale20 séances. Sans renforcement. Maximum20 positions,10 entrées par
titre sur180 jours, risques/corrélation/secteur/B4 inchangés, plafond brut1x,
8pb/jambe, mêmes frais/financement. **Pas d'ajout de liquidation globale DD25**.
Les positions encore ouvertes à la fin sont valorisées, pas vendues fictivement.

Le témoin parent utilisait une admission externe SL3/position complète pour
dimensionner les approbations multi-profils, puis redimensionnait chaque plan
selon son vrai SL5. Ce chemin reste identique. La fraction50% intervient
**une seule fois au staging de la campagne**, pas aussi sur l'admission externe.
Il ne faut pas fabriquer des quarts de position. Le contrôle risque au fill
reste actif, les arrondis/actions entières et minima notionnels sont conservés.

## Exécution isolée et preuves

Script `scripts/research/us_winner_top20_half_continuous_20261025.py` ; dossier
`artifacts/research/us_winner_top20_half_continuous/20261025-v1`.
Le même moteur archivé que le témoin est chargé dans un processus neuf ; les
deux fichiers production ne sont ni restaurés ni édités. Le correctif de
périmètre pré-open et le correctif du premier fill au centime sont conservés.
Leurs sources, celles du moteur effectivement chargé, le témoin, les données et
ce protocole sont liés par empreintes. Aucun autre run n'est modifié ou arrêté.

Le témoin terminé est réutilisé après vérification. Un seul nouveau compte
HALF est rejoué. Même tape locale SIP5min/daily et cohorte commune stricte,
manifest vérifié. Aucune connexion SQL, collecte, appel LLM, prédiction,
entraînement, ordre ou changement de YAML. Worker unique à priorité basse.

Contrôles : confirmations causales, politiques réellement figées à50%, absence
de double division du sizing, pas de dépassement de la demi-quantité approuvée,
sorties scalaires SL/gap/horizon, cash/frais/positions/PnL/DD réconciliés. Les
refus d'une demi-position trop petite pour une action entière sont conservés.

Suivi dans `progress.json` et `stdout.log`/`stderr.log`. Bilan final dans
`report.json`, détails dans `cases/HALF_SL5_TROFF_H20_TPOFF/`, audit de sizing
dans `half-sizing-audit.json`. Les années2020–2024 seront aussi détaillées,
sans réinitialiser le capital qui a commencé en2019.

## Limites

Période déjà examinée, univers survivant, secteurs actuels non PIT, données
daily révisées, OHLC et non bid/ask/fills. Exclusions suivant la couverture
future communes aux deux bras : biais explicite, pas un filtre disponible en
live. Aucune parité live complète ou validation prospective annoncée. Le DD
n'est pas garanti par un stop, ni supposé divisé par deux. Aucune promotion.
