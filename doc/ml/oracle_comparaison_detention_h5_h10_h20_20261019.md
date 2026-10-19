# Même sélection Oracle : détention H5, H10 ou H20

## Conclusion

**COMPARAISON TERMINÉE — PAS D'AVANTAGE TRANSVERSAL DE H5/H10 DÉMONTRÉ.**
Raccourcir la durée limite certaines pertes, mais coupe aussi des hausses avant
leur TP. Les résultats LONG moyens par occasion sont généralement meilleurs à
H20 ; les SHORT filtrés et le choix LONG/SHORT restent fragiles ou négatifs.
Les contrôles sans chevauchement ne désignent pas non plus un horizon gagnant
dans toutes les périodes.

**Ce résultat ne teste pas un Oracle entraîné pour H10.** Les candidats et
sélections historiques restent ceux des modèles parcours H20 existants. Il
mesure uniquement l'effet d'une sortie plus tôt, toutes choses égales par ailleurs.
Pas de nouveau modèle entraîné, pas de changement de production ou de SQL.

## Périmètre figé avant le calcul

GO du 19 octobre 2026 : comparer H5/H10/H20 sans commencer par un réentraînement.

- Univers complet : les **1 790 titres** du fichier
  `config/univers_batch/univers_filtred_tradable.txt`, sans restriction Oracle.
- Sous-ensemble Oracle : **TOP20 % prédit**, pas vingt titres ni TOP10 ;
  350–358 candidats par séance dans les archives disponibles.
- Mêmes candidats, mêmes dates, mêmes côtés et mêmes qualifications de prix à
  chaque durée. Aucun remplacement par un rang inférieur en cas de donnée absente.
- 2025 : 447 460 couples qualifiés pour l'univers complet, 89 479 pour TOP20 %.
- 2026 : 293 574 / 58 926 couples, décisions matures jusqu'au **1er septembre**,
  observation des parcours jusqu'au 30 septembre 2026.
- Chaque couple est évalué LONG et SHORT ; ce ne sont pas des ordres réels.
- Modèles annuels Oracle parcours inchangés : 437ed1 (2024 historique), 102eca
  (2025), bc35a7 (2026), identifiants complets dans le protocole source TOP20 %.
- Le filtre causal de fiabilité titre/sens déjà calculé pour H20 est **figé**,
  séparément pour chaque périmètre et protection. Pas de réapprentissage des
  adhésions sur les résultats H5/H10. Il repose sur l'historique initial 2024
  puis des mises à jour mensuelles antérieures aux décisions de test.

Les dates récentes uniquement matures pour H5/H10 ne sont pas ajoutées : cela
changerait la population de comparaison. La qualification future H20 commune
est une restriction de cette analyse rétrospective, pas un filtre disponible à J.
L'univers courant reste survivant, pas un univers historique parfaitement PIT.

## Exécution et comparaison

- Entrée à l'ouverture J+1 ; cette séance compte comme séance **1**.
- TP10/SL10, ou TP10 **sans aucun SL**, sans trailing.
- Si aucun seuil n'est atteint : clôture de la séance 5, 10 ou 20.
- TP à sa limite, sans amélioration favorable de gap ; SL exécuté à l'open si
  gap au-delà du stop. Collision intrabar stop-first sauf si l'ouverture la résout.
- Les pertes ne sont pas plafonnées artificiellement au SL.
- Frictions supposées : 8 bps par jambe, sur les montants respectifs ; SHORT,
  emprunt 0,3 % annualisé selon la durée réellement détenue. Pas de locate réel.
- La convention close-N des expériences précédentes est conservée ; ce n'est
  pas la convention expiry-open-N+1 du mode d'entraînement `oracle_barrier`.

Le contrôle sans chevauchement garde les **mêmes épisodes espacés selon les
vingt séances de référence** pour les trois durées. Une sortie à H5 ne crée donc
pas automatiquement trois nouvelles entrées supplémentaires dans ce contrôle.
Une simulation de portefeuille avec capital recyclé serait une autre expérience.

Les taux gagnants ci-dessous sont `net_outcome > 0`, pas toujours TP atteint.
Toutes les moyennes sont nettes par occasion hypothétique, **pas des rendements
annuels de capital**. Durée de mobilisation, rotation du capital, levier, capacité
et positions simultanées ne sont pas simulés dans ces tableaux.

## LONG filtrés : résultat principal

