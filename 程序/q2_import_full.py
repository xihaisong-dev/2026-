"""Import verified server archive without replacing different local evidence."""
import argparse, hashlib, shutil, zipfile
from q1_io import ROOT, write_json


def main():
    ap=argparse.ArgumentParser();ap.add_argument('archive');ap.add_argument('--sha256',required=True);a=ap.parse_args()
    with open(a.archive,'rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    assert digest==a.sha256
    evidence=ROOT/'审查/证据/20260924-A-q2-full-r05';receipt=evidence/'server_receipt.json';assert not receipt.exists()
    count=0
    with zipfile.ZipFile(a.archive) as z:
        for item in z.infolist():
            if item.is_dir():continue
            if item.filename in {'full_launch.log','full_post.log'}:p=evidence/'server'/item.filename
            else:
                assert item.filename.startswith('图表/runs/20260924-A-q2-full-r05/')
                p=ROOT/item.filename
            assert p.resolve().is_relative_to(ROOT.resolve())
            if p.exists():assert p.read_bytes()==z.read(item)
            else:
                p.parent.mkdir(parents=True,exist_ok=True)
                with z.open(item) as source,p.open('xb') as dest:shutil.copyfileobj(source,dest)
            count+=1
    write_json(receipt,dict(archive=a.archive,sha256=digest,files=count,existing_different_files_overwritten=0))
    print('IMPORTED',count,digest)


if __name__=='__main__':main()
