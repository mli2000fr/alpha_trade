"""Small progress view; independent of the expensive result/report panels."""
import math

import streamlit as st

from ihm.services.backtesting_registry import read_backtesting_progress


def render_backtesting_progress(record):
    progress = read_backtesting_progress(record)
    if not progress:
        if record.get('status') in ('starting', 'running'):
            st.caption('Démarrage du programme ; les premiers logs apparaîtront ici automatiquement.')
        return
    error = progress.get('error')
    if error:
        st.error(f"Motif de l’arrêt : {progress.get('error_type') or 'Erreur'} — {error}")
        if error == 'Empty or duplicate Oracle predictions':
            st.info('Les prédictions Oracle sont absentes ou dupliquées. Vérifiez ML Predict pour ce modèle '
                    'et les dates de signal nécessaires, dont la séance précédant la première entrée. '
                    'Le backtest ne génère pas de prédictions automatiquement.')
        return
    labels = {'READ_ONLY_INPUTS': 'Lecture des données et vérification des prédictions',
              'AUDIT_INTRADAY_COVERAGE': 'Vérification des bougies intraday',
              'RECOVER_INTRADAY': 'Récupération des bougies manquantes',
              'SIMULATION': 'Simulation des séances'}
    phase = labels.get(progress.get('phase'), 'Simulation des séances')
    try:
        done, total = float(progress.get('completed', 0)), float(progress.get('total', 0))
    except (ValueError, TypeError):
        done, total = 0., 0.
    if math.isfinite(total) and math.isfinite(done) and total > 0:
        detail = f"{phase} : {int(done)} / {int(total)}"
        if progress.get('last_date'):
            detail += f" — dernière séance : {progress['last_date']}"
        st.progress(min(1., max(0., done / total)), text=detail)
    else:
        st.caption(phase + '…')
