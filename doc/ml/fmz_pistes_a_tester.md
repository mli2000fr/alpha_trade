# FMZ — pistes qui méritent une expérience Alpha Trade

Mise à jour : 22 octobre 2026. **Périmètre de lecture terminé, aucun nouveau backtest lancé.**

Avancement : **1 000 documents examinés, texte utile et code fourni**, soit
tout le périmètre demandé au commit archivé, jusqu'à
`The-Bollinger-Band-Automated-Trading-Strategy.md` inclus. La tranche 901–1000
n'ajoute aucune piste suffisamment distincte ; la sélection reste à sept.
Ce bilan porte sur ces 1 000 documents, pas sur les 5 807 Markdown du dépôt.
Ce suivi ne certifie ni les images, ni les pages secondaires liées, ni les
performances annoncées. Le document 708 est le README/index du dépôt, pas une
stratégie : lire sa structure et son texte ne signifie pas lire les 5 810 liens
qu'il contient. Plusieurs autres documents sont des exemples techniques.
Les sept pistes ci-dessous restent des expériences
à préenregistrer, pas des stratégies validées.

Ce fichier ne conserve que les idées justifiant un test distinct. Il n'est
ni une liste des stratégies rejetées, ni un inventaire des indicateurs déjà
testés. Les pistes sont des hypothèses, pas des avantages démontrés.
Les paramètres d'illustration ne sont pas des optima validés.

## P01 — Attendre une sortie de compression avant la cassure Oracle

**Priorité : première expérience proposée. Statut : à préenregistrer.**

### Idée

Oracle sélectionne les titres susceptibles de bouger ; une compression locale
suivie d'une expansion servirait à choisir le moment d'entrée. Attendre une
séquence calme → expansion → cassure confirmée, plutôt que toute cassure.

Sources :
[BB/Keltner Squeeze](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/BB-Keltner-Squeeze%E4%BA%A4%E6%98%93%E7%AD%96%E7%95%A5BB-Keltner-Squeeze-Trading-Strategy.md)
et [Squeeze Momentum](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/Squeeze-Momentum-Indicator.md).
Retenir le concept, pas recopier les implémentations publiées.

### Différence justifiant le test

Le test porte sur l'ordre temporel **compression avant déclenchement**, pas
sur un nouvel indicateur statique ni sur plusieurs jours de hausse. Une forte
amplitude daily peut coexister avec une consolidation intraday récente.

### Comparaison proposée

- Témoin : cassure Winner actuelle sur les candidats Oracle causaux.
- Variante : même contrat, mais compression bilatérale antérieure puis sortie
  de compression exigées avant la confirmation de cassure.
- Exemple de départ : Bollinger20/2 écarts-types et Keltner20/1,5ATR sur cinq
  minutes. Durée minimale et délai admissible à figer avant calcul.
- Mêmes quantités, frais, capital, levier et protections ; pas ajout simultané
  de VWAP, macro ou filtre sectoriel.

### Conditions et limites

Bougies closes uniquement, calendrier officiel, pas achat rétroactif au prix
qui confirme le signal. Warmup et reset de séance explicites. Conserver les
non-entrées et données absentes. Comparer à exposition et risque documentés.
Mesurer le retard, les occasions manquées, le gain restant, le PnL net et le DD,
pas uniquement le pourcentage de directions reconnues après le mouvement.

## P02 — Prendre un bénéfice partiel, laisser courir le solde

**Priorité : seconde expérience indépendante. Statut : à préenregistrer.**

### Idée

Conserver exactement les mêmes entrées, mais réaliser une partie du gain
après une première excursion favorable et laisser courir le reste avec le
stop dur, le trailing et l'échéance de détention.

Source : [AlphaTrend + KAMA et sortie partielle](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/AlphaTrend%E4%B8%8EKAMA%E7%BB%93%E5%90%88%E7%9A%84%E8%87%AA%E9%80%82%E5%BA%94%E8%B6%8B%E5%8A%BF%E8%B7%9F%E8%B8%AA%E4%B8%8E%E9%A3%8E%E9%99%A9%E7%AE%A1%E7%90%86%E7%AD%96%E7%95%A5Adaptive-Trend-Following-Strategy-Combining-AlphaTrend-and-KAMA-with-Risk-Management.md).
Isoler la sortie partielle, sans adopter ses signaux de tendance ni ses
hypothèses de remplissage.

### Différence justifiant le test

Ni renforcement gagnant, ni TP liquidant toute la position : il s'agit de
réduire la quantité détenue après gain tout en gardant un potentiel résiduel.
Les grilles antérieures de TP complets ne mesurent pas cette intervention.

