# P01 — compression, expansion puis cassure confirmée : protocole figé

Date : 22 octobre 2026. Recherche exploratoire, aucune modification de production.
Ce document est figé avant lecture des nouveaux résultats ; le bilan sera ajouté
au registre `experiences_done.md`, sans réécrire les paramètres après calcul.

## Hypothèse et comparaison

Sur les candidats Oracle d'amplitude, une compression locale suivie d'une
expansion peut améliorer le moment d'entrée. Aucun pouvoir directionnel ni
gain n'est présumé. LONG uniquement pour ce premier pilote.

Trois bras, sans grille de seuils :

- **WINNER** : premier franchissement frais du haut brut de la veille,
  confirmé par deux clôtures régulières 5m au-dessus, précédées d'une clôture
  au niveau/en dessous. Trois barres terminées dans la même séance ; entrée
  à l'ouverture contiguë suivante, jamais sur le high/close qui confirme.
- **WARMUP_CONTROL** : même règle, mais les trois barres de preuve doivent
  toutes disposer des indicateurs calculables. Ce contrôle isole une partie
  de l'effet d'attente ; il n'est pas ajusté aux heures/expositions de P01.
- **P01** : même règle et warmup, avec compression puis libération qualifiée
  avant ou pendant la première clôture au-dessus du niveau. Une confirmation
  trop tardive ou une nouvelle compression ne réactive pas une vieille preuve.

Chaque bras prend sa première occasion admissible pendant les vingt séances
après Oracle. P01 peut attendre une cassure fraîche ultérieure, pas reprendre
un prix d'entrée passé. Un refus de risque consomme la tentative ; pas de retry,
de remplacement TOP11, de reclassement ou de renforcement.

## Indicateurs et chronologie fixés avant résultats

Calculs sur bougies régulières terminées, **réinitialisés à chaque séance** :

- Bollinger : moyenne simple20, deux écarts-types population (`ddof=0`).
- Keltner : EMA20, initialisée au premier close, largeur ±1,5ATR20 de Wilder.
  ATR initialisée par la moyenne des vingt premiers true ranges ; première
  barre : high−low. Les gaps nocturnes ne font pas partie de cet ATR intraday.
- Warmup vingt barres ; pas de remplissage des données manquantes.
- Compression : les deux bandes Bollinger strictement à l'intérieur des deux
  bandes Keltner pendant **trois barres consécutives**.
- Libération : première barre hors de cette compression, avec largeur Bollinger
  supérieure à celle de la barre précédente.
- La libération doit être connue au plus tard à la première clôture de cassure,
  dater d'au plus **six barres** et n'être suivie d'aucune nouvelle compression.
- Même confirmation Winner ; une confirmation sur la dernière barre de séance
  ne permet pas une entrée synthétique au lendemain.

20/2/1,5, trois barres et six barres sont des choix simples préenregistrés,
pas des paramètres optimisés. Ne pas recopier les bugs des scripts FMZ, notamment
l'utilisation du multiplicateur Keltner dans l'écart-type Bollinger.

## Périmètre effectivement testable

Archives immuables existantes :
`artifacts/research/us_winner_context_headroom/20261021-v1`.
Toutes les **213 campagnes LONG**, 72 titres, sont considérées avant les nouveaux
résultats. Elles proviennent d'un Oracle **CatBoost PATH H20 de recherche**, pas
du champion LightGBM de production ni de l'ensemble du TOP10 quotidien.
2025 et 2026 jusqu'au 30 septembre sont déjà explorées : pas de holdout vierge.
2024 n'est pas simulée avec des données intraday absentes de cette archive.

Les archives comportent un biais hérité : campagnes sélectionnées antérieurement
pour leurs chemins complets et univers actuel/survivants. La qualification
commune ajoute une sélection par couverture future, **jamais une feature live** :
manque dans le scan d'entrée, maturité insuffisante, trou avant l'open21 d'un
des bras ou opération sur titres connue réservent la campagne pour tous les bras,
même si l'un aurait touché son stop plus tôt. Publier tous les motifs, sans
substitution. L'absence d'événement enregistré ne certifie pas l'exhaustivité.

Prix bruts SIP Alpaca, séances régulières, non remplis, calendrier NYSE et
horodatages UTC qualifiés. Archives actuelles, pas preuve d'une réception
historique par l'application. Aucun nouveau téléchargement ni accès SQL.

