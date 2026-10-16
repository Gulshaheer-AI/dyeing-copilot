"""Read-only versioned evaluation evidence; never runs an evaluation on navigation."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]


def render_evaluation_evidence(case):
    with st.expander('Evidence: permission sensitivity and interpretation limits'):
        manifest=ROOT/'evaluation/permission_sensitivity_integrated_v1.json'
        result=ROOT/'reports/permission_sensitivity_integrated_v1.json'
        if not manifest.exists() or not result.exists():
            st.info('Offline sensitivity evidence is not available in this installation. No result is invented.')
            return
        definition=json.loads(manifest.read_text(encoding='utf-8'))
        if definition['source_sha256']!=case.source_sha256:
            st.info('Bundled-case sensitivity results do not evaluate these uploaded orders.')
            return
        evidence=json.loads(result.read_text(encoding='utf-8'))
        rows=[]
        for row in evidence['rows']:
            comparison=row['comparison']
            rows.append({'Permission scenario':row['id'],'Verified comparison':comparison is not None,
                'Deadline-first cleanings':comparison['cleaning_counts']['baseline']['total'] if comparison else None,
                'CP-SAT cleanings':comparison['cleaning_counts']['proposal']['total'] if comparison else None,
                'On time':row['selected_deadlines']['on_time'] if row['selected_deadlines'] else None,
                'Stage A':row['stage_a']['status'],'Stage B':row['stage_b']['status']})
        st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
        st.caption('Offline scenarios from one published case, not independent factory trials or this recovery plan. Restricted permissions are every other existing permission in documented sorted order. No new permission is invented.')
        st.write('Per-cleaning cost only rescales the secondary resource score; it does not change the cleaning-count or deadline-buffer objectives.')
        st.write('The new interpretation corpus contains 34 authored requests. Local screening and AMD interpretation are evaluated separately; live evaluation requires an explicit command and is not run from this screen.')