### Comparaison proposée

- Témoin : entrées Winner, SL7/TR15/H20/sans TP, contrat actuel.
- Variante illustrative : céder50% à+10%, garder le solde sous les mêmes
  protections et vendre au plus tard à l'open21.
- Pas de déplacement automatique du SL au prix d'entrée, de desserrement du
  stop dur, de réentrée ni de renforcement ajouté.
- Frais de chaque fill, actions entières, prix exécutable, cash libéré et
  interactions avec le portefeuille réellement recalculés.

### Conditions et limites

Une partie des grands gagnants sera coupée plus tôt : le résultat peut être
moins bon malgré un taux de réussite accru. Examiner concentration des gains,
gain/perte moyens, DD et capital immobilisé. Une amélioration du confort de
la courbe n'est pas forcément une augmentation de rendement.

## P03 — Entrer sur le premier retest confirmé d'un niveau déjà cassé

**Priorité : expérience de timing distincte. Statut : à préenregistrer.**

### Idée

Sur les candidats Oracle, mémoriser un niveau connu avant la cassure. Après
une cassure haussière confirmée, attendre un premier retour près de ce niveau,
puis une nouvelle clôture au-dessus pour acheter. Pour SHORT, logique miroir
à tester séparément, sans présumer sa rentabilité.

Sources d'inspiration : [zones après franchissement et engulfing](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/15%E5%88%86%E9%92%9F%E5%9B%BE%E8%A1%A8%E5%90%9E%E6%B2%A1%E7%AA%81%E7%A0%B4%E5%A4%9A%E9%87%8D%E7%A1%AE%E8%AE%A4%E7%AD%96%E7%95%A5-15-Minute-Engulfing-Breakout-Multi-Confirmation-Strategy.md)
et [zone de repli 3EMA](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/3EMA.md).
**L'adaptation proposée est la nôtre** : le script engulfing peut entrer dès la
création de sa zone et ne garantit pas un retest ultérieur. Le motif de
chandelles et les moyennes ne sont pas à ajouter au test.

### Différence justifiant le test

Pas un achat après une simple baisse arbitraire depuis Oracle : le signal
exige la séquence **niveau prédéfini → cassure → retour → reprise**, avec des
barres distinctes. Hypothèse : entrer moins étendu et éviter les cassures
immédiatement réintégrées. Le gain de prix peut être compensé par des occasions
manquées ou un retard : aucune amélioration n'est acquise.

### Comparaison proposée

- Témoin : première cassure Winner avec sa confirmation habituelle.
- Variante : premier retest confirmé du même niveau, une seule tentative.
- Contrôle : cassure avec retard comparable, pour distinguer effet du retest
  et simple attente. Définir ce retard causalement, sans le choisir à partir
  du futur retest de chaque occasion.
- Même risque, sizing, frais, SL/trailing/horizon et calendrier. Aucun
  élargissement du stop dur pour rendre le signal admissible.

### Conditions et limites

Tolérance autour du niveau exprimée en ATR connu, délai maximal, nombre de
confirmations et règle d'invalidation à figer avant calcul. Ne pas déplacer
après coup le niveau sur le creux le plus favorable. Entrée seulement après
confirmation, au prochain prix exécutable ; aucun fill de limite présumé
simplement parce que le low5m a touché un niveau. Conserver les occasions sans
retest, refus risque et données manquantes dans le bilan.

## P04 — Dual Thrust : déclenchement autour de l'ouverture, calibré par le passé

**Priorité : après les trois premières pistes. Statut : à préenregistrer.**

### Idée

Sur le TOP10 Oracle connu après J, fixer à l'ouverture de J+1 deux seuils dont
la distance dépend uniquement des séances déjà terminées. L'hypothèse est
qu'un mouvement intraday significatif **depuis l'ouverture**, rapporté aux
amplitudes récentes, choisisse mieux le moment d'entrée qu'une cassure brute.
Il ne s'agit ni d'une nouvelle information fondamentale, ni d'une direction
garantie par Oracle.

Sources : [Dual Thrust OKCoin](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/Dual-Thrust-OKCoin-%E6%9C%9F%E8%B4%A7.md)
et [version pédagogique OKEX](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/Dual-Thrust-OKEX%E6%9C%9F%E8%B4%A7-%E6%95%99%E5%AD%A6.md),
documents258 et260 de l'inventaire archivé.

### Différence justifiant le test

