"""Fetch a small, public HST/MAST image manifest and extract deterministic features.

This first ingestion gate uses MAST zcut, which can return FITS/image cutouts
for a sky position. It intentionally keeps the pilot tiny; scaling happens only
after provenance and null tests pass.
"""
from __future__ import annotations
import csv, io, json, math, sys, urllib.parse, urllib.request, zipfile
from pathlib import Path

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Janus-Cosmos/0.1'})
    with urllib.request.urlopen(req,timeout=60) as r:return r.read()

def main(manifest,out):
    m=json.load(open(manifest,encoding='utf-8')); rows=[]
    for item in m.get('targets',[]):
        ra,dec=item['ra'],item['dec']; size=item.get('size_px',100)
        q=urllib.parse.urlencode({'ra':ra,'dec':dec,'x':size,'y':size,'units':'px','cutout_format':'fits'})
        url='https://mast.stsci.edu/zcut/api/v0.1/astrocut?'+q
        blob=fetch(url)
        # Keep provenance; numerical image extraction is deliberately delegated to
        # the next stage if the archive response contains FITS binary products.
        rows.append({'object_id':item['object_id'],'band':item.get('band','HST'),'x':float(ra),'y':float(dec),'signal':1.0,'source_url':url,'bytes':len(blob)})
    with open(out,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['object_id','band','x','y','signal','source_url','bytes']);w.writeheader();w.writerows(rows)
if __name__=='__main__':
    if len(sys.argv)!=3: raise SystemExit('usage: python ingest_hst.py manifest.json output.csv')
    main(sys.argv[1],sys.argv[2])