### TOP20 % Oracle

| Protection | Détention maximale | Gagnantes 2025 / 2026 | Moyenne nette 2025 | Moyenne nette 2026 |
| --- | --- | ---: | ---: | ---: |
| TP10/SL10 | 5 séances | 53,87 % / 48,91 % | +0,34 % | −0,19 % |
| TP10/SL10 | 10 séances | 57,37 % / 48,50 % | +0,92 % | −0,41 % |
| TP10/SL10 | 20 séances | 58,58 % / 50,30 % | +1,25 % | −0,26 % |
| TP10 sans SL | 5 séances | 56,51 % / 51,21 % | +0,75 % | +0,13 % |
| TP10 sans SL | 10 séances | 62,83 % / 56,26 % | +1,66 % | +0,52 % |
| TP10 sans SL | 20 séances | 71,76 % / 65,20 % | +3,11 % | +1,10 % |

Effectifs identiques entre durées : 3 486 / 2 660 LONG SL10 ;
3 640 / 3 388 LONG sans SL, pour 2025/2026.

### Univers tradable complet

| Protection | Détention maximale | Moyenne nette 2025 | Moyenne nette 2026 |
| --- | --- | ---: | ---: |
| TP10/SL10 | 5 séances | −0,03 % | −0,04 % |
| TP10/SL10 | 10 séances | +0,18 % | +0,03 % |
| TP10/SL10 | 20 séances | +0,30 % | +0,28 % |
| TP10 sans SL | 5 séances | +0,14 % | +0,17 % |
| TP10 sans SL | 10 séances | +0,50 % | +0,41 % |
| TP10 sans SL | 20 séances | +0,87 % | +0,92 % |

Effectifs LONG SL10 : 22 614 / 19 883 ; sans SL : 32 377 / 22 153.
Références sans filtre, tous LONG et tous SHORT, également conservées dans les
rapports : les résultats ci-dessus ne sont pas ceux d'un achat indistinct de
tout le périmètre.

## SHORT et choix du sens

Moyennes TOP20 % filtrés :

| Protection | Durée | SHORT 2025 / 2026 | Sens choisi LONG/SHORT 2025 / 2026 |
| --- | --- | ---: | ---: |
| TP10/SL10 | H5 | −0,73 % / −1,06 % | −0,32 % / −0,63 % |
| TP10/SL10 | H10 | −1,19 % / −1,26 % | −0,38 % / −0,84 % |
| TP10/SL10 | H20 | −1,38 % / −1,38 % | −0,37 % / −0,83 % |
| TP10 sans SL | H5 | −0,84 % / −1,28 % | −0,15 % / −0,44 % |
| TP10 sans SL | H10 | −1,47 % / −1,64 % | −0,11 % / −0,35 % |
| TP10 sans SL | H20 | −2,64 % / −1,48 % | −0,13 % / +0,06 % |

Les SHORT filtrés sont aussi négatifs à toutes les durées/années dans l'univers
complet. Le bras combiné s'abstient quand les deux côtés passent ; il ne cumule
pas deux positions opposées sur le même titre/date.

## Direction finale et moment du mouvement : mesures distinctes

La direction finale est calculée depuis l'open d'entrée jusqu'à la clôture de N,
même si le TP/SL aurait fait sortir auparavant. Ce n'est pas le rendement obtenu
par la protection. Pour les titres LONG TOP20 % du filtre sans SL :

| Durée | Clôture N au-dessus de l'entrée, 2025 | Même mesure, 2026 |
| --- | ---: | ---: |
| H5 | 56,10 % | 49,50 % |
| H10 | 58,32 % | 49,35 % |
| H20 | 60,41 % | 50,77 % |

Un taux d'occasions positives de 65,20 % avec TP10 à H20 en 2026 ne signifie
donc pas 65,20 % de clôtures haussières ou de prédictions directionnelles justes.
La hausse peut avoir été encaissée au TP avant une baisse ultérieure.
Les taux du choix LONG/SHORT au terminal restent proches de 50 %, sans
purification directionnelle robuste démontrée par le simple raccourcissement.

Le constat temporel antérieur est reproduit : parmi tous les candidats TOP20 %
ayant atteint +10 % en vingt séances, 31,90/40,79 % le font avant ou à la séance 5,
64,37/70,40 % avant ou à la séance 10 (2025/2026). La médiane du premier contact
est séance 8/7. Le côté baissier est proche. Il s'agit de fréquences conditionnelles
rétrospectives, pas de probabilités connues à l'entrée ni du moment du pic maximum.

