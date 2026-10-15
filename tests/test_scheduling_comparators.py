import hashlib
from preservation import preserved_sha
import json
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from app.importer import load_bundled_orders
from planner.comparators import compare_methods, grouping_priority, summarise
from planner.search import build_schedule, plan
from planner.scenario import demo_config, orders_from_import
from copilot.planning_manual import manual_proposal
from planner.change_requests import initial_case, apply_changes
from tools.benchmark_scheduling import instantiate, aggregate
from test_scheduler import tiny_case

ROOT = Path(__file__).resolve().parents[1]


class SchedulingComparatorTests(unittest.TestCase):
    def test_preservation(self):
        for name, sha in json.loads((ROOT / 'reports/milestone_9_preservation_baseline.json').read_text()).items():
            self.assertEqual(preserved_sha(ROOT, name), sha, name)

    def test_grouping_deterministic_no_colour_depth_or_extra_permissions(self):
        orders, config = tiny_case(enabled=False)
        expected = tuple(sorted(orders, key=lambda o: (o.vessel, o.fabric, o.shade, o.deadline, int(o.order_id))))
        self.assertEqual(grouping_priority(tuple(reversed(orders))), expected)
        report = compare_methods(orders, config).report
        for row in report['methods'].values():
            self.assertTrue(row['eligible_for_comparison'])
            self.assertEqual(row['cleaning_counts'], {'initial':1, 'between_orders':2, 'terminal':1, 'total':4})
            self.assertEqual(row['deadline_performance']['on_time'], 3)
            self.assertGreaterEqual(row['runtime_seconds'], 0)
        self.assertEqual(report['optimiser_against']['grouping']['cleaning_events_difference'], 0)

    def test_accounting_reconciles_all_boundaries_and_slack(self):
        orders, config = tiny_case()
        report = compare_methods(orders, config).report
        for row in report['methods'].values():
            counts = row['cleaning_counts']
            self.assertEqual(counts['initial'] + counts['between_orders'] + counts['terminal'], counts['total'])
            self.assertEqual(row['resource']['cleaning_events'], counts['total'])
            self.assertEqual(row['slack_hours']['minimum'], min(r['slack_hours'] for r in row['deadline_performance']['orders']))
        for name, difference in report['optimiser_against'].items():
            self.assertTrue(difference['eligible'])
            self.assertEqual(difference['cleaning_events_difference'], report['methods'][name]['cleaning_counts']['total'] - report['methods']['optimiser']['cleaning_counts']['total'])
            self.assertTrue(difference['transition_comparison']['reconciliation']['passed'])
        config = replace(config, terminal_cleaning=False, machines=(replace(config.machines[0], initially_clean=True),))
        report = compare_methods(orders, config).report
        self.assertTrue(all(r['cleaning_counts']['initial'] == r['cleaning_counts']['terminal'] == 0 for r in report['methods'].values()))

    def test_failed_grouping_is_not_replaced_with_valid_edd(self):
        orders, config = tiny_case(enabled=False)
        # Force grouping's last category to contain an early deadline, whereas EDD
        # can complete it first. This is an internal synthetic accounting test.
        orders = tuple(replace(o, shade='Z' if i == 0 else 'A', deadline=o.release + timedelta(hours=3) if i == 0 else o.deadline) for i,o in enumerate(orders))
        report = compare_methods(orders, config).report
        self.assertTrue(report['methods']['edd']['eligible_for_comparison'])
        group = report['methods']['grouping']
        self.assertFalse(group['eligible_for_comparison'])
        self.assertEqual(group['construction_status'], 'failed')
        self.assertIsNone(group['resource'])
        self.assertFalse(report['optimiser_against']['grouping']['eligible'])
        summary = aggregate([{'comparison':report}])
        self.assertEqual(summary['paired']['grouping']['eligible_denominator'],0)
        self.assertEqual(summary['paired']['grouping']['excluded'],1)

    def test_negative_difference_preserved_not_clipped(self):
        orders, config = tiny_case()
        original = plan(orders, config)
        worse = replace(original, proposal=original.baseline)
        with patch('planner.comparators.plan', return_value=worse):
            report = compare_methods(orders, config).report
        difference = report['optimiser_against']['grouping']
        self.assertLess(difference['cleaning_events_difference'],0)
        self.assertLess(difference['percentage_difference'],0)
        self.assertEqual(aggregate([{'comparison':report}])['paired']['grouping']['optimiser_more_cleanings'],1)

    def test_effective_overrides_and_source_ids(self):
        source=load_bundled_orders(); case=initial_case(source,demo_config(source))
        answer=manual_proposal(case,operation='order_deadline',identifier='12',deadline=case.orders[11].release+timedelta(hours=1))
        changed=apply_changes(case,answer)
        report=compare_methods(changed.orders,changed.config).report
        self.assertFalse(report['methods']['edd']['eligible_for_comparison'])
        self.assertIsNone(report['methods']['optimiser']['resource'])
        # The public import still requires all 35; subsets are built downstream.
        manifest=json.loads((ROOT/'evaluation/scheduling_scenarios_v9.json').read_text())
        self.assertEqual(len(manifest['scenarios']),26)
        for definition in manifest['scenarios']:
            orders, config=instantiate(definition,source)
            ids={o.order_id for o in orders}
            self.assertEqual(ids,set(definition['order_ids']))
            self.assertTrue(all(p.from_order_id in ids and p.to_order_id in ids for p in config.transition_permissions))
            original={o.order_id:o for o in orders_from_import(source)}
            self.assertTrue(all(o.quantity==original[o.order_id].quantity for o in orders))

