# E17-B — Confirmation prospective du momentum résiduel H120

## Statut

**Pré-enregistré et verrouillé — `BLOCKED_DATA_UNAVAILABLE`.**

E17-B ne réanalyse pas 2018–2025. Cette période a servi à découvrir le signal
et ne peut plus servir de confirmation indépendante. La première date de signal
autorisée est le **14 septembre 2026**, première séance suivant le
pré-enregistrement du 11 septembre 2026.

La base de barres disponible s’arrête au 30 juin 2026, avant cette date. E17-B
est donc conservée pour sa valeur de gouvernance, mais ne peut actuellement
produire aucune cohorte. Elle ne doit pas être surveillée activement tant que
l’alimentation des cours postérieurs n’a pas repris.

Rapport initial :
`artifacts/research/directional_alpha_book_confirmation/e17b-confirmation-20260911195638/report.json`.

## Hypothèse figée

> Sur de nouvelles données, le TOP20 du momentum résiduel 120–10 à H120 produit
> un rendement long-only net positif et un rendement excédentaire positif et
> statistiquement significatif contre l’univers éligible et SPY.

E17-B ne cherche plus une jambe SHORT. E17 a montré que le signal classe les
gagnants relatifs mais ne détecte pas les baisses absolues du bottom.

## Contrat enregistré avant confirmation

| Élément | Valeur verrouillée |
|---|---|
| Signal | `residual_momentum_120_10` |
| Oracle | absent, `oracle_used=false` |
| Horizon | H120 uniquement |
| Temps du signal | close J |
| Entrée | open ajusté J+1 |
| Sortie | open ajusté J+121 |
| Sélection | TOP 20 % des titres éligibles |
| Pondération | équipondérée, long-only |
| Rebalance | 20 séances |
| Coût | 6 bps aller-retour |
| Comparateurs | univers éligible équipondéré et SPY |
| Univers | `univers_filtred_equities.txt` |
| Début prospectif | 2026-09-14 |

Le signal est la somme, sur la fenêtre J−119 à J−10, des rendements du titre
résiduels à SPY après estimation d’une bêta glissante 126 séances.

L’éligibilité reste identique à E17 : 252 séances valides, cours ≥ 10 USD,
volume moyen 20 jours ≥ 50 000 actions, ADV20 ≥ 10 MUSD, barre exacte non
synthétique et instrument action éligible.

## Verrouillage anti-optimisation

Le contrat est conservé dans
`config/research/e17b_residual_momentum_h120_preregistration.json`.

L’évaluateur calcule une empreinte SHA-256 canonique de son contenu. L’empreinte
attendue est :

```text
20f7376e5bd09b5dc394070bb3104cbd81fbce1439ba810f322893535bde8936
```

Toute modification d’une valeur — signal, coûts, dates, taille du TOP, gates ou
bootstrap — bloque l’exécution. Les changements de mise en forme ou de fins de
ligne n’affectent pas l’empreinte canonique.

## Preuve minimale avant verdict

E17-B reste `PENDING_DATA` tant que les trois conditions suivantes ne sont pas
toutes réunies :

- au moins 24 cohortes H120 arrivées à maturité ;
- au moins quatre semestres distincts de dates d’entrée ;
- au moins 50 titres sélectionnés en moyenne.

Des rapports intermédiaires peuvent être générés, mais ils ne doivent pas être
interprétés comme GO ou NO_GO. Avec une rebalance toutes les 20 séances et une
maturité H120, la validation finale demande plusieurs années de nouvelles
données. Cette durée est la conséquence du choix scientifique H120, pas un
problème de performance du programme.

## Gates de décision

Une fois la preuve minimale disponible, tous les gates doivent passer :

1. rendement LONG net moyen > 0 ;
2. excès moyen contre l’univers éligible > 0 ;
3. borne basse IC95 de cet excès > 0 ;
4. excès moyen contre SPY > 0 ;
5. borne basse IC95 de cet excès > 0 ;
6. au moins 60 % des semestres avec excès positif contre l’univers ;
7. aucun semestre ne porte plus de 35 % du PnL positif.

Les IC95 sont calculés par block bootstrap de six cohortes, cohérent avec H120
et une rebalance de 20 séances.

## États possibles

```text
preuve insuffisante
    └── PENDING_DATA

preuve suffisante + tous les gates
    └── GO_RESEARCH_SHADOW_ONLY

preuve suffisante + au moins un gate échoué
    └── NO_GO
```

Même `GO_RESEARCH_SHADOW_ONLY` n’autorise pas la production. Il ouvre seulement
une étape shadow avec audit du survivorship bias, des coûts réels et de la
capacité.

## Exécution

L’évaluateur peut être relancé sans modifier son contrat :

```powershell
.\.venv\Scripts\python.exe -u -m modelFactory.directional_alpha_book_confirmation --end-date AAAA-MM-JJ --log-level INFO
```

Sans `--end-date`, il utilise la date du jour. Avant le 14 septembre 2026 ou en
l’absence de barres nouvelles, il produit normalement `PENDING_DATA`.

Chaque exécution écrit un nouveau répertoire sous :

```text
artifacts/research/directional_alpha_book_confirmation/
```

avec :

- `report.json` : preuve disponible, métriques, gates et verdict ;
- `confirmation_cohorts.csv` : cohortes arrivées à maturité.

## Gouvernance

- aucun paramètre ne doit être ajusté après lecture d’un rapport intermédiaire ;
- les observations 2018–2025 ne doivent pas être réintroduites ;
- un échec ne peut pas être remplacé par un autre seuil sous le même ID ;
- une nouvelle formulation exige un nouvel identifiant et un nouveau
  pré-enregistrement ;
- aucun artefact de serving, aucune prédiction et aucune politique live ne sont
  modifiés par E17-B.

Implémentation : `modelFactory/directional_alpha_book_confirmation.py`.

Tests : `tests/test_directional_alpha_book_confirmation.py`.