Notre [cassure intraday H10 déjà rejetée](oracle_top10_cassure_intraday_tp10_sl5_20261019.md)
déclenchait au franchissement du haut/bas de J. Ici, les seuils sont ancrés
sur **l'ouverture de J+1**, avec une distance issue de plusieurs séances
antérieures. Un gap ne constitue donc pas à lui seul un signal de poursuite.
Contrairement à P01, aucune compression préalable n'est exigée ; contrairement
à P03, aucun retest n'est attendu. Cette différence motive un test limité,
pas une présomption que la cassure précédemment perdante est devenue rentable.

### Comparaison proposée

- Exemple à figer avant calcul : N=4 séances régulières achevées jusqu'à J ;
  `R = max(max(high)-min(close), max(close)-min(low))` sur ces seules séances.
- À J+1 : seuil haut `open + 0,5*R`, seuil bas `open - 0,5*R`, fixes pour
  toute la séance. Pas de recalcul avec le haut/bas ou le close final de J+1.
- Première clôture5m au-delà du seuil → entrée à l'open de la barre suivante ;
  une tentative par occasion, pas d'inversion automatique. Les valeurs N=4 et
  k=0,5 illustrent un protocole simple, pas des paramètres optimisés.
- Isoler d'abord le changement de déclencheur : mêmes candidats Oracle,
  capital, quantités, frais, risque et SL/trailing/horizon que le témoin Winner
  figé. Inclure aussi la cassure du haut/bas de J et un contrôle toujours LONG
  aux mêmes heures, pour distinguer le timing d'une vraie information de sens.
- Pas de grille k/N, de filtre EMA/ADX, de prise partielle ou de renforcement
  ajoutés simultanément. LONG et SHORT évalués séparément.

### Conditions et limites

Adapter le concept, **ne pas reprendre tel quel le bot crypto** : il inverse
les positions sans stop dur autonome ; la fenêtre des extrema dans son helper
doit être rendue explicitement antérieure à la séance de déclenchement.
Les prix daily et intraday doivent partager une base qualifiée (splits et
identité compris), avec calendrier NYSE, ouverture réelle et bougies closes.
Une absence de signal reste une abstention, pas une occasion remplacée.
Conserver trous et refus de risque dans le bilan ; comparer couverture, retard,
exposition, frais, PnL net et DD. Les années déjà examinées restent exploratoires,
pas un nouvel échantillon hors sélection.

## P05 — Protéger la position par un canal de creux récents

**Priorité : test de sortie indépendant, après les pistes prioritaires.
Statut : à préenregistrer.**

### Idée

Conserver les entrées Oracle/Winner, mais remplacer le trailing à distance
fixe du sommet par une protection qui remonte avec les creux récents. Tester
si une rupture de la structure récente du prix constitue une meilleure sortie
qu'un recul uniforme de 15 % depuis le sommet. Aucune nouvelle prédiction de
direction n'est supposée.

Sources : [Highest high / lowest low stop](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/Highest-high-lowest-low-stop.md)
(document 413) et [présentation Turtle](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/M-Language-Turtle-Trading-strategy-implementationsV-10.md)
(document 492). Le premier utilise les extrema des barres antérieures ; le
second décrit notamment une sortie par canal de dix périodes. Ne reprendre
ni leurs entrées ni leurs renforcements, et rendre explicites les décalages
du canal plutôt que présumer la causalité de chaque helper publié.

### Différence justifiant le test

Les grilles de pourcentages SL/TR/TP/horizon et le test de stop adapté à l'ATR
ne mesurent pas cette géométrie de sortie. Ici, la distance au sommet dépend
des creux effectivement formés. Ce n'est pas le filtre de tendance persistante
EMA/ADX déjà abandonné : il n'y a aucun nouveau veto d'entrée.

### Comparaison proposée

- Témoin : mêmes entrées Winner, SL7/TR15/H20/sans TP, sans renforcement.
- Variante illustrative LONG : stop dur initial à `E * 0,93`, où E est le
  prix d'entrée réellement exécuté. Après chaque séance achevée, calculer le
  plus bas des dix dernières séances régulières terminées, puis fixer pour
  la séance suivante `S_nouveau = max(S_précédent, E * 0,93, plus_bas_10)`.
- Le canal remplace seulement le trailing de 15 % ; il ne s'y ajoute pas.
  N=10 est un exemple à figer avant calcul, pas le meilleur choix démontré.
  Pas de buffer ATR, de filtre MA, de réentrée ou de sortie partielle ajoutés.
- Mêmes quantités initiales, capital, levier, coûts et risque de production.
  Échéance inchangée : vingt séances entrée incluse, vente à l'open 21.
