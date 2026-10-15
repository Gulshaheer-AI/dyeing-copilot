from ui_helpers import click as ui_click
import unittest
from datetime import timedelta
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from copilot.planning_manual import manual_proposal
from test_interface import APP
from legacy_ui import select_legacy
from planner.comparators import compare_methods
from planner.change_requests import digest


class SchedulingComparatorInterfaceTests(unittest.TestCase):
    def test_headline_partial_grouping_compact_sequence_and_effective_override(self):
        app=AppTest.from_file(APP).run(timeout=40)
        def click(label):
            ui_click(app,label)
        click('Batch scheduling simulator')
        select_legacy(app)
        click('Load demo setup')
        click('Run scenario comparison')
        self.assertFalse(app.exception)
        self.assertTrue(any(s.value=='4. What changed?' for s in app.subheader))
        self.assertTrue(any('EDD comparison resource detail' in e.label for e in app.expander))
        case=app.session_state['planning_case']
        report=compare_methods(case.orders,case.config).report
        self.assertTrue(report['methods']['edd']['eligible_for_comparison'])
        self.assertFalse(report['methods']['grouping']['eligible_for_comparison'])
        self.assertFalse(any('Grouping' in b.label for b in app.selectbox))
        self.assertFalse(any(s.label=='Inspect machine sequence changes against' for s in app.selectbox))
        original_fp=report['effective_case_fingerprint']
        case=app.session_state['planning_case']
        next(r for r in app.radio if r.label=='Constraint entry').set_value('Manual controls').run(timeout=40)
        # Insert a legitimate form-origin preview, then exercise the shared UI apply.
        app.session_state['planning_manual_proposal']=manual_proposal(case, operation='order_deadline', identifier='12',
            deadline=case.orders[11].release+timedelta(hours=1))
        app.run(timeout=40)
        click('Apply changes and reschedule')
        self.assertFalse(app.exception)
        changed=app.session_state['planning_case']
        new=compare_methods(changed.orders,changed.config).report
        self.assertNotEqual(new['effective_case_fingerprint'],original_fp)
        self.assertFalse(new['methods']['edd']['eligible_for_comparison'])
        self.assertFalse(new['optimiser_against']['edd']['eligible'])
        self.assertTrue(any('No feasible baseline' in e.value for e in app.error))
        click('Reset to original scenario and reschedule')
        restored=app.session_state['planning_case']
        self.assertEqual(digest({'orders':restored.orders,'config':restored.config}),original_fp)

