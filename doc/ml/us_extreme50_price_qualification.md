# Qualification des très grands mouvements US avant rejeu économique

Date de revue : 6 octobre 2026. **Qualification partielle terminée ; aucun
rejeu économique lancé, aucune modification des prix, labels ou modèles.**

## Périmètre et conclusion

Suite de l'[audit de capture ≥50 %](us_extreme50_capture.md), batch Oracle H20
`model-factory-20261003082853-e98332`, univers actuel
`config/univers/univers_filtred_tradable.txt`, 2020–2026. Les 100 plus grands
chemins archivés couvrent 19 titres. Ils ne constituent ni un échantillon
aléatoire, ni toutes les opérations futures d'un portefeuille concentré.

Il existe **au moins une contamination de rendement par un ajustement de
split insuffisant** : INDV en octobre 2022. Mais il serait incorrect d'en
déduire que les mouvements de plusieurs centaines de pour cent sont tous
faux. Certains prix sont corroborés ponctuellement par la SEC, certains
événements correspondent à des annonces officielles, et des différences
d'échelle de prix ne changent pas nécessairement les rendements.

Les contrôles automatiques réservent quatre chemins de cet échantillon :
trois INDV et un GRND. Les 96 autres ont seulement le statut
`NO_LOCAL_BLOCKER_IN_SAMPLE_NOT_CERTIFIED` : **absence de blocage local
détecté n'est pas certification indépendante du chemin entier**.

## Méthode et artefacts reproductibles

Script : `scripts/research/us_extreme50_price_qualification.py`.
Il ne se connecte pas à la base ; il lit l'audit archivé. Six appels
bornés ont également récupéré prix/splits EODHD pour trois titres.
Ce sont des données du **même fournisseur**, pas une source indépendante.

Résultats retenus :
`artifacts/research/us_extreme50_capture/price-qualification-20261006-v2/`.

- `path_qualification.json` : les 100 chemins, sauts quotidiens ≥50 %,
  réserves et points indépendamment corroborés ;
- `INDV_eod.json`, `INDV_splits.json`, idem KNTK et REPX : réponses fournisseur ;
- `vendor_path_comparison.json` : rendements locaux, bruts et ajustés EODHD ;
- `sensitivity.parquet` : résultats par année, politique, seuil et signe ;
- `sensitivity_summary.json` : agrégation ≥50 % et ≥100 % ;
- `report.json` : périmètre, empreintes, réserves, état de récupération.

L'essai v1 de rafraîchissement a échoué sur la validation des certificats TLS.
Le v2 utilise les certificats de confiance du système, sans désactiver TLS,
sans modifier la configuration applicative et avec compteur de quota local.
Les six réponses ont été reçues. La copie des certificats n'est pas une
preuve de marché. Les sources publiques ci-dessous ont été consultées le
6 octobre 2026 ; seuls leurs faits utiles sont synthétisés ici.

Relance hors réseau, sans SQL :

```powershell
python -m scripts.research.us_extreme50_price_qualification --output artifacts/research/us_extreme50_capture/price-qualification-20261006-v2
```

Ajouter `--refresh-provider` demande à nouveau les six réponses ; aucun import
en base n'est effectué. Conserver le dossier v2 avant un nouveau téléchargement
si l'on veut comparer les révisions ultérieures du fournisseur.

## Cas prioritaires : preuves et réserves

### INDV : composante mécanique confirmée en octobre, novembre non résolu

Localement, le 10 octobre 2022 vaut 3,13, puis le 11 octobre 15,65,
exactement cinq fois plus ; les volumes sont nuls. Le chemin
10 octobre →7 novembre est étiqueté **+534,50 %**.

