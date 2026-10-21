# Pourquoi les SHORT de la dernière grille sont perdants

## Conclusion et périmètre

**La sélection SHORT n'a pas d'avantage directionnel démontré. Le problème
principal n'est pas le financement, ni une erreur de signe identifiée.**
L'Oracle PATH_H20 classe l'amplitude maximale, hausse OU baisse ; il ne prédit
pas que les titres classés vont descendre. La première cassure baissière de deux
clôtures 5m n'a pas suffi à transformer cette sélection en stratégie SHORT.
Les rebonds et les gaps aggravent cette faiblesse.

Attribution terminée le 21 octobre, sans nouveau backtest, modèle, collecte,
appel LLM, écriture SQL, ordre ni changement de paramètres/univers.

Sources locales : les quatre grilles scellées ×2, ×1, ×1+B4/DD20 et ×1+B4/DD15
sous `artifacts/research/us_intraday_protection_grid/`. Les empreintes des
rapports, barres, candidats et régimes ont été vérifiées. Les PnL des **288
comptes SHORT DD15** ont été reconstruits indépendamment à partir des prix,
quantités, frais et emprunts ; erreur maximale inférieure à 9e-12 USD.

Ces grilles portent sur **213 campagnes Oracle / 72 titres**, 2025 et 2026
jusqu'au 30 septembre, cohorte conditionnelle sur la couverture future, pas
tout l'univers ni tout le TOP10 historique. Le modèle est le CatBoost PATH_H20
de recherche. Les 144 politiques sont corrélées, pas 144 essais indépendants.
L'ancien H inclut l'attente depuis le signal Oracle : **ce n'est pas un test
du nouveau watcher à vingt séances après première entrée**, raccordé ensuite.

## 1. Le constat persiste avec différents niveaux de levier et de protection

Rendement médian / meilleur des 144 profils SHORT, pour chaque année :

| Variante | 2025 | 2026 au 30/09 |
| --- | ---: | ---: |
| ×2, sans B4 | −32,09 % / −3,96 % | −31,18 % / −15,10 % |
| ×1, sans B4 | −29,10 % / −3,62 % | −30,14 % / −14,69 % |
| ×1, B4 DD20 | −24,13 % / −3,62 % | −24,57 % / −18,90 % |
| ×1, B4 DD15 | −21,31 % / −3,62 % | −21,52 % / −16,17 % |

**Zéro profil SHORT net positif dans chaque groupe année/variante.** Le risque
peut réduire les pertes sans créer un signal rentable. Cela n'établit pas que
toute stratégie SHORT serait impossible : seulement que ces règles n'ont pas
fonctionné sur cette cohorte.

## 2. Trop peu de gagnants pour le rapport gain/perte observé

Référence déjà suivie, non choisie comme meilleur profil après observation :
SHORT SL7 / trailing15 / H20 / sans TP, ×1 et B4 DD15, 4 000 USD par année.

| Mesure | 2025 | 2026 au 30/09 |
| --- | ---: | ---: |
| Rendement / capital final | −24,72 % / 3 011,37 USD | −25,61 % / 2 975,41 USD |
| Trades clos gagnants / perdants | 26 / 68 | 12 / 49 |
| Taux gagnant | 27,66 % | 19,67 % |
| Gain moyen d'un gagnant | +67,87 USD | +60,88 USD |
| Perte moyenne d'un perdant | −40,87 USD | −35,82 USD |
| Gain moyen / perte moyenne absolue | 1,66 | 1,70 |
| Taux d'équilibre avec CES moyennes observées | 37,59 % | 37,04 % |
| Durée moyenne gagnant / perdant, séances | 12,81 / 4,85 | 10,17 / 3,84 |

Formule descriptive : perte moyenne absolue / (gain moyen + perte moyenne
absolue). Ce n'est pas une prévision de probabilité ; ces moyennes dépendent
aussi des tailles et de la séquence des trades.

Le LONG du même profil DD15 gagne malgré seulement 37,00 % / 34,25 % de trades
gagnants : son rapport gain/perte atteint 2,30 / 2,53. Copier les paramètres
LONG vers SHORT ne conserve donc pas son espérance. Les deux sens entrent
sur des confirmations distinctes, pas au même instant avec signes inversés.

## 3. Les coûts ne suffisent pas à expliquer les pertes

Décomposition comptable du même profil SHORT, aux transactions/tailles figées :

| Composante USD | 2025 | 2026 |
| --- | ---: | ---: |
| PnL prix, positions ouvertes incluses | −903,42 | −970,01 |
| Frais de transaction | −81,66 | −52,92 |
| Emprunt de titres simulé | −3,56 | −1,66 |
| Financement cash | 0,00 | 0,00 |
| PnL net / MTM | −988,63 | −1 024,59 |

La majorité de la perte existe donc avant frais. Dans les 144 profils DD15 :
seulement trois sont légèrement positifs avant coûts en 2025, meilleur PnL
prix +16,80 USD, soit +0,42 % du capital initial ; aucun en 2026, meilleur
PnL prix −569,86 USD. Retirer les coûts ne révèle pas un avantage robuste.

Ce retrait est une **attribution aux mêmes transactions**, pas une simulation
zéro frais : cash, tailles, admissions et état B4 changeraient dans un nouveau
rejeu. L'emprunt est supposé disponible, tarif constant 0,3 % annualisé /252 ;
les vrais frais, locates et rappels historiques ne sont pas qualifiés.

## 4. Les gaps rendent le SL non garanti — exemples concrets

| Titre | Entrée SHORT | Rachat après gap | Perte nette de la position |
| --- | --- | --- | ---: |
| APP | 11/02/2025, 370,68 USD | 13/02, 499,43 USD | −34,92 %, −258,91 USD |
| MP | 01/07/2025, 31,92 USD | 10/07, 48,10 USD | −50,90 %, −227,45 USD |

