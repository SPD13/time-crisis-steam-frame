"""Summarize Quest or Steam Frame runtime samples; skip intervals with zero app render scale.

FPS values are one-second runtime counters, not a per-frame latency trace. Different
play sessions are observational comparisons, not a deterministic benchmark.
"""
from pathlib import Path
import argparse, datetime, json, re, shutil, statistics, subprocess, time

def summarize(directory):
    text=(directory/'android.log').read_text(errors='replace')
    samples=[]; idle=0
    for line in text.splitlines():
        match=re.search(r'FPS=(\d+)/(\d+).*?Stale=(\d+),',line)
        if not match:continue
        scale=re.search(r'SF=([\d.]+)',line)
        if not scale or float(scale[1])<=0:
            idle+=1;continue
        fps,hz,stale=map(int,match.groups())
        def field(pattern):
            found=re.search(pattern,line)
            return float(found[1]) if found else None
        samples.append(dict(fps=fps,hz=hz,stale=stale,
            cpu_gpu_ms=field(r'CPU&GPU=([\d.]+)ms'),
            temperature_c=field(r'Temp=([\d.]+)C')))
    def distribution(values):
        values=sorted(v for v in values if v is not None)
        if not values:return None
        return dict(mean=round(statistics.mean(values),3),minimum=values[0],
            p05=values[int((len(values)-1)*.05)],median=statistics.median(values),
            p95=values[int((len(values)-1)*.95)],maximum=values[-1])
    game=(directory/'game.log').read_text(errors='replace')
    frames=re.findall(r'\[TC\] frame (\d+)',game)
    report=dict(active_runtime_samples=len(samples),idle_samples_excluded=idle,
        target_hz=sorted(set(s['hz'] for s in samples)),
        fps=distribution(s['fps'] for s in samples),
        runtime_cpu_gpu_ms=distribution(s['cpu_gpu_ms'] for s in samples),
        temperature_c=distribution(s['temperature_c'] for s in samples),
        stale_total=sum(s['stale'] for s in samples),
        last_game_frame=int(frames[-1]) if frames else 0,
        errors=[line for line in game.splitlines() if re.search(r'GL error|fault [1-9]|traps [1-9]|initialization failed',line)],
        note='One-second runtime counters; excludes SF=0 idle intervals. Different game sessions are not a controlled scene comparison.')
    # The app's own render timing; the only frame-rate evidence on runtimes without Meta's FPS log.
    xr=[tuple(map(float,m)) for m in re.findall(r'\[XRPERF\] render wall mean ([\d.]+) ms max ([\d.]+) ms over-budget (\d+)/(\d+) period ([\d.]+) ms',game)]
    report['app_render_ms']=distribution(m[0] for m in xr)
    report['app_over_budget_percent']=round(100*sum(m[2] for m in xr)/sum(m[3] for m in xr),3) if xr else None
    report['app_display_period_ms']=sorted(set(m[4] for m in xr))
    total=sum(s['hz'] for s in samples)
    report['stale_per_target_frame_percent']=round(100*report['stale_total']/total,3) if total else None
    (directory/'performance.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path)
    parser.add_argument('--capture',action='store_true');parser.add_argument('--serial')
    parser.add_argument('--package',default='org.timecrisis.quest',help='org.timecrisis.frame for the Steam Frame build')
    parser.add_argument('--seconds',type=int,default=0,help='Stream a fresh measurement window instead of reading the log ring buffer')
    args=parser.parse_args();args.directory.mkdir(parents=True,exist_ok=True)
    if args.capture:
        adb=[shutil.which('adb') or r'C:\platform-tools\adb.exe']+(['-s',args.serial] if args.serial else [])
        def call(*cmd):return subprocess.check_output(adb+list(cmd)).decode(errors='replace')
        pid=call('shell','pidof',args.package).strip()
        if not pid:raise SystemExit('App is not running.')
        if args.seconds:
            start=datetime.datetime.now(datetime.timezone.utc).isoformat()
            initial=call('exec-out','run-as',args.package,'cat','files/timecris-vr.log')
            (args.directory/'initial-game.log').write_text(initial)
            frames=re.findall(r'\[TC\] frame (\d+)',initial)
            with (args.directory/'android.log').open('w') as stream:
                process=subprocess.Popen(adb+['logcat','-T','1','--pid='+pid,'-v','brief'],stdout=stream,stderr=subprocess.DEVNULL)
                try:
                    deadline=time.monotonic()+args.seconds
                    while time.monotonic()<deadline:time.sleep(min(1,max(0,deadline-time.monotonic())))
                finally:
                    process.terminate();process.wait(timeout=10)
            (args.directory/'window.json').write_text(json.dumps(dict(start_utc=start,end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),requested_seconds=args.seconds,pid=pid,initial_game_frame=int(frames[-1]) if frames else 0),indent=2)+'\n')
        else:
            (args.directory/'android.log').write_text(call('logcat','-d','--pid='+pid,'-v','brief'))
        current_pid=call('shell','pidof',args.package).strip()
        if current_pid!=pid:
            (args.directory/'game.log').write_text(initial if args.seconds else '')
            if args.seconds:
                window=json.loads((args.directory/'window.json').read_text());window['interrupted_by_app_restart']=True
                (args.directory/'window.json').write_text(json.dumps(window,indent=2)+'\n')
        else:
            (args.directory/'game.log').write_text(call('exec-out','run-as',args.package,'cat','files/timecris-vr.log'))
    print(json.dumps(summarize(args.directory),indent=2))