## Contrôles de robustesse

LONG TOP20 % avec **mêmes épisodes sans chevauchement de référence H20** :

| Protection | Durée | 2025 | 2026 |
| --- | --- | ---: | ---: |
| TP10/SL10 | H5 | +0,56 % | +0,53 % |
| TP10/SL10 | H10 | +1,94 % | +0,72 % |
| TP10/SL10 | H20 | +1,78 % | +0,86 % |
| TP10 sans SL | H5 | +0,50 % | +0,56 % |
| TP10 sans SL | H10 | +2,41 % | +0,81 % |
| TP10 sans SL | H20 | +3,69 % | +0,36 % |

Effectifs : 217/198 pour SL10, 228/226 sans SL. H10 dépasse parfois H20 dans ce
contrôle, mais pas dans les deux années pour la même protection. Aucun horizon
ne doit être choisi comme « optimal » sur ces seules observations déjà explorées.

Différences quotidiennes appariées LONG TOP20 % contre H20, IC95 descriptifs par
blocs de vingt séances : tous les IC SL10 incluent zéro. Sans SL, H5/H10 font
moins bien en 2025 : H10 −1,55 point, IC95 [−2,19 ; −0,72] ; en 2026, H10
−0,45 point, IC95 [−1,63 ; +0,72], non concluant. Les écarts appariés quotidiens
ne sont pas la simple différence des moyennes pondérées par nombre d'occasions.
Pas de correction des multiples expériences/sélections réalisées auparavant.

La détention courte réduit certaines pertes : sans SL, perte moyenne des LONG
TOP20 % perdants en 2026 : −6,78 % à H5, −9,65 % à H10, −14,37 % à H20. Mais elle
réduit aussi les profits et contacts de TP. Cette baisse des pertes ne suffit
donc pas à prouver une amélioration nette ou une direction mieux prédite.

## Qualité, vérification et reproduction

83 tests passent, dont 26 nouveaux : parité H20, entrée/expiration exacte,
absence d'effet des prix après expiration H5/H10, touches sur dernière séance,
collision/gaps, absence de SL, coûts et conservation des adhésions/espacement.
432 parties produites sur 1 790 titres ; parité exacte de la formule H20 sur
2 964 136 lignes, deux protections et deux sens compris.

Audit final `PASS_EXPLORATORY_ONLY` : les douze combinaisons
(trois durées × deux protections × deux périmètres) ont les mêmes couples et
adhésions que leurs références, les mêmes nombres d'épisodes indépendants,
des sorties précoces inchangées, les coûts et échéances corrects. H20 reproduit
les références jusque dans les lignes individuelles, pas seulement la moyenne.

Réserves conservées : prix ajustés/OST dont des échelles suspectes non
indépendamment qualifiées (KLAC notamment), univers survivant, années déjà vues,
pas de vrais bid/ask/fills, dividendes/locates/marge non reconstitués. Sans SL,
SHORT peut perdre plus de 100 % du nominal ; pas de liquidation forcée simulée.
Aucun prix suspect n'a été corrigé, supprimé ou plafonné après observation.

Scripts : `scripts/research/us_oracle_holding_horizons.py`, phases
`prepare`, `build`, `run` ; audit `scripts/research/us_oracle_holding_horizons_audit.py`.
Dossier : `artifacts/research/us_oracle_holding_horizons/20261019-v1/`.
`progress.json`, `protocol.json`, `paths-manifest.json`, `comparison.csv`,
`report.json`, `final-audit.json` ; chaque protection/durée conserve ses deux
populations et statistiques, risques, contrôles semestriels et différences appariées.

**Aucun réentraînement H10 n'est lancé à la fin.** La question « un Oracle
spécialement entraîné sur dix séances sélectionnerait-il d'autres titres plus
prévisibles ? » reste distincte. Le présent essai ne la valide ni ne la réfute.

Suite, après un GO distinct : [qualification bornée des prix puis six modèles
réellement entraînés H10/H20](oracle_h10_h20_prix_et_comparaison_20261019.md).
Cette suite ne remplace pas les artefacts ni les résultats figés du présent essai.

Source : [TOP20 % contre univers complet, TP10](oracle_top20pct_et_univers_complet_tp10_20261019.md).