Les prix et PnL ci-dessus viennent des archives du backtest, pas d'une nouvelle
validation de prix par une place boursière. Le simulateur rachète au prix
d'ouverture observé lorsqu'il dépasse le stop, pas à un SL7 fictivement garanti.

Deux événements émetteurs corroborent le contexte temporel, sans constituer
à eux seuls une preuve de causalité de tout le gap :

- APP : résultats du 12 février après clôture ; ce rendez-vous avait déjà été
  annoncé le **8 janvier**, donc avant l'entrée du 11 février.
  [Annonce officielle préalable](https://investors.applovin.com/news/news-details/2025/AppLovin-to-Announce-Fourth-Quarter-and-Full-Year-2024-Results/default.aspx),
  [publication des résultats](https://investors.applovin.com/news/news-details/2025/AppLovin-Announces-Fourth-Quarter-and-Full-Year-2024-Financial-Results/default.aspx?code=c10cTynra).
- MP : partenariat avec le Department of Defense annoncé le 10 juillet,
  conférence à 8 h 30 ET, avant l'ouverture. Ne pas prétendre que notre système
  pouvait connaître cette annonce au moment de l'entrée du 1er juillet.
  [Communiqué officiel](https://investors.mpmaterials.com/investor-news/news-details/2025/MP-Materials-Announces-Transformational-Public-Private-Partnership-with-the-Department-of-Defense-to-Accelerate-U-S--Rare-Earth-Magnet-Independence/default.aspx).

Ces deux trades représentent −486,36 USD, environ 49 % de la perte nette 2025.
Les autres trades clos restent néanmoins à −528,47 USD : pas uniquement deux
accidents. En 2026, les deux pires représentent −190,57 USD ; les autres clos
perdent encore −834,02 USD. Contributions nettes par symbole négatives pour
31/44 titres tradés clos en 2025 et 24/29 en 2026. APP est négatif en 2025 mais
positif en 2026 sur ce profil : une blacklist de titres choisie après pertes
n'est pas une solution validée.

## 5. Fausses confirmations, excursions et régime

Sur les signaux SHORT candidats arrivés à maturité avant la borne annuelle,
le cours monte encore en moyenne de **4,61 % en 2025** et **5,79 % en 2026**
entre entrée théorique et échéance de campagne. Les directions terminales
favorables au SHORT ne sont que 41,51 % / 46,81 %. Ce n'est pas le rendement
du portefeuille : tous les signaux ne sont pas exécutés. Onze signaux SHORT
2025 censurés par la fin d'année sont exclus de ces statistiques terminales.

Même sur les seuls trades réellement exécutés du profil de référence et
arrivés à maturité, la direction terminale favorable atteint 43,48 % / 44,26 %,
mais le taux de gagnants avec protections tombe à 27,66 % / 19,67 % sur les
trades clos. Les dénominateurs terminaux excluent deux cas 2025 censurés.
Le parcours et la chronologie comptent : un prix peut finir plus bas après
avoir déjà invalidé le SHORT. Cela ne justifie pas de supprimer le stop.

44,12 % / 65,31 % des perdants SHORT ont également présenté un profit confirmé
d'au moins +3 % avant leur sortie ; seulement 33,82 % / 36,73 % ont présenté
+5 %. Le problème combine donc entrées sans suivi baissier et restitutions
de gains. Ces excursions sont rétrospectives, bornées aux barres STRICTEMENT
antérieures à la barre de sortie plus le fill réel ; aucun ordre de contacts
à l'intérieur de la barre de sortie n'est inventé. Un TP plus court ne peut
pas être promu rentable à partir de ces seuls pourcentages.

Le contexte global n'est pas une explication suffisante. Sur le régime SPY
SMA50/200 **SLIDE**, le même profil perd −372,34 USD sur 19 trades clos 2025
et −159,69 USD sur six trades 2026. BULL pèse davantage en nombre et en pertes,
mais filtrer uniquement BULL après observation n'est pas une preuve prédictive.
Ne pas confondre ces régimes SPY avec une tape macro complète VIX/MOVE/etc.

## Suite raisonnable, non exécutée ici

1. Ne pas élargir le SL ni rechercher simplement un autre optimum de grille.
2. Si une nouvelle expérience SHORT est autorisée : calendrier de résultats
   connu avant décision, règles de détention autour des annonces et gestion
   séparée du risque overnight ; témoin sans filtre, règles figées avant test.
   La confirmation APP montre un cas évitable en principe, pas une rentabilité
   globale démontrée ni l'existence d'un reçu PIT dans notre application.
3. Exiger une hypothèse directionnelle SHORT distincte, pas l'inversion
   mécanique du LONG. Valider sur d'autres périodes sans supprimer après coup
   les titres qui ont perdu. Aucune nouvelle expérience lancée dans cet audit.

## Reproduction

Rapport faisant foi :
`artifacts/research/us_short_loss_audit/20261021-v2/report.json` et
`reference-trade-attribution.parquet`. V1 conservée, remplacée pour les
diagnostics terminaux par V2 qui explicite la censure annuelle.

```powershell
python -u -m scripts.research.us_short_loss_attribution --output artifacts/research/us_short_loss_audit/NOUVEAU-DOSSIER
```

Trois tests unitaires passent (signe LONG/SHORT, frais/emprunt, intégrité,
absence de prix futur à l'intérieur de la barre de sortie) :
`artifacts/tmp/short-loss-attribution-20261021.xml`. Les identités comptables
indépendantes passent pour les 288 comptes SHORT DD15. Même assistant,
pas une seconde revue humaine indépendante ni une certification live.