- SHORT éventuel séparé : canal des hauts, stop qui ne peut que descendre,
  emprunt et exécution préalablement qualifiés.

### Conditions et limites

Utiliser uniquement les séances achevées pour déplacer le stop : le low d'une
séance ne peut pas protéger rétroactivement cette même séance. Le stop initial
reste actif immédiatement après l'entrée ; les ordres de remplacement doivent
préserver la protection existante. Ne jamais desserrer le stop quand le canal
redescend. Prix/splits/identités doivent être cohérents entre daily et intraday.
Un franchissement par gap se traite au prix exécutable, pas au niveau théorique.

Comparer PnL net, DD, restitution des gains, durée, rotation et frais. Un canal
plus serré peut réduire la perte moyenne mais provoquer davantage de sorties
prématurées. Aucun résultat favorable n'est encore mesuré pour Alpha Trade.

## P06 — Limiter la restitution à une fraction du gain déjà atteint

**Priorité : autre test de sortie, séparé de P02 et P05.
Statut : à préenregistrer.**

### Idée

Une fois une avance suffisante obtenue, protéger une fraction de cette avance,
plutôt que conserver une distance constante en pourcentage du cours maximal.
L'ensemble de la position reste détenu jusqu'à la sortie : aucune vente
partielle ni renforcement n'est introduit.

Source : [K Consecutive Candles, protection d'une fraction du gain](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/K%E7%BA%BF%E8%BF%9E%E7%BB%AD%E6%95%B0%E7%9B%AE%E7%89%9B%E7%86%8A%E5%88%A4%E6%96%AD%E7%AD%96%E7%95%A5-K-Consecutive-Candles-Bull-Bear-Strategy.md),
document 483. Son calcul soustrait une fraction du gain depuis l'entrée au
sommet observé. Retenir ce concept seulement : le code utilise un autre nom
de position pour fermer le SHORT, et ses entrées, ticks et backtest ne sont
pas à reprendre comme preuve d'exécution.

### Différence justifiant le test

Pour une entrée à 100 et un sommet déjà observé à 120, restituer au maximum
50 % du gain donne un seuil à 110. Un trailing de 15 % du sommet donne 102.
Ce ne sont donc pas deux noms du même trailing. Le seuil n'est pas un profit
net garanti : gaps et frais peuvent dégrader le prix de sortie.

P02 vend une quantité partielle à un gain fixe ; ici, la quantité reste
inchangée. L'ancien audit E15 décalait l'activation d'un trailing à distance
ATR : il ne testait pas cette distance proportionnelle au gain accumulé.

### Comparaison proposée

- Témoin : mêmes entrées Winner, SL7/TR15/H20/sans TP, sans renforcement.
- Variante illustrative LONG : garder le SL initial de 7 %. Activer la
  protection quand un sommet observé après entrée atteint `E * 1,10` ; utiliser
  ensuite `S_nouveau = max(S_précédent, E * 0,93, E + 0,50 * (P - E))`, où P
  est le plus haut déjà connu depuis l'entrée. Le trailing TR15 est remplacé.
- Seuil d'activation +10 % et fraction conservée 50 % à figer avant calcul,
  sans grille ni sélection du meilleur couple après lecture des pertes.
- Mise à jour après une bougie régulière de cinq minutes terminée, effective
  au plus tôt pour la suivante. Avant activation : stop dur maintenu, aucun
  desserrement. Même horizon, sizing, capital, levier et coûts que le témoin.
- LONG d'abord ; miroir SHORT uniquement avec contrôles d'emprunt et de fills.
  Pas de comparaison simultanée de nouveaux filtres, renforcement ou TP fixe.

### Conditions et limites

P est un maximum connu à cet instant, **jamais le maximum futur de H20**.
Ne pas utiliser le high d'une bougie pour relever le stop puis son low comme
si le nouvel ordre avait déjà été actif : avec des OHLC5m, l'ordre des passages
est inconnu. Rejouer les gaps, les frais et la protection antérieure ; aucun
prix synthétique garanti. Examiner les sorties précoces, grands gagnants
tronqués, gain/perte moyens, DD, exposition et PnL net du portefeuille.
Cette règle pourrait préserver davantage de gains intermédiaires, mais aussi
sortir avant une continuation. Son utilité reste entièrement à mesurer.

## P07 — Balayage d'un creux récent, reprise et confirmation ultérieure

**Priorité : test d'entrée distinct, après les premières pistes.
Statut : à préenregistrer.**

### Idée

Parmi les candidats Oracle connus après J, rechercher une séance J qui a
atteint un nouveau creux récent, présente une amplitude inhabituellement
grande, mais termine près du haut de sa propre fourchette. Ne pas acheter
ce creux rétrospectivement : attendre ensuite une reprise confirmée au-dessus
du haut de J. Hypothèse : cette séquence distingue certains rebonds durables
des titres qui continuent simplement à baisser. Elle ne prouve pas une
« capitulation » ni une intervention institutionnelle.

Source : [Mean Reversion Breakout / Larry Conners SMTP](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/RSI%E5%9D%87%E5%80%BC%E5%9B%9E%E5%BD%92%E7%AA%81%E7%A0%B4%E7%AD%96%E7%95%A5-RSI-Mean-Reversion-Breakout-Strategy.md),
document 797. Malgré son titre, le code ne calcule aucun RSI : il combine
un creux sur dix barres, une grande fourchette et une clôture dans son quart
supérieur. L'adaptation actions daily/intraday proposée ici est la nôtre.

### Différence justifiant le test

La cassure du haut de J a déjà été testée seule ; ce n'est pas un nouveau
signal. La nouveauté à isoler est la **configuration de rejet baissier à J
avant cette cassure**. Ce n'est ni P03 (retest d'une résistance déjà cassée),
ni P01 (compression préalable), ni un simple RSI survendu ou filtre EMA/ADX.
L'ancien audit d'épuisement prix tick examinait `-return_5m` près de la clôture,
pas cette séquence daily puis confirmation ultérieure ; son NO_GO n'est pas
annulé pour autant.

