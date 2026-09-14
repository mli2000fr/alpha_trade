# E21 — Backfill historique et validation manuelle de guidance

## Résultat du 14 septembre 2026

Le correctif des URL du collecteur est appliqué. Le smoke historique a récupéré
14 annexes distinctes pour six sociétés : OXM, TTC, ABM, DOCU, TSN et LULU,
sur janvier–juin 2025. Ce n'est ni un test ML ni un backtest.

Deux collectes utiles totalisent 18 téléchargements, dont quatre documents en
commun. La première a téléchargé 12 annexes et rencontré trois erreurs HTTP
503 sur les index HTML. La reprise par index JSON, limitée à trois émetteurs,
a téléchargé six annexes sans erreur, dont deux manquantes. Les traces des
essais échoués sont conservées ; nous ne revendiquons pas une collecte exhaustive.

## Correctif du collecteur quotidien

Dans `service/forward_pit/batch.py`, les href sont résolus avec `urljoin` :
un lien absolu ou relatif à la racine conserve son chemin SEC complet, plutôt
que d'être réduit à son nom de fichier. Le chemin de base des liens relatifs
inclut le numéro d'accession sans tirets. Les liens du visualiseur `/ix?doc=`
sont déballés. Les destinations hors HTTPS/sec.gov/Archives/edgar/data sont
rejetées. La persistance habituelle n'est pas modifiée.

Le service de recherche utilise la confiance TLS système Windows, sans
désactiver la vérification des certificats. Le mode `--directory-index` est
une reprise propre à ce POC : les noms EX99 sont des candidats, pas une
classification d'annexe certifiée. Le titre et le contenu doivent être revus.

## Comparaisons manuellement vérifiées

Chaque paire concerne la même période fiscale et une mesure déterminée.
Les unités de tableau, la base comptable et la période sont annotées par
lecture humaine : le parseur numérique ne les déduit pas automatiquement.

| Société | Mesure annuelle | Ancienne fourchette | Nouvelle fourchette | Lecture |
|---|---|---|---|---|
| OXM | Ventes, milliards USD | 1,490–1,530 | 1,475–1,515 | Baisse |
| OXM | EPS GAAP, USD/action | 4,21–4,61 | 2,28–2,68 | Baisse |
| OXM | EPS ajusté, USD/action | 4,60–5,00 | 2,80–3,20 | Baisse |
| TTC | EPS ajusté dilué, USD/action | 4,25–4,40 | 4,15–4,30 | Baisse |
| DOCU | Revenus, millions USD | 3 129–3 141 | 3 151–3 163 | Hausse nominale |
| DOCU | Billings, millions USD | 3 300–3 354 | 3 285–3 339 | Baisse nominale |
| LULU | Revenus, milliards USD | 11,150–11,300 | 11,150–11,300 | Inchangé |
| LULU | EPS dilué GAAP, USD/action | 14,95–15,15 | 14,58–14,78 | Baisse |
| TSN | Résultat opérationnel ajusté groupe, milliards USD | 1,9–2,3 | 1,9–2,3 | Inchangé |

Les 18 fourchettes anciennes/nouvelles sont retrouvées dans les documents
locaux par `money_range_candidates`. Cela vérifie les nombres, pas la
résolution automatique du sens économique. Neuf mesures représentent seulement
cinq paires de publications d'émetteurs, pas neuf événements indépendants.

Pièges conservés dans les annotations :

- ABM : EPS ajusté 3,65–3,80 apparemment inchangé, mais définition non-GAAP
  modifiée concernant les ajustements d'auto-assurance. Comparaison exclue
  sans retraitement de l'ancienne base.
- OXM : communiqué de janvier relatif à FY2024, non utilisable comme ancien
  FY2025. Les prévisions nouvelles intègrent des coûts de tarifs douaniers.
- TTC : hypothèses de tarifs douaniers différentes ; pas une comparaison
  à hypothèses constantes.
- DOCU : hypothèses de change différentes ; hausse des revenus et baisse des
  billings ne constituent pas un signal directionnel uniforme.
- LULU : revenus inchangés et EPS abaissé : conserver les deux mesures.
- TSN : séparer groupe et segments ; communiqué de conférence du 8 mai exclu.

## Artefacts et reproduction

`artifacts/research/guidance_historical_backfill/e21-20260914-smoke2/` contient
`collection_report.json`, les annexes locales, les passages candidats et
`manual_annotations.json` (sources par émetteur/accession, périodes, unités,
bases, valeurs et exclusions). La reprise est dans
`../e21-20260914-retry-json/`. Les rapports contiennent URL, hash et date de
collecte ; la collecte n'est jamais antidatée.

```powershell
python -u -m service.forward_pit.guidance_backfill --start-date 2025-01-01 --end-date 2025-06-30
python -u -m service.forward_pit.guidance_backfill --symbols OXM,TTC,LULU --max-filings-per-symbol 2 --directory-index
python -m pytest tests/test_sec_document_urls.py tests/test_forward_pit_batch.py tests/test_guidance_audit.py tests/test_guidance_backfill.py --no-cov -q
```

Vérifier les options via `--help` avant une fenêtre différente. Le POC lit
les CIK locaux et les dépôts récents de submissions ; il ne parcourt pas les
fichiers anciens de submissions. Maximum deux annexes par dépôt et 2 Mo par
annexe ; PDF non parsé. Ces limites sont documentées dans le rapport.

## Statut et prochaine étape

**SMOKE technique et revue manuelle réussis ; DATA_READY ML non acquis.**
La date d'acceptation SEC est tracée, mais l'heure réelle de disponibilité
historique de l'annexe n'est pas validée. L'échantillon est choisi, petit et
concentré sur 2025, notamment les tarifs douaniers. Aucune précision de trading
ni généralisation n'est mesurée. Aucun batch en cours n'a été touché, aucune
table de production alimentée par ce backfill, aucun modèle entraîné.

Prochaine étape : extraction sémantique mesure/période/unité/base, annotation
indépendante incluant faux positifs et exclusions, puis historique multi-années
avec prédécesseurs et contrat de disponibilité PIT. Seulement ensuite, test
temporel pré-enregistré LONG/SHORT, comparé à un benchmark et net de coûts.
