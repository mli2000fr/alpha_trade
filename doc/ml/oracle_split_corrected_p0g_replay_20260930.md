# Splits Oracle : prix et labels reconstruits, replay P0g — 30 septembre 2026

Statut : **replay P0g à gate Oracle OOF figé terminé ; NO_GO_DIRECTION inchangé**.
Tous les calculs ont utilisé des copies de recherche. Aucune barre, cible, prédiction
ou modèle canonique n'a été réécrit en base ; aucun serving n'a été activé.

## Source et périmètre de la réparation

L'[audit des splits](oracle_split_label_audit_20260930.md) a trouvé deux
discontinuités non ajustées dans les prix locaux NVIDIA. Les dates et ratios sont
confirmés par les [documents NVIDIA 2021](https://investor.nvidia.com/files/doc_downloads/doc_faq/08/Investor-NVIDIA-2021-Stock-Split-FAQ-08.9.2021.pdf)
et [2024](https://investor.nvidia.com/news/press-release-details/2024/NVIDIA-Announces-Financial-Results-for-First-Quarter-Fiscal-2025/) :
4:1 à partir du 20/07/2021, puis 10:1 à partir du 10/06/2024. Les clôtures
locales antérieures à chaque date ont été divisées par le ratio correspondant,
sur une base de prix postérieure à 2024 : facteur 1/40 avant juillet 2021,
1/10 entre les deux splits, 1 ensuite. La série reconstruite contient **2 014**
barres réelles NVIDIA depuis le 05/07/2018, dans
`work/guidance_pit_followup_20260930/nvda_rebuilt_split_adjusted_close.csv`
(SHA-256 `d5647e4f80220e772c8589f315ffd95111a1495db4480891485dbd47c1fa7350`).
L'overlay de features a appliqué les mêmes facteurs aux OHLC/VWAP, le facteur
inverse au volume, puis recalculé le rendement quotidien NVIDIA en mémoire.
Les autres titres ont gardé leurs prix locaux : leurs splits classés indéterminés
n'ont pas été « corrigés » par supposition.

Pour couvrir la période d'entraînement antérieure à l'OOF, 153 splits Alpaca
supplémentaires ont été audités entre le 01/01/2013 et le 04/07/2018 : 133
sont cohérents avec l'ajustement local, 16 indéterminés et quatre sans barres
encadrant la date. Aucun nouveau candidat franchement non ajusté selon la
règle de l'audit. Ce contrôle ne certifie pas l'absence d'autres erreurs de prix.

## Reconstruction des cibles H20

Les **40 labels NVIDIA** traversant les splits étaient valides et D1 dans le
batch `model-factory-20260909051302-323684`. Le rendement enregistré se
reproduit exactement à partir des anciennes clôtures aux deux extrémités
(`max_abs_error=0`). Après ajustement, leurs rendements H20 vont de **−4,27 %
à +43,05 %** ; aucun ne reste D1 et **17 deviennent D10**. Les rangs ont été
recalculés sur les **69 136 labels valides des 40 dates** : 304 déciles et
80 indicateurs `oracle_extreme10` changent, parmi 308 lignes où le rendement,
le décile ou le statut extrême change. Les rangs percentiles sont recalculés
pour toutes les lignes, y compris celles qui restent dans leur décile.

Le sidecar complet est
`work/guidance_pit_followup_20260930/oracle_split_rebuilt_all_label_overrides.jsonl`
(SHA-256 `b4ab5c834e4595e63481ee2876dad38911553bb918077b06c3f481ab1dd89ea0`).
La liste compacte des 308 changements de rendement/décile/cible est
[`oracle_split_corrected_label_changes_20260930.csv`](oracle_split_corrected_label_changes_20260930.csv)
(SHA-256 `206e2a9cba7a71bf8acadfbbe025f21eb2540d97acc0351bf2add1b035ec9711`).
Aucune nouvelle valeur n'a été injectée en SQL.

## Replay P0g : folds, population et résultat

Les features de prix ont été recalculées sur **7 386 735 barres** et les rangs
de features sur les 2 493 symboles, puis seules les entrées du TOP20 Oracle OOF
d'origine ont été conservées. Le panel contient exactement **582 700 lignes**,
1 764 dates, 1 472 symboles et 84 features numériques. **71 des 308 lignes
modifiées appartiennent à ce panel.** Les neuf fenêtres de test matérialisées
sont identiques date pour date à celles du [P0g publié](oracle_universe_p0g_directional_impact.md).
Le modèle conserve le contrat P0g : CatBoost sans contexte, 600 itérations max,
profondeur 6, taux 0,03, Walk-Forward 504/126/126, pas 126 et graine 42.

Un témoin apparié restaure les anciens labels sur **les mêmes features de prix
NVIDIA corrigées**, les mêmes 582 700 événements, les mêmes scores Oracle OOF,
les mêmes folds et le même environnement logiciel. Il retrouve exactement les
**179 605** lignes D1/D10 évaluées dans P0g. Le bras corrigé en a 179 612 ;
les ensembles partagent 179 597 clés OOS (8 seulement dans l'ancien, 15 seulement
dans le corrigé).

| Mesure OOS | Anciens labels, mêmes features corrigées | Labels corrigés |
|---|---:|---:|
| AUC D10 contre D1 | 0,5004 | **0,4882** |
| IC directionnel quotidien | −0,0107 | **−0,0212** |
| Lignes D1/D10 | 179 605 | 179 612 |

Sur les 179 597 clés communes, l'AUC avec les **labels corrigés** est 0,5005
pour le modèle entraîné sur les anciennes cibles et 0,4882 pour celui entraîné
sur les cibles corrigées. Le changement de cible a donc modifié le fit ; il ne
révèle pas une séparabilité directionnelle robuste. Les AUC par fold corrigé
sont 0,501 / 0,453 / 0,486 / 0,539 / 0,435 / 0,456 / 0,506 / 0,484 / 0,568.
Le fichier de synthèse est
`work/guidance_pit_followup_20260930/p0g_paired_replay_summary.json` ; les
modèles, métriques et prédictions OOS des deux bras sont conservés sous `work/`.

**Portée :** ce test isole l'effet des labels corrigés dans un replay P0g dont
le gate d'entrée reste l'Oracle d'amplitude historique. Les scores Oracle n'ont
pas été réentraînés sur les 80 cibles extrêmes corrigées. Il serait trompeur de
présenter ce 0,4882 comme le résultat d'une reconstruction complète Oracle →
P0g. L'AUC P0g publiée de 0,4904 provient en outre d'un autre environnement
logiciel et de features de prix non corrigées ; la comparaison causale ici est
le témoin apparié 0,5004, pas cette valeur historique.

Les splits indéterminés et les sauts sans split rapproché de l'audit précédent
restent non résolus. Pour une validation définitive, reconstruire les barres
ajustées et l'univers avec une règle de corporate actions contrôlée, relancer
les 14 folds OOF de l'Oracle d'amplitude sur les nouvelles cibles, puis rejouer
P0g avec ce **nouveau gate OOF**, tout en gardant ses neuf folds directionnels
et un témoin apparié. Les présentes données de recherche ne justifient aucune
promotion directionnelle.
