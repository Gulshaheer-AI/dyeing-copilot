"""Read-only ZIP manifest, credential and redistribution checks; prints no secrets."""
import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]


def check(path):
    known=[v.encode() for k,v in dotenv_values(ROOT/'.env').items() if v and re.search('KEY|TOKEN|SECRET|PASSWORD',k,re.I)]
    patterns=[rb'\bgh[pousr]_[A-Za-z0-9]{20,}\b',rb'\bgithub_pat_[A-Za-z0-9_]{30,}\b',
        rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',rb'\bsk-[A-Za-z0-9_-]{24,}\b']
    count=0;findings=[]
    def inspect(name,data,depth=0):
        nonlocal count
        count+=1
        if any(value in data for value in known) or any(re.search(pattern,data) for pattern in patterns):
            findings.append(name)
        if zipfile.is_zipfile(io.BytesIO(data)):
            if depth>=4:raise ValueError('Nested ZIP exceeds review depth.')
            with zipfile.ZipFile(io.BytesIO(data)) as nested:
                if sum(m.file_size for m in nested.infolist())>500_000_000:raise ValueError('Nested archive exceeds review size.')
                for item in nested.infolist():
                    if not item.is_dir():inspect(name+'!'+item.filename,nested.read(item),depth+1)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():raise ValueError('ZIP CRC failed.')
        manifest=json.loads(archive.read('dyeing-copilot/PACKAGE_MANIFEST.json'))
        for item in archive.infolist():
            if item.is_dir():continue
            name=item.filename;parts=Path(name).parts
            if (not name.startswith('dyeing-copilot/') or '..' in parts or
                any(p in parts for p in ('.env','.git','.venv','__pycache__','data','checkpoints','publication','dist','06_restricted_reuse_experiments')) or name.endswith(('.db','.sqlite3','.pyc'))):
                raise ValueError('Forbidden packaged path: '+name)
            data=archive.read(item);inspect(name,data)
            key=name.removeprefix('dyeing-copilot/')
            if key!='PACKAGE_MANIFEST.json':
                entry=manifest[key]
                if hashlib.sha256(data).hexdigest()!=entry['sha256'] or len(data)!=entry['bytes']:
                    raise ValueError('Packaged manifest mismatch: '+key)
        example=dotenv_values(stream=io.StringIO(archive.read('dyeing-copilot/.env.example').decode()))
        if set(example)!={'AMD_API_KEY','AMD_BASE_URL','AMD_MODEL'} or not all(v and v.startswith('PASTE_') for v in example.values()):
            raise ValueError('Environment example must contain placeholders only.')
    if findings:raise ValueError('Credential screen rejected paths (no values printed): '+', '.join(findings))
    return {'zip':str(path),'credential_findings':0,'payloads_and_nested_members_scanned':count,
        'manifest_files_verified':len(manifest),'restricted_reuse_files_included':False,
        'environment_example':'placeholders only','scan_limit':'Known local AMD secrets and high-confidence token/private-key patterns, not a proof that arbitrary unknown credentials cannot exist.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('zip',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'reports/integrated_recovery_credentials_check.json')
    args=parser.parse_args();result=check(args.zip)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
