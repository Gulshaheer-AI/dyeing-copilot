"""Fail closed on known credentials/high-confidence tokens; never print values."""
import argparse
import io
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path
from dotenv import dotenv_values

PATTERNS={
    'GitHub token':rb'\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b',
    'AWS access key':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'private key':rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'provider secret':rb'\bsk-[A-Za-z0-9_-]{24,}\b',
}
FORBIDDEN={'.env','.git','__pycache__','.venv','.venv-cpsat-check','data','dist','checkpoints','06_restricted_reuse_experiments'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository',type=Path)
    parser.add_argument('--private-env',type=Path)
    parser.add_argument('--history',action='store_true')
    args=parser.parse_args();root=args.repository.resolve()
    marker=json.loads((root/'PUBLIC_DISTRIBUTION.json').read_text(encoding='utf-8'))
    names=marker['files'];findings=[];known=[];checked=0;archive_members=0
    if args.private_env:
        known.extend(v.encode() for k,v in dotenv_values(args.private_env).items()
            if v and re.search('KEY|TOKEN|SECRET|PASSWORD',k,re.I) and not v.startswith('PASTE_'))
    # Git authentication is read into memory only, never echoed or written.
    cred=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',
        capture_output=True,text=True,env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'never'})
    for line in cred.stdout.splitlines():
        if line.startswith('password=') and len(line)>13:known.append(line.split('=',1)[1].encode())
    def inspect(label,data,depth=0):
        nonlocal checked,archive_members
        checked+=1
        if any(value in data for value in known):findings.append({'file':label,'rule':'known local credential'})
        for rule,pattern in PATTERNS.items():
            if re.search(pattern,data):findings.append({'file':label,'rule':rule})
        if zipfile.is_zipfile(io.BytesIO(data)):
            if depth>=4:raise ValueError('Archive inspection depth exceeded; review required.')
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(m.file_size for m in archive.infolist())>500_000_000:
                    raise ValueError('Archive inspection bound exceeded; review required.')
                for item in archive.infolist():
                    if not item.is_dir():
                        archive_members+=1;inspect(label+'!'+item.filename,archive.read(item),depth+1)
    for name in names:
        p=root/name
        if not p.resolve().is_relative_to(root) or any(part in FORBIDDEN for part in p.relative_to(root).parts) or p.suffix in ('.db','.sqlite3','.pyc'):
            findings.append({'file':name,'rule':'forbidden public path'});continue
        inspect(name,p.read_bytes())
    example=dotenv_values(root/'.env.example')
    if set(example)!={'AMD_API_KEY','AMD_BASE_URL','AMD_MODEL'} or not all(v and v.startswith('PASTE_') for v in example.values()):
        findings.append({'file':'.env.example','rule':'example must contain placeholders only'})
    tracked=subprocess.run(['git','ls-files','-z'],cwd=root,capture_output=True)
    if tracked.returncode==0:
        for name in tracked.stdout.decode().split('\0'):
            if name and name not in names:findings.append({'file':name,'rule':'tracked outside reviewed file selection'})
    history_blobs=0
    if args.history:
        objects=subprocess.run(['git','rev-list','--objects','HEAD','--not','--remotes'],cwd=root,capture_output=True,text=True,check=True)
        for row in objects.stdout.splitlines():
            oid=row.split(' ',1)[0]
            kind=subprocess.run(['git','cat-file','-t',oid],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
            if kind=='blob':
                content=subprocess.run(['git','cat-file','blob',oid],cwd=root,capture_output=True,check=True).stdout
                inspect('outgoing-history:'+oid,content);history_blobs+=1
    result={'selected_files':len(names),'checked_payloads_including_archives':checked,'archive_members':archive_members,
        'outgoing_history_blobs':history_blobs,'known_local_credentials_checked':len(known),'findings':findings,
        'scope':'Known AMD/Git credentials, high-confidence token/private-key patterns, nested archives, tracked selection and outgoing Git blobs. Values never printed.'}
    print(json.dumps(result,indent=2))
    if findings:raise SystemExit(1)


if __name__=='__main__':main()
