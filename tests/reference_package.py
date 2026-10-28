"""Developer-only A/B artifact: original node + original backend, same dependencies."""
import hashlib,json,os,shutil,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from common import digest,atomic

def prepare(target):
    record=json.loads((ROOT/'releases'/ (target+'.json')).read_text());meta=json.loads((ROOT/'build'/target/'current.json').read_text());work=Path(meta['stage']).parent
    source=Path(record['install']);stage=work/'reference-package/install'
    if stage.exists():shutil.rmtree(stage)
    shutil.copytree(source,stage,copy_function=os.link)
    baseline=work/'reference-stage'
    for src,dest in [(baseline/'lib/vins/vins_node',stage/'bin/vins_node'),(baseline/'lib/libvins_lib.so',stage/'lib/libvins_lib.so')]:
        dest.unlink();shutil.copy2(src,dest);subprocess.run([ROOT/'cache/tools/patchelf/usr/bin/patchelf','--remove-rpath',dest],check=True)
    release=json.loads((stage/'release.json').read_text());release.update(variant='pristine-upstream-reference',algorithm_commit='be55a937a57436548ddfb1bd324bc1e9a9e828e0')
    (stage/'release.json').unlink();atomic(stage/'release.json',release)
    (stage/'files.json').unlink();manifest={str(p.relative_to(stage)):digest(p) for p in sorted(stage.rglob('*')) if p.is_file()};atomic(stage/'files.json',manifest)
    ident=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:16];dest=source.parent.parent/ident;dest.mkdir(exist_ok=True)
    if not (dest/'install').exists():shutil.copytree(stage,dest/'install',copy_function=os.link)
    archive=dest/Path(record['archive']).name
    with tarfile.open(archive,'w:gz') as t:t.add(dest/'install',arcname='install')
    result=dict(record,id=ident,install=str(dest/'install'),archive=str(archive),sha256=digest(archive),files=len(manifest))
    atomic(dest/'package.json',result);atomic(ROOT/'build'/(target+'-reference-package.json'),result);print(json.dumps(result));return result
if __name__=='__main__':prepare(sys.argv[1])
