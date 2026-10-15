import unittest
from unittest.mock import patch
from datetime import timedelta
from app.planner_presentation import result_summary,useful_window,shift_day,timeline_rows
from app.dashboard_style import panel_heading
from planner.search import plan
from test_scheduler import tiny_case


class DashboardPresentationTests(unittest.TestCase):
    def test_summary_handles_positive_zero_negative_missing_comparisons(self):
        self.assertEqual(result_summary(10,4,35,35),'6 fewer cleanings. All 35 orders on time.')
        self.assertEqual(result_summary(4,4,35,35),'No change in cleaning count. All 35 orders on time.')
        self.assertEqual(result_summary(4,5,2,3),'1 more cleaning. 2 of 3 orders on time.')
        self.assertIn('Baseline comparison unavailable',result_summary(None,4,3,3))

    def test_initial_cleaning_starts_daily_window_and_navigation_is_clamped(self):
        orders,config=tiny_case()
        schedule=plan(orders,config).proposal
        frame,lo,hi=timeline_rows(orders,config,schedule)
        start,end=useful_window(frame,lo,hi,[config.machines[0].virtual_id])
        self.assertEqual(start,lo)
        self.assertLessEqual(end-start,timedelta(hours=24))
        self.assertEqual(end,hi)  # Tiny case finishes within a day.
        self.assertEqual(shift_day(start,lo,hi,-1),lo)
        self.assertLess(shift_day(start,lo,hi,100),hi)

    def test_custom_html_escapes_dynamic_text(self):
        with patch('app.dashboard_style.st.html') as render:
            panel_heading('<script>alert(1)</script>','x & y','<img src=x>')
        html=render.call_args.args[0]
        self.assertNotIn('<script>',html)
        self.assertNotIn('<img',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn('x &amp; y',html)
