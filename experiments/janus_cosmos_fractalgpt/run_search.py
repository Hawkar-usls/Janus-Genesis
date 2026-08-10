"""Janus Cosmos v0.2 provenance-aware HST feature search runner."""
from __future__ import annotations
import csv, hashlib, json, math, random, sys
from pathlib import Path
WINDOWS=(8,16,32); ORIENTATIONS=tuple(range(0,180,30)); NULLS=256; SEED=20260810

def planner(x,y,scale,orientation):
    a=math.radians(orientation); u=x*math.cos(a)+y*math.sin(a); v=-x*math.sin(a)+y*math.cos(a)
    return math.sin(u*scale*.17)*math.cos(v*scale*.11)

def score(rows):
    if not rows:return 0.0
    return sum(sum(abs(planner(r['x'],r['y'],s,o))*abs(r['signal']) for s in WINDOWS for o in ORIENTATIONS)/(len(WINDOWS)*len(ORIENTATIONS)) for r in rows)/len(rows)

def main(path):
    source=Path(path); rows=[]
    with source.open(newline='',encoding='utf-8') as f:
        for r in csv.DictReader(f): rows.append({'object_id':r['object_id'],'band':r['band'],'x':float(r['x']),'y':float(r['y']),'signal':float(r.get('signal',1.0))})
    if not rows: raise SystemExit('empty feature corpus')
    observed=score(rows); rng=random.Random(SEED); xs=[r['x'] for r in rows]; ys=[r['y'] for r in rows]; null=[]
    for _ in range(NULLS):
        sx=xs[:]; sy=ys[:]; rng.shuffle(sx); rng.shuffle(sy); null.append(score([dict(r,x=x,y=y) for r,x,y in zip(rows,sx,sy)]))
    ge=sum(v>=observed for v in null); p=(ge+1)/(NULLS+1); ns=sorted(null)
    print(json.dumps({'schema':'janus.cosmos.fractalgpt.receipt.v0.2','status':'CANDIDATE_ONLY' if p<.05 else 'NO_CANDIDATE','corpus_rows':len(rows),'object_count':len({r['object_id'] for r in rows}),'band_count':len({r['band'] for r in rows}),'observed_score':observed,'null_median':ns[len(ns)//2],'p_empirical':p,'windows':list(WINDOWS),'orientations':list(ORIENTATIONS),'nulls':NULLS,'seed':SEED,'semantic_analysis':False,'null_model':'independent x/y coordinate permutation preserving row signal and band','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'claim_ceiling':'Image-level statistical candidate only; independent astronomical replication required.'},indent=2,sort_keys=True))
if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: python run_search.py <hst_features.csv>')
    main(sys.argv[1])
