"""Authored classes and Streamlit's documented container-key CSS hooks only."""
from html import escape
import streamlit as st

CSS='''
<style>
.st-key-planner_dashboard {gap: 1rem;}
.st-key-dashboard_summary,.st-key-dashboard_setup,.st-key-dashboard_timeline,
.st-key-dashboard_change,.st-key-dashboard_review,.st-key-dashboard_counts,.st-key-recovery_summary,
.st-key-kpi_cleaning,.st-key-kpi_deadlines,.st-key-kpi_buffer {
  background:#fff; border:1px solid #DFE5ED; border-radius:14px;
  box-shadow:0 3px 14px rgba(20,36,59,.045); padding:1.15rem 1.3rem;
}
.st-key-dashboard_summary {border-left:5px solid #0F8A83;}
.st-key-kpi_cleaning {border-top:3px solid #0F8A83;}
.st-key-kpi_deadlines {border-top:3px solid #4D78AA;}
.st-key-kpi_buffer {border-top:3px solid #D69B32;}
.dc-eyebrow {font-size:.85rem;font-weight:650;letter-spacing:.035em;color:#526379;margin:0 0 .35rem;}
.dc-title {font-size:1.4rem;line-height:1.35;font-weight:700;color:#14243B;margin:0;overflow-wrap:anywhere;}
.dc-secondary {font-size:1rem;line-height:1.5;color:#526379;margin:.4rem 0 0;}
.dc-context {font-size:.95rem;color:#526379;margin:.1rem 0 .6rem;}
.dc-legend {display:flex;flex-wrap:wrap;gap:.5rem 1.2rem;color:#526379;font-size:.95rem;}
.dc-legend-item {display:flex;align-items:center;gap:.4rem;}
.dc-swatch {display:inline-block;width:12px;height:12px;border-radius:2px;}
/* Pinned Streamlit semantic caption hook; never style button/label paragraphs. */
.st-key-dashboard_review [data-testid="stCaptionContainer"],
.st-key-dashboard_change [data-testid="stCaptionContainer"],
.st-key-dashboard_timeline [data-testid="stCaptionContainer"],
.st-key-dashboard_setup [data-testid="stCaptionContainer"] {opacity:1;}
.st-key-dashboard_review [data-testid="stCaptionContainer"] p,
.st-key-dashboard_change [data-testid="stCaptionContainer"] p,
.st-key-dashboard_timeline [data-testid="stCaptionContainer"] p,
.st-key-dashboard_setup [data-testid="stCaptionContainer"] p {
  font-size:1rem;line-height:1.5;color:#526379;
}
/* The Workspace container is app-owned; no generated class names are used. */
.st-key-sidebar_navigation [role="radiogroup"] {gap:.3rem;}
.st-key-sidebar_navigation [role="radiogroup"] label {padding:.6rem .75rem;border-radius:9px;}
.st-key-sidebar_navigation [role="radiogroup"] label:has(input:checked) {
  background:#234C60;box-shadow:inset 3px 0 #53D0C5;
}
@media(max-width:700px) {
 .st-key-dashboard_summary,.st-key-dashboard_setup,.st-key-dashboard_timeline,
 .st-key-dashboard_change,.st-key-dashboard_review,.st-key-dashboard_counts,.st-key-recovery_summary,
 .st-key-kpi_cleaning,.st-key-kpi_deadlines,.st-key-kpi_buffer {padding:.85rem;}
 .dc-title {font-size:1.2rem;}
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
