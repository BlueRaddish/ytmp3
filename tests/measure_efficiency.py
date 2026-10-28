"""Fresh-process resource probes; fixtures isolate app work from external services."""
import argparse
import gc
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
from unittest.mock import patch

import psutil
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if os.name != 'nt':
    raise SystemExit('This resource-counter adapter targets Windows private memory and handles.')
args.output.parent.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(args.repo))
start_import = time.perf_counter()
from ytmp3.app import AppServer, Library
import_s = time.perf_counter()-start_import
owner = psutil.Process()
samples = []
stop = threading.Event()
tracked = [owner]
tracked_at = 0
gpu_pids = set()

def processes():
    global tracked, tracked_at
    now = time.monotonic()
    if now - tracked_at > 2:
        tracked = [owner, *owner.children(recursive=True)]
        tracked_at = now
        for process in tracked:
            try:
                if '--type=gpu-process' in process.cmdline(): gpu_pids.add(process.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    result = {'rss':0,'private':0,'cpu_s':0,'threads':0,'handles':0,'read_bytes':0,'write_bytes':0,'processes':0,'gpu_private':0}
    for process in tracked:
        try:
            with process.oneshot():
                memory = process.memory_info()
                result['rss'] += memory.rss
                result['private'] += getattr(memory, 'private', memory.rss)
                result['cpu_s'] += sum(process.cpu_times()[:2])
                result['threads'] += process.num_threads()
                result['handles'] += process.num_handles() if os.name == 'nt' else process.num_fds()
                io = process.io_counters()
                result['read_bytes'] += io.read_bytes
                result['write_bytes'] += io.write_bytes
                result['processes'] += 1
                if process.pid in gpu_pids: result['gpu_private'] += getattr(memory, 'private', memory.rss)
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    return result

def monitor():
    while not stop.wait(.5): samples.append(processes())

threading.Thread(target=monitor, daemon=True).start()
results = {'measurement_version':2,'repo':str(args.repo),'import_ms':import_s*1000,'workload':'5000 synthetic tracks; native bridge fixture; 20 identical refreshes; 6 seconds idle (3 visible/3 hidden); 400 real MP3 tag-cache churn; 20 repeated fixture searches',
           'environment':{'python':sys.version,'platform':sys.platform,'available_ram':psutil.virtual_memory().available,'logical_cpus':psutil.cpu_count()}}
results['revision'] = subprocess.check_output(['git','rev-parse','HEAD'], cwd=args.repo, text=True).strip()
with tempfile.TemporaryDirectory(prefix='ytmp3-efficiency-') as temp:
    root = Path(temp)
    library = Library(root/'library')
    server = AppServer(('127.0.0.1',0), library)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with patch('ytmp3.app.check_updates', return_value={'current':'1.0.0','version':'1.0.0','available':False}), sync_playwright() as pw:
            launch = time.perf_counter()
            browser = pw.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', headless=True, args=['--mute-audio'])
            results['browser_launch_ms'] = (time.perf_counter()-launch)*1000
            page = browser.new_page(viewport={'width':1280,'height':900})
            page.add_init_script("""(() => {
              const tracks = Array.from({length:5000}, (_,i) => ({id:`track-${i}.mp3`,title:`Song ${i}`,
                artist:`Artist ${i%30}`,album:`Album ${i%100}`,folder:'Library',folderId:'own',
                rootFolder:'Library',rootFolderId:'own',modified:i,duration:180,artwork:false}));
              window.__tracks = tracks; window.__reads = 0; window.__hidden = false;
              Object.defineProperty(document, 'visibilityState', {get:()=>window.__hidden?'hidden':'visible'});
              const playback = JSON.stringify({id:'track-0.mp3',index:0,playing:false,position:0,duration:180000,shuffle:false,repeat:0});
              window.Ytmp3Android = {cachedTracks:()=>JSON.stringify({tracks}),refreshTracks:()=>setTimeout(()=>window.ytmp3TracksReady(true),0),
                playback:()=>{window.__reads++;return playback},checkAppUpdate:()=>{},command:()=>{}};
              localStorage.setItem('ytmp3_snapshot', JSON.stringify({tracks,at:Date.now()}));
              localStorage.setItem('ytmp3_queue',JSON.stringify(tracks.slice(0,1000).map(t=>t.id)));
            })();""")
            began = time.perf_counter()
            page.goto(f'http://127.0.0.1:{server.server_port}/?key={server.key}#browse')
            page.locator('#browse-tracks .track-row').first.wait_for()
            results['browser_ready_ms'] = (time.perf_counter()-began)*1000
            results['application_ready_ms'] = results['browser_ready_ms']+results['import_ms']
            results['startup_resources'] = page.evaluate("() => performance.getEntriesByType('resource').map(e=>({path:new URL(e.name).pathname,transfer_bytes:e.transferSize}))")
            cdp = page.context.new_cdp_session(page)
            cdp.send('Performance.enable')
            results['library_refresh'] = page.evaluate("""() => {
              let writes=0,bytes=0; const original=Storage.prototype.setItem;
              Storage.prototype.setItem=function(k,v){if(k==='ytmp3_snapshot'){writes++;bytes+=v.length*2} return original.call(this,k,v)};
              const times=[]; const map=state.trackById;
              for(let i=0;i<20;i++){const start=performance.now();applyTracks({tracks:window.__tracks});times.push(performance.now()-start)}
              Storage.prototype.setItem=original;
              return {times_ms:times,writes,serialized_bytes:bytes,kept_index:map===state.trackById,tracks:state.tracks.length,rendered:document.querySelectorAll('#browse-tracks .track-row').length};
            }""")
            results['ui_render'] = page.evaluate("""() => {
              const times=[];for(let i=0;i<8;i++){let t=performance.now();renderBrowseTracks();times.push(performance.now()-t)}
              return {times_ms:times,rendered:document.querySelectorAll('#browse-tracks .track-row').length};
            }""")
            page.evaluate("""() => {
              window.__updates=0;const old=updatePlayer;updatePlayer=function(...args){window.__updates++;return old(...args)};
              window.__reads=0;
            }""")
            baseline = processes()
            page.wait_for_timeout(3000)
            results['visible_idle'] = {'bridge_reads':page.evaluate('window.__reads'),'player_updates':page.evaluate('window.__updates'),'cpu_s':processes()['cpu_s']-baseline['cpu_s']}
            page.screenshot(path=str(args.output.with_suffix('.png')))
            page.evaluate("() => {window.__reads=0;window.__updates=0;window.__hidden=true;document.dispatchEvent(new Event('visibilitychange'))}")
            baseline = processes()
            page.wait_for_timeout(3000)
            results['hidden_idle'] = {'bridge_reads':page.evaluate('window.__reads'),'player_updates':page.evaluate('window.__updates'),'cpu_s':processes()['cpu_s']-baseline['cpu_s']}
            results['browser_heap'] = {item['name']:item['value'] for item in cdp.send('Performance.getMetrics')['metrics'] if item['name'] in ['JSHeapUsedSize','Nodes','Documents','TaskDuration','ScriptDuration','LayoutDuration']}
            results['active_process_tree'] = processes()
            page.evaluate("() => {window.__hidden=false;document.dispatchEvent(new Event('visibilitychange'))}")
            browser.close()
        # Simulate library turnover using actual own-tone MP3 files and the real tag parser.
        tone = root/'tone.mp3'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=duration=0.05','-q:a','9',str(tone)],check=True,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        data = tone.read_bytes()
        gc.collect(); tracemalloc.start(); traced_before = tracemalloc.get_traced_memory()[0]
        began=time.perf_counter()
        for batch in range(20):
            for path in library.path.glob('*.mp3'): path.unlink()
            for i in range(20): (library.path/f'{batch}-{i}.mp3').write_bytes(data)
            library.tracks()
        for path in library.path.glob('*.mp3'): path.unlink()
        library.tracks(); gc.collect()
        traced_after,peak = tracemalloc.get_traced_memory();tracemalloc.stop()
        results['tag_cache']={'entries_after_empty_scan':len(library.tag_cache),'retained_traced_bytes':traced_after-traced_before,'peak_traced_bytes':peak,'elapsed_ms':(time.perf_counter()-began)*1000}
        class Extractor:
            calls=0
            def __init__(self,*args,**kwargs): pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def extract_info(self,*args,**kwargs):
                Extractor.calls+=1;time.sleep(.01)
                return {'entries':[{'id':f'{i:011d}','title':f'Result {i}'} for i in range(12)]}
        with patch('ytmp3.app.YoutubeDL',Extractor):
            times=[]
            for i in range(20):
                began=time.perf_counter();library.search('repeated fixture');times.append((time.perf_counter()-began)*1000)
        results['repeated_search']={'times_ms':times,'extractor_calls':Extractor.calls}
    finally:
        server.shutdown();server.server_close();library.pool.shutdown(wait=True)
stop.set()
results['peak_process_tree']={key:max((sample[key] for sample in samples),default=0) for key in ['rss','private','threads','handles','processes','gpu_private']}
results['post_close_process_tree']=processes()
results['unmeasured']=['Android OS/native runtime and actual device battery/power','GPU utilization/VRAM; GPU subprocess private RAM is included','Real external search latency in controlled fixture; live endpoint checked separately']
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps({'output':str(args.output),'ready_ms':round(results['application_ready_ms'],1),'refresh_median_ms':statistics.median(results['library_refresh']['times_ms']),
    'snapshot_writes':results['library_refresh']['writes'],'hidden_bridge_reads':results['hidden_idle']['bridge_reads'],'tag_cache':results['tag_cache'],'extractor_calls':Extractor.calls}))
