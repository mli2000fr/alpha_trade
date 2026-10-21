# Univers tradable : TP10/SL10 et TP10 sans SL

Complément demandé ensuite : [TOP20 % Oracle contre univers complet](oracle_top20pct_et_univers_complet_tp10_20261019.md).
Le contrôle TOP10 de ce document n'est pas le TOP20 % ; les deux périmètres sont
explicitement séparés dans le complément.

## Conclusion

**DEUX TESTS TERMINÉS, EXPLORATOIRES, RÉSERVE PRIX MAINTENUE.** Même fichier de
1 790 titres que le test TP20/SL7, sans restriction Oracle dans le test principal.

En LONG, les moyennes par occasion sont positives pour les deux variantes :

- TP10/SL10 : **+0,30 % en 2025, +0,28 % en 2026** ;
- TP10 sans SL : **+0,87 %, +0,92 %**, avec davantage d'occasions gagnantes mais
  des pertes et parcours contraires plus importants.

Les SHORT sélectionnés restent négatifs. Mélanger les deux sens selon leur
fiabilité historique donne encore des moyennes négatives dans les deux années.
Le filtre de titres n'a pas d'avantage robuste confirmé contre la règle
correspondante « tous LONG » ; **pas de nouvel univers de production**.

Ces moyennes ne sont **ni un rendement annuel de capital ni un PnL de portefeuille**.
Aucun modèle entraîné/modifié, aucune donnée SQL écrite et aucun ordre passé.

## Interprétation des deux demandes

1. **TP10/SL10** : LONG +10 % avant −10 %, SHORT −10 % avant +10 %.
2. **Juste TP10** signifie ici **sans stop-loss**, pas sans limite de durée :
   TP +10 % LONG ou −10 % SHORT ; à défaut, sortie à la clôture de la vingtième
   séance **incluant la séance d'entrée**.

Pour les deux : entrée open J+1, pas de trailing, TP exécuté à sa limite,
stop au prix d'ouverture si gap au-delà du seuil, collision OHLC conservatrice
stop-first sauf si l'ouverture de séance résout l'ordre. Sans SL, aucune sortie
de protection n'est inventée et aucune perte n'est plafonnée.

Le scénario sans SL n'a **pas** de vrai moteur de marge/liquidation forcée :
en SHORT une perte peut dépasser le montant d'entrée. Ce n'est pas une politique
d'exécution live autorisée ou validée.

## Protocole et populations figées

- Source : `artifacts/research/us_tradable_symbol_reliability/20261019-v1/`.
- Fichier : `config/univers_batch/univers_filtred_tradable.txt`, 1 790 symboles,
  même empreinte et mêmes exclusions de qualité que la référence.
- 1 192 036 fenêtres qualifiées date/titre, chacune LONG et SHORT pour chaque
  variante. **La population ne change pas avec le résultat du nouveau TP/SL.**
- 2024 historique initial, test en 2025–2026 ; 2026 mature jusqu'au 1er septembre,
  observation jusqu'au 30 septembre.
- Même règle mensuelle de confiance : 504 séances passées, minimum huit fenêtres
  sans chevauchement par titre/sens, Wilson90 au-dessus de la référence globale
  passée du même sens, moyenne nette positive/supérieure au global, stabilité
  des deux moitiés historiques. Maturité intégrale avant sélection, même si TP
  ou SL avait été touché rapidement.
- Chaque variante **recalcule ses propres labels et adhésions** : un titre
  historiquement bon en TP20/SL7 ne l'est pas nécessairement en TP10 sans SL.
- Contrôle supplémentaire : ancienne sélection TP20/SL7 conservée à l'identique,
  seule la protection change, pour distinguer effet des sorties et re-sélection.
- En cas de qualification des deux sens : abstention dans le bras combiné.

Coûts hypothétiques inchangés : commission 1 bp + demi-spread 5 bp + slippage
2 bp **par jambe** ; frais de sortie proportionnels au prix de sortie. Emprunt
SHORT supposé 0,3 %/an, `(séance de sortie−1)/252` du montant d'entrée.
Pas de locates/rappels/dividendes/marge réels certifiés.

## Résultats principaux : titres retenus pour chaque sens

« Occasion gagnante » signifie résultat positif après les coûts hypothétiques,
y compris une expiration positive sans TP. Ce n'est donc pas uniquement le
taux d'atteinte du TP.

| Variante | Année | Sens | Occasions | Titres | Occasions gagnantes | Moyenne nette par occasion |
|---|---|---|---:|---:|---:|---:|
| TP10/SL10 | 2025 | LONG | 22 614 | 198 | 52,56 % | **+0,30 %** |
| TP10/SL10 | 2026 | LONG | 19 883 | 393 | 53,01 % | **+0,28 %** |
| TP10/SL10 | 2025 | SHORT | 35 075 | 275 | 44,66 % | −1,33 % |
| TP10/SL10 | 2026 | SHORT | 14 202 | 311 | 43,91 % | −1,69 % |
| TP10 sans SL | 2025 | LONG | 32 377 | 246 | 58,89 % | **+0,87 %** |
| TP10 sans SL | 2026 | LONG | 22 153 | 369 | 61,18 % | **+0,92 %** |
| TP10 sans SL | 2025 | SHORT | 35 648 | 294 | 50,89 % | −1,91 % |
| TP10 sans SL | 2026 | SHORT | 15 213 | 297 | 53,57 % | −2,22 % |

