# Sous-ensemble FR réellement utilisable — qualification bornée du 9 octobre 2026

## Conclusion et usages autorisés

Il existe un sous-ensemble **utilisable pour une étude exploratoire des entrées
fournisseur**, mais aucun titre n'est admis automatiquement au shadow ou au
trading. La qualification récente ne remplace pas les qualifications historiques
des sprints 5–13 et ne démontre aucun gain directionnel D1/D10.

| Niveau vérifié | Titres | Usage |
|---|---:|---|
| Identités de recherche du manifeste de modèle | 330 | Périmètre audité, pas univers tradable |
| Univers configuré de collecte quotidienne | 294 | Ne comprend pas toutes les identités historiques |
| Panel récent complet, prix traçables en archives et présents en staging, volumes positifs, sans prix retenu non reconfirmé | 255 | Étude de prix fournisseur sur les cinq séances examinées |
| Entrées du profil de features calculables, identité résolue et couverture fournisseur des dividendes/splits sans événement réservé dans la fenêtre | 235 | Étude exploratoire ; réserves indépendantes maintenues |
| Même niveau, restreint au MIC résolu XPAR | 164 | Sous-ensemble recommandé pour une étude limitée à Paris |
| Admission shadow / ordres | **0** | Aucune activation |

Les 235 titres comprennent 164 XPAR, 70 ALXP et 1 XMLI. Ces places ne sont pas
interchangeables. Les 36 identités supplémentaires du manifeste ne signifient
pas 36 échecs du batch : le manifeste inclut des identités historiques hors
périmètre actuel de collecte. Les 246 titres dont les features sont calculables
ne sont pas tous admissibles au niveau « entrées fournisseur » : une feature
calculable ne lève ni les réserves d'identité ni celles d'événements.

## Fenêtres et disponibilité

- Panel récent : 2, 5, 6, 7 et 8 octobre 2026.
- Features : 21 séances closes terminant le 8 octobre, formules existantes
  inchangées, archives disponibles avant l'ouverture XPAR du 9 octobre.
- Complétude récente, reconfirmation et présence SQL : observées à l'heure de
  l'audit du 9 octobre, indiquée dans `report.json`.

**Ces instants sont distincts.** La publication SQL du 9 octobre ne rend pas ces
barres disponibles rétroactivement à une ouverture antérieure. L'inventaire
utilise aussi des contrôles effectués après l'ouverture : il n'est donc pas une
sélection historique PIT à appliquer au backtest du 9 octobre. Une étude future
doit reconstruire chaque sélection à son propre instant de décision.

## Contrôles effectués

Le service réutilise les contrôles existants : SHA-256 du brut, correspondance
observation/réponse, versions disponibles avant la décision, séance close,
OHLCV valide, 21 séances de warmup, features finies, identité ISIN/MIC résolue
et réponses fournisseur dividendes/splits couvrant la fenêtre. Les archives du
bootstrap du 7 octobre complètent les archives quotidiennes.

La base `alpha_trade_fr` est contrôlée et consultée dans une transaction
explicitement en lecture seule. La présence d'une version SQL à la date de
l'audit est vérifiée, sans assimiler ses multiples versions à des doublons.

Les réponses fournisseur ne prouvent **pas indépendamment** l'absence d'une
opération sur titres. La devise nominale ESMA n'est pas automatiquement une
preuve de devise de négociation. La continuité ESMA reste réservée pour les
330 identités ; elle ne rend pas toutes leurs features fausses, mais interdit
une promotion implicite vers le shadow.

## Exclusions et réserves concrètes

- LHYFE.PA et PERR.PA : barres récentes absentes ; changement de place déjà
  documenté, sans substitution automatique d'une cotation étrangère.
- ARTO.PA : prix retenus non reconfirmés et volumes nuls dans la fenêtre ; exclu
  du sous-ensemble récent complet.
- 37 titres ont au moins un volume récent non positif ; ces lignes ne sont pas
  supprimées mais ne satisfont pas ce profil de recherche.
- 39 diagnostics signalent un warmup incomplet et 45 une barre à volume nul
  incompatible avec les features figées. Les motifs se recouvrent : ne pas
  additionner ces compteurs pour compter des titres.
- 10 diagnostics réservent un dividende dans la fenêtre ; aucun ajustement
  automatique non qualifié n'est inventé.
- 30 diagnostics ont une identité terminée ou réservée, et 6 exigent une preuve
  de devise de négociation malgré leur devise nominale non EUR.

AIR.PA, OR.PA et SAN.PA passent le niveau « entrées fournisseur » dans cette
fenêtre. Ils ne constituent toujours pas une release shadow qualifiée.

## Livrables reproductibles

Rapport : `artifacts/fr/research/usable_subset/qualification-20261009-v2/report.json`.

- `research_provider_inputs.json` : les 235 identités et leurs réserves.
- `research_provider_inputs_xpar.json` : les 164 identités XPAR et leurs réserves.
- `feature_assembly.json` : diagnostic complet, dates, preuves et empreintes.
- `report.json` : les 330 fiches, exclusions par titre et distinctions d'usage.

```powershell
python -u -m service.fr.usable_subset_qualification --decision-date 2026-10-09 --start 2026-10-02 --bootstrap-dir artifacts/fr/research/data_readiness_16c/bootstrap-remediation-20261007-v1 --output-dir artifacts/fr/research/usable_subset/qualification-NOUVELLE-VERSION
```

Choisir un nouveau répertoire ; aucun rapport précédent n'est écrasé. La date
de décision doit avoir eu lieu. Le service ne télécharge rien, ne modifie aucun
univers configuré, n'entraîne pas, n'écrit pas en base et n'active aucun ordre.

Tests ciblés : **20 réussis**, classification, adapter de features existant et
audit de couverture. Les cas testés incluent prix non reconfirmés, volume nul,
warmup incomplet, identité ambiguë et interdiction d'admission shadow implicite.

## Suite bornée

Pour une prochaine expérience exploratoire limitée à Paris, partir des 164
titres, sans changer le modèle ni annoncer un résultat économique validé.
Pour un shadow qualifié, conserver les gates indépendantes de prix/devise,
événements et continuité, puis les revues de modèle et d'exploitation. Ne pas
réouvrir sans limite la prospection documentaire ni activer le trading pour
compenser une preuve manquante.

Références : [publication SQL quotidienne](publication_quotidienne_staging_sql.md),
[remédiation](remediation_collectes_couverture_20261009.md),
[clôture bornée du Sprint 16](sprint_16_cloture_bornee.md).
