# Consensus EODHD : audit actualisé de fiabilité

22 octobre 2026. Nouveau dossier ; ne modifie pas les pilotes et leurs cohortes
scellés les 19–20 octobre. Aucun appel fournisseur/LLM, achat, entraînement,
écriture SQL, ordre ou changement de batch/modèle.

## 1. Fiabilité des données

Inventaire SELECT-only de `alpha_trade.stock_analyst_consensus_eodhd_history` :
dates **réellement observées**, couverture globale et univers tradable courant
de 1 790 titres, valeurs manquantes, intervalles low/avg/high et statuts.
Ne pas compter les fins de périodes fiscales ou J−7/30/60/90 comme des vintages.

Export borné aux collectes depuis le 11 octobre, avant un cutoff UTC fixé par
le protocole machine ; horizons `0q` et `0y`, ancrages 1er juin 2026–30 juin
2027. Limite 300 000 lignes, arrêt explicite si dépassée. Contrôle de toutes
ces lignes contre leurs items bruts (hash, code, période, horizon, valeurs),
horodatages et runs. Ne pas certifier par là les autres périodes historiques.

Vérification supplémentaire d'enveloppes déjà archivées : au plus vingt
symboles changés et dix stables, tri alphabétique sans prix, plus les six
contextes documentés DOCN/FUN/TWLO/FIVN/ENTG/AKAM. Hash et appartenance aux
enveloppes contrôlés. Réceptions de runs incomplets réservées ; pas reprise
automatique d'une collecte. Échantillon ≠ certification de toutes les enveloppes.

## 2. Diagnostic directionnel court, séparé et exploratoire

**Primaire revenus** : hausse de moyenne → LONG, baisse → SHORT ; zéro/manquant
→ abstention. Comparer les derniers états réellement disponibles avant deux
ouvertures NYSE successives, même fournisseur/titre/ancrage/horizon `0q`.
La disponibilité conservatrice est max(observation, disponibilité, insertion,
fin du run COMPLETED). Ne pas choisir les états selon le prix futur.

Un seul candidat d'ancrage par titre : le plus récent `0q` dans la fenêtre
entrée−100 à entrée+100 jours. C'est un **heuristique d'ancrage**, pas la
qualification de son trimestre courant ni de son statut non encore annoncé.
Un changement d'ancrage n'est jamais comparé à l'ancien trimestre.
État courant/précédent âgé de plus de quatre jours réservé.

Au moins trois analystes revenus à chaque borne. Groupe primaire : nombre
inchangé ; groupe avec nombre changé conservé séparément. Aucune identité de
contributeurs connue. EPS, EPS+revenus concordants et compteurs de révisions
7jours sont **diagnostics secondaires réservés**, pas des variantes à optimiser
ou un remplacement du primaire revenus.

Tout l'univers tradable est étudié, pas seulement le TOP10. Les six contextes
publiquement documentés sont présentés séparément, sans rétroactivité de
qualification. Devise/échelle/base du fournisseur non certifiées globalement :
pas de signal production même si l'association semble favorable.

## 3. Prix, maturité et contrôles

Après gel des features : export READ ONLY de prix journaliers déjà stockés,
du 1er octobre au cutoff, aucune récupération fournisseur. Première ouverture
après information, fin de la 1re/3e/5e séance entrée incluse. H1 primaire court,
H3/H5 secondaires, H10 inventaire de maturité seulement dans ce nouvel audit.
**Ne pas ouvrir ni modifier l'ancien évaluateur TP10/SL5 H10 avant sa maturité.**

Exiger toutes les barres de la fenêtre, OHLCV valides, non remplis, ajustement
unique connu par fenêtre, même source/identité si les colonnes existent ;
réserves de provenance, ajustements et OST maintenues sinon. Toutes les séances
doivent être closes avant cutoff. Pas d'utilisation d'une barre du jour inachevée,
pas de remplissage ou écrêtage. Les prix historiques stockés ne sont pas un
reçu immuable de leur publication ; cet audit est rétrospectif.

Mesurer : nombre de titres, **dates distinctes**, hausse/baisse correcte,
retour signé et excès simple contre SPY, contrôles toujours LONG/SHORT sur les
mêmes occasions. Friction illustrative fixe16bps aller-retour, **pas PnL**,
pas de TP/SL, capital, levier, exécution ou emprunt SHORT certifié.

Pondération par occasion ET par date. Contrôle sans chevauchement par titre,
tous motifs (y compris abstentions/réserves) réservant leur créneau avant les
prix. Pas d'affirmation d'indépendance entre titres/secteurs. Pas de seuil
ajusté après résultat, pas de « validation » avec quelques journées. La
confirmation précédente exige50 dates et100 épisodes TOP10 : elle reste en
place, sans assouplissement ni réutilisation d'un ancien classement Oracle.

## Décision

Distinguer trois conclusions : fidélité de stockage, comparabilité économique,
utilité directionnelle. Une bonne copie du fournisseur ne garantit pas que
le consensus anticipe le cours. Un horizon immature reste inconnu même si le
prix a déjà touché un niveau favorable. Documenter le bilan et le registre,
sans élargissement automatique, entraînement ou abonnement supplémentaire.
