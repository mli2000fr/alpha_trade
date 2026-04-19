"""ihm/components/tables.py — Helpers pour afficher des DataFrames."""
from __future__ import annotations

import pandas as pd
import streamlit as st


def show_dataframe(df: pd.DataFrame, title: str | None = None, height: int = 400) -> None:
    """Affiche un DataFrame ou un message vide."""
    if title:
        st.subheader(title)
    if df.empty:
        st.info("Aucune donnée disponible.")
    else:
        st.dataframe(df, width="stretch", height=height)


