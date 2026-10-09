"""Read-only FR operational preparation panel; no broker/SQL/launch service."""
import json

import streamlit as st

from service.fr.operations_preparation_18 import build_report, run_drills


def render_operations_preparation(page):
    with st.expander('Exploitation France — préparation uniquement (Sprint 18)', expanded=False):
        st.warning('LIVE désactivé. Sprint 17 clôturé avec réserves ; aucun ordre FR autorisé.')
        st.caption('Diagnostic local à la demande, pas un batch installé ni une surveillance active. '
                   'Les archives DEMO ne constituent pas un état de compte actuel.')
        try:
            report = build_report()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            st.error(f'Préparation indisponible : {type(exc).__name__}. Aucun repli US/CN ni autorisation.')
            return
        st.dataframe([{'Blocage': blocker, 'État': 'NON LEVÉ'} for blocker in report['blockers']],
                     hide_index=True, width='stretch')
        st.json({'Limites des exercices synthétiques uniquement': report['configured_synthetic_limits'],
                 'Preuves archivées': report['evidence']})
        st.code('python -m service.fr.operations_preparation_18 --phase audit', language='powershell')
        st.code('python -m service.fr.operations_preparation_18 --phase drills', language='powershell')
        if st.button('Exécuter les 17 scénarios hors ligne', key=f'fr18_{page}_drills'):
            try:
                drills = run_drills()
            except (OSError, ValueError, KeyError, TypeError):
                st.error('Exercices non exécutés : configuration de préparation invalide.')
            else:
                if drills['status'] == 'DRILLS_PASS_NOT_RELEASED':
                    st.success('17 scénarios synthétiques passent — aucun GO PAPER/LIVE.')
                else:
                    st.error('Échec d’exercice synthétique — aucune autorisation.')
                st.dataframe([{'Scénario': row['scenario'], 'Test': 'OK' if row['passed'] else 'ÉCHEC',
                               'Blocages simulés': ', '.join(row['reasons'])}
                              for row in drills['scenarios']], hide_index=True, width='stretch')
        st.download_button('Télécharger le diagnostic de préparation FR',
                           json.dumps(report, ensure_ascii=False, indent=2),
                           file_name='FR_EQ_preparation_S18_non_release.json', mime='application/json',
                           key=f'fr18_{page}_export')
