"""Selected-only empty numeric contract; shared grounding remains fail closed."""
import copy
import json
import unittest
from unittest.mock import patch

from copilot.selected_evidence import build_selected_evidence
from copilot.selected_workflow import explain_selected,selected_messages,SelectedExplanationRejected
from copilot.workflow import Explanation,validate_output
from planner.backend import run_backend
from planner.change_requests import PlanningCase
from test_scheduler import tiny_case


class SelectedNumericContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        orders,config=tiny_case(enabled=False)
        case=PlanningCase('0'*64,'synthetic contract test',orders,config,config)
        run=run_backend(orders,config,budget_seconds=2,case_fingerprint=case.fingerprint)
        cls.bundle=build_selected_evidence(case,run,'Explain order 1')
        cls.payload=explain_selected(cls.bundle,'Explain order 1',mode='mock').output.model_dump()

    def respond(self,payload):
        with patch('copilot.selected_workflow.request_completion',return_value=(json.dumps(payload),
                {'origin':'mock','actual_model':'test-only','outcome':'mocked_completion'})):
            return explain_selected(self.bundle,'Explain order 1',config=object())

    def test_model_facing_schema_requires_exact_empty_list(self):
        messages=selected_messages(self.bundle,'Explain order 1')
        schema=json.loads(messages[1]['content'])['schema']
        self.assertIn('quantitative_claims',schema['required'])
        field=schema['properties']['quantitative_claims']
        self.assertEqual((field['minItems'],field['maxItems']),(0,0))
        self.assertIn('must be exactly []',messages[0]['content'])
        self.assertEqual(Explanation.model_json_schema()['properties']['quantitative_claims']['maxItems'],20)
        answer=self.respond(self.payload)
        self.assertEqual(answer.output.quantitative_claims,[])
        self.assertEqual(answer.output.explanation[0].text,self.payload['explanation'][0]['text'])

    def test_original_numeric_conversion_failure_is_rejected_not_discarded(self):
        payload=copy.deepcopy(self.payload)
        payload['quantitative_claims']=[{'fact_id':'fact:selected.minimum_slack','value':'1','unit':'litres'}]
        with self.assertRaisesRegex(ValueError,'unsupported numeric fact or unit conversion'):
            validate_output(json.dumps(payload),self.bundle)
        with self.assertRaisesRegex(SelectedExplanationRejected,'exactly') as caught:
            self.respond(payload)
        self.assertEqual(caught.exception.receipt['validation'],'rejected')
        self.assertEqual(caught.exception.receipt['origin'],'mock')

    def test_even_supported_numeric_copy_is_rejected_only_in_selected_workflow(self):
        payload=copy.deepcopy(self.payload)
        ref='fact:selected.minimum_slack'
        fact=self.bundle['facts'][ref]
        payload['evidence_references'].append(ref)
        payload['quantitative_claims']=[{'fact_id':ref,'value':str(fact['value']),'unit':fact['unit']}]
        self.assertEqual(len(validate_output(json.dumps(payload),self.bundle).quantitative_claims),1)
        with self.assertRaises(SelectedExplanationRejected):self.respond(payload)
        del payload['quantitative_claims']
        with self.assertRaises(SelectedExplanationRejected):self.respond(payload)

    def test_empty_numeric_list_does_not_bypass_other_grounding(self):
        mutations=(lambda p:p['explanation'][0].update(text='Unsupported explanation'),
            lambda p:p['explanation'][0].update(evidence_references=['fact:invented']),
            lambda p:p['evidence_references'].append('fact:invented'),
            lambda p:p.update(assumptions=['invented']),
            lambda p:p.update(limitations=['not_sops','no_factory_approval','limited_scope','invented']),
            lambda p:p['explanation'].pop())
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                payload=copy.deepcopy(self.payload);mutate(payload)
                with self.assertRaises(SelectedExplanationRejected):self.respond(payload)


if __name__=='__main__':unittest.main()