Le [communiqué de l'émetteur](https://www.indivior.com/latest/category/news/2022/indv-2022-gm-approval)
fixe une consolidation 5:1 au 10 octobre. Le nouvel appel EODHD fournit
ce même split. Il fournit aussi, au 10 octobre, `close=3.13` mais
`adjusted_close=15.65`. Avec ses deux prix ajustés, le rendement de cette
fenêtre est **+26,90 %**, et non +534,50 %. Cela confirme une composante
non économique dans le rendement local. Ce calcul est une contre-vérification,
**pas une correction prête à injecter** : l'ajusté fournisseur inclut aussi
les dividendes, contrairement à la convention split-only de l'application.

Les chemins des 23 et 25 novembre atteignent **+602,88 %**, avec un saut
3,13 →21,03 le 28 novembre et 16 barres de volume nul dans chaque chemin.
La nouvelle réponse EODHD reproduit cette rupture, y compris dans son ajusté.
**Re-télécharger le même fournisseur ne la résout donc pas.** Le split
d'octobre ne prouve pas la cause du saut de novembre.

La [cotation Nasdaq](https://ir.indivior.com/news-releases/news-release-details/indivior-commence-trading-nasdaq-0)
ne commence que le 12 juin 2023. Avant cette date, il faut reconstituer le
véhicule coté, la place et les éventuels ratios ADR/actions. Il n'est pas
justifié de supprimer toute l'histoire INDV, ni de diviser tous ses anciens
prix par cinq. Ces fenêtres ne sont pas utilisables pour certifier un profit.

### KNTK / ancien ALTM : changement d'échelle, pas preuve de faux rendement

La fenêtre 28 octobre →25 novembre 2020 vaut **+321,35 %** localement.
Le 4 novembre le prix local est 5,015, contre 10,03 dans la nouvelle réponse
brute ; le 5 novembre 15,27 contre 30,54. Le facteur deux est stable, donc
le saut quotidien **+204,49 %** et le rendement H20 persistent après comparaison.
Les ajustés fournisseur donnent +321,36 % à H20, très proche du local.

Le [regroupement ALTM 1:20 signalé par Nasdaq](https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2020-119)
date du 1er juillet, **hors de ces fenêtres**. Il ne peut pas expliquer
directement le saut du 5 novembre. Un [communiqué du 4 novembre déposé à la SEC](https://www.sec.gov/Archives/edgar/data/1692787/000119312520286365/d93377dex991.htm)
annonce résultats et projet de dividende. C'est un contexte compatible avec
un mouvement réel, pas la preuve de son ampleur exacte. Qualification
restante : chaîne ALTM/KNTK et cours indépendants des extrémités.

### REPX / ancien TGC : le split de fin février n'explique pas janvier

La fenêtre 12 janvier →10 février 2021 vaut **+236,67 %**. Les réponses
brutes/ajustées EODHD reproduisent ce rendement. Les prix locaux sont douze
fois les bruts historiques aux points contrôlés, mais le facteur constant
ne crée pas un rendement artificiel entre ces deux dates.

Le [dépôt SEC](https://www.sec.gov/Archives/edgar/data/1001614/000114036121007330/brhc10021161_8k.htm)
décrit fusion et regroupement 1:12 effectifs le 26 février après clôture ;
EODHD date son split de séance du 1er mars. Ces dates sont postérieures aux
deux fenêtres examinées, terminées les 10 et 22 février. Ne pas attribuer
le saut du 28 janvier à cette opération. Identité historique et cours
indépendants restent à qualifier.

### GRND : frontière de combinaison d'entreprises

Le chemin du 21 octobre 2022 traverse le 18 novembre : le prix passe
11,63 →36,50 ce jour-là ; H20 +249,95 %.
Le [10-K](https://www.sec.gov/Archives/edgar/data/1820144/000182014423000005/grnd-20221231.htm)
documente la combinaison Tiga/Grindr le 18 novembre. C'est une réserve
d'identité, **pas une preuve de mauvais prix**. Reconstituer les titres
détenus, conversions et droits avant de certifier un rendement investissable.

### CLDX : un cours effectivement corroboré

Les 19 chemins culminent à +411,83 %. Le [S-3/A déposé le 11 juin 2020](https://www.sec.gov/Archives/edgar/data/744218/000110465920072503/tm2022403-1_s3a.htm)
indique un dernier cours Nasdaq de **4,80 $ le 10 juin**, exactement le prix
local. Le document décrit également le programme clinique CDX-0159.
Ce point indépendant rend une explication « tous ces prix sont fictifs »
intenable, mais ne certifie pas toutes les extrémités H20 ni les fills.

### MXL, CAR et NBR : ne pas exclure sur la seule taille du mouvement

- **MXL**, 14 chemins jusqu'à +382,50 % : saut du 24 avril 2026 +76,12 %,
  avec volume positif. Les [résultats officiels du 23 avril](https://investors.maxlinear.com/press-releases/detail/607/maxlinear-inc-announces-first-quarter-2026-financial)
  constituent un événement temporellement compatible, pas une validation de prix.
- **CAR**, huit chemins jusqu'à +565,52 % : le plus grand n'est pas un saut
  mécanique unique, mais une succession de séances ; volume positif tout
  le long du chemin. Les [résultats officiels Q1 2026](https://avisbudgetgroup.gcs-web.com/news-releases/news-release-details/avis-budget-group-reports-first-quarter-2026-results)
  et documents associés permettent de poursuivre la revue. Pas de certification
  des cours d'entrée/sortie ni de tradabilité sur la seule cohérence locale.
- **NBR**, sept chemins jusqu'à +496,03 % : leur départ le plus ancien est
  le 28 avril 2020. Le [10-Q officiel](https://www.sec.gov/Archives/edgar/data/1163739/000155837020009105/nbr-20200630x10q.htm)
  documente le regroupement 1:50 d'avril ; les fenêtres étudiées commencent
  après sa mise en œuvre. Avoir connu un reverse split ne suffit pas à
  invalider ces fenêtres. Prix indépendants et exécution restent à vérifier.

Les onze autres titres examinés — ACIC, APA, AR, CHEF, HPK, MFA, MTDR, PR,
RYTM, SM, W — n'ont pas de réserve automatique d'identité/volume dans cet
échantillon. Leur statut reste **non certifié indépendamment**. Aucun de
ces titres n'est déclaré faux, sûr ou sélectionnable en production ici.

## Sensibilité : l'effet d'amplitude disparaît-il sans les cas réservés ?

Diagnostic **rétrospectif**, pas filtre négociable PIT. Les sélections Oracle
et ATR sont inchangées, aucun candidat n'est remplacé. On rend inconnus :

1. les labels INDV dont le départ est antérieur au 12 juin 2023 ;
2. les labels GRND qui traversent le 18 novembre 2022, soit
   `départ < frontière <= sortie`.

Cette réserve d'identité est volontairement plus large que la seule rupture
confirmée d'octobre INDV. Elle retire de l'évaluation **886 lignes**, dont
**25 fenêtres ≥50 %** sur les 14 316 initiales ; les autres ne sont pas
des grands mouvements, ou n'étaient déjà pas évaluables. Ce n'est pas une
estimation du nombre total d'erreurs présentes dans toute la base.

| Sélection | Précision ≥50 % avant | Après réserve | Capture avant | Après réserve |
|---|---:|---:|---:|---:|
| Oracle TOP20 % | 1,629 % | ≈1,628 % | 67,71 % | 67,69 % |
| Oracle ET ATR TOP20 % | 1,875 % | ≈1,872 % | 60,55 % | 60,52 % |
| 10 premiers scores Oracle | 6,557 % | ≈6,569 % | 7,68 % | 7,69 % |
| 10 premiers ATR | 6,359 % | ≈6,352 % | 7,44 % | 7,43 % |

Les dix premiers Oracle conservent leurs **1 099 occurrences ≥50 %** ;
30 labels de cette sélection sont rendus inconnus. L'effet descriptif de
concentration n'est donc pas porté par ces deux familles réservées. Cela
**ne démontre ni direction prédictible, ni profit net, ni absence d'autres
anomalies**. Les fenêtres chevauchantes et le poids de 2020 restent importants.

## Pourquoi le label natif ne protège pas suffisamment

`modelFactory/oracle/build_labels.py` utilise `COALESCE(adj_close, close)`.
Sa barrière de rupture inexpliquée est un rapport quotidien ≥20 ou ≤1/20,
complété par un registre de discontinuités connues. Un saut cinq fois plus
grand peut donc rester `target_quality_valid=1`. Les volumes nuls n'y
constituent pas une certification de marché.

Les contrôles SQL en lecture seule sur les dix cas prioritaires n'ont trouvé
aucun événement dans `corporate_actions_events` et leurs dates de cotation
dans `instruments` étaient NULL. L'identifiant instrument inchangé ne
prouve donc pas la continuité historique. **Une table d'actions sur titres
vide n'est pas la preuve qu'aucune action sur titres n'a eu lieu.**

L'adaptateur EODHD applique un ajustement split-only puis stocke
`adj_close=close`. Un retour brut identique au retour local n'est pas une
validation indépendante. Ce travail n'a pas modifié ce contrat ni identifié
avec certitude quelle ancienne exécution a laissé la série INDV insuffisamment
neutralisée. Réduire arbitrairement la barrière 20x risquerait aussi d'écarter
des événements réels : une correction dédiée exige preuves et tests.

## Décision et reste à faire avant un test économique

**Pas de GO économique certifié à ce stade.** La qualification fournit un
registre des réserves et une sensibilité reproductible, pas une validation
de toutes les opérations d'une politique concentrée.

Pour avancer proprement :

1. figer la politique concentrée, la période, le sens et les règles de risque
   sans les optimiser sur ces rendements ;
2. extraire tous ses chemins réellement requis, pas seulement les 100 records ;
3. appliquer les réserves d'identité et d'ajustement, sans combler les trous
   ni remplacer rétroactivement les candidats ;
4. qualifier les splits, distributions, changements de véhicule et prix aux
   extrémités par preuves indépendantes sur les cas matériels ;
5. conserver une vue fournisseur exploratoire distincte si la certification
   exhaustive reste indisponible ; ne pas appeler celle-ci preuve économique ;
6. seulement après nouveau GO, mesurer rendement signé net, drawdown,
   concentration, exposition, liquidité et sensibilité aux coûts.

Aucune promesse de capter les +500 % avec une entrée réalisable n'est faite.
Les faibles volumes, gaps et fenêtres qui se chevauchent peuvent rendre la
performance d'un portefeuille très différente de la fréquence des labels.

Validation logicielle : **63 tests ciblés passent**, dont cinq nouveaux tests
de qualification (frontières de dates, prix ponctuel non certifiant, réserves
localisées, volumes nuls et changement d'échelle sans faux rendement).
Deux avertissements pandas préexistants restent présents ; aucun échec.
