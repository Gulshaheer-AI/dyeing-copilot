from ui_helpers import click as ui_click
import json
import tempfile
import unittest
from datetime import date
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from copilot.reviews import ReviewStore
from copilot.amd import AMDConfig
from copilot.selected_evidence import build_selected_evidence
from copilot.selected_reviews import applicable_review
from app.cp_sat_view import export_backend
from test_interface import APP
from test_planning_requests import fixture


class SelectedCopilotInterfaceTests(unittest.TestCase):
    def test_manual_and_mocked_amd_preview_apply_solve_explain_review_export_reset(self):
        with tempfile.TemporaryDirectory() as directory, patch('app.selected_copilot_view.ReviewStore',side_effect=lambda:ReviewStore(Path(directory)/'review.db')):
            app=AppTest.from_file(APP).run(timeout=40)
            def click(label):ui_click(app,label)
            def select(label,value):next(s for s in app.selectbox if s.label==label).set_value(value).run(timeout=40)
            click('Batch scheduling simulator');click('Load demo setup');click('Generate schedule')
            original=app.session_state['planning_case']
            marker,run=app.session_state['sim_cp_result']
            app.session_state['sim_cp_result']=(marker,replace(run,cp_sat=replace(run.cp_sat,version='cp-sat-dyeing-v1')))
            app.run(timeout=40)
            self.assertEqual(app.session_state['sim_cp_result'][1].cp_sat.version,'cp-sat-dyeing-v2-slack-guard')
            next(r for r in app.radio if r.label=='Constraint entry').set_value('Manual controls').run(timeout=40)
            select('Order ID','12')
            next(d for d in app.date_input if d.label=='Deadline date').set_value(date(2019,12,23))
            click('Preview manual change')
            self.assertEqual(app.session_state['planning_case'],original)
            click('Apply changes and reschedule')
            self.assertFalse(app.exception)
            case=app.session_state['planning_case'];marker,run=app.session_state['sim_cp_result']
            self.assertTrue(run.cp_sat.verification.valid)
            self.assertEqual(case.history[-1]['receipt']['origin'],'manual')
            next(r for r in app.radio if r.label=='Selected schedule explanation source').set_value('Mock demonstration (no API call)').run(timeout=40)
            click('Explain this plan');click('Save for supervisor review')
            click('Record review decision')
            click('Save for supervisor review')
            self.assertTrue(any('Existing review retained as Accepted for further review' in i.value for i in app.info))
            self.assertFalse(app.exception)
            store=ReviewStore(Path(directory)/'review.db');row=store.list_reviews()[0]
            bundle=json.loads(row['evidence_json'])
            record=applicable_review(store,bundle,row['id'])
            export=json.loads(export_backend(case,run,bundle=bundle,review=record))
            self.assertEqual(export['review_status'],'accepted_for_further_review')
            self.assertEqual(export['applicable_review']['receipt_json']['origin'],'mock')
            click('Reset to original scenario and reschedule')
            self.assertEqual(app.session_state['planning_case'].orders,original.orders)
            self.assertTrue(any('STALE evidence' in w.value for w in app.markdown))
            self.assertTrue(next(b for b in app.button if b.label=='Record review decision').disabled)
            reset=app.session_state['planning_case']
            next(r for r in app.radio if r.label=='Constraint entry').set_value('AMD request').run(timeout=40)
            text='Change order 12 deadline to 2019-12-24T18:15.'
            next(t for t in app.text_area if t.label=='Describe an outage or explicit deadline change').set_value(text).run(timeout=40)
            answer=fixture(reset,text,[{'operation':'order_deadline','order_id':'12','deadline':'2019-12-24T18:15'}])
            with patch('app.planning_changes_view.interpret',return_value=answer), patch('app.planning_changes_view.load_config',
                    return_value=AMDConfig('offline-test-key','https://developer.amd.com.cn/radeon/api/v1','test-model')):
                app.run(timeout=40)
                click('Interpret planning request with AMD')
                self.assertEqual(app.session_state['planning_case'],reset)
                click('Apply changes and reschedule')
            self.assertTrue(app.session_state['sim_cp_result'][1].cp_sat.verification.valid)
            click('Explain this plan')
            click('Save for supervisor review')
            self.assertFalse(app.exception)
            self.assertEqual(store.list_reviews()[0]['status'],'pending_review')
            click('Copilot and supervisor review')
            select('Question topic','Explain selected schedule')
            self.assertFalse(app.exception)
            self.assertTrue(any(b.label=='Explain this plan' for b in app.button))

