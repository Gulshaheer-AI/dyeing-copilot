"""Applicable review exports bind the exact selected-schedule evidence snapshot."""
import json


def applicable_review(store,bundle,review_id=None):
    rows=store.list_reviews()
    if review_id is not None:
        rows=[r for r in rows if r['id']==review_id]
    matches=[r for r in rows if r['fingerprint']==bundle['fingerprint'] and json.loads(r['evidence_json'])==bundle]
    if not matches:
        if review_id is not None:raise ValueError('Review does not match the current selected-schedule evidence.')
        return None
    row=matches[0]
    return {**row,'evidence_json':json.loads(row['evidence_json']),'answer_json':json.loads(row['answer_json']),
        'receipt_json':json.loads(row['receipt_json']),'decision_history':store.decision_history(row['id']),
        'meaning':'Accepted means further review only; pending is not acceptance; no production approval or control.'}
