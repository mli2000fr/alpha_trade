# Grille intraday LONG / SHORT — 21 octobre 2026

## Demande et état

GO utilisateur : tester **144 combinaisons LONG et 144 SHORT**, sur **2025** et
**2026 jusqu'au 30 septembre**, en conservant le **levier maximal ×2** des
backtests sur marge. Cela représente **576 simulations annuelles**. Ce ne sont
pas 576 échantillons indépendants et aucune combinaison n'est promue au live.

Dossier faisant foi :
`artifacts/research/us_intraday_protection_grid/20261021-v1`.

## Bilan du calcul terminé

**576/576 simulations terminées, aucun échec, en 22 min 20 s.** Les empreintes
sources/entrées et tous les fichiers scellés des simulations sont vérifiés.
Les 576 audits de sorties/cash passent, écart maximal de reconstruction
**1,82 × 10⁻¹¹ USD** ; marqueurs individuels identiques au rapport global.
`final-review.json` conserve cette vérification. Le statut
`COMPLETED_EXPLORATORY` ne certifie pas une parité live complète.

### Résultat d'ensemble

| Sens | Combinaisons positives 2025 / 144 | Positives 2026 / 144 | Positives les deux années / 144 | Rendement médian 2025 / 2026 |
| --- | ---: | ---: | ---: | ---: |
| LONG | 46 | 139 | 44 | −12,82 % / +21,33 % |
| SHORT | 0 | 0 | 0 | −32,09 % / −31,18 % |

Les plus hauts rendements annuels LONG ne correspondent pas exactement à la
même politique : SL7/trailing15/H15/sansTP en2025 (**+59,70 %**, DD33,31 %),
SL7/trailing15/H20/sansTP en2026 (**+71,76 %**, DD29,56 %). Ils sont sélectionnés
**après observation** de la grille, pas annoncés comme une prévision.

### Profil commun illustratif : LONG, SL7 / trailing15 / H20 / sansTP

Ce profil a le rendement moyen arithmétique le plus élevé des politiques LONG
sur les deux comptes annuels indépendants. C'est un critère descriptif **choisi
après le calcul**, pas un protocole préenregistré de sélection du champion.
Il sert à rendre les résultats lisibles, pas à promouvoir une combinaison.

| Mesure | 2025 | 2026 jusqu'au30septembre |
| --- | ---: | ---: |
| Capital initial indépendant | 4 000 USD | 4 000 USD |
| Capital final, après frais et financement | **6 229,38 USD** | **6 870,28 USD** |
| PnL net / rendement | +2 229,38 USD / **+55,73 %** | +2 870,28 USD / **+71,76 %** |
| DD maximal | **34,64 %** | **29,56 %** |
| Trades clos gagnants / perdants | 38 / 64 | 32 / 52 |
| Taux gagnant / perdant | **37,25 % / 62,75 %** | **38,10 % / 61,90 %** |
| Gain moyen par gagnant | +200,25 USD / +17,50 % | +234,66 USD / +20,52 % |
| Perte moyenne par perdant | −83,26 USD / −7,00 % | −88,32 USD / −6,45 % |
| Détention moyenne gagnants, séances | 15,45 | 15,03 |
| Détention moyenne perdants, séances | 5,25 | 5,19 |
| Détention moyenne gagnants, jours calendaires | 21,03 | 20,51 |
| Détention moyenne perdants, jours calendaires | 6,09 | 5,93 |
| Capital brut moyen engagé | **4 723,41 USD** | **5 061,03 USD** |
| Moyenne du ratio capital engagé / equity | **90,30 %** | **84,47 %** |
| Capital brut maximal engagé | 12 764,11 USD | 15 446,84 USD |
| Levier maximal observé | ×1,90 | ×1,83 |
| Temps régulier au-dessus de×1 | 43,28 % | 41,19 % |
| Débit cash moyen financé | 826,43 USD | 1 024,99 USD |
| Intérêts de financement annuels | 48,76 USD | 46,26 USD |
| Positions encore ouvertes à la fin | 7 | 0 |
| PnL non réalisé de ces positions, frais d'entrée inclus | −2,92 USD | 0 USD |

