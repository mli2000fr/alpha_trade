# 17. Page ⚙️ Paramètres / Santé

## À quoi sert cette page

- Modifier les **paramètres** de chaque module (Risk, Selector, Screener,
  ML, Sentiment, Execution).
- Vérifier la **santé** des dépendances (DB, Alpaca, EODHD, providers
  divers).
- Voir les **diagnostics** environnement (version Python, versions des
  packages, place disque).

## Onglets

### a) Santé / Diagnostics

- 🟢 / 🔴 par dépendance
- versions Python / packages
- chemin du `.env` détecté
- chemin des artefacts
- usage disque

### b) Paramètres pipeline

Pour chaque module, les options modifiables sont regroupées. Toute
modification est sauvegardée dans `st.session_state` et utilisée au
prochain lancement.

> 💡 Les valeurs par défaut viennent de votre **preset de capital**. Les
> modifications ne sont pas persistées en YAML : pour cela, modifiez
> `config.yaml` ou `config/capital_presets.yaml`.

### c) Mode d'exécution global

Toggle `simulate` / `paper` / `live`. **C'est ici qu'on bascule en argent
réel.**

### d) Theme

Light / dark / auto.

## Conseils débutant

- Ne modifiez **jamais** les paramètres ML / Risk sans avoir lu la doc
  technique correspondante.
- Pour un micro-compte, laissez le preset `capital_0_2000` faire son
  travail et ne touchez à rien.

## Pour aller plus loin

- Liste exhaustive des options : `ihm/services/pipeline_runner.py`
  (`PipelineLaunchOptions`).

