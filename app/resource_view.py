"""Streamlit rendering for descriptive recorded resource analysis."""

import pandas as pd
import streamlit as st

from app.resource_analysis import WATER_FIELDS, analyze_resources

LABELS = {
    "water_total_source": "Recorded modelled water total",
    "water_component_1_source": "Recorded water component 1",
    "water_component_2_source": "Recorded water component 2",
    "water_component_3_source": "Recorded water component 3",
    "customer_source": "Customer",
    "fabric_type_source": "Fabric type",
    "vessel_type_source": "Recorded vessel type",
}


def render_resource_analysis(result, customers, fabrics, vessels):
    analysis = analyze_resources(result, customers=customers, fabrics=fabrics, vessels=vessels)
    st.subheader("Resource analysis")
    st.caption("All water values below use unresolved source units. Recorded vessel type "
               "(Open, Jet or Pressure) is a category, not a machine ID. "
               "Higher recorded consumption is not confirmed waste.")
    for title, summary in (("Overall imported case", analysis.overall), ("Filtered view", analysis.filtered)):
        st.subheader(f"{title} · {summary.order_count} orders")
        columns = st.columns(4)
        for column, field in zip(columns, (WATER_FIELDS[-1], *WATER_FIELDS[:3])):
            column.metric(f"{title}: {LABELS[field]}", f"{summary.totals[field]:,f}")
    st.caption("Filters select recorded orders; they do not recalculate sequence-dependent water. "
               "Overall totals always include the entire accepted import. "
               "Breakdowns and rankings below describe the filtered view.")
    for field, rows in analysis.filtered.groups.items():
        st.subheader(f"Breakdown by {LABELS[field].lower()}")
        frame = pd.DataFrame(rows, columns=[field, "order_count", *WATER_FIELDS])
        st.dataframe(frame, hide_index=True, width="stretch")
    st.subheader("Orders ranked by recorded modelled consumption")
    st.caption("Descending recorded total; ties use source row ID. Rank is within the filtered view. "
               "Each contribution is order total / overall imported case total × 100. "
               "Displayed percentages are rounded; a zero overall total has undefined shares.")
    if not analysis.filtered.ranked_orders:
        st.info("No orders match these filters. Filtered totals are zero; overall totals are unchanged.")
    else:
        frame = pd.DataFrame(analysis.filtered.ranked_orders)
        frame["overall_case_contribution_pct"] = frame["overall_case_contribution_pct"].map(
            lambda value: float(value) if value is not None else None
        )
        st.dataframe(frame, hide_index=True, width="stretch", column_config={
            "overall_case_contribution_pct": st.column_config.NumberColumn(
                "Contribution to overall case (%)", format="%.4f"
            ),
        })
    with st.expander("Source water-rule audit"):
        st.markdown("The source code uses fixed factors and sequence rules. One primary formula "
                    "yields the paper's manual total, but differs from twelve recorded order totals. "
                    "The authoritative version and reasons for those differences remain unresolved. "
                    "See **reports/source_rule_audit.md** for evidence and limitations. "
                    "This screen sums recorded fields; it does not run or correct the research model.")