Le plafond ×2 est relatif à **l'equity courante**, pas à un plafond permanent
de8 000USD : si le compte monte, son pouvoir d'achat monte aussi. Le capital
maximal engagé n'arrive pas nécessairement au moment du levier maximal. Les
deux années repartent de4 000USD : ces montants ne sont pas un compte composé
2025→2026. La moyenne d'exposition comprend les barres à zéro position.

Le faible taux gagnant n'empêche pas un bénéfice dans cette simulation parce
que le gain moyen dépasse largement la perte moyenne. Cela n'établit pas un
avantage directionnel général ni un comportement fiable hors de cet échantillon.
Le financement est déduit de l'equity finale, pas attribué arbitrairement aux
trades pour calculer leurs taux gagnants.

### Sensibilité et limites de la conclusion

- Autre profil commun LONG, SL7/trailing20/H20/sansTP : **+56,96 % en2025** et
  **+64,25 % en2026**, DD **37,14 % / 33,79 %**. Son minimum annuel est le plus
  élevé de la grille LONG, mais c'est encore un classement rétrospectif ; son
  DD est supérieur au profil trailing15 sur les deux années.
- Référence SL5/trailing15/H20/sansTP, elle aussi avec×2 et comptes annuels
  indépendants : LONG **+9,71 % / +28,73 %**, DD **28,70 % / 27,57 %**. Les
  performances de l'ancien témoin continu sans levier ne doivent pas remplacer
  cette référence appariée à la nouvelle grille.
- Toutes les politiques LONG H5 sont perdantes en2025 : **−27,37 à−20,94 %**.
  En2026 elles sont toutes positives : **+0,31 à+30,55 %**. Un horizon court ne
  résout donc pas automatiquement le problème de direction.
- SHORT : même le meilleur résultat annuel reste négatif, **−3,96 % en2025** et
  **−15,10 % en2026**, avec deux politiques différentes. Il n'y a aucune
  combinaison SHORT à promouvoir sur ce test, même sous emprunt hypothétique.
- Les gains sont concentrés : pour le profil LONG illustratif, MP apporte
  **+1 257,25 USD** de PnL clos en2025 ; TTMI/MU/DOCN apportent respectivement
  **+882,92/+762,51/+629,48 USD** en2026. Ce constat de dépendance ne constitue
  pas un filtre de titres connu à l'avance.
- DD de30–35 %, nombreux trades perdants, 213campagnes seulement et sélection
  sur disponibilité complète des trajectoires : **résultat encourageant sous
  hypothèses, pas validation économique hors échantillon nouvelle ni GO live**.

Le fichier `annual-summary.csv` donne les **576 lignes** et toutes les mesures
demandées ; `report.json` contient les audits et fichiers individuels. Aucun
paramètre de production, modèle ou batch n'a été modifié après ces résultats.

Le protocole est écrit avant le calcul ; `prepared.json` scelle les entrées.
`progress.json` donne terminés/échecs/total et estimation restante ; chaque
simulation terminée possède son `done.json` et son audit. Une reprise vérifie
les empreintes et ignore uniquement les simulations terminées et intactes.
Les prototypes `benchmark-*` et `smoke-*` ne constituent pas la grille complète.

## Paramètres figés

| Paramètre | Valeurs |
| --- | --- |
| SL fixe | 3 %, 5 %, 7 % |
| Trailing | désactivé, 10 %, 15 %, 20 % |
| Échéance depuis le jour Oracle J | J+5, J+10, J+15, J+20 séances |
| TP fixe | désactivé, 10 %, 20 % |
| Sens | compte LONG seul / compte SHORT seul, séparés |

3 × 4 × 4 × 3 = 144 combinaisons par sens, identiques pour chaque année.
Pas de sélection des seuls titres dont le sens futur convient.

## Capital et levier : ce qui est réellement aligné

- **4 000 USD au début de chaque année**, comptes annuels indépendants : ni gains
  ni positions 2025 transférés au compte 2026.
- Compte sur marge, configuration de levier **explicitement activée à ×2** dans
  le moteur natif. 4 000 USD donnent initialement 8 000 USD de pouvoir d'achat,
  pas un rendement artificiellement multiplié par deux.
- Sous 2 000 USD d'equity, le mécanisme natif retire le levier ; les nouvelles
  entrées SHORT sont refusées. Cela ne certifie pas les conditions d'un courtier.
