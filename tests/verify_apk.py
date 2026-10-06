"""Verify ROM integrity, the ARM64 ELF headers, manifest identity and exported entry point."""
from pathlib import Path
import argparse,hashlib,json,math,re,struct,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));import bootstrap
EXE='.exe' if bootstrap.HOST=='windows' else ''
BT=ROOT/'.tools/buildtools/android-15'
TARGETS={'quest':('org.timecrisis.quest',ROOT/'artifacts/TimeCrisisVR-quest3-debug.apk','package-libs'),
         'frame':('org.timecrisis.frame',ROOT/'artifacts/frame/TimeCrisisVR-frame-debug.apk','package-libs-frame')}
p=argparse.ArgumentParser();p.add_argument('--target',choices=sorted(TARGETS),default='quest');p.add_argument('--apk',type=Path);args=p.parse_args()
package,default_apk,libs_dir=TARGETS[args.target]
apk=(args.apk or default_apk).resolve();info=json.loads(apk.with_name('build-info.json').read_text());bundled=info['roms_bundled']
assert info.get('target','quest')==args.target,'APK was built for '+info.get('target','quest')
with zipfile.ZipFile(apk) as z:
    assert z.testzip() is None
    manifest=z.read('assets/roms.sha256').decode().splitlines()
    assert len(manifest)==31, len(manifest)
    if not bundled:assert not any(n.startswith('assets/roms/') or n.endswith('timecris.zip') for n in z.namelist()),'ROM-free APK must not bundle ROMs'
    for line in manifest:
        digest,name=line.split('  ',1)
        data=z.read('assets/roms/'+name) if bundled else (ROOT/'build/assets/roms'/name).read_bytes()
        assert hashlib.sha256(data).hexdigest()==digest,name
    for line in z.read('assets/models.sha256').decode().splitlines():
        digest,name=line.split('  ',1);model=z.read('assets/models/'+name)
        assert hashlib.sha256(model).hexdigest()==digest,name
        assert model==(ROOT/'quest/assets/models'/name).read_bytes(),name
        assert model[:8] in (b'TCGUN001',b'TCGUN002')
        vertices,indices=struct.unpack_from('<2I',model,8)
        assert 0<vertices<=100000 and 0<indices<=300000 and indices%3==0
        if model[:8]==b'TCGUN001':
            w,h=struct.unpack_from('<2I',model,16);assert 0<w<=2048 and 0<h<=2048
            assert len(model)==36+vertices*32+indices*4+w*h*4
            offset,stride=36,32
        else:
            offset,stride=28,40
            assert len(model)==offset+vertices*stride+indices*4
            parts=set()
            for v in struct.iter_unpack('<10f',model[offset:offset+vertices*stride]):
                assert all(math.isfinite(x) for x in v)
                assert all(0<=x<=1 for x in v[6:9]) and v[9] in (0,1,2)
                parts.add(v[9])
            assert parts=={0,1,2}
        assert all(math.isfinite(x) for x in struct.unpack_from('<3f',model,offset-12))
        assert max(struct.unpack_from(f'<{indices}I',model,offset+vertices*stride))<vertices
    libs=[n for n in z.namelist() if n.startswith('lib/')]
    assert sorted(libs)==['lib/arm64-v8a/libSDL2.so','lib/arm64-v8a/libmain.so','lib/arm64-v8a/libopenxr_loader.so']
    for lib in libs:
        elf=z.read(lib);assert elf[:5]==b'\x7fELF\x02';assert struct.unpack_from('<H',elf,18)[0]==183,lib
    assert z.read('classes.dex')[:4]==b'dex\n'
    for name in ['namco22-LICENSE.txt','SDL2-LICENSE.txt','OpenXR-LICENSE.txt']:assert z.read('assets/licenses/'+name)
badging=subprocess.check_output([str(BT/('aapt'+EXE)),'dump','badging',str(apk)],text=True)
assert f"package: name='{package}'" in badging
entry='MainActivity' if bundled else 'LauncherActivity'
assert f"launchable-activity: name='org.timecrisis.quest.{entry}'" in badging
tree=subprocess.check_output([str(BT/('aapt'+EXE)),'dump','xmltree',str(apk),'AndroidManifest.xml'],text=True)
activities=re.findall(r'(?ms)^([ ]+)E: activity\b(.*?)(?=^\1E: |\Z)',tree)
# Both builds use the shared org.timecrisis.quest classes, short or fully qualified.
def activity(name):return next(block for _,block in activities if re.search(r'="(?:org\.timecrisis\.quest)?\.'+name+'"',block))
main=activity('MainActivity');setup=activity('LauncherActivity')
categories=['org.khronos.openxr.intent.category.IMMERSIVE_HMD']+(['com.oculus.intent.category.VR'] if args.target=='quest' else [])
for category in categories:
    assert category in main,'The actual OpenXR activity must be marked immersive'
    assert category not in setup,'Setup must not masquerade as the immersive game'
assert package+'.setup' in setup,'Setup needs a separate Android task'
assert ('android.intent.category.LAUNCHER' in main)==bundled
assert "native-code: 'arm64-v8a'" in badging
if args.target=='quest':assert 'quest2|quest3|quest3s' in tree,'Quest 2 must not fall back to an older-device compatibility profile'
if args.target=='frame':
    assert 'com.oculus' not in tree,'Steam Frame manifest must not carry Quest-only entries'
    preferences=json.loads(apk.with_name('vrpreferences.json').read_text())
    assert preferences['steam_frame']['preferMinRefreshRate']>=72,'vrpreferences.json must sit beside the APK'
readelf=ROOT/(f'.tools/ndk/android-ndk-r27c/toolchains/llvm/prebuilt/{bootstrap.HOST}-x86_64/bin/llvm-readelf'+EXE)
symbols=subprocess.check_output([str(readelf),'--dyn-syms',str(ROOT/'build'/libs_dir/'libmain.so')],text=True)
assert ' SDL_main' in symbols
assert info['sha256']==hashlib.sha256(apk.read_bytes()).hexdigest()
print(f'APK verified ({args.target}): bundled={bundled}, 31 chip hashes, gun, ARM64/DEX/SDL_main, {entry} launcher, actual game marked immersive, isolated setup task, licenses and hash')
