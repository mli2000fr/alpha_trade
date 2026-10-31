"""Copyable standalone restore command, with no embedded credentials."""
import streamlit as st

from ihm.services.migration_runner import build_restore_command


def render_restore_command(folder,*,pending=False):
    if not str(folder).strip():return
    st.markdown('**Restaurer depuis PowerShell, sans l’IHM**')
    try:st.code(build_restore_command(folder),language='powershell')
    except ValueError as exc:st.error(str(exc));return
    st.caption('Copier cette commande sur le PC cible. Après déplacement de la sauvegarde, adapter le chemin du script. Les mots de passe et la confirmation seront demandés dans le terminal ; aucun secret n’est inclus dans la commande.')
    if pending:st.caption('À utiliser après la création et la copie complète des packages.')
