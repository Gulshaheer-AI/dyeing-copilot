"""Local real Edge screenshots via CDP; no external site or AMD calls."""
import base64
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[1]
EDGE=Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')


def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]


def fetch(url):
    with urllib.request.urlopen(url,timeout=2) as r:return json.loads(r.read())


def main():
    if not EDGE.exists():raise ValueError('Local Edge unavailable; browser inspection pending.')
    destination=ROOT/'reports/integrated_recovery_screenshots';destination.mkdir(exist_ok=True)
    server_port,browser_port=port(),port()
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    server=subprocess.Popen([sys.executable,'-m','streamlit','run','streamlit_app.py','--server.headless','true',
        '--server.address','127.0.0.1','--server.port',str(server_port),'--browser.gatherUsageStats','false'],
        cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags,
        env={**os.environ,'AMD_API_KEY':'PASTE_BROWSER_OFFLINE_DISABLED',
             'AMD_BASE_URL':'PASTE_BROWSER_OFFLINE_DISABLED','AMD_MODEL':'PASTE_BROWSER_OFFLINE_DISABLED'})
    report={'browser':'Microsoft Edge headless via CDP','live_amd_calls':0,'screens':[]}
    browser=None
    try:
        with tempfile.TemporaryDirectory(prefix='dashboard-browser-',dir=ROOT/'dist',ignore_cleanup_errors=True) as folder:
            browser=subprocess.Popen([str(EDGE),'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
                '--disable-extensions','--remote-debugging-address=127.0.0.1','--remote-debugging-port='+str(browser_port),
                '--user-data-dir='+folder,'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
            deadline=time.monotonic()+25
            while True:
                try:targets=fetch(f'http://127.0.0.1:{browser_port}/json');break
                except OSError:
                    if time.monotonic()>deadline:raise ValueError('Edge remote debugging did not start.') from None
                    time.sleep(.25)
            target=next(t for t in targets if t['type']=='page')
            with connect(target['webSocketDebuggerUrl'],max_size=20_000_000) as ws:
                sequence=0
                def command(method,params=None):
                    nonlocal sequence
                    sequence+=1;ws.send(json.dumps({'id':sequence,'method':method,'params':params or {}}))
                    while True:
                        message=json.loads(ws.recv(timeout=30))
                        if message.get('id')==sequence:
                            if 'error' in message:raise ValueError(str(message['error']))
                            return message.get('result',{})
                def js(expression):
                    result=command('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
                    if 'exceptionDetails' in result:raise ValueError('Browser script failed: '+str(result['exceptionDetails']))
                    return result.get('result',{}).get('value')
                def wait_text(text,seconds=35):
                    until=time.monotonic()+seconds
                    while not js('(document.body?.innerText??"").includes('+json.dumps(text)+')'):
                        if time.monotonic()>until:
                            capture('failed_wait',1440,1500)
                            report['failed_wait']=text
                            raise ValueError('Browser did not show: '+text)
                        time.sleep(.25)
                    time.sleep(.75)
                def click(label,selector='button'):
                    expression=f'''(()=>{{const e=[...document.querySelectorAll({json.dumps(selector)})].find(e=>e.innerText.includes({json.dumps(label)})&&e.getBoundingClientRect().width>0&&!e.disabled);if(!e)return null;e.scrollIntoView({{block:'center',behavior:'instant'}});if({json.dumps(selector)}==='[role=tab]')return true;const input=e.querySelector('input');if(input)input.click();else e.click();return true}})()'''
                    deadline=time.monotonic()+20
                    while True:
                        point=js(expression)
                        if point:break
                        if time.monotonic()>deadline:
                            capture('failed_control',1440,1400)
                            report['failed_control']=label
                            raise ValueError('Missing visible enabled control: '+label)
                        time.sleep(.3)
                    if selector=='[role=tab]':
                        time.sleep(.3)
                        point=js(f'''(()=>{{const e=[...document.querySelectorAll('[role=tab]')].find(e=>e.innerText.includes({json.dumps(label)}));const r=e.getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}}}})()''')
                        command('Input.dispatchMouseEvent',{'type':'mouseMoved',**point})
                        point_click(point)
                    time.sleep(.75)
                def point_click(point):
                    command('Input.dispatchMouseEvent',{'type':'mousePressed','button':'left','clickCount':1,**point})
                    command('Input.dispatchMouseEvent',{'type':'mouseReleased','button':'left','clickCount':1,**point})
                    time.sleep(.4)
                def fill(label,value):
                    # Streamlit uses React Aria segmented fields. The first native
                    # input is hidden; interact with the visible spinbuttons.
                    pieces=(dict(zip(('hour','minute','second'),value.split(':'))) if 'time' in label.lower()
                        else dict(zip(('year','month','day'),value.replace('/','-').split('-'))))
                    for kind,part in pieces.items():
                        info=js("""(()=>{const w=[...document.querySelectorAll('[data-testid=stDateInput],[data-testid=stTimeInput]')].find(e=>e.innerText.includes("""+json.dumps(label)+"""));const fields=[...w.querySelectorAll('[role=spinbutton]')];const e=fields.find(e=>e.dataset.type==="""+json.dumps(kind)+""");if(!e)return {missing:true,html:w.outerHTML};e.scrollIntoView({block:'center'});e.focus();return {active:document.activeElement===e,kind:e.dataset.type,text:e.innerText}})()""")
                        if info.get('missing'):
                            report['field_diagnostic']=info
                            raise ValueError('Segmented control not found: '+label+' '+kind)
                        for char in part:
                            command('Input.dispatchKeyEvent',{'type':'keyDown','key':char,'code':'Digit'+char,'windowsVirtualKeyCode':ord(char),'text':char})
                            command('Input.dispatchKeyEvent',{'type':'keyUp','key':char,'code':'Digit'+char,'windowsVirtualKeyCode':ord(char)})
                        time.sleep(.2)
                    command('Input.dispatchKeyEvent',{'type':'keyDown','key':'Tab','code':'Tab','windowsVirtualKeyCode':9})
                    command('Input.dispatchKeyEvent',{'type':'keyUp','key':'Tab','code':'Tab','windowsVirtualKeyCode':9})
                    time.sleep(.5)
                def choose(label,value):
                    locator="""(()=>{const w=[...document.querySelectorAll('[data-testid=stSelectbox]')].find(e=>e.innerText.includes("""+json.dumps(label)+"""));return w.querySelector('button[aria-haspopup=listbox]')})()"""
                    js('('+locator+").scrollIntoView({block:'center',behavior:'instant'})")
                    time.sleep(.4)
                    point=js('(()=>{const e='+locator+';const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()')
                    command('Input.dispatchMouseEvent',{'type':'mouseMoved',**point})
                    point_click(point)
                    time.sleep(.5)
                    report.setdefault('dropdown_diagnostics',[]).append(js('({expanded:('+locator+").getAttribute('aria-expanded'),options:[...document.querySelectorAll('[role=option]')].map(e=>({text:e.innerText,label:e.getAttribute('aria-label')}))})"))
                    click(value,'[role=option]')
                    time.sleep(.75)
                    actual=js("""(()=>{const w=[...document.querySelectorAll('[data-testid=stSelectbox]')].find(e=>e.innerText.includes("""+json.dumps(label)+"""));return w.querySelector('[role=combobox]').value})()""")
                    report.setdefault('select_control_checks',[]).append({'label':label,'requested':value,'actual':actual})
                    if actual!=value:raise ValueError('Exact browser selection did not match the requested option.')
                def capture(label,width,height,focus=None):
                    command('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':False})
                    js("window.scrollTo(0,0);document.querySelector('[data-testid=stMain]').scrollTo(0,0)")
                    if focus:
                        js('document.querySelector('+json.dumps(focus)+").scrollIntoView({block:'start'});document.querySelector('[data-testid=stMain]').scrollBy(0,-70)")
                    time.sleep(1)
                    data=command('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
                    path=destination/(label+'.png');path.write_bytes(base64.b64decode(data['data']))
                    report['screens'].append({'name':label,'width':width,'height':height,'path':path.relative_to(ROOT).as_posix()})
                command('Page.enable');command('Runtime.enable')
                command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
                deadline=time.monotonic()+20
                while True:
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{server_port}/_stcore/health',timeout=2) as response:
                            if response.status==200:break
                    except OSError:pass
                    if time.monotonic()>deadline:raise ValueError('Local Streamlit server did not become ready.')
                    time.sleep(.25)
                command('Page.navigate',{'url':f'http://127.0.0.1:{server_port}'})
                wait_text('Build your dyeing production plan')
                capture('desktop_setup',1440,1100);capture('narrow_setup',680,1100)
                command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1200,'deviceScaleFactor':1,'mobile':False})
                click('Load demo setup');wait_text('Each required cleaning takes')
                click('Use illustrative cleaning permissions','label')
                report['permissions_explicitly_enabled']=js("[...document.querySelectorAll('label')].find(e=>e.innerText.includes('Use illustrative cleaning permissions')).querySelector('input').checked")
                if not report['permissions_explicitly_enabled']:raise ValueError('Permission opt-in was not enabled by the browser action.')
                click('Generate schedule');wait_text('Illustrative scheduling result',seconds=45)
                capture('desktop_initial',1440,1400)
                click('Recovery and alternative objectives','summary')
                fill('Replan from date','2019/12/01');fill('Replan from time','05:00:00')
                capture('reference_selection',1440,1400)
                click('Use current verified plan as reference')
                wait_text('Replan from 2019-12-01 05:00:00')
                click('Enter a change manually','label')
                choose('Constraint type','Machine outage')
                choose('Virtual machine ID','virtual-Pressure-PolyCotton')
                fill('Outage start date','2019/12/01');fill('Outage start time','04:00:00')
                fill('Outage end date','2019/12/01');fill('Outage end time','06:00:00')
                click('Preview manual change');wait_text('Interrupted-batch recovery is not supported.')
                capture('desktop_conflict',1440,1400)
                fill('Outage start time','12:00:00')
                fill('Outage end date','2019/12/02');fill('Outage end time','12:00:00')
                click('Preview manual change');wait_text('Before/after constraint preview')
                capture('desktop_preview',1440,1400)
                click('Apply changes and reschedule');wait_text('Recovery impact',seconds=45)
                capture('desktop_recovery',1440,1400);capture('narrow_recovery',680,1400)
                click('Machine schedule','[role=tab]')
                capture('desktop_timeline',1440,1200,'.st-key-dashboard_timeline')
                capture('narrow_timeline',680,1300,'.st-key-dashboard_timeline')
                click('Reference','label')
                capture('reference_timeline',1440,1200,'.st-key-dashboard_timeline')
                click('More deadline protection','label')
                capture('deadline_protection',1440,1300)
                click('Review & export','[role=tab]')
                click('Mock demonstration (no API call)','label')
                wait_text('MOCK demonstration: no AMD inference.')
                click('Explain this plan');wait_text('MOCKED explanation')
                capture('desktop_explanation',1440,1400,'.st-key-dashboard_review')
                click('Save for supervisor review');wait_text('Saved pending review')
                click('Record review decision');wait_text('Accepted for further review')
                capture('desktop_review',1440,1400,'.st-key-dashboard_review');capture('narrow_review',680,1400,'.st-key-dashboard_review')
                capture('narrow_review_decision',680,1300,'.st-key-dashboard_review [data-testid=stSelectbox]')
                download_folder=Path(folder)/'review-download';download_folder.mkdir()
                command('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(download_folder.resolve())})
                click('Download planner review package')
                deadline=time.monotonic()+15
                while not list(download_folder.glob('*.json')):
                    if time.monotonic()>deadline:raise ValueError('Planner review download did not complete.')
                    time.sleep(.25)
                downloaded=next(download_folder.glob('*.json'));payload=downloaded.read_bytes()
                artifact=json.loads(payload)
                if (not artifact['verification']['valid'] or artifact['review_status']!='accepted_for_further_review'
                        or artifact['objective_option']!='deadline_protection' or artifact['execution_reference'] is None):
                    raise ValueError('Downloaded package did not match the current accepted-for-further-review recovery selection.')
                (ROOT/'reports/integrated_recovery_browser_export.json').write_bytes(payload)
                report['downloaded_export']={'sha256':hashlib.sha256(payload).hexdigest(),'verification':artifact['verification'],
                    'review_status':artifact['review_status'],'objective_option':artifact['objective_option'],
                    'scenario_fingerprint':artifact['scenario_fingerprint'],'selected_evidence_fingerprint':artifact['selected_evidence_fingerprint']}
                click('Fewer cleanings','label');click('Review & export','[role=tab]');wait_text('STALE evidence')
                capture('stale_review',1440,1400,'.st-key-dashboard_review')
                click('Request a change','[role=tab]')
                capture('narrow_change',680,1400,'.st-key-dashboard_change')
                command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1300,'deviceScaleFactor':1,'mobile':False})
                click('Planning engine and technical settings','summary')
                choose('Planning engine','Legacy heuristic (explicit fallback)')
                wait_text('The legacy engine does not preserve simulated execution history')
                capture('legacy_recovery_blocked',1440,1300)
                report['legacy_recovery_engine_blocked']=True
                choose('Planning engine','CP-SAT (default)')
                wait_text('Recovery impact')
                click('Request a change','[role=tab]')
                click('Reset to original scenario and reschedule');wait_text('Illustrative scheduling result',seconds=45)
                report['journey']='Actual browser: reference selection, fixed-work conflict, manual preview/apply, both verified priorities, reference/revised timelines, mock explanation, pending/accepted review, stale selection and reset.'
                report['live_amd_calls']=0
                report['amd_disabled_in_browser_server_environment']=True
                report['outcome']='screens_captured_for_visual_inspection'
                report['browser_version']=fetch(f'http://127.0.0.1:{browser_port}/json/version')['Browser']
                command('Browser.close')
            browser.wait(timeout=10)
    finally:
        if browser and browser.poll() is None:browser.terminate()
        server.terminate();server.wait(timeout=10)
        (ROOT/'reports/integrated_recovery_browser.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
