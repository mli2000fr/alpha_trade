# Sprint 16-G — Preuve ponctuelle de devise MiFIR

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Résultat du 8 octobre 2026

Le fichier officiel Euronext Paris contient des publications de transactions
sur XPAR pour les trois identités du pilote. Toutes indiquent EUR.

| Titre | ISIN | Séance | Publications retenues | Devise |
|---|---|---|---:|---|
| AIR.PA | NL0000235190 | 2026-10-07 | 14 768 | EUR |
| OR.PA | FR0000120321 | 2026-10-07 | 6 771 | EUR |
| SAN.PA | FR0000120578 | 2026-10-07 | 9 006 | EUR |

Ces nombres comptent des **lignes de publication**, pas un total de transactions
certifié exhaustif. Sur 457 059 lignes du fichier, 30 545 concernent le pilote.
Aucune exclusion ni duplication exacte n'est relevée dans cette population.

Cela prouve une devise de transaction datée, pas simplement une devise nominale.
Cela ne qualifie **ni l'intervalle complet, ni les opérations sur titres, ni
l'absence d'événement**. Le Sprint 16 reste non libéré ; aucun élargissement
automatique à vingt titres n'est effectué.

## Source et autorisations

[Euronext — Delayed Trade Data](https://marketdata.euronext.com/data-reporting-service/trades-file) :
formulaire Equities / Previous trading day / Paris. Les conditions spécifiques
permettent l'utilisation interne gratuite, sous restrictions de redistribution.
Cette vérification ne constitue pas un avis juridique ni une autorisation
générale Euronext : elle ne réactive aucun fichier Excel ou collecteur suspendu.
La disponibilité récente de ces fichiers n'assure pas un backfill historique.
Ce POC ne fournit ni NBBO, ni preuve d'ajustement, ni collecte planifiée.

## Traçabilité et PIT

Rapport final :
`artifacts/fr/research/issuer_pilot_16g/mifir-currency-20261008-v2/report.json`.

Archive initiale :
`artifacts/fr/research/issuer_pilot_16g/mifir-currency-20261008-v1/trades.zip`.

- Réception réelle : **2026-10-08 20:22:41 UTC**, soit **22:22:41 Paris**.
- ZIP : 7 582 944 octets ; CSV décompressé : 80 049 766 octets.
- SHA-256 ZIP : `0fc4b0062df51bb1e0e4b63b4edf3c0388d347d6d74a86c12c94eed199889352`.

La réception est postérieure à l'ouverture du 8 octobre : le bilan figé de
cette ouverture reste inchangé. Une décision future pourra examiner cette
observation, sans en extrapoler la couverture à toutes les séances requises.

La première lecture a échoué en attendant des champs de dérivés absents du
fichier actions. Le rapport FAILED v1 est conservé. Après correction du lecteur
cash, la même archive a été relue hors réseau en v2, avec vérification des
empreintes du ZIP et de la page source. Aucun échec n'a été effacé.

## Contrôles et reproduction

Service : `service/fr/mifir_equity_currency_16g.py`.
Le lecteur contrôle schéma actions, tailles, ISIN/place, identifiants,
doublons/conflits/modifications, prix et quantités finis positifs, notation
monétaire, devise, horodatages cohérents et délai de quinze minutes. Les champs
propres aux dérivés ne sont pas inventés. Le résultat demeure non servable.

Relecture sans réseau : utiliser le rapport **v1**, contenant l'archive
initiale, avec un nouveau répertoire de sortie :

```powershell
python -u -m service.fr.mifir_equity_currency_16g --archive-report artifacts/fr/research/issuer_pilot_16g/mifir-currency-20261008-v1/report.json --output-dir artifacts/fr/research/issuer_pilot_16g/nouvelle-relecture-mifir
python -m pytest tests/test_fr_mifir_equity_currency_16g.py --no-cov -q
```

Les quatorze tests couvrent notamment observation ponctuelle sans qualification
implicite, doublons, modifications, mauvaise place, notation invalide, valeur
non finie, délai, conflit de devise et schéma cash. **200 tests ciblés Sprint
16 passent** après cette évolution ; ce n'est pas une certification globale.
Aucune écriture SQL, modification de modèle ou de batch, ni aucun ordre.

## Réserves restantes

Compléter la preuve de devise sur l'intervalle exigé ; qualifier les opérations
effectives et leur traitement ; résoudre les réserves de continuité et de
disponibilité du dossier prospectif. N'élargir qu'après validation du pilote.

Voir le [pilote](sprint_16g_pilote_devises_actions.md), la
[revue des sources](sprint_16g_revue_sources_pilote_20261008.md) et le
[bilan](sprint_16g_bilan_et_plan_de_liberation.md).