- Demi-position sans renforcement. Cible complète bornée à 50 % de l'equity et
  budget de risque SL de 4 %, puis moitié entière, soit au plus environ 25 %
  d'equity par entrée. Maximum huit positions, pas deux achats du même titre.
  Le budget restant, les frais, les prix et les refus peuvent réduire la taille.
  **Le levier ×2 est autorisé, pas imposé à chaque instant.**
- Exposition brute limitée à 200 % à l'admission ; la variation ultérieure des
  cours peut faire dépasser ce ratio. Le rapport distingue ce dépassement par
  dérive d'une autorisation de nouvelle entrée.
- Comme l'ancien backtest annuel ×2 : **financement supposé 6,5 %/an**, débit cash
  de fin de séance, **ACT/360 incluant les week-ends**, borné à la fin annuelle.
  Ce n'est pas une série historique des tarifs du courtier.
- SHORT : crédit de vente comptabilisé, dette de titres retranchée de l'equity ;
  le crédit ne devient pas du pouvoir d'achat gratuit. Disponibilité d'emprunt
  **supposée**, frais constants 0,3 %/an sur notionnel d'entrée et durée en
  séances/252. Charges des positions encore ouvertes provisionnées en fin d'année.
- Maintenance hypothétique observée à la clôture : LONG 100 % sous 2,5 USD,
  50 % jusqu'à 6 USD, 30 % au-dessus ; SHORT maximum de 2,5 USD/action sous
  5 USD, sinon maximum de 5 USD/action ou 30 % du notionnel. Violation : sortie
  à l'ouverture suivante, aucune nouvelle entrée cette séance. Pas de preuve
  des exigences historiques/HTB, appels de marge intraday ou rappels réels.

Les frais communs sont **8 bps par jambe** : demi-spread 5, commission 1,
slippage 2. Ils sont débités sur chaque notionnel exécuté, en plus des intérêts
et de l'emprunt SHORT. Pas de commission fixe ajoutée. Une grille de stress à
25 bps n'est pas incluse dans ces 576 simulations.

**Ce ne sont pas toutes les conditions identiques à l'ancien TOP5 quotidien** :
ici TOP10, confirmation intraday, demi-position, échéance J+H et cohorte commune.
Le levier et les conventions annuelles/financement sont alignés ; les stratégies
et les preuves disponibles restent différentes. Ce n'est pas une certification
de reproduction intégrale de l'exécution PAPER/live.

## Signaux, protections et données

Archives déjà scellées de l'expérience de campagnes puis de fidélité intraday :
**213 campagnes**, 119 en 2025 et 94 en 2026, 72 symboles. Oracle **CatBoost
PATH_H20 OOS de recherche**, TOP10 originel ; pas le LightGBM de production.
Toutes les campagnes retenues disposent des 21 séances de prix SIP5m qualifiées.
Cela exclut une partie importante du TOP10 originel et introduit un biais de
couverture future, outre le biais de survivants de l'univers actuel.

Pour chaque campagne : première nouvelle cassure de la borne de veille,
confirmée par deux clôtures5m terminées, entrée au prochain open contigu ; LONG
au-dessus du haut, SHORT sous le bas. Premier essai seulement, même s'il est
refusé. Pas de réentrée, remplacement par un rang inférieur ou renforcement.
Bloc d'admission parent de vingt séances identique pour tous les horizons.

L'attente avant entrée compte dans J+H. Une entrée à/après l'échéance n'est pas
prise. L'échéance est l'open de la dernière barre5m de J+H ; ce n'est ni H séances
depuis l'entrée ni une liquidation au close. À la fin annuelle, les positions
non échues restent valorisées, sans inventer une sortie gagnante/perdante.

Gap contre le stop connu : open réel. Gap favorable au TP : limite TP, pas open
avantageux. Stop prioritaire en cas de collision SL/TP dans la même barre.
Le haut/bas de la barre courante ne resserre le trailing qu'après sa clôture,
jamais rétroactivement dans cette barre. Stops connus/TP/échéances avant nouveaux
ordres ; ventes intrabar ne financent pas un achat antérieur dans la barre.

Le dimensionnement et les bookings réutilisent les composants natifs. L'ATR et
l'ADV viennent exclusivement de séances antérieures de l'archive quotidienne ;
les valeurs manquantes bloquent l'entrée concernée, sans chiffre fabriqué.
SL fixe : l'ATR ne sert pas à modifier la distance SL. Trackers natifs de
répétition/pertes conservés. Pas de secteur/régime/corrélation/circuit breaker
certifié ni flux complet d'opérations sur titres/dividendes ; ces absences ne
sont pas assimilées à des données neutres qualifiées.