### Comparaison proposée

- Exemple figé LONG : à la clôture J, `low_J` strictement inférieur au minimum
  des neuf séances précédentes ; `high_J-low_J` strictement supérieur aux neuf
  fourchettes précédentes ; `(close_J-low_J)/(high_J-low_J) >= 0,75`.
  Exiger une fourchette positive et toutes les observations qualifiées.
- Figer le haut de J. Pendant J+1/J+2 seulement, première clôture régulière 5m
  strictement au-dessus de ce haut → achat à l'open de la barre suivante,
  une seule tentative. Annuler avant entrée si le low de J est cassé, ou à
  l'expiration ; un ordre non exécuté ne doit pas rester actif indéfiniment.
- Témoin : même cassure et même attente sur tous les candidats, sans le filtre
  de configuration. Conserver aussi le témoin Winner actuel. Documenter les
  différences d'exposition et le coût des occasions rejetées, pas seulement
  le rendement des rares trades finalement entrés.
- Mêmes quantités, capital, levier, frais, risque et sorties SL7/TR15/H20/sansTP,
  sans renforcement. Vingt séances à partir de l'entrée, sortie à l'open21.
  Ne pas adopter simultanément le trailing structurel de la source.
- Dix séances, quart supérieur et deux séances d'attente sont des choix
  illustratifs à préenregistrer, pas des optima. Pas de grille de chandelles,
  filtre volume/RSI, modèle directionnel ou miroir SHORT dans ce premier test.

### Conditions et limites

Le bot publié remet immédiatement `orderPending` à faux après l'envoi de
l'ordre stop ; cela ne démontre ni son expiration ni son annulation effective.
Son relèvement du stop avec le low courant ne donne pas l'ordre intrabar des
passages. Ne pas copier ces hypothèses de fill ou de protection.

Calendrier, prix bruts/splits, identité et bougies closes doivent être qualifiés.
Ne jamais attribuer une entrée au low de J, ni anticiper sa clôture ou celle
de la barre de confirmation. Mesurer fréquence, couverture, retard, faux
rebonds, occasions manquées, PnL net/DD et concentration par titre/date.
Un échantillon trop petit donne une conclusion insuffisante, pas une raison
d'assouplir après coup les seuils. Les années déjà vues restent exploratoires.

## Conditions communes avant lancement

- Qualifier la couverture intraday SIP, sans sélection des seuls chemins
  complets futurs ; ne pas interrompre les téléchargements en cours.
- Employer des scores Oracle OOS réellement disponibles pour chaque période.
  Des prix depuis2016 ne fournissent pas automatiquement des signaux OOS2016.
- Préenregistrer une comparaison limitée par piste, sans chercher les seuils
  sur les pertes de2025/2026 déjà consultées.
- LONG/SHORT séparés ; SHORT économique seulement si emprunt et accès sont
  qualifiés. Risque et protections de production maintenus.
- Aucun avantage n'est promu avant confirmation chronologique et coûts/risque.

La lecture du périmètre demandé est clôturée. Les sept protocoles restent à
préenregistrer avant tout test ; aucun lancement n'est implicite dans ce bilan.
