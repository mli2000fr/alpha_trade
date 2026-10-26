# P05 — protocole figé, canal des dix creux quotidiens

Préenregistrement du 22 octobre 2026, avant nouveaux résultats économiques.
Répertoire canonique : `artifacts/research/us_oracle_low_channel_p05/20261022-v2`.

V1 préenregistrée avant résultats, conservée **NON VALIDÉE** : son vérificateur
utilisait l'arrondi vectoriel pandas, différent de l'arrondi scalaire Python
spécifié à certains demi-cents (exemple6,675→6,67 contre6,68). V2 ne change
ni le canal exécuté, ni les entrées, ni N, ni les critères. Le vérificateur
scalaire est corrigé et toute la comparaison est rejouée dans un dossier neuf.

## Hypothèse et intervention unique

Inspirations FMZ archivées : documents 413 « Highest-high-lowest-low-stop » et
492 « M-Language-Turtle-Trading-strategy-implementationsV-10 », au commit
`7853bb2bf262c4567ac238d3552d97f0e50cb801`. Adaptation propre, pas reprise de bots.
Remplacer le trailing15 % du témoin par un canal de dix **séances** régulières
achevées, sans nouveau signal directionnel et sans recherche de N optimal.

LONG uniquement. Stop initial `round(E*(1-.07),2)` ; conserver exactement cette
expression du contrat Winner, y compris son arrondi à demi-cent flottant.
Pendant la séance d'entrée, seul ce stop s'applique. Après chaque clôture
complète, calculer `C=round(min(low des dix dernières séances),2)` et
`S=max(S_précédent, stop_initial, C)`. La nouvelle protection ne devient active
qu'à l'ouverture suivante. Jamais de low final de séance utilisé rétroactivement.
Le stop ne redescend pas. Un gap s'exécute à l'open réel, pas au stop théorique.
Pas de TR15 résiduel, TP, partiel, buffer ATR, MA, renforcement, réentrée ou
réinitialisation de l'échéance. Vingt séances de détention entrée incluse,
puis vente à l'open21 ; stops et risque déjà en place gardent leur priorité.

## Données et témoins

Archives locales scellées P01-v2 / `us_winner_context_headroom/20261021-v1`.
Creux reconstruits uniquement depuis les séances raw SIP régulières non remplies
et complètes suivant le calendrier NYSE, fermetures anticipées comprises.
Ne pas mélanger les daily ajustés split aux prix intraday bruts. Aucun nouveau
téléchargement ni lecture/écriture SQL. Pas de modification de la collecte en cours.

Population initiale : 200 occasions Winner, sélection de recherche CatBoost
PATH_H20 conditionnelle à la couverture, pas tout le TOP10 quotidien de production.
Le canal exige dix séances complètes pour chacun des vingt jours de détention
potentiels, **avant** tout calcul de sortie. Une occasion dont l'historique manque
est réservée à l'identique dans les deux bras, même si elle aurait été stoppée tôt.
La vérification de couverture préliminaire donne 109 admissibles, 91 réservées.
Ce filtre de couverture future introduit un biais de sélection hérité et supplémentaire.

Trois bras : WINNER complet (ancre), COMMON_WINNER (couverture commune), P05
(mêmes entrées que COMMON_WINNER). Ne pas attribuer l'effet de restriction du
périmètre au canal. Douze portefeuilles : trois bras × 2025/2026 × 8/25 bps par jambe.
Les quatre ancres doivent reproduire les transactions, valorisations, décisions,
maintenance et événements B4 de P01 à l'octet près.

Capital annuel remis à 4 000 USD, plafond d'admission brut 1×, demi-cible,
quantités entières, sizing SL7 %, composants risque natifs et B4 DD15 figés,
frais, exposition et financement identiques. Une allocation effective différente
peut résulter des sorties/cash/états B4 : les quantités **ne sont pas** artificiellement
figées entre portefeuilles. Les unités appariées isolent mieux l'effet de sortie.
Pas de simulation 2024 : absente de l'archive intraday figée utilisée ici.

## Qualification et décision

Comparer rendement net, DD, taux gagnant, gains/pertes et détention, coûts,
capital mobilisé, résultats par entrée, cas sans chevauchement (fenêtre OracleJ40),
bootstrap de mois Oracle : 2 000 tirages, graine731. Seuils de confirmation :
au moins30 occasions sans chevauchement/an dont10 stops réellement remontés,
gain portefeuille dans les deux années aux deux coûts, DD non aggravé à8bps,
gain unitaire positif aux coûts stressés, six mois minimum et borne basse95 %
du gain apparié strictement positive. Sinon non-confirmation ou échantillon
insuffisant ; aucun ajustement postérieur sur les pertes.

Audit scalaire distinct, reconstruction indépendante des canaux et des mises à
jour, contrôle du cash, des frais et des événements risque, empreintes avant/après.
Même assistant : ce n'est pas une seconde revue humaine indépendante.
Les années déjà examinées ne sont pas un holdout neuf ; archives conditionnelles,
absence NBBO/fills/latence remplacement et limites sectorielles/PIT héritées :
**recherche exploratoire, pas parité live complète ni preuve exploitable en production**.
Aucun modèle, entraînement, SQL, fournisseur, ordre ou paramètre de production modifié.

## Lancement

```powershell
python -u -m scripts.research.us_oracle_low_channel_p05 --phase run
python -u -m scripts.research.us_oracle_low_channel_p05_audit
```

Ne jamais réutiliser un dossier scellé. Source, tests et présent protocole sont
empreintés avant calcul ; les changements correctifs exigent un dossier neuf.
