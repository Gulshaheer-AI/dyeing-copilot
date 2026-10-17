"""Run with: .venv/Scripts/python.exe -m streamlit run streamlit_app.py"""
import pandas as pd
import streamlit as st
from app.importer import import_orders,load_bundled_orders
from app.resource_view import render_resource_analysis
from app.simulator_view import render_simulator
from app.copilot_view import render_copilot
from app.daily_view import render_daily
from app.dashboard_style import install_dashboard_style,context_note

st.set_page_config(page_title='Dyeing Copilot',layout='wide')
install_dashboard_style()
st.title('Dyeing Copilot')
context_note('Plan dyeing batches, reduce cleaning and respond to production changes.')
if st.session_state.get('pending_view'):
    st.session_state.view=st.session_state.pop('pending_view')
# Preserve existing links from synthetic monitoring into the global copilot.
if st.session_state.pop('daily_open',False):st.session_state.view='Daily resource monitoring'
labels={'Scheduling simulator':'Production planner','Orders':'Orders',
    'Resource analysis':'Source data / resource analysis','Daily resource monitoring':'Synthetic resource monitoring',
    'Copilot':'Copilot & supervisor review','Plan history':'Plan history'}
with st.sidebar:
    with st.expander('Order import',expanded=False):
        mode=st.radio('Import source',['Bundled Sitara case','Upload Sitara CSV'])
        uploaded=st.file_uploader('Choose the text-derived Sitara CSV',type=['csv']) if mode=='Upload Sitara CSV' else None
        st.caption('Uploads replace the case and use the same 35-order validation contract.')
    with st.container(key='sidebar_navigation'):
        view=st.radio('Workspace',['Orders','Resource analysis','Scheduling simulator','Copilot','Daily resource monitoring','Plan history'],
            index=2,key='view',format_func=labels.get)
previous_view=st.session_state.get('last_workspace')
st.session_state.last_workspace=view
if view=='Plan history':
    from app.plan_history_view import render_plan_history,retain_planner_widgets,pause_planner_controls
    if previous_view!='Plan history':pause_planner_controls(st.session_state)
    retain_planner_widgets(st.session_state)
    render_plan_history()
    st.stop()
if view=='Scheduling simulator' and '_history_paused_controls' in st.session_state:
    from app.plan_history_view import resume_planner_controls
    resume_planner_controls(st.session_state)
if view=='Copilot' and previous_view=='Daily resource monitoring' and st.session_state.get('daily_context'):
    st.session_state.copilot_requested_topic='Explain selected synthetic resource day'
if view=='Daily resource monitoring':
    render_daily()
    st.stop()
if mode=='Upload Sitara CSV':
    if uploaded is None:st.info('Choose a CSV in Order import to validate and display.');st.stop()
    result=import_orders(uploaded.getvalue(),uploaded.name)
    st.caption('Uploaded copy · values not authenticated against the published source')
else:
    try:result=load_bundled_orders()
    except (OSError,ValueError,KeyError) as exc:
        st.error(f'Cannot load bundled orders or integrity manifest: {exc}');st.stop()
errors=sum(i['severity']=='error' for i in result.issues)
with st.sidebar.expander('Data quality and provenance',expanded=not result.valid):
    cols=st.columns(2)
    cols[0].metric('Accepted orders',len(result.records));cols[1].metric('Errors',errors)
    st.caption(f'{len(result.issues)-errors} warnings · {result.duplicates_removed} repeats removed · {result.filename}')
    st.code('SHA256: '+result.sha256,language=None)
    st.caption('Published Sitara orders. Vessel type is a category, not a machine ID. Source units remain unresolved.')
    for issue in result.issues:st.caption(str(issue))
if not result.valid:
    st.error('Import rejected. Fix the listed CSV lines and fields; no partial records can be planned.');st.stop()
if view=='Copilot':render_copilot(result);st.stop()
if view=='Scheduling simulator':
    with st.container(key='planner_dashboard'):render_simulator(result)
    st.stop()
df=pd.DataFrame(result.records)
st.subheader("Orders" if view == "Orders" else "Filter recorded orders")
customers = st.multiselect("Customer", sorted(df["customer_source"].unique()))
fabrics = st.multiselect("Fabric", sorted(df["fabric_type_source"].unique()))
vessels = st.multiselect("Recorded vessel type (not machine ID)", sorted(df["vessel_type_source"].unique()))
visible = df
if customers:
    visible = visible[visible["customer_source"].isin(customers)]
if fabrics:
    visible = visible[visible["fabric_type_source"].isin(fabrics)]
if vessels:
    visible = visible[visible["vessel_type_source"].isin(vessels)]
if view == "Resource analysis":
    render_resource_analysis(result, customers, fabrics, vessels)
else:
    st.caption(f"Showing {len(visible)} of {len(df)} orders. Source spellings and values are preserved. "
               "Parsed dates appear separately in ISO format (YYYY-MM-DD).")
    st.dataframe(visible, hide_index=True, width="stretch")

    st.subheader("Order detail")
    if visible.empty:
        st.info("No orders match these filters.")
    else:
        selected = st.selectbox("Source row ID", visible["source_row_id"].tolist())
        detail = visible[visible["source_row_id"] == selected].iloc[0]
        st.table(pd.DataFrame({"Field": detail.index, "Value": [str(value) for value in detail.values]}))

with st.expander("Provenance and limitations"):
    st.markdown(
        "Source: **Sitara Faisalabad**, 35 text-derived order records from the supplement to "
        "*An evolutionary algorithm for multi-objective optimization of freshwater consumption "
        "in textile dyeing industry*, Elahi et al., PeerJ Computer Science (2022), e932. "
        "[Article](https://doi.org/10.7717/peerj-cs.932) · "
        "[Supplement](https://doi.org/10.7717/peerj-cs.932/supp-1). "
        "CC BY per archived article metadata. Archive access: NCBI/NLM; no endorsement implied.\n\n"
        "The original text has 70 records containing a repeated block of 35. "
        "Workbook variants are alternative versions, not extra independent orders. "
        "Source group IDs identify groups, not unique orders; source row IDs provide record identity. "
        "The unchanged bundled source water-total sum is **47,950 in unresolved source units**. "
        "This differs from the paper's manual example and does not establish savings or reproduction "
        "of the paper. The records do not support a measured-consumption training claim.\n\n"
        "The importer reads files without modifying the dataset pack. See "
        "`dyeing_dataset_pack/README.md` and `dataset_inventory.json` for the audit and licences."
    )
