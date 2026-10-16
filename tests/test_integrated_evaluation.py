"""New evaluation definitions and offline gates, not live accuracy tests."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from copilot.planning_guard import local_decision
from copilot.planning_interpreter import make_request,interpret
from copilot.planning_contract import source_spans
from copilot.amd import AMDConfig
from planner.change_requests import preview_changes,apply_changes
from planner.recovery_solver import solve_option
from planner.recovery import verify_recovery
from tools.evaluate_interpreter_integrated import contexts,hashes,FREEZE,Diagnostics

ROOT=Path(__file__).resolve().parents[1]


class IntegratedEvaluationTests(unittest.TestCase):
    def test_fresh_corpus_frozen_local_and_deferred_amd_separately(self):
        corpus=json.loads((ROOT/'evaluation/planning_requests_integrated_v1.json').read_text(encoding='utf-8'))['cases']
        self.assertGreaterEqual(len(corpus),30)
        self.assertEqual(len({i['id'] for i in corpus}),len(corpus))
        self.assertEqual({i['split'] for i in corpus},{'development','held_out'})
        self.assertEqual(hashes(),json.loads(FREEZE.read_text(encoding='utf-8'))['files'])
        cases=contexts()
        for row in corpus:
            decision=local_decision(make_request(cases[row['context']],row['text']))
            if row['route']=='local':self.assertEqual(decision.status,row['status'],row['id'])
            else:self.assertIsNone(decision,row['id'])
        report=json.loads((ROOT/'reports/integrated_interpreter_offline_v1.json').read_text(encoding='utf-8'))
        self.assertEqual(report['semantic_amd_calls'],0);self.assertEqual(report['amd_summary']['n'],0)
        self.assertEqual(report['local_summary']['first_pass_correct'],report['local_summary']['n'])

    def test_mocked_amd_recovery_proposal_still_needs_confirmation_and_history_checks(self):
        corpus=json.loads((ROOT/'evaluation/planning_requests_integrated_v1.json').read_text(encoding='utf-8'))['cases']
        case=contexts()['recovery']
        for key in ('h09','h23'):
            row=next(i for i in corpus if i['id']==key)
            request=make_request(case,row['text']);span=source_spans(request)[0]['clause_id']
            content=json.dumps({'status':'ready','changes':[{**row['changes'][0],'clause_id':span}],
                'clarification_questions':[],'unsupported_reasons':[]})
            with patch('copilot.planning_interpreter.request_completion',return_value=(content,
                {'origin':'mock','actual_model':None,'outcome':'offline injected completion'})):
                answer=interpret(request,config=AMDConfig('test-only','https://developer.amd.com.cn/radeon/api/v1','test-only'))
            before=case.fingerprint
            self.assertEqual(answer.receipt['origin'],'mock')
            if row['application']=='history_conflict':
                with self.assertRaisesRegex(ValueError,'Interrupted-batch'):preview_changes(case,answer)
            else:
                self.assertTrue(preview_changes(case,answer));self.assertEqual(before,case.fingerprint)
                updated=apply_changes(case,answer);run=solve_option(updated,'fewer_cleanings',budget_seconds=2)
                self.assertTrue(verify_recovery(updated.orders,updated.config,run.schedule,updated.recovery).valid)
            self.assertEqual(before,case.fingerprint)

    def test_diagnostics_suppress_whole_secret_payload(self):
        corpus=json.loads((ROOT/'evaluation/planning_requests_integrated_v1.json').read_text(encoding='utf-8'))['cases']
        item=corpus[0];request=make_request(contexts()[item['context']],item['text'])
        diag=Diagnostics(corpus)
        diag.capture(request,'secret-test-value',{'origin':'mock'},None,'secret-test-value')
        self.assertIsNone(diag.records[0]['content']);self.assertIsNone(diag.records[0]['receipt'])
        self.assertEqual(diag.records[0]['credential_screen'],'payload_suppressed')
        with self.assertRaises(ValueError):diag.capture(make_request(contexts()['full'],'unlisted text'),'{}',{},None,'')

    def test_permission_subset_reconciliation_no_hidden_baseline_fallback(self):
        manifest=json.loads((ROOT/'evaluation/permission_sensitivity_integrated_v1.json').read_text(encoding='utf-8'))
        rows=json.loads((ROOT/'reports/permission_sensitivity_integrated_v1.json').read_text(encoding='utf-8'))['rows']
        all_rules=manifest['scenarios'][2]['permissions']
        self.assertEqual(manifest['scenarios'][1]['permissions'],all_rules[::2])
        self.assertFalse(manifest['scenarios'][0]['active'])
        self.assertEqual(len(rows),3)
        for row in rows:
            if row['comparison']:
                self.assertTrue(row['baseline_verified'] and row['solver_verified'])
                for side in ('baseline','proposal'):
                    counts=row['comparison']['cleaning_counts'][side]
                    self.assertEqual(counts['total'],counts['initial']+counts['between_orders']+counts['terminal'])
                self.assertTrue(row['cost_rescaling_only']['cleaning_events_unchanged'])


if __name__=='__main__':unittest.main()
