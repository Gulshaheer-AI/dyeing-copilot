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
from app.dashboard_style import application_header
application_header()
main_modules=['Scheduling simulator','Orders','Plan history','Reports','More tools']
tools={'Resource analysis':'Source data / resource analysis','Daily resource monitoring':'Synthetic resource monitoring',
       'Copilot':'Copilot & supervisor review'}
if st.session_state.get('pending_view'):
    st.session_state.view=st.session_state.pop('pending_view')
if st.session_state.pop('daily_open',False):st.session_state.view='Daily resource monitoring'
if st.session_state.get('view') in tools:
    st.session_state.more_tool=st.session_state.view
    st.session_state.view='More tools'
if 'more_tool' not in st.session_state:st.session_state.more_tool=st.session_state.get('more_tool_saved','Resource analysis')
labels={'Scheduling simulator':'Production planner'}
with st.sidebar:
    st.caption('MODULE MENU')
    with st.container(key='sidebar_navigation'):
        module=st.radio('Workspace',main_modules,index=0,key='view',format_func=lambda v:labels.get(v,v))
        if module=='More tools':
            view=st.selectbox('More tools',list(tools),format_func=tools.get,key='more_tool')
            st.session_state.more_tool_saved=view
        else:view=module
    with st.expander('Dataset / upload',expanded=False):
        mode=st.radio('Import source',['Bundled Sitara case','Upload Sitara CSV'],key='order_import_mode')
        uploaded=st.file_uploader('Choose the text-derived Sitara CSV',type=['csv'],key='order_import_file') if mode=='Upload Sitara CSV' else None
        st.caption('Uploads replace the case and use the same 35-order validation contract.')
previous_view=st.session_state.get('last_workspace')
st.session_state.last_workspace=view
# Reuse the history pause/resume mechanism for every module. No archive is restored.
from app.plan_history_view import retain_planner_widgets,pause_planner_controls,resume_planner_controls
if view!='Scheduling simulator':
    if previous_view=='Scheduling simulator':pause_planner_controls(st.session_state)
    retain_planner_widgets(st.session_state)
elif '_history_paused_controls' in st.session_state:resume_planner_controls(st.session_state)
if view=='Scheduling simulator':retain_planner_widgets(st.session_state)
if view=='Scheduling simulator' and 'pending_planner_tab' in st.session_state:
    st.session_state.planner_result_tabs=st.session_state.pop('pending_planner_tab')
if view=='Plan history':
    from app.plan_history_view import render_plan_history
    with st.container(key='history_panel'):render_plan_history()
    st.stop()
if view=='Copilot' and previous_view=='Daily resource monitoring' and st.session_state.get('daily_context'):
    st.session_state.copilot_requested_topic='Explain selected synthetic resource day'
if view=='Daily resource monitoring':
    render_daily()
    st.stop()
if mode=='Upload Sitara CSV':
    if uploaded is None:st.info('Choose a CSV in Dataset / upload to validate and display.');st.stop()
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
if view=='Reports':
    from app.reports_view import render_reports
    render_reports(result)
    st.stop()
if view=='Copilot':render_copilot(result);st.stop()
if view=='Scheduling simulator':
    with st.container(key='planner_dashboard'):render_simulator(result)
    st.stop()
df=pd.DataFrame(result.records)
st.subheader("Orders" if view == "Orders" else "Filter recorded orders")
st.caption('Published order records ? Recorded vessel category is not a machine assignment.')
with st.container(horizontal=True,wrap=True):
    customers=st.multiselect('Customer',sorted(df.customer_source.unique()),key='orders_customer',width=260)
    fabrics=st.multiselect('Fabric',sorted(df.fabric_type_source.unique()),key='orders_fabric',width=260)
    vessels=st.multiselect('Recorded vessel type',sorted(df.vessel_type_source.unique()),key='orders_vessel',width=260)
visible=df
if customers:visible=visible[visible.customer_source.isin(customers)]
if fabrics:visible=visible[visible.fabric_type_source.isin(fabrics)]
if vessels:visible=visible[visible.vessel_type_source.isin(vessels)]
if view == "Resource analysis":
    render_resource_analysis(result, customers, fabrics, vessels)
else:
    st.caption(f"Showing {len(visible)} of {len(df)} orders. Source spellings and values are preserved. "
               "Parsed dates appear separately in ISO format (YYYY-MM-DD).")
    columns={'source_row_id':'Order ID','customer_source':'Customer','fabric_type_source':'Fabric',
        'fabric_specification_source':'Specification','shade_source':'Shade','cloth_length_source':'Cloth length (source unit)',
        'vessel_type_source':'Recorded vessel type','order_date_source':'Order date (source)','delivery_date_source':'Delivery date (source)'}
    with st.container(key='orders_panel'):
        st.dataframe(visible[list(columns)].rename(columns=columns),hide_index=True,width='stretch')
        with st.expander('All recorded fields and parsed dates'):st.dataframe(visible,hide_index=True,width='stretch')

    st.subheader("Order detail")
    if visible.empty:
        st.info("No orders match these filters.")
    else:
        selected = st.selectbox("Source row ID", visible["source_row_id"].tolist(),key="orders_selected")
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
