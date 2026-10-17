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
    destination=ROOT/'reports/plan_history_screenshots';destination.mkdir(exist_ok=True)
    server_port,browser_port=port(),port()
    history_db=ROOT/'data'/('plan_history_browser_'+__import__('uuid').uuid4().hex+'.sqlite3')
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    server=subprocess.Popen([sys.executable,'-m','streamlit','run','streamlit_app.py','--server.headless','true',
        '--server.address','127.0.0.1','--server.port',str(server_port),'--browser.gatherUsageStats','false'],
        cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags,
        env={**os.environ,'AMD_API_KEY':'PASTE_BROWSER_OFFLINE_DISABLED',
             'AMD_BASE_URL':'PASTE_BROWSER_OFFLINE_DISABLED','AMD_MODEL':'PASTE_BROWSER_OFFLINE_DISABLED',
             'DYEING_PLAN_HISTORY_DB':str(history_db)})
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
                deadline=time.monotonic()+25
                while True:
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{server_port}/_stcore/health',timeout=2) as response:
                            if response.status==200:break
                    except OSError:pass
                    if time.monotonic()>deadline:raise ValueError('Local server unavailable.')
                    time.sleep(.25)
                command('Page.navigate',{'url':f'http://127.0.0.1:{server_port}'})
                wait_text('Build your dyeing production plan')
                click('Plan history','label');wait_text('No saved plans in this session')
                capture('empty_history',1440,1100)
                click('Production planner','label');wait_text('Build your dyeing production plan')
                click('Load demo setup');wait_text('Each required cleaning takes')
                click('Use illustrative cleaning permissions','label')
                click('Generate schedule');wait_text('Illustrative scheduling result',seconds=50)
                report['permissions_enabled']=True
                click('Review & export','[role=tab]')
                # Real typing/blur exercises persistence of the optional title.
                js("(()=>{const w=[...document.querySelectorAll('[data-testid=stTextInput]')].find(e=>e.innerText.includes('History title'));const e=w.querySelector('input');e.scrollIntoView({block:'center'});e.focus()})()")
                command('Input.insertText',{'text':'Demo archived plan'})
                command('Input.dispatchKeyEvent',{'type':'keyDown','key':'Tab','code':'Tab','windowsVirtualKeyCode':9})
                command('Input.dispatchKeyEvent',{'type':'keyUp','key':'Tab','code':'Tab','windowsVirtualKeyCode':9})
                time.sleep(1)
                downloads=Path(folder)/'downloads';downloads.mkdir()
                command('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(downloads.resolve())})
                click('Download planner review package')
                until=time.monotonic()+15
                while not (downloads/'dyeing_planner_review_package.json').exists():
                    if time.monotonic()>until:raise ValueError('Active export missing.')
                    time.sleep(.25)
                original=json.loads((downloads/'dyeing_planner_review_package.json').read_text(encoding='utf-8'))
                click('Save to history');wait_text('Saved to plan history.')
                click('Save to history');wait_text('Already saved.')
                report['idempotent_click_confirmed']=True
                capture('saved_without_explanation',1440,1200,'.st-key-dashboard_review')
                click('Plan history','label');wait_text('Archived planned result')
                capture('archived_selected',1440,1200)
                capture('archived_selected_narrow',680,1200)
                command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1200,'deviceScaleFactor':1,'mobile':False})
                click('Generated deadline-first planned baseline','label')
                capture('archived_baseline',1440,1200)
                click('Saved verification, solver status and metrics','summary')
                capture('archived_verification',1440,1200)
                click('Download saved review package (JSON)')
                until=time.monotonic()+15
                while not list(downloads.glob('dyeing_saved_plan_*.json')):
                    if time.monotonic()>until:raise ValueError('Saved history download missing.')
                    time.sleep(.25)
                archived=json.loads(next(downloads.glob('dyeing_saved_plan_*.json')).read_text(encoding='utf-8'))
                if archived['title']!='Demo archived plan':raise ValueError('Entered title was not retained.')
                snapshot=archived['snapshot'];saved=snapshot['package']
                if saved['schedule']!=original['schedule'] or saved['scenario_fingerprint']!=original['scenario_fingerprint']:
                    raise ValueError('Archive did not preserve the exact selected schedule/scenario.')
                if snapshot['explanation'] is not None or saved['applicable_review'] is not None:
                    raise ValueError('Unexpected explanation/review required or attached.')
                if any(k in json.dumps(archived) for k in ('session_scope','scope_hash','session_id')):
                    raise ValueError('Private scope found in download.')
                report['archived_download']={'run_id':archived['run_id'],'verified':saved['verification']['valid'],
                    'same_schedule_and_scenario':True,'no_explanation_required':True,'session_identifier_exported':False,
                    'cleaning_count':snapshot['summary']['cleaning_count'],'on_time':snapshot['summary']['on_time']}
                click('Production planner','label');wait_text('Illustrative scheduling result',seconds=45)
                click('Review & export','[role=tab]');click('Download planner review package')
                time.sleep(1.5)
                second=sorted(downloads.glob('dyeing_planner_review_package*.json'))[-1]
                after=json.loads(second.read_text(encoding='utf-8'))
                if after['schedule']!=original['schedule'] or after['scenario_fingerprint']!=original['scenario_fingerprint']:
                    raise ValueError('Opening history changed active planner.')
                if after['cp_sat_result']!=original['cp_sat_result']:
                    raise ValueError('Navigating history unexpectedly recalculated the solver result.')
                if not after['assumptions']['allow_cleaning_exemptions']:
                    raise ValueError('History navigation cleared explicit permission opt-in.')
                report['returned_active_plan_unchanged']=True
                report['solver_receipt_unchanged']=True
                report['title_round_trip']=True
                click('Save to history');wait_text('Already saved.')
                report['duplicate_after_return_prevented']=True
                report['streamlit_exceptions']=js("document.querySelectorAll('[data-testid=stException]').length")
                capture('returned_active_planner',1440,1100)
                report['outcome']='passed_real_browser_inspected_screens'
                report['browser_version']=fetch(f'http://127.0.0.1:{browser_port}/json/version')['Browser']
                command('Browser.close')
            browser.wait(timeout=10)
    finally:
        if browser and browser.poll() is None:browser.terminate()
        server.terminate();server.wait(timeout=10)
        (ROOT/'reports/plan_history_browser.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
