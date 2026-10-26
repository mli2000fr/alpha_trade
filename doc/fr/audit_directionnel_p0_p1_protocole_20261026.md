# Audit directionnel FR P0/P1 — protocole borné du 26 octobre 2026

Demande : vérifier si les collectes permettent de distinguer LONG/SHORT pendant
vingt séances, et non seulement au cours de clôture terminal. Aucun entraînement
ni ordre, SQL FR en lecture seule, aucune collecte/API/LLM ou modification batch.
Six collectes de marché P0/P1 et deux sauvegardes. Consensus EODHD classéP3,
non inclus. INPI/Yahoo et données bloquées pour droits/prudence exclus.

## Cible fixée avant les résultats

À partir des preuves réellement reçues après une clôture J et strictement avant
l'ouverture suivante, référence prix = open J+1. Vingt séances entrée incluse.
Deux parcours séparés : LONG avec stop fixe−10%, SHORT avec stop fixe+10%.
Retenir l'excursion favorable maximale AVANT le stop propre à chaque sens,
puis comparer ces excursions. Un gain LONG de25% puis une chute ultérieure ne
devient pas simplement un label baissier H20. Ne pas faire revivre un côté stoppé.

« Premier pic » signifie ici la première séance où le maximum favorable du
parcours protégé est atteint ; ce n'est pas un premier maximum local défini par
un algorithme de retournement. Les dates des deux maxima et leur ordre sont
archivés. Deux pics le même jour : ordre intraday inconnu. Stop et nouveau pic
sur une même bougie daily : bornes basse/haute, pas de chronologie inventée.
Un gap adverse stoppe avant tout rebond. Fenêtre H20 incomplète = NOT_MATURE,
jamais rendement terminal partiel ou remplacement silencieux par H14.

H5/H10 sont des diagnostics secondaires explicitement exploratoires, pas des
substituts de H20 ni une validation hors échantillon. Signaux figés : momentum
5/20séances (plus haut orienté LONG), somme publique AMF et variation chez les
mêmes détenteurs (augmentation orientée SHORT). AUC par date et contrôle d'une
première observation par titre ; aucun modèle, inversion opportuniste ou PnL.
Fenêtres chevauchantes et quelques dates seulement : aucune promotion.

## Preuves, périmètre et réserves

Univers courant actif vérifié S6C, migration datée PERR→ALPER et exclusion Lhyfe
comme la collecte de cours. Ce n'est pas un univers historique tradable/PIT.
Le libellé AMF historique2017 ne crée pas une observation en2017 : sélectionner
uniquement le snapshot réellement archivé avant la décision. Seuil public0,5%,
dernière publication par détenteur, égalités ambiguës exclues ; absence ou
passage sous seuil = inconnu, pas zéro. DILA : documents logiques dédupliqués,
types/titres et couverture seulement ; pas de PDF/sentiment/guidance inventés.

SQL `alpha_trade_fr.fr_provider_bars_staging`, snapshots/versions reçus au cutoff
réel, qualité VALID et grille officielleXPAR complète. Features prix : dernière
version effectivement disponible avant l'entrée et session strictement passée.
Labels : derniers prix observés au cutoff. Opérations sur titres fournisseur
connues réservées ; cela ne qualifie pas leur absence ou les devises/prix auprès
d'une source indépendante. Référentiel/calendrier et sauvegardes ne sont pas des
scores directionnels autonomes. Pas d'emprunt FR qualifié ni de PnL SHORT ici.

Figer prix SQL récents, identités, catalogue, observations publiques normalisées,
labels/ambiguïtés et empreintes des archives. Résultat : audit achevé possible
même si validation directionnelle H20 bloquée par sa maturité. Aucun élargissement
documentaire ou téléchargement pour masquer ce manque temporel.

Script : `scripts.research.fr_p0_p1_directional_audit_20261026`.
Sorties : `artifacts/fr/research/p0_p1_directional/20261026-v1`.
