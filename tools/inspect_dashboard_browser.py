"""Local real Edge screenshots via CDP; no external site or AMD calls."""
import base64
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
    destination=ROOT/'reports/industrial_dashboard_screenshots';destination.mkdir(exist_ok=True)
    server_port,browser_port=port(),port()
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    server=subprocess.Popen([sys.executable,'-m','streamlit','run','streamlit_app.py','--server.headless','true',
        '--server.address','127.0.0.1','--server.port',str(server_port),'--browser.gatherUsageStats','false'],
        cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
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
                    while not js('document.body.innerText.includes('+json.dumps(text)+')'):
                        if time.monotonic()>until:raise ValueError('Browser did not show: '+text)
                        time.sleep(.25)
                    time.sleep(.75)
                def click(label,selector='button'):
                    expression=f'''(()=>{{const e=[...document.querySelectorAll({json.dumps(selector)})].find(e=>e.innerText.includes({json.dumps(label)})&&e.getBoundingClientRect().width>0);if(!e)throw Error('Missing visible control');e.scrollIntoView({{block:'center'}});const r=e.getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}}}})()'''
                    point=js(expression)
                    command('Input.dispatchMouseEvent',{'type':'mousePressed','button':'left','clickCount':1,**point})
                    command('Input.dispatchMouseEvent',{'type':'mouseReleased','button':'left','clickCount':1,**point})
                    time.sleep(.75)
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
                command('Page.navigate',{'url':f'http://127.0.0.1:{server_port}'})
                wait_text('Build your dyeing production plan')
                capture('desktop_setup',1440,1100);capture('narrow_setup',680,1100)
                command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
                click('Load demo setup');wait_text('Each required cleaning takes')
                click('Generate schedule');wait_text('Illustrative scheduling result',seconds=45)
                capture('desktop_result',1440,1400);capture('narrow_result',680,1400)
                capture('desktop_timeline',1440,1200,'.st-key-dashboard_timeline')
                capture('narrow_timeline',680,1200,'.st-key-dashboard_timeline')
                capture('phone_timeline',390,1300,'.st-key-dashboard_timeline')
                click('Request a change','[role=tab]')
                capture('narrow_change',680,1400,'.st-key-dashboard_change');capture('desktop_change',1440,1400,'.st-key-dashboard_change')
                click('Review & export','[role=tab]')
                capture('desktop_review',1440,1400,'.st-key-dashboard_review');capture('narrow_review',680,1400,'.st-key-dashboard_review')
                capture('phone_review',390,1500,'.st-key-dashboard_review')
                command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1400,'deviceScaleFactor':1,'mobile':False})
                time.sleep(1)
                click('Machines and cleaning rules','summary')
                click('Use illustrative cleaning permissions','label')
                wait_text('Changes to assumptions require a fresh plan')
                click('Generate schedule');wait_text('Illustrative scheduling result',seconds=45)
                report['enabled_headline']=js("document.querySelector('.st-key-dashboard_summary .dc-title').innerText")
                capture('desktop_enabled_result',1440,1400);capture('narrow_enabled_result',680,1400)
                report['outcome']='screens_captured_for_visual_inspection'
                report['browser_version']=fetch(f'http://127.0.0.1:{browser_port}/json/version')['Browser']
                command('Browser.close')
            browser.wait(timeout=10)
    finally:
        if browser and browser.poll() is None:browser.terminate()
        server.terminate();server.wait(timeout=10)
        (ROOT/'reports/industrial_dashboard_browser.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
