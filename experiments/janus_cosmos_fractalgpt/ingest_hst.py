"""Small public HST/MAST image ingestion gate for Janus Cosmos.
Requires numpy and astropy. MAST zcut returns ZIP/FITS cutouts; this pilot samples
those images to a fixed grid and emits provenance plus pixel features."""
from __future__ import annotations
import csv, io, json, sys, urllib.parse, urllib.request, zipfile
import numpy as np
from astropy.io import fits

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Janus-Cosmos/0.1'})
    with urllib.request.urlopen(req,timeout=90) as r:return r.read()

def resize(a,n=64):
    a=np.asarray(a,dtype=float); a=np.nan_to_num(a,nan=0.0,posinf=0.0,neginf=0.0)
    if a.ndim>2:a=np.squeeze(a)
    if a.ndim!=2:return None
    yy=np.linspace(0,a.shape[0]-1,n).astype(int); xx=np.linspace(0,a.shape[1]-1,n).astype(int)
    b=a[np.ix_(yy,xx)]; b-=np.median(b); s=np.std(b); return b/(s if s>0 else 1.0)

def main(manifest,out):
    m=json.load(open(manifest,encoding='utf-8')); rows=[]
    for item in m['targets']:
        q=urllib.parse.urlencode({'ra':item['ra'],'dec':item['dec'],'x':item.get('size_px',96),'y':item.get('size_px',96),'units':'px','cutout_format':'fits'})
        url='https://mast.stsci.edu/zcut/api/v0.1/astrocut?'+q; blob=fetch(url)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names=[n for n in z.namelist() if n.lower().endswith(('.fits','.fit','.fits.gz'))]
            if not names: raise RuntimeError(f'No FITS product returned for {item["object_id"]}')
            for fn in names:
                with fits.open(io.BytesIO(z.read(fn)),memmap=False) as hdul:
                    arr=next((np.asarray(h.data) for h in hdul if getattr(h,'data',None) is not None and np.asarray(h.data).ndim==2),None)
                arr=resize(arr,64)
                if arr is None:continue
                for iy,y in enumerate(np.linspace(-1,1,64)):
                    for ix,x in enumerate(np.linspace(-1,1,64)):
                        rows.append({'object_id':item['object_id'],'band':fn,'x':float(x),'y':float(y),'signal':float(arr[iy,ix]),'source_url':url,'source_file':fn})
    with open(out,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['object_id','band','x','y','signal','source_url','source_file']);w.writeheader();w.writerows(rows)
    print(json.dumps({'status':'INGESTED','rows':len(rows),'objects':sorted({r['object_id'] for r in rows})},indent=2))
if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('usage: python ingest_hst.py manifest.json output.csv')
    main(sys.argv[1],sys.argv[2])
