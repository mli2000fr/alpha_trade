# E10 — Pullback LONG après Oracle H20

## Verdict

E10 est terminé en `NO_GO`. Le filtre « Oracle TOP20, baisse à J+1, achat
LONG à l'open J+2 » est rentable en absolu sur la confirmation, mais il ne fait
pas mieux que l'achat LONG de tous les événements Oracle au même instant. E10-B
(replay du lifecycle canonique) n'est donc pas ouvert. Le serving, le backtest
applicatif et le live restent inchangés.

Artefact canonique :

```text
artifacts/research/oracle_pullback_long/oracle-pullback-long-20260910232658-323684
```

## Hypothèse testée

E9 a démontré qu'une baisse après un signal Oracle n'était pas une confirmation
SHORT : ces titres continuaient souvent à monter jusqu'au terminal H20. E10 a
donc testé séparément l'interprétation contrariante suivante :

```text
close J   : Oracle H20 appartient au TOP20 d'amplitude
close J+1 : rendement depuis le close J inférieur ou égal à -seuil
open J+2  : entrée LONG
open J+21 : liquidation au terminal H20 d'origine
```

Le close J+1 est intégralement connu avant l'open J+2. Les prix sont ajustés et
les coûts valent 1 bp de commission plus 2 bps de slippage par côté, soit 6 bps
aller-retour.

## Séparation développement / confirmation

| Partie | Source | Période | Usage |
|---|---|---|---|
| Développement | événements OOF E9 | 2018-07-05 au 2024-07-09 | choisir une seule fois le seuil |
| Confirmation | Oracle H20 `model-factory-20260909051302-323684` | 2024-07-10 au 2025-07-11 | appliquer le seuil gelé sans ajustement |

Le batch de confirmation utilise 168 features Oracle, avec le même SHA-256 de
profil que la campagne Oracle de référence. Ses prédictions sont Walk-Forward
OOF et son univers est construit dynamiquement depuis les barres disponibles à
chaque date. Il s'agit toutefois d'un univers plus large que celui de la
découverte ; cette différence rend le test plus exigeant et mesure aussi la
portabilité de l'effet.

## Sélection du seuil sur le développement

La grille pré-enregistrée est 0 %, 0,25 %, 0,50 %, 1 % et 2 %. Le score de
sélection est le delta quotidien contre tous les Oracle TOP20 achetés LONG au
même open J+2, avec au moins 500 événements et 15 % de couverture. Aucune
observation de confirmation n'intervient dans ce choix.

Le seuil gelé est **0,25 %**. Sur le développement :

- 37 921 trades et 46,13 % de couverture ;
- rendement LONG net quotidien : +2,176 % ;
- benchmark LONG au même délai : +1,852 % ;
- delta : +0,324 point, IC95 bootstrap [+0,066 ; +0,601] ;
- delta positif dans 11/12 folds et 84,62 % des semestres ;
- queue quotidienne à 5 % toutefois inférieure au benchmark de 1,047 point.

Ces chiffres autorisaient la confirmation, mais ne constituaient pas une preuve
indépendante puisque l'hypothèse provenait de l'analyse E9.

## Résultats de confirmation

| Mesure | Pullback LONG | Oracle LONG retardé | Écart |
|---|---:|---:|---:|
| Événements éligibles | 96 366 | 96 366 | — |
| Trades sélectionnés | 43 965 | — | couverture 45,62 % |
| Rendement net moyen par événement | +1,072 % | +0,762 % | +0,310 pt descriptif |
| Rendement net moyen par date | +0,732 % | +0,788 % | **-0,056 pt** |
| IC95 du delta quotidien | — | — | **[-0,603 ; +0,436] pt** |
| Folds avec delta positif | — | — | 1/2 |
| Semestres avec delta positif | — | — | 1/3 |
| Quantile quotidien 5 % | -10,192 % | -10,843 % | +0,650 pt |

Le rendement par événement paraît meilleur parce que les dates ayant beaucoup
de pullbacks reçoivent davantage de poids dans cette moyenne. La mesure
quotidienne donne au contraire le même poids à chaque date de décision et
correspond au gate pré-enregistré. Elle montre que le filtre ne crée pas de
valeur incrémentale.

Par fold, le delta quotidien vaut seulement +0,031 point sur le fold démarrant
le 10 juillet 2024, puis -0,142 point sur celui démarrant le 8 janvier 2025.
Les semestres complets 2024H2 et 2025H1 sont tous deux négatifs. Le résultat
positif de 2025H2 ne couvre que huit dates et ne change pas la décision.

## Gates

Passent : volume, couverture, rendement LONG absolu positif et queue quotidienne
à 5 % non dégradée.

Échouent : delta quotidien positif, borne basse bootstrap positive, au moins
60 % des folds positifs et au moins 60 % des semestres positifs.

La règle est donc `NO_GO`. Sa rentabilité absolue reflète principalement le
biais haussier restant des événements Oracle, déjà capturé par le benchmark
LONG. Il ne faut ni optimiser un nouveau seuil sur la confirmation, ni ouvrir
un replay stops/TP pour tenter de sauver ce résultat.

## Reproduction

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.oracle_pullback_long --discovery-artifact artifacts/research/oracle_post_signal_confirmation/oracle-post-signal-confirmation-20260910230114 --confirmation-batch-id model-factory-20260909051302-323684 --confirmation-start 2024-07-10 --confirmation-end 2025-07-11 --bootstrap-samples 2000 --log-level INFO
```

Le dossier produit contient `report.json`, la grille de développement, les
événements et sélections de confirmation, ainsi que les résultats quotidiens,
par fold et par semestre. Aucune table SQL n'est écrite.
