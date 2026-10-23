# Grille Winner native — comparaison parallèle plafond 1x / 2x

GO utilisateur du23octobre2026 : lancer en parallèle la même grille avec levier2x.
Nouveau dossier indépendant :
`artifacts/research/us_winner_native_grid_2017_2026/20261023-2x-v1/`.
Référence inchangée : `20261023-v1` dans le même répertoire parent.

## Amendement unique

Les300profilsLONG,10années,TOP10causal, dates02/06/2017–30/09/2026, HALF,
absence de renforcement, coûts8bps/jambe, intérêts6,5 %/an, resetannuel4000USD,
fenêtres de couverture communes et classement prédéfini sont inchangés.

Seule la limite d'exposition brute du risque passe **de1 à2**. Le moteur
possède déjà un compte margin avec pouvoir d'achat2x, minimumd'equity2000USD
et restrictions de mode d'entrée. L'adaptateur rend les paramètres margin2x
explicites et vérifie que la réapprobation native reçoit la limitebrute2x.
Les sources scellées du run1x, les modèles et la production ne sont pas édités.

**Autoriser2x ne force pas chaque position ni le portefeuille à doubler.**
Le budget de risque partrade reste1,25 % de l'equity, le poids maximalparposition
25 %, huitpositionsmax, capsecteur et contrôle de corrélation inchangés,
demi-position maintenue. Ces contraintes peuvent empêcher d'employer le levier,
voire rendre les résultats identiques à1x. Ne pas augmenter implicitement les
quantités ou doubler le risque partrade pour fabriquer un résultat «2x».
Le risque B4/DD15 n'est ni supprimé ni converti en plafond garanti deDD15.

Rapporter les valeurs observées : capitalbrut moyen/max, gross/equity moyen/max,
fraction desbougies au-dessusde1x, capital emprunté moyen/max (gross−equity
positif, sous le contrat margin sanssettlement/OSTréservée), financement
comptabilisé, rendement/DD. La volatilité des cours peut modifier le ratio
d'exposition après entrée ; le plafond est une règle d'admission, pas une
garantie de ratio exact à chaque instant.

## Comparaison appariée et contrôles

**Aucun nouvel appel fournisseur ouSQL pour ce second run.** Chaque année
réutilise une copie vérifiée parSHA256 des snapshots annuels scellés du run1x.
Si une année n'est pas encore archivée, attendre le snapshot de référence ;
ne pas figer un autre univers ni des prix différents. En cas de référence
terminalement en échec et de snapshot manquant, laisser le bilan incomplet.
Les cohortes admissibles et rangs sont recalculés puis comparés exactement
à la référence. Les résultats1x ne servent pas à modifier les profils2x.

Adaptateur limité au processus : préparation du protocole2x, configuration de
capacité, reprise des archives, métriques d'utilisation. Restauration des
symboles du module de référence même en cas d'exception. Un worker parannée,
deuxmaximum pour ce run (quatremaximum pour lesdeuxgrilles). Aucun batch
existant n'est modifié ou interrompu ; aucun ordre réel oupapier.

Tests de configuration/différences strictes, pouvoir d'achat natif aveccash
négatif et garde-fouequity, métriques d'exposition et restauration ducontexte.
Smoke20séances2017, mêmeprofilSL3/TR3/H10/TP15, cash/frais/achats/sorties
audités. Audit scalaire du run1x imposé aussi à chaque compte2x.

Après3 000comptes2x : classement selon2017–2023 inchangé, confirmation2024–2026
publiée sansréglage, puis comparaisonannée/profil avec les comptes1x disponibles.
`paired-1x-2x.partial.csv` n'est qu'une comparaison partielle si la référence
n'est pas encore complète ; fichierfinal `paired-1x-2x.csv` seulement avec
3 000paires. Ne pas présenter quelquescomptes terminés comme verdictglobal.

Les réserves du protocole1x restent intégrales : OHLCsansquotes/fills,
univers survivant, secteursactuelsnonPIT, OSTnonexhaustives, cohortes choisies
surcouverturefuture (seulement213/1470signaux2017), annéesdéjàexaminées. Pas
de garantie de rendement ni de paritélive intégrale, pas de promotionautomatique.
