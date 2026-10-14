# Signaux directionnels faibles : réutilisation après audit du registre

Audit du 14 octobre 2026, demandé après le filtre d'entrée Oracle parcours.
Sources : `experiences_done.md`, rapports liés et implémentations de recherche.
Pas de nouvel entraînement, modification des modèles, restauration de données
Yahoo, activation de fournisseur bloqué ou écriture SQL.

## Conclusion

Plusieurs effets faibles ont existé, mais **aucun ensemble de signaux déjà
validés n'est disponible pour améliorer aujourd'hui le LONG TP20/SL10**.
Les cibles, univers et instants de décision diffèrent ; on ne peut pas additionner
leurs AUC. Les combinaisons équipondérées et la complémentarité résiduelle ont
déjà été auditées sans avantage stable. Un résultat exploratoire n'est pas une
raison de réactiver une source bloquée ou de sélectionner des poids sur les pertes.

## Pistes retrouvées et réserves de confirmation

| Famille | Résultat initial | Confirmation / réserve | Usage actuel |
| --- | --- | --- | --- |
| LONG H3, E2 | AUC 0,544, neuf folds au-dessus de 0,50 | E2-B : AUC 0,536, lift de tête insuffisant ; rendement terminal H3, pas TP20/SL10 | Ancien effet faible, non promu |
| LONG path-aware E3 | AUC 0,541 | Lift économique négatif ; protections ATR / TP plafonné 7 %, différentes de TP20/SL10 | Pas de filtre transférable tel quel |
| Volatilité60/ATR + momentum120 | Volatilité AUC 0,533–0,539 ; combinaison 2025 D10 32,05 % contre 22,18 % | 27 mois négatifs sur 87 ; combinaison supérieure aux deux composants seulement deux années sur sept ; parcours 2026 proche du hasard | Déjà représentés dans le profil prix ; pas de règle robuste |
| Surprise EPS précédente DDR-5 | AUC 0,519, IC +0,034, trois folds positifs | Lift de tête nul ; disponibilité et vintage de l'estimation non démontrés par le code | Requalification PIT indispensable, pas d'entrée dans un nouveau modèle strict |
| Révisions EPS Yahoo | AUC H10 brute 0,679 sur dix dates | Contrôle secteur/momentum : AUC 0,595, TOP20 D10 7,16 % contre 11,26 % ; très peu de dates indépendantes | Source désactivée, tables supprimées : aucune restauration ici |
| Volume call/put prospectif | AUC H5 0,547, 14/15 dates au-dessus de 0,50 | Un mois, chemins chevauchants ; options indicatives ; pas de démonstration H20 | Collecter/qualifier avant confirmation indépendante |
| Open interest call/put prospectif | AUC H3 0,547 | Moins stable ; horizon et données différents des barres options historiques | Même réserve |
| Barres options historiques | Petit pilote H20 AUC 0,593 | Février–mars 2024 conditionnel Oracle TOP20 : AUC H20 0,509, pas de stabilité | Pas de signal validé pour un ensemble |
| Prix après ouverture E20-B | Précision D1/D10 56,91 % | Information J+1 après ouverture ; replay économique symétrique négatif ; feed retardé | Pas une feature disponible à la décision J |
| News très positives | Association de prix le même jour | Haut de J potentiellement antérieur à la news, scores/mises à jour historiques non qualifiés PIT | Nouvelle étude bornée des excursions, distincte des anciens tests terminaux |

## Les tentatives de combinaison déjà réalisées

[Consensus des experts OOF](oof_consensus_audit.md) : les moyennes de rangs,
l'accord renforcé et le veto de régime n'ont pas franchi les gates H3/H5/H10/H20.
L'IC du consensus est environ −0,0014 à +0,0118, inférieur au meilleur composant.
Ne pas optimiser maintenant des poids sur ces mêmes résultats.

[Audit de complémentarité](directional_complementarity_audit.md) : 402 017
événements sur 1 134 dates, deux familles comparables. Les six intervalles
d'IC résiduel incluent des valeurs négatives ; H20 est pratiquement nul.
Une faible corrélation entre scores ne démontre pas une information utile commune.

Les 17 chemins de composants référencés par
`config/research/oof_consensus_0802c8.json` sont absents au contrôle du 14 octobre,
après la remise à zéro US demandée. Les rapports subsistent, pas une matrice OOF
rejouable ; aucune ancienne campagne n'a été restaurée.

[Filtre d'entrée du nouvel Oracle parcours](oracle_path_filtre_entree_separabilite_20261014.md) :
183 colonnes / TOP10/20/50, aucun signal univarié ne passe la confirmation.
Cela n'exclut pas toutes les interactions non linéaires, mais ne constitue pas
un ensemble d'experts directionnels validés à empiler.

## Anomalie documentaire de qualification PIT : DDR-5

Le code `modelFactory/directional_data_research/analyst_revisions.py` charge les
valeurs courantes de `stock_earnings_calendar`, puis joint par `earnings_date`.
Il ne charge ni heure de publication, ni date de première disponibilité, ni
version de l'estimation avant les résultats. `earnings_date <= J` ne suffit donc
pas à certifier une surprise historiquement connue à J, et un calendrier courant
ne certifie pas les annonces futures connues à chaque date passée.

Les anciennes statistiques restent conservées, mais leur appellation « PIT
strict » ne doit plus servir de garantie. Le support EODHD a explicitement
confirmé l'absence d'historique as-known des estimations sur ses offres.
Aucun correctif de calcul partagé ou migration n'est réalisé dans cet audit.

## Consensus EODHD réellement disponible maintenant

Lecture seule le 14 octobre : `stock_analyst_consensus_eodhd_history` contient
959 094 lignes, **trois dates de snapshot** (11–13 octobre 2026) et 5 742 symboles.
Les trois marqueurs `fiscal_identity_qualified`, `units_qualified`,
`historical_pit_qualified` sont à faux sur ces lignes. Un grand nombre de lignes
ne constitue pas des années de décisions indépendantes : pas encore de parcours
H20 arrivé à maturité pour ces snapshots.

## Suite réalisée dans ce tour

L'utilisateur a demandé les fortes news positives et le **maximum haussier
pendant H0…H20**, puis J−1/J−2. Cette hypothèse distincte est évaluée hors ligne,
sur les archives 2025–2026, avec fenêtres et seuil >0,9 figés, témoins et couverture.
Elle ne réentraîne pas Oracle et ne transforme pas une excursion en PnL.
Voir [l'étude news/parcours](news_positives_parcours_h20_20261014.md).
