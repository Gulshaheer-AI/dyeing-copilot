"""Narrow question boundary for recovery facts, not industrial diagnosis."""
import re


def check_recovery_question(question,orders):
    supported=re.search(r'\b(?:explain|schedule|plan|order|cleaning|deadline|buffer|assumptions?|review|comparison|recovery|reference|outage|changes?|verify|verification|machine)\b',question,re.I)
    requested=set(re.findall(r'\border\s*#?\s*(\d+)\b',question,re.I))
    if requested-{o.order_id for o in orders}:
        raise ValueError('Unknown order in this recovery question. Use an exact loaded order ID.')
    # Pressure as part of an exact machine ID is not a setting request.
    cleaned=re.sub(r'virtual-[A-Za-z0-9_-]+','known machine identifier',question)
    unsupported=re.search(r'\b(?:pressure|temperature|chemical|dosage|recipe|diagnos\w*|root\s+cause|PKR|litres?|liters?|safety\s+cert\w*|production\s+approv\w*)\b',cleaned,re.I)
    if unsupported or not supported:
        raise ValueError('Recovery explanations support computed plans, changed orders, constraints and review assumptions only. They cannot diagnose industrial causes, prescribe settings, convert source units or approve production.')
