"""Real owned native/API pause preloading; no user process is controlled."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import socket
import sys
import threading
import time
import urllib.request
from unittest.mock import patch


def preload_outcome(value):
    native = value['native']
    if native['preloadLimited']:
        return 'limited'
    if native['cacheComplete']:
        return 'complete'
    return None


def budget_stable(byte_samples, budget, range_bytes):
    # The caller samples for three seconds after the cap. Allow one pending
    # Range read, but require the last second (six samples) to stop growing.
    return (len(byte_samples) >= 16 and
            max(byte_samples) <= budget + range_bytes and
            len(set(byte_samples[-6:])) == 1)


def wait_server_started(server, thread, timeout=5):
    deadline = time.monotonic() + timeout
    while not server.started:
        if not thread.is_alive():
            raise RuntimeError('Test API exited before listening')
        if time.monotonic() >= deadline:
            raise TimeoutError('Test API did not start')
        time.sleep(.01)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--native-package', type=Path, required=True)
    parser.add_argument('--prefetch-package', type=Path, required=True)
    parser.add_argument('--mpv', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--software', action='store_true')
    parser.add_argument('--cache-budget', type=int)
    args = parser.parse_args()
    staging = tempfile.TemporaryDirectory()
    stage = Path(staging.name); backend = stage/'backend'; backend.mkdir()
    for source in (args.native_package.resolve()/'src',args.prefetch_package.resolve()/'src'):
        for file in source.glob('*.py'):shutil.copyfile(file,backend/file.name)
    patch_file=Path(__file__).resolve().parents[1]/'enable-paused-preload.patch'
    subprocess.run(['git','-C',str(stage),'apply',str(patch_file)],check=True)
    sys.path[:0] = [str(backend),str(Path(__file__).resolve().parent)]
    import desktop_native as module
    from desktop_native import NativeHost, NativeSession
    from desktop_hls_service import HlsJobs, make_router
    from desktop_prefetch import EpisodePrefetcher
    from desktop_stream import ProgressiveSource, source_progress
    from progressive_fixture import ProgressiveFixture
    from fastapi import FastAPI
    import uvicorn
    assert hashlib.sha256(args.source.read_bytes()).hexdigest() == args.sha
    if args.cache_budget: module.CACHE_FILE_BUDGET = args.cache_budget
    run = args.run.resolve()
    (run/'reports').mkdir(parents=True,exist_ok=True)
    work = run/('pause-work-'+str(time.time_ns()))
    work.mkdir(parents=True)
    app = FastAPI()
    fixture = ProgressiveFixture(app, work, [args.source])
    host = NativeHost(parent_pid=os.getpid(), hardware=not args.software,
                      dll_path=args.mpv.resolve())
    assert host.available
    hwnd = host.user.CreateWindowExW(0x08000080, 'STATIC', 'Owned pause preload test',
                                    0x00CF0000, -20000, -20000, 960, 640, None, None, None, None)
    assert hwnd
    encodes = []
    def encode(*a, **kw): encodes.append(True); raise AssertionError('Unexpected encoding')
    listener = socket.socket(); listener.bind(('127.0.0.1',0))
    origin = 'http://127.0.0.1:'+str(listener.getsockname()[1])
    prefetch = EpisodePrefetcher(lambda _:fixture.source(origin,0),
        lambda _:({},[{'index':i,'vid':str(1234567890123456+i)} for i in range(1,5)]),
        work/'cache', encoder=encode, download_loader=lambda _:args.source, source_status=source_progress)
    jobs = HlsJobs(work,prefetch.load_source,native=host,encoder=encode,
                   on_start=prefetch.begin,before_work=prefetch.before_work,on_finish=prefetch.finish)
    key = secrets.token_hex(32)
    app.include_router(make_router(jobs,lambda value:value==key))
    server = uvicorn.Server(uvicorn.Config(app,log_level='critical'))
    server_thread = threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True)
    server_thread.start()
    report = {'pass':False,'forcedSoftware':args.software,'cacheBudget':module.CACHE_FILE_BUDGET,
              'sourceSha256':args.sha,'checks':[],'pausedSamples':[]}
    done = threading.Event()
    errors = []
    def request(path,method='GET',body=None):
        headers={'x-api-key':key,'x-desktop-codec-negotiation':'1'}
        if body is not None: headers['content-type']='application/json'
        with urllib.request.urlopen(urllib.request.Request(origin+'/desktop/hls'+path,method=method,
                headers=headers,data=json.dumps(body).encode() if body is not None else None),timeout=6) as response:
            return None if response.status==204 else json.load(response)
    def check(name,condition,evidence=None):
        row={'name':name,'pass':bool(condition),'evidence':evidence}
        report['checks'].append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
        assert condition,name
    def wait(identifier,predicate,timeout=15):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            value=request('/'+identifier+'/status')
            if predicate(value): return value
            if value.get('native',{}).get('state')=='failed': raise AssertionError('Native failed')
            time.sleep(.1)
        raise AssertionError('Native timeout')
    def scenario():
        identifier=None
        try:
            identifier=request('?series_id=1234567890123456&ep=1','POST')['id']
            wait(identifier,lambda s:bool(s.get('source')))
            request('/'+identifier+'/mode','POST',{'mode':'native'})
            initial=wait(identifier,lambda s:s.get('native',{}).get('state')=='ready')
            session=host.sessions[identifier]
            check('first-frame-before-full-input',not initial['sourceProgress']['complete'] and initial['native']['outputReady'],initial)
            started=time.monotonic()
            while time.monotonic()-started<60:
                value=request('/'+identifier+'/status');report['pausedSamples'].append(value)
                if preload_outcome(value):break
                time.sleep(.2)
            limited = preload_outcome(value) == 'limited'
            if limited:
                # A flag only confirms that the option commands were issued.
                # Observe the byte count afterwards to catch ignored commands.
                byte_samples = [value['native']['cacheFileBytes']]
                for _ in range(15):
                    time.sleep(.2)
                    value = request('/'+identifier+'/status')
                    report['pausedSamples'].append(value)
                    byte_samples.append(value['native']['cacheFileBytes'])
                check('disk-budget-growth-stabilizes',
                      budget_stable(byte_samples, module.CACHE_FILE_BUDGET, ProgressiveSource.block_size),
                      {'bytes': byte_samples, 'observationSeconds': 3,
                       'allowedOvershootBytes': ProgressiveSource.block_size})
            samples=report['pausedSamples']
            check('pause-position-fixed',all(s['native']['paused'] and abs(s['native']['time'])<.1 for s in samples))
            if not limited:
                check('paused-bytes-and-range-advance',value['sourceProgress']['receivedBytes']>initial['sourceProgress']['receivedBytes'] and
                      value['native']['bufferEnd']>initial['native']['bufferEnd'],{'initial':initial,'last':value})
            if limited:
                check('disk-budget-keeps-original-decoder',value['native']['preloadLimited'] and
                      value['native']['state']=='ready' and not encodes,value)
            else:
                check('paused-preload-past-12-seconds-to-eof',value['sourceProgress']['complete'] and
                      value['native']['cacheComplete'] and value['native']['bufferEnd']==value['duration'] and
                      value['native']['bufferEnd']>12,value)
                check('payload-cached-on-disk',value['native']['cacheFileBytes']>0 and not value['native']['preloadLimited'])
            for rate in (2,3):
                request('/'+identifier+'/control','POST',{'paused':False,'rate':rate,'volume':0})
                state=wait(identifier,lambda s:s['native']['rate']==rate and not s['native']['paused'])
                position=state['native']['time']
                # Resuming software output can take longer than a fixed sleep.
                # This checks eventual progress/sync, not real-time throughput.
                state=wait(identifier,lambda s:s['native']['time']>position+1 and
                           not s['native']['buffering'],timeout=6)['native']
                check(str(rate)+'x-resumes-default-audio',state['time']>position+1 and abs(state['avsync'])<.1 and
                      state['audioDevice']=='auto' and state['audioOutput']=='wasapi' and
                      (not args.software or state['hwdec']=='no'),state)
            request('/'+identifier+'/control','POST',{'paused':True,'seek':25})
            wait(identifier,lambda s:s['native']['paused'] and not s['native']['seeking'] and abs(s['native']['time']-25)<.15)
            check('future-three-downloads-zero-encoding',prefetch.wait_idle(3) and
                  prefetch.snapshot()['downloadCompletedEpisodes']==[2,3,4] and not encodes,prefetch.snapshot())
            directory=jobs.get(identifier).directory
            request('/'+identifier,'DELETE');identifier=None
            check('release-closes-thread-and-temporary-cache',not session.thread.is_alive() and
                  not directory.exists() and not jobs.jobs and not host.sessions)
            report['pass']=True
        except BaseException as exc: errors.append(type(exc).__name__);report['errorType']=type(exc).__name__
        finally:
            if identifier:jobs.release(identifier)
            prefetch.close();done.set()
    with patch.object(NativeSession,'forward_input',return_value=True):
        try:
            wait_server_started(server, server_thread)
        except (RuntimeError, TimeoutError):
            prefetch.close()
            server.should_exit = True
            server_thread.join(5)
            listener.close()
            host.user.DestroyWindow(hwnd)
            raise
        client=threading.Thread(target=scenario,daemon=True);client.start()
        message=W.MSG()
        while not done.is_set():
            while host.user.PeekMessageW(C.byref(message),None,0,0,1):
                host.user.TranslateMessage(C.byref(message));host.user.DispatchMessageW(C.byref(message))
            time.sleep(.005)
        client.join(2)
    server.should_exit=True;server_thread.join(5);host.user.DestroyWindow(hwnd)
    name='paused-preload'+('-budget' if args.cache_budget else '')+('-software' if args.software else '')+'.json'
    target=run/'reports'/name
    if target.exists():target.rename(target.with_name(target.stem+'-attempt-'+str(time.time_ns())+'.json'))
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    assert report['pass'],errors


if __name__=='__main__': main()