## Résultats livrés et lecture

`annual-summary.partial.csv`, puis `annual-summary.csv`, une ligne par
combinaison et année. Détails dans `cases/<identifiant>/` : trades, marques5m,
positions ouvertes, décisions/refus, maintenance/intérêts, audit et résultat.

| Mesure | Définition |
| --- | --- |
| Capital final / rendement / PnL | Equity finale, gains réalisés et positions ouvertes valorisées, après frais et financement |
| DD Max | Plus grande baisse depuis un pic, en % positif, avec capital initial inclus ; marques5m et financement de clôture, pas pire valeur intratick |
| Taux gagnant | Trades clos à PnL net positif / tous trades clos ; positions ouvertes exclues et comptées séparément |
| Gain/perte moyen USD et % | Moyenne par trade gagnant/perdant clos, frais d'entrée/sortie et emprunt inclus ; financement de portefeuille présenté séparément, non attribué arbitrairement à un trade |
| Détention gagnants/perdants | Moyenne séparée en séances, séance d'entrée incluse, et en jours calendaires fractionnaires depuis l'open d'entrée |
| Capital moyen utilisé USD | Moyenne temporelle du notionnel brut réellement détenu aux closes5m de toutes les séances, y compris les périodes à zéro position |
| Capital moyen utilisé % | Moyenne du ratio notionnel brut / equity simultanée ; pas ratio de deux moyennes |
| Fonds propres mobilisés | Moyenne de min(notionnel brut, equity positive) |
| Excès de notionnel sur equity | Moyenne de max(notionnel brut − equity, 0), pas assimilé automatiquement au prêt cash |
| Débit cash moyen | Montant moyen réellement négatif du solde cash, pertinent pour le financement LONG |
| Utilisation maximale / levier observé | Notionnel brut maximal, ratio brut/equity maximal et % du temps régulier au-dessus de ×1 |
| Taille d'entrée moyenne | Notionnel moyen d'entrée des trades clos ; distinct du capital simultanément engagé |

L'exposition moyenne est pondérée par **temps de marché régulier5m**, pas par
jours calendaires/nuits. Les frais de financement, eux, incluent les nuits et
week-ends selon ACT/360. Les durées intrabar exactes sont inconnues : une sortie
intrabar est horodatée à la fin de sa barre, borne supérieure de cinq minutes.

## Contrôles et commandes

**98 tests passent** : 15 nouveaux et 83 de composants/non-régression. Contrôles
×2 réellement accessible, retrait sous minimum, cash SHORT, véritable exposition
>×1, financement week-end, index quotidien natif, collision et TP à l'échéance,
mesures de durée/DD/allocation. Quatre essais LONG/SHORT, 2025/2026, passent leur
reconstruction séparée des sorties et du cash avant le lancement complet.
Même assistant : pas revue humaine indépendante.

Chaque simulation complète est également auditée : sortie scalaire depuis les
barres, frais/emprunt, durées, cash, intérêt ACT/360, valeurs de toutes les
positions et equity de chaque marque5m. Une erreur donne FAILED, pas un zéro
de rendement. Dossier immuable et empreintes contrôlées avant/après le run.

```powershell
python -u -m scripts.research.us_intraday_protection_grid --output artifacts/research/us_intraday_protection_grid/20261021-v1 --workers 2
Get-Content artifacts/research/us_intraday_protection_grid/20261021-v1/progress.json
```

Pas d'entraînement, SQL, fournisseur, LLM, ordre, modification de batch ou
configuration de production. Classer les 288 politiques sur ces années déjà
observées reste exploratoire : le meilleur résultat n'est pas une combinaison
« optimale » prouvée ni une raison suffisante de la déployer.

## Comparaison suivante, séparée

GO pour rejouer la même grille sans levier dans `20261021-1x-v1`, sans modifier
les données/résultats/sources scellées du présent run. Cibles individuelles
inchangées, plafond global ramené à×1, quantités/refus/cash entièrement rejoués.
[Protocole ×1 et comparaison appariée](grille_intraday_sans_levier_20261021.md).
