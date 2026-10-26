# P04 — Dual Thrust depuis l'ouverture : protocole figé

Préenregistré le22octobre2026 avant les nouveaux résultats économiques.
Répertoire neuf : `artifacts/research/us_oracle_dual_thrust_p04/20261022-v1`.

## Question et périmètre

Un seuil de mouvement **depuis l'ouverture**, calibré sur quatre séances passées,
sélectionne-t-il mieux l'entrée des candidats Oracle que les cassures déjà testées ?
Sources FMZ258/260, Dual-Thrust-OKCoin et Dual-Thrust-OKEX au commit
`7853bb2bf262c4567ac238d3552d97f0e50cb801`. Adaptation propre : ne pas exécuter
les bots crypto ni reprendre leurs inversions sans stop dur.

Premier test **LONG économique seulement**. Le seuil bas fournit une décision
d'abstention et un contrôle de timing, **pas un SHORT dont l'emprunt serait qualifié**.
Aucun modèle, paramètre de production, SQL, fournisseur, LLM, entraînement ou ordre.
Archives locales seulement ; ne pas toucher aux téléchargements en cours.

## Formule et causalité

Pour un Oracle connu après J, les quatre séances NYSE régulières complètes
terminées à J fournissent les daily agrégés depuis les **raw5m SIP** : haut=maxhigh,
bas=minlow, clôture=dernierclose5m régulier. Cette clôture n'est pas revendiquée
comme le prix officiel d'enchère de clôture. Aucun daily ajusté mélangé aux raw.

`R = round(max(max(H)-min(C), max(C)-min(L)),8)`.
À l'open réel de **J+1 seulement**, figer `U=round(open+0,5R,8)` et
`D=round(open−0,5R,8)`. Exiger `R>0` et `0<D<open<U`. Arrondi scalaire Python,
pas arrondi vectoriel à demi-cent. Pas d'actualisation avec les H/L/C de J+1.
Un gap par rapport à J ne déclenche donc pas automatiquement P04.

Pendant J+1, chercher la **première clôture5m** strictement >U ou <D :

- UP en premier : P04LONG à l'open contigu suivant, dans la même séance.
- DOWN en premier : P04 reste en cash pour cette occasion, même si U est
  cassé ensuite. Une tentative ; pas d'inversion ni de réessai le lendemain.
- Égalité au seuil : pas un franchissement. Toucher seulement high/low : pas
  un signal. Si la première clôture franchissante est la dernière bougie de
  séance, pas de fill fictif à la clôture ou au lendemain.

Le sens est décidé à la clôture de la bougie, jamais depuis l'ordre high/low
inconnu à l'intérieur d'une bougie. Le prix d'entrée est l'open observé suivant,
pas le seuil garanti. Le garde-fou natif signal/fill3 % reste appliqué au
portefeuille ; aucun filtre de prix futur supplémentaire pour améliorer le test.

## Témoins et protection inchangée

Six bras ×2025/2026 ×8/25bps parjambe = **24portefeuilles** :

1. WINNER : ancienne ancre P01-v2/200campagnes, quatre replays reproduits à
   l'octet près pour trades, valorisations, décisions, maintenance et B4.
2. COMMON_WINNER : règle Winner actuelle sur la nouvelle population commune,
   première cassure fraîche confirmée par deux clôtures du haut précédent,
   pendant vingt séances après Oracle. Contrôle du changement de fenêtre.
3. J1_WINNER : même règle de deux clôtures, mais J+1 seulement. Distingue
   le changement de fenêtre de l'effet du seuil Dual Thrust.
4. HIGH_J : première clôture5m >haut de J pendant J+1, open suivant. Même
   confirmation simple que P04 ; pas condition supplémentaire de cross frais.
5. TIME_LONG : au premier franchissement UP **ou DOWN** du Dual Thrust,
   acheter toujours en LONG au même open. Sur UP, entrée identique P04 ; sur
   DOWN, mesure ce que P04 abandonne. Pas d'attente choisie depuis le futur.
6. P04 : LONG seulement au premier UP, abstention au premier DOWN.

Pas de grille N/k, compression, retest, EMA/ADX, filtre de volume, vente partielle
ou renforcement ajoutés. SL7/TR15/sansTP, vingt séances **depuis l'entrée**,
entrée incluse, vente à l'open21. Protections/gaps/risque prioritaires identiques.
Capital annuel réinitialisé4 000USD, plafond d'admission1×, demi-cible, quantités
entières, composants natifs sizing/contraintes/frais et B4DD15 figés. Les formules
sont identiques, les cash/quantités/admissions réels peuvent diverger avec les sorties.

## Population et couverture

Les213campagnes CatBoost PATH_H20 de recherche héritées ne représentent pas
tout le TOP10 quotidien ni le LightGBM de production. Elles sont déjà conditionnelles
à d'anciens signaux/chemins futurs complets/survivants. Les archives préliminaires
couvrent quatre séances antérieures et J1 pour112/213occasions ; pas de lecture des
rendements pour choisir les paramètres. Les absences sont réservées identiquement.

Manque dans le lookback4/J1, dans le scan Winner ou dans un chemin futur émis
jusqu'à l'open21 : réserver toute l'occasion des cinq bras communs, même si le
futur stop aurait eu lieu avant le manque. Aucun remplissage, aucune conversion
silencieuse de daily ajustés en raw. Les non-signaux restent des occasions à zéro.
Les opérations connues du lookback, de J1 et de la détention sont réservées,
mais la table d'événements héritée est vide/incomplète : pas preuve d'absence
d'événement ni qualification exhaustive d'identité. Le risque continue à utiliser
les mêmes archives daily ATR/ADV que les autres expériences.

NYSE réel, jours fériés et clôtures anticipées ; pas de continuation overnight
du signal P04. Pas de simulation2024, absente de l'archive intraday figée.
2025/2026au30septembre déjà étudiées, pas un holdout neuf. Nouveau filtre de
couverture future : biais explicite, pas un signal de trading disponible à J.

## Confirmation et audit

Comparer rendements nets/DD/capital engagé, gagnants/perdants/détention,
abstentions, couverture, timing et concentration. Unités appariées par occasion,
cash zéro pour les absences, sensibilité sans chevauchement par symbole jusqu'à
OracleJ40, bootstrap mensuel Oracle2 000tirages,graine731.

Pour poursuivre : au moins30signaux P04 non chevauchants et10titres par an,
rendement P04 positif dans les deux années aux deux coûts, surplus portefeuille
positif contre **chacun des quatre témoins communs**, DD non aggravé à8bps,
surplus unitaire positif à25bps et borne basse95 % mensuelle >0 contre chacun,
au moins6mois. Sinon non-confirmation ou échantillon insuffisant. Ne jamais
assouplir N, k, fenêtre ou critères après les résultats.

Sélecteur/range/premierhit indépendants en code, puis contrôle des unités et
cash/sorties/B4, sources et archives empreintées. Même assistant, **pas revue
humaine indépendante**. NBBO/latence/queue/fills, secteurs et PIT/identités
non entièrement qualifiés : pas de parité live complète. B4DD15 ne garantit
pas que le drawdown ne dépasse jamais15 %.

```powershell
python -u -m scripts.research.us_oracle_dual_thrust_p04 --phase run
python -u -m scripts.research.us_oracle_dual_thrust_p04_audit
```

Sources/tests/présent protocole figés avant calcul ; dossier neuf pour toute
correction technique, jamais réécriture d'un run scellé.
