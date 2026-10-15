"""Fresh selected-schedule evidence, independent of EDD feasibility."""
import json
from dataclasses import asdict
from statistics import median

from copilot.documents import retrieve_project_sections, MODEL_EQUATIONS
from copilot.evidence import retrieve_recorded_facts, fingerprint
from planner.change_requests import digest, effective_orders
from planner.comparison import compare_schedules, deadline_performance, RULE_LABELS
from planner.evaluator import evaluate_resources
from planner.scenario import to_json
from planner.verifier import verify_schedule


def build_selected_evidence(case, run, question, *, source=None, context_marker=None):
    if source is not None:
        effective_orders(source, case.config, case)
    if (run.case_fingerprint != case.fingerprint or run.effective_fingerprint != digest({'orders':case.orders,'config':case.config})
            or run.schedule is None):
        raise ValueError('A current selected-backend schedule is required; stale/failed results cannot be explained.')
    check=verify_schedule(case.orders,case.config,run.schedule)
    if not check.valid:
        raise ValueError('Independent verification rejected the selected schedule.')
    if run.origin=='cp_sat':
        if run.cp_sat is None or run.cp_sat.schedule!=run.schedule:
            raise ValueError('Selected CP-SAT origin does not match its solver artifact.')
    elif run.origin=='heuristic_fallback_not_cp_sat':
        if run.cp_sat is None or run.cp_sat.schedule is not None or run.legacy.proposal!=run.schedule:
            raise ValueError('Fallback origin does not match the failed solver and verified heuristic.')
    elif run.origin=='legacy_heuristic':
        if run.cp_sat is not None or run.legacy.proposal!=run.schedule:
            raise ValueError('Legacy origin does not match the selected heuristic.')
    else:raise ValueError('Unsupported selected-backend origin.')
    resources=evaluate_resources(case.orders,case.config,run.schedule)
    self_comparison=compare_schedules(case.orders,case.config,run.schedule,run.schedule)
    deadlines=deadline_performance(case.orders,run.schedule)
    slacks=[r['slack_hours'] for r in deadlines['orders']]
    stages={k:getattr(run.cp_sat,k) for k in ('version','solver_status','active_stage','stage_a','stage_b','scale','timing','cleaning_optimal','slack_optimal_at_fixed_count')} if run.cp_sat else None
    comparison=None
    # No fabricated baseline, fallback substitution, or non-worse prerequisite.
    baseline=run.legacy.baseline if run.legacy is not None else None
    if baseline is not None and verify_schedule(case.orders,case.config,baseline).valid:
        comparison={'baseline_method':'EDD heuristic comparator',
                    **compare_schedules(case.orders,case.config,baseline,run.schedule)}
    scenario={'source_sha256':case.source_sha256,'source_filename':case.source_filename,
        'case_fingerprint':case.fingerprint,'schedule_fingerprint':digest(run.schedule),
        'backend_origin':run.origin,'effective_orders':case.orders,'assumptions':case.config,
        'schedule':run.schedule,'verification':{'valid':check.valid,'errors':check.errors},
        'cleaning_counts':self_comparison['cleaning_counts']['proposal'],
        'deadlines':deadlines,'minimum_slack_hours':min(slacks),'median_slack_hours':median(slacks),
        'resources_secondary':{**asdict(resources),'total':resources.total,'unit':case.config.resource_unit},
        'solver_evidence':stages,'comparison':comparison,'request_history':case.history,'deadline_overrides':case.overrides}
    # Canonical JSON snapshot makes SQLite/export round trips exact and read-only.
    scenario=json.loads(to_json(scenario))
    documents,document_hashes=retrieve_project_sections(question)
    facts=retrieve_recorded_facts(source) if source is not None else {}
    def fact(key,value,unit,kind='selected_schedule'):
        facts['fact:selected.'+key]={'value':json.loads(to_json(value)),'unit':unit,'kind':kind}
    fact('identity',{k:scenario[k] for k in ('source_sha256','source_filename','case_fingerprint','schedule_fingerprint','backend_origin')},'identity')
    fact('verification',scenario['verification'],'scenario checks')
    fact('cleaning',scenario['cleaning_counts'],'events')
    fact('minimum_slack',scenario['minimum_slack_hours'],'scenario hours')
    fact('deadlines',scenario['deadlines'],'orders and scenario hours')
    fact('assumptions',scenario['assumptions'],'hypothetical assumptions')
    fact('solver',scenario['solver_evidence'],'solver evidence; bounds in reported ticks')
    fact('history',scenario['request_history'],'request provenance')
    fact('comparison',comparison,'verified scenario comparison; modelled source units')
    statements={}
    def add(key,text,refs):statements[key]={'text':text,'evidence_references':refs}
    counts=scenario['cleaning_counts']
    add('selected_summary',f"The selected {run.origin} schedule passes independent scenario verification: {len(case.orders)} orders, {counts['total']} cleaning events ({counts['initial']} initial, {counts['between_orders']} between orders, {counts['terminal']} terminal). All {deadlines['on_time']} orders are on time; minimum deadline slack is {min(slacks)} scenario hours.",['fact:selected.identity','fact:selected.verification','fact:selected.cleaning','fact:selected.deadlines',MODEL_EQUATIONS])
    add('selected_assumptions','Virtual capacities, calendars, durations, initial/terminal states and exact directed recipe/quality permissions remain hypothetical. Factory specialists must validate them before use.',['fact:selected.assumptions',MODEL_EQUATIONS])
    if stages and run.origin=='heuristic_fallback_not_cp_sat':
        add('selected_solver',f"The CP-SAT attempt returned Stage A {stages['stage_a']['status']} and Stage B {stages['stage_b']['status']}; no CP-SAT schedule is displayed. Its solver bounds belong to that attempt, not to the independently verified heuristic fallback.",['fact:selected.solver','fact:selected.identity'])
    elif stages:
        retention=(' '+stages['stage_b']['rejection_reason']) if stages['stage_b'].get('rejection_reason') else ''
        add('selected_solver',f"Solver Stage A is {stages['stage_a']['status']} and Stage B is {stages['stage_b']['status']}; the displayed schedule is from stage {stages['active_stage']}. Cleaning optimality proven: {stages['cleaning_optimal']}; maximum minimum slack proven at the fixed cleaning count: {stages['slack_optimal_at_fixed_count']}. Bounds and exact time scaling are in the cited solver receipt."+retention,['fact:selected.solver'])
    else:
        add('selected_solver','The selected schedule is a legacy heuristic result, not a CP-SAT solve.',['fact:selected.identity'])
    if run.origin=='heuristic_fallback_not_cp_sat':
        add('selected_origin','The displayed schedule is an explicitly permitted heuristic fallback; the CP-SAT receipt does not establish CP-SAT success.',['fact:selected.identity','fact:selected.solver'])
    else:
        add('selected_origin','The cited backend identity is the origin of this freshly verified selected schedule; inference receipts are separate from solver evidence.',['fact:selected.identity'])
    if comparison is None:
        add('selected_comparison','No current independently verified EDD baseline exists. This explains the selected schedule only; no baseline, reduction percentage or savings is inferred.',['fact:selected.comparison'])
    else:
        difference=comparison['difference'];events=comparison['reconciliation']['cleaning_events_difference']
        direction='lower' if difference>0 else 'unchanged' if difference==0 else 'higher'
        add('selected_comparison',f"Against the independently verified EDD heuristic, baseline-minus-selected cleaning events are {events} and the modelled resource difference is {difference} modelled source units ({direction} selected demand). This is a same-scenario comparison, not realised factory savings.",['fact:selected.comparison'])
    examples=[]
    for row in self_comparison['order_transitions']:
        side=row['proposal'];order_id=row['order_id'];ref='fact:selected.order.'+order_id
        facts[ref]={'value':json.loads(to_json({'order_id':order_id,'quantity':row['quantity'],**side})),
                    'unit':'source quantity, scenario timestamps and configured cleaning rule','kind':'selected_order'}
        predecessor='initial state' if side['predecessor'] is None else 'order '+side['predecessor']
        add('selected_order_'+order_id,f"Order {order_id} follows {predecessor} on {json.dumps(side['machine'])} at position {side['position']}; cleaning is {'required' if side['cleaning_required'] else 'not required'} because of {RULE_LABELS[side['rule']]}. It completes at {side['completion']}; its quantity remains {row['quantity']} source quantity units.",[ref])
        examples.append('selected_order_'+order_id)
    import re
    requested=set(re.findall(r'\border\s*#?\s*(\d+)\b',question,re.I))
    chosen=[k for k in examples if k.rsplit('_',1)[1] in requested] or examples[:2]
    add('selected_orders',' '.join(statements[k]['text'] for k in chosen[:2]),[r for k in chosen[:2] for r in statements[k]['evidence_references']])
    catalog={'statements':statements,'assumptions':{'source_units':'Source quantity/duration/water units remain unresolved.',
        'scenario_config':'Virtual machines, calendars, rates and cleaning permissions are scenario assumptions.'},
        'limitations':{'not_sops':'Project documents are not approved machine SOPs.',
            'no_factory_approval':'Acceptance is for further review only; it cannot change constraints or control equipment.',
            'limited_scope':'A bounded hypothetical scheduling model does not establish production reliability, safety or real factory savings.',
            'unresolved_source':'Recorded resource units and source-rule authority remain unresolved.',
            'unsupported_question':'The selected evidence cannot establish unstated causes, settings or approval.'},
        'review_actions':{'validate_scenario_assumptions':'Review source orders, exact permissions, calendars, capacities, processing times, deadline buffer and solver bounds with factory specialists.',
            'request_approved_documentation':'Request approved factory documentation; no settings or procedures are authorised.'}}
    identity={'version':'selected-schedule-evidence-v1','scenario':scenario,'documents':documents,
              'facts':facts,'catalog':catalog,'context_marker':context_marker}
    return {'kind':'selected_schedule','fingerprint':fingerprint(identity),'source_fingerprint':case.source_sha256,
        'context_marker':context_marker,
        'scenario_fingerprint':fingerprint(identity),'documents':documents,'document_hashes':document_hashes,
        'scenario':scenario,'scenario_error':None,'facts':facts,'catalog':catalog,
        'tool_trace':['verify_selected_schedule','retrieve_selected_orders','retrieve_optional_verified_comparison','retrieve_project_sections']}


def selected_fingerprint(bundle):
    return fingerprint({'version':'selected-schedule-evidence-v1','scenario':bundle['scenario'],
        'documents':bundle['documents'],'facts':bundle['facts'],'catalog':bundle['catalog'],
        'context_marker':bundle.get('context_marker')})