## Sorties, portefeuille et frais inchangés entre bras

- SL7 %, trailing15 %, pas de TP, pas d'ajout gagnant. Arrondi au cent comme
  le contrat Winner ; trailing fondé sur les sommets déjà terminés seulement.
- Vingt séances **depuis l'entrée**, entrée incluse ; vente à l'ouverture de
  la 21e. Le stop actif prime sur un gap adverse, sans garantie de perte à7 %.
- Comptes annuels repartant à4 000USD. Plafond d'admission **1x**, comme le
  dernier témoin DD15 ; aucune comparaison P01 levier1x contre témoin2x.
  Une position encore ouverte à la borne annuelle est valorisée au marché,
  frais d'entrée comptés ; ni liquidation inventée ni rendement réalisé fictif.
- Même formule : cible complète au plus50 % de l'equity et risque4 %, puis
  demi-position. Huit positions maximum, actions entières, pas de doublon détenu.
  Les quantités effectives peuvent différer après divergence de cash/B4.
- Composants natifs de sizing, contraintes, comptabilité et risque B4DD15 ;
  régimes SPY de la veille archivés, règles de reprise/fermetures forcées conservées.
  Pas tous les contrôles sectoriels/corrélation/PIT/quotes du portefeuille live.
- **8bps par jambe**, puis **25bps** en stress, sur notionnels exécutés.
  Hypothèses de friction, pas historiques NBBO/queue/fills certifiés. Financement
  natif conservé ; pas d'emprunt de titres puisque LONG seul.

Reconstruction séparée des sorties au cent, du cash, des frais, des valorisations
et des événements B4. Elle emploie l'auditeur existant paramétré pour les frais,
avec un résolveur scalaire distinct du moteur de sortie. Même assistant,
pas revue humaine indépendante ni certification de parité live complète.

## Mesures et critères de suite

Publier pour chaque année/bras/friction : capital final, rendement, DD max,
gagnants/perdants, gains/pertes moyens, durée et capital moyen mobilisé.
Publier aussi fréquence, délai d'entrée, non-entrées, exclusions et refus risque.
Les occasions sans signal restent en cash ; rendement unitaire d'occasion zéro,
sans les supprimer de la population pour améliorer artificiellement la moyenne.

Mesure unitaire appariée P01−WARMUP_CONTROL, puis contrôle sans chevauchement :
première occasion Oracle par titre, blocage conservateur jusqu'à J+40, borne
maximale commune entrée+20. Ce n'est pas une preuve d'indépendance entre titres.

Critères nécessaires pour justifier seulement une confirmation ultérieure :
au moins30 signaux P01 non chevauchants et10 titres par année ; surplus de
portefeuille positif en2025 et2026 aux deux frictions ; surplus unitaire
d'occasion positif chaque année et aux frais stressés ; positif dans les deux
semestres2026 ; intervalle bootstrap mensuel (2 000tirages, graine731, mois
d'Oracle, au moins6mois) avec borne basse95 % positive. Pas de correction de
la multiplicité des recherches antérieures revendiquée.

Sinon : `INSUFFICIENT_P01_SAMPLE` ou `NO_GO_P01_NOT_CONFIRMED`, sans élargir les
seuils après lecture des résultats. Même si ces critères passent, pas de promotion
automatique : deux années déjà vues et un échantillon conditionnel ne suffisent pas.

## Suivi

Programme : `scripts/research/us_oracle_compression_p01.py`.
Dossier canonique : `artifacts/research/us_oracle_compression_p01/20261022-v2`.
Le premier passage v1 est conservé mais non validé : l'audit a détecté une
différence d'un cent à un demi-cent initial (GLW, entrée151,5) entre `1-0,07`
du contrat partagé et la constante `0,93` de l'adaptateur. V2 emploie exactement
l'expression du contrat existant, sans changer seuils, échantillon ou frais,
et rejoue les douze cas. Tests de non-régression ajoutés ; production inchangée.
`protocol.json` fige règles/sources avant calcul ; `signals.parquet`,
`unit-results.parquet`, `nonoverlap.parquet`, `reservations.parquet` conservent
les décisions ; `annual-summary.csv` et `report.json` donnent le bilan terminal.
`progress.json` suit l'avancement ; un statut FAILED n'est pas une conclusion.
