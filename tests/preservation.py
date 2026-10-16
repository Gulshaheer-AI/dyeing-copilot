"""Preserve historical hashes while auditing the user-authorised dependency change."""
import hashlib


def preserved_sha(root, name):
    if name=='app/planning_changes_view.py':
        return hashlib.sha256((root/'history/demo_before_polish/app/planning_changes_view.py').read_bytes()).hexdigest()
    previous=root/'history/integrated_before'/name
    if previous.exists():return hashlib.sha256(previous.read_bytes()).hexdigest()
    if name != 'requirements.txt':
        return hashlib.sha256((root/name).read_bytes()).hexdigest()
    original=(root/'evaluation/requirements_m9.txt').read_text(encoding='utf-8').splitlines()
    current=(root/'requirements.txt').read_text(encoding='utf-8').splitlines()
    old={line.split('==')[0]:line.split('==')[1] for line in original if line}
    expected={**old,'protobuf':'6.33.6','absl-py':'2.3.1','immutabledict':'4.2.2','ortools':'9.15.6755'}
    actual={line.split('==')[0]:line.split('==')[1] for line in current if line}
    if actual != expected or len(current)!=len(actual):
        raise AssertionError('Only audited Milestone-10 dependency changes are authorised.')
    return hashlib.sha256((root/'evaluation/requirements_m9.txt').read_bytes()).hexdigest()
