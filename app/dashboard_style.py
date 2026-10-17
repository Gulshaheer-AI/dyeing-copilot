"""Authored classes and Streamlit's documented container-key CSS hooks only."""
from html import escape
import streamlit as st

CSS='''
<style>
.dc-app-header {background:#185681;border-bottom:3px solid #0F8A83;border-radius:10px;padding:.85rem 1.2rem;margin-bottom:1rem;color:white;}
.dc-app-name {font-size:1.5rem;font-weight:700;margin:0;color:white;}
.dc-app-tagline {font-size:1rem;margin:.2rem 0 0;color:#EEF7FF;}
.st-key-planner_dashboard {gap:.85rem;}
.st-key-dashboard_summary,.st-key-dashboard_setup,.st-key-dashboard_timeline,
.st-key-dashboard_change,.st-key-dashboard_review,.st-key-dashboard_counts,.st-key-recovery_summary,
.st-key-kpi_cleaning,.st-key-kpi_deadlines,.st-key-kpi_buffer,.st-key-reports_current,.st-key-reports_archive,
.st-key-orders_panel,.st-key-history_panel {
 background:#fff;border:1px solid #D5DEE8;border-radius:10px;
 box-shadow:0 2px 6px rgba(20,36,59,.035);padding:1rem 1.15rem;
}
.st-key-dashboard_summary {border-left:4px solid #0F8A83;}
.st-key-kpi_cleaning {border-top:3px solid #0F8A83;}
.st-key-kpi_deadlines {border-top:3px solid #3077A4;}
.st-key-kpi_buffer {border-top:3px solid #B57F22;}
.st-key-dashboard_setup .dc-title {color:#185681;}
.st-key-dashboard_setup [data-testid="stCaptionContainer"],
.st-key-dashboard_review [data-testid="stCaptionContainer"],
.st-key-dashboard_change [data-testid="stCaptionContainer"],
.st-key-dashboard_timeline [data-testid="stCaptionContainer"],
.st-key-history_panel [data-testid="stCaptionContainer"],
.st-key-reports_current [data-testid="stCaptionContainer"],
.st-key-reports_archive [data-testid="stCaptionContainer"] {opacity:1;color:#425971;}
.st-key-dashboard_setup [data-testid="stCaptionContainer"] p,
.st-key-dashboard_review [data-testid="stCaptionContainer"] p,
.st-key-dashboard_change [data-testid="stCaptionContainer"] p,
.st-key-dashboard_timeline [data-testid="stCaptionContainer"] p {font-size:1rem;color:#425971;}
.dc-eyebrow {font-size:.9rem;font-weight:650;color:#236181;margin:0 0 .35rem;}
.dc-title {font-size:1.3rem;line-height:1.35;font-weight:700;color:#14243B;margin:0;overflow-wrap:anywhere;}
.dc-secondary {font-size:1rem;line-height:1.5;color:#425971;margin:.4rem 0 0;}
.dc-context {font-size:1rem;color:#425971;margin:.1rem 0 .6rem;}
.dc-legend {display:flex;flex-wrap:wrap;gap:.5rem 1.2rem;color:#425971;font-size:.95rem;}
.dc-legend-item {display:flex;align-items:center;gap:.4rem;}
.dc-swatch {display:inline-block;width:12px;height:12px;border-radius:2px;}
.st-key-sidebar_navigation [role="radiogroup"] {gap:.45rem;align-items:stretch;}
.st-key-sidebar_navigation [role="radiogroup"] label {
 width:100%;padding:.7rem .8rem;border:1px solid #CDD9E6;background:#fff;border-radius:8px;min-height:48px;
}
.st-key-sidebar_navigation [role="radiogroup"] label:has(input:checked) {
 background:#DFEEF6;border-color:#2D739E;box-shadow:inset 3px 0 #0F8A83;
}
.st-key-dashboard_setup h3,.st-key-dashboard_timeline h3,.st-key-dashboard_change h3,
.st-key-dashboard_review h3,.st-key-history_panel h3,.st-key-reports_current h3,.st-key-reports_archive h3 {color:#185681;}
@media(max-width:700px) {
 .st-key-dashboard_summary,.st-key-dashboard_setup,.st-key-dashboard_timeline,
 .st-key-dashboard_change,.st-key-dashboard_review,.st-key-dashboard_counts,.st-key-recovery_summary,
 .st-key-kpi_cleaning,.st-key-kpi_deadlines,.st-key-kpi_buffer,.st-key-orders_panel,
 .st-key-history_panel,.st-key-reports_current,.st-key-reports_archive {padding:.8rem;}
 .dc-title {font-size:1.15rem;}
}
</style>
'''



def install_dashboard_style():
    st.html(CSS)


def panel_heading(title,subtitle='',eyebrow=''):
    """All dynamic text is escaped; no model/source content becomes markup."""
    content=(f'<p class="dc-eyebrow">{escape(str(eyebrow))}</p>' if eyebrow else '')
    content+=f'<p class="dc-title">{escape(str(title))}</p>'
    if subtitle:content+=f'<p class="dc-secondary">{escape(str(subtitle))}</p>'
    st.html(content)


def context_note(text):
    st.html(f'<p class="dc-context">{escape(str(text))}</p>')


def application_header():
    st.html('<header class="dc-app-header"><p class="dc-app-name">Dyeing Copilot</p>'
            '<p class="dc-app-tagline">Production planning | Changes and recovery | Review and reports</p></header>')