La simple sélection du sens historiquement qualifié reste négative :

| Variante | Année | Occasions retenues | Gagnantes | Moyenne nette |
|---|---|---:|---:|---:|
| TP10/SL10 | 2025 | 57 689 | 47,75 % | −0,69 % |
| TP10/SL10 | 2026 | 34 085 | 49,22 % | −0,54 % |
| TP10 sans SL | 2025 | 65 111 | 54,56 % | −0,60 % |
| TP10 sans SL | 2026 | 36 096 | 58,14 % | −0,28 % |

## Le filtre apporte-t-il plus que « tous LONG » ?

Mêmes prix et mêmes protections, mais sans sélection de titres :

| Variante | Année | Tous LONG, moyenne nette | LONG sélectionnés, moyenne nette |
|---|---|---:|---:|
| TP10/SL10 | 2025 | +0,25 % | +0,30 % |
| TP10/SL10 | 2026 | +0,30 % | +0,28 % |
| TP10 sans SL | 2025 | +0,52 % | +0,87 % |
| TP10 sans SL | 2026 | +0,50 % | +0,92 % |

Les comparaisons appariées par date et leurs intervalles par blocs de vingt
séances sont dans les rapports. **Pour les deux variantes, les intervalles
du supplément moyen net LONG incluent zéro dans les deux années.** Ils sont
descriptifs, non corrigés de toutes les sélections multiples.

Le contrôle par période montre aussi une dégradation : LONG sélectionnés au
second semestre 2026, **−0,93 % par occasion en TP10/SL10, −0,30 % sans SL**,
contre respectivement +0,71 % / +1,31 % au premier semestre. Aucun gain stable
par régime n'est démontré par ces deux simples règles.

### Fenêtres sans chevauchement par titre/sens

| Variante | Année | LONG : fenêtres | LONG : gagnantes | LONG : moyenne nette | Bras combiné : moyenne nette |
|---|---|---:|---:|---:|---:|
| TP10/SL10 | 2025 | 1 311 | 53,93 % | +0,63 % | −0,85 % |
| TP10/SL10 | 2026 | 1 432 | 51,12 % | +0,12 % | −0,90 % |
| TP10 sans SL | 2025 | 1 829 | 60,80 % | +1,52 % | −0,28 % |
| TP10 sans SL | 2026 | 1 487 | 59,31 % | +0,90 % | −0,76 % |

Pas d'indépendance statistique garantie entre sociétés/secteurs ou régimes.
Le point de départ des fenêtres est chronologique, pas optimisé sur les gains.

## Risque du scénario sans SL

Sur les LONG sélectionnés sans SL, le gain moyen des occasions gagnantes est
**+8,36 / +8,77 %** en 2025/2026, contre une perte moyenne des perdantes de
**−9,85 / −11,47 %**. Pour les SHORT sans SL, les pertes moyennes atteignent
**−12,26 / −14,71 %**, contre des gains moyens de +8,07 / +8,60 %. Cela explique
qu'un taux de réussite supérieur à 50 % puisse rester perdant.

Sans SL, **33,41 % / 38,52 %** des LONG retenus ont déjà dépassé 10 % de mouvement
contraire **avant la barre de sortie**. Le quantile 95 % du mouvement contraire
jusqu'à la barre de sortie est d'environ **25,60 / 27,08 %**. Ce sont des
descriptions de parcours, **pas un drawdown de portefeuille** ni une mesure
intraday exacte : pour une sortie intraday TP, le haut/bas de cette dernière
barre peut se situer après la vente. Les rapports donnent bornes basse/haute ;
une sortie à l'open est traitée sans utiliser le bas/haut ultérieur.

La réserve source sur prix/OST reste entière, particulièrement pour les pires
pertes. Aucun plancher, plafonnement ou ajustement opportuniste n'est appliqué.

## Contrôle : garder l'ancienne sélection TP20/SL7

Même couples date/titre/sens que la référence, seule la sortie change :

| Variante de sortie | 2025 LONG, moyenne nette | 2026 LONG, moyenne nette | Combiné 2025 | Combiné 2026 |
|---|---:|---:|---:|---:|
| Référence TP20/SL7 | +1,01 % | −0,04 % | −0,33 % | −0,58 % |
| TP10/SL10 | +0,52 % | −0,02 % | −0,56 % | −0,61 % |
| TP10 sans SL | +1,07 % | +0,86 % | −0,53 % | −0,24 % |

