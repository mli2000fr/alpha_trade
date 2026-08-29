# Univers tradable PIT et gate d'entrée

Retour : [références Data](README.md)

## Modèle

Un run d'univers possède identifiant, snapshot date, preset capital, fingerprint, grade qualité, nombre attendu/écrit et statut. Les membres stockent symbole, booléen tradable, reason code principal, liste des raisons et diagnostics de marché.

## Atomicité

`begin_universe_run` crée un run non visible comme publié. `publish_universe_run` insère les membres, contrôle la cardinalité et publie. `fail_universe_run` conserve la preuve d'échec. `resolve_universe_asof` ne retourne qu'un snapshot admissible à ou avant la date selon son contrat ; il ne consomme jamais un run en construction.

## Construction `full`

Le publisher requiert un snapshot screener complet exact pour la date. Il charge preset/seuils, quote récente dans la fenêtre, market cap et earnings. Pour chaque symbole, il conserve les raisons amont et évalue la cascade. Les diagnostics enregistrés incluent history days, bars flag/source, close, ADV USD, spread bps, market cap, ATR% et blackout.

Le booléen final est `source_tradable AND reason == tradable`. Une quote absente n'est pas un spread nul. `--ignore-quotes` retire explicitement ce contrôle et change le fingerprint.

## Historique de plage

Avec `--start-date/--end-date`, seules les séances NYSE sont parcourues. Une date sans screener exact est listée dans `missing_screener_snapshot_dates`; les autres peuvent être publiées. Le code de sortie 2 signale une publication incomplète.

## Fingerprint

Le hash court couvre run/fingerprint screener source, preset et seuils effectifs de spread, market cap et blackout. Il permet de détecter une variation de contrat, mais ne remplace pas un hash complet de toutes les rows source.

## Gate d'entrée

`EntryDataGate` classe les sources : critiques `price_data`,`volume_adv`; requises `borrow`,`universe`,`corporate_actions`; optionnelles `sentiment`,`macro`,`regime`,`earnings`. Pour chaque source, il vérifie présence, `available_at <= cutoff`, âge et quality. Le max age par défaut est 26 h.

Une source critique manquante/future/stale/dégradée met `go=false`. Une requise alimente `degraded_sources`; une optionnelle passe avec reason. Le résultat est sérialisable et `EntryDataBlocked` le transporte sans perdre les détails.

## Commandes

```powershell
python -m common.publish_tradable_universe --trade-date 2026-08-28
python -m common.publish_tradable_universe --start-date 2026-08-01 --end-date 2026-08-28
```

## Invariants

Un seul contrat de qualité par run ; pas de mutation des membres publiés ; aucune quote future ; aucun snapshot actuel répété sur le passé ; reason codes conservés ; cardinalité vérifiée ; fingerprint attaché aux consumers ML/risk.

