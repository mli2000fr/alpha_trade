# Août2026 — Winner LONG, extension du veto GPT aux scores1–5

Demande du25 octobre2026 après les tests1–3 et1–4. Un seul nouveau portefeuille,
sans nouvel appel GPT/DeepSeek, collecte, SQL, entraînement ni ordre réel.
Les trois comptes déjà audités sont réutilisés après vérification des sources
et de chaque fichier de résultat. Aucun paramètre de production n'est changé.

## Protocole figé avant replay

Même TOP20 original des21 séances d'août2026 :420 couples titre/date,37 sociétés.
Même cohorte de couverture commune :237 signaux admissibles,183 réservés.
Exclure uniquement les scores GPT **VALID de1 à5 inclus**, avant création d'un
nouveau plan. Aucun reclassement, remplacement par TOP21, annulation d'un plan
plus ancien ou vente d'une position déjà ouverte. Les avis invalides ou sans
score restent sans veto, comme dans les comparateurs : ce n'est PAS une
stratégie achetant exclusivement les seuls avis valides6–10.

193 avis1–5 d'origine ;86 dans la cohorte admissible, contre74 pour1–4.
Le nouveau seuil écarte donc12 signaux notés5 supplémentaires. Ces chiffres
ne sont ni des achats évités ni des trades indépendants.

SL7 fixe, sans TP ni trailing, H20/open21 depuis l'entrée, demi-position sans
renforcement, deux confirmations5m, attente d'entrée20 séances. Capital4000USD,
jusqu'à8 positions, plafond brut1x, frais8pb/jambe, risques/corrélation/secteurs
et B4/DD15 d'allocation identiques à l'ancien test. **Pas les nouvelles règles
DD15/liquidation/pause trois mois** des expériences mensuelles séparées.

Signaux du3 au31 août ; portefeuille suivi jusqu'au30 septembre2026. Positions
encore ouvertes valorisées, non liquidées artificiellement et non incluses dans
le taux gagnant des clôtures. Rejouer le cash partagé, pas supprimer après coup
les trades connus perdants.

## Audit et sorties

Module `scripts.research.us_winner_gpt_veto_1_5_august_2026`.
Dossier `artifacts/research/us_winner_gpt_veto_august_2026/20261025-score1-5-v1`.
`report.json` compare Winner seul, veto1–3, veto1–4 et veto1–5. Chaque entrée,
sortie SL/gap/horizon, frais, cash, PnL, stock final et DD est audité. La cohorte
est comparée exactement à l'archive hors seul indicateur de veto. Fichiers et
sources scellés ; verrous Windows et journaux actifs exclus des empreintes.

Mesurer capital final, rendement, DD, trades/gagnants/perdants, gains/pertes
moyens, exposition, frais et positions restantes. Décrire les clôtures absentes
et nouvelles séparément : les interactions de capital/risque ne permettent pas
d'attribuer simplement toute variation de capital à des pertes évitées.

## Limites

GPT rétrospectif, pas PIT ni absence garantie de mémoire ; un seul mois,
scores élargis après résultats déjà observés, répétitions/chevauchements des
titres et sélection de couverture future J..J+40. Secteurs actuels, prix OHLC5m
plutôt que quotes/fills historiques. Test exploratoire, non indépendant, pas
de preuve de robustesse ni de promotion live, quel que soit le résultat.

Résultat économique à lire seulement dans le rapport final audité.