Les nombres d'occasions sont inchangés par construction : LONG 14 579/15 618,
combiné 26 093/24 276. Ce contrôle n'est pas une qualification de ces anciennes
adhésions pour la nouvelle cible, mais isole l'effet des protections.

## Résultat secondaire : croisement avec le TOP10 Oracle

Les adhésions sont toujours apprises sur tout le fichier, puis croisées avec
le TOP10 original, sans remplacement hors des dix rangs.

| Variante | Année | LONG retenus dans TOP10 | Gagnantes | Moyenne nette par occasion |
|---|---|---:|---:|---:|
| TP10/SL10 | 2025 | 450 | 51,33 % | −0,12 % |
| TP10/SL10 | 2026 | 555 | 55,68 % | +0,76 % |
| TP10 sans SL | 2025 | 454 | 73,57 % | **+3,42 %** |
| TP10 sans SL | 2026 | 661 | 80,94 % | **+4,50 %** |

Ce dernier résultat mérite d'être conservé, **pas présenté comme une preuve
de prévision directionnelle**. Tous les TOP10 pris LONG sans filtre de confiance
et avec TP10 sans SL donnent déjà +2,76 / +2,33 % par occasion. Sans chevauchement,
les LONG filtrés donnent +2,34 / +2,41 % sur 49/74 fenêtres, contre +3,18 /
+2,57 % pour tous les TOP10 LONG sur 257/197 fenêtres. Populations/dates
différentes ; cela ne prouve pas un supplément robuste du filtre.

Le contrôle apparié du filtre sans SL est favorable en 2026 mais incertain en
2025 ; années déjà observées et sélections multiples restent des réserves.
Sur le sous-ensemble filtré 2026, les perdantes perdent en moyenne **17,64 %**
et le mouvement contraire au quantile 95 % de la barre de sortie est **33,13 %**.
Pas de capital final, levier, dimensionnement ou perte simultanée de portefeuille
calculé ici ; les chiffres ne suffisent pas à autoriser le scénario live sans SL.

## Qualité, précision numérique et réserves

- Sources figées et héritage du contrôle prix/OST du test complet : KLAC et
  d'autres ruptures d'échelle restent à qualifier, aucune correction SQL.
- Univers tradable actuel survivant, pas reconstitution historique exhaustive
  des titres actifs/radiés ; données EODHD rétrospectivement split-adjusted.
- Sans SL, une grande perte SHORT peut excéder le montant d'entrée ; pas de
  moteur certifié de marge/locates, ni courtier historique reproduit.
- 2025/2026 déjà examinées : ce n'est pas un nouveau holdout indépendant.
- Correction de précision propre à ce script : `100 × 1.1` peut valoir
  `110.00000000000001`. Les touches exactes à ±10 % utilisent une tolérance
  relative **1e−12**, sans déplacer un seuil économiquement significatif.
  Les cinq tests supplémentaires couvrent TP/SL exacts, LONG/SHORT et sans SL.
- `20261019-v1` est conservé pour traçabilité mais **supplanté par v2** après
  ce correctif ; seuls les chiffres v2 ci-dessus font référence. Aucun seuil
  du filtre historique n'a été réajusté sur les résultats.

## Livrables et reproduction

Résultat final : `artifacts/research/us_tradable_tp10_variants/20261019-v2/`.

- `protocol.json`, `paths-manifest.json` : profils, hypothèses et empreintes.
- `TP10_SL10/`, `TP10_NO_SL/` : parties par titre, résultats, listes mensuelles,
  évaluations, réserves prix et rapports de risque.
- Par profil : `primary.json`, `secondary_top10.json`, `frozen_old_membership.json`.
- `secondary-risk-audit.json` : risque du sous-ensemble TOP10.
- Racine : `report.json`, `comparison.csv`, `final-audit.json`, `progress.json`.

Script : `scripts/research/us_tradable_tp10_variants.py`.
**50 tests passent**, dont reproduction du contrat TP20/SL7, récupération après
un mouvement adverse sans SL, expiration sans TP, gap au-delà du SL, priorité
de l'ouverture et touches exactes. Pour chaque profil, 1 790 parties et huit
livrables vérifiés ; 1 482 068 lignes de test, mêmes clés et même signe final
H20 que la référence. Maturité avant chaque sélection et effectifs du témoin
figé contrôlés.

```powershell
python -u -m scripts.research.us_tradable_tp10_variants --phase prepare --output artifacts/research/us_tradable_tp10_variants/NOUVEAU_DOSSIER
python -u -m scripts.research.us_tradable_tp10_variants --phase build --output artifacts/research/us_tradable_tp10_variants/NOUVEAU_DOSSIER
python -u -m scripts.research.us_tradable_tp10_variants --phase run --output artifacts/research/us_tradable_tp10_variants/NOUVEAU_DOSSIER
```

Pas d'API, GPT/DeepSeek, SQL, entraînement, ordre ou changement de production.
Registre des expériences mis à jour ; aucune combinaison déclarée championne.
