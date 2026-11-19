# OSM 터널 구간 중 '지하차도'(도로·철도 밑을 지나는 낮은 통로)만 골라 roads.json 도로 구간과 연결 -> underpass.json
# 산악 터널은 제외: 이름에 터널/생태 포함, 또는 터널 가운데 지반이 양쪽 입구보다 12m 이상 높으면 산을 뚫은 것으로 봄
# 사용: python3 build_underpass.py osm_roads.json ../landslide/roads.json DEM.tif underpass.json
import json, sys, numpy as np, rasterio
from pyproj import Transformer
from shapely.geometry import LineString, Polygon, Point
SRC, ROADS, DEMF, OUT = sys.argv[1:5]
to5186 = Transformer.from_crs(4326, 5186, always_xy=True)
J = json.load(open(SRC, encoding='utf-8'))
R = json.load(open(ROADS, encoding='utf-8'))
nodes = {e['id']: to5186.transform(e['lon'], e['lat']) for e in J['elements'] if e['type'] == 'node'}
tw = [w for w in J['elements'] if w['type'] == 'way' and w.get('tags', {}).get('tunnel') not in (None, 'no') and all(n in nodes for n in w['nodes'])]
r = rasterio.open(DEMF); dem = r.read(1).astype(float); dem[dem < -1000] = np.nan
def z(x, y):
    c = int((x - r.transform.c) / 90); rr = int((r.transform.f - y) / 90)
    return float(dem[rr, c]) if 0 <= rr < dem.shape[0] and 0 <= c < dem.shape[1] else np.nan
def lowrank(x, y, rad=1500):
    c = int((x - r.transform.c) / 90); rr = int((r.transform.f - y) / 90); k = rad // 90
    w = dem[max(0, rr - k):rr + k + 1, max(0, c - k):c + k + 1]; w = w[~np.isnan(w)]
    zz = z(x, y); return float((w < zz).mean()) if len(w) and not np.isnan(zz) else 0.5
polys = [(i, [Polygon(rg) for rg in d['rings']]) for i, d in enumerate(R['dongs'])]
def dong(x, y):
    p = Point(x, y)
    for i, ps in polys:
        if any(q.contains(p) for q in ps): return i
    return -1
# 도로 구간 매칭용
vid = {tuple(v): i for i, v in enumerate(R['verts'])}
E = R['edges']
eByPair = {}
for i, e in enumerate(E): eByPair.setdefault(frozenset((e[0], e[1])), []).append(i)
info = []
for w in tw:
    tg = w['tags']; pts = [nodes[n] for n in w['nodes']]; ls = LineString(pts)
    nm = tg.get('name', ''); hw = tg['highway']
    m = ls.interpolate(.5, normalized=True)
    za, zb, zm = z(*pts[0]), z(*pts[-1]), z(m.x, m.y)
    hump = zm - np.nanmean([za, zb]) if not np.isnan(zm) else 0
    vs = set(vid.get((round(x), round(y))) for x, y in pts) - {None}
    es = sorted({i for a in vs for b in vs if a != b for i in eByPair.get(frozenset((a, b)), [])})
    info.append(dict(w=w, ls=ls, nm=nm, hw=hw, hump=hump, es=es, mid=(m.x, m.y)))
def is_under(t):
    nm = t['nm']
    if any(k in nm for k in ('지하차도', '지하도로', '굴다리')): return True
    if any(k in nm for k in ('터널', '생태', '통로')): return False
    if t['hw'].startswith('motorway'): return False
    return t['ls'].length <= 700 and t['hump'] < 12
cand = [t for t in info if is_under(t) and t['es']]
# 같은 지하차도의 상·하행 묶기 (60m 이내, 이름이 같거나 한쪽이 이름 없음)
par = list(range(len(cand)))
def f(i):
    while par[i] != i: par[i] = par[par[i]]; i = par[i]
    return i
for i in range(len(cand)):
    for j in range(i + 1, len(cand)):
        a, b = cand[i], cand[j]
        if (a['nm'] == b['nm'] or not a['nm'] or not b['nm']) and a['ls'].distance(b['ls']) < 60: par[f(i)] = f(j)
grp = {}
for i, t in enumerate(cand): grp.setdefault(f(i), []).append(t)
out = []
for ts in grp.values():
    es = sorted({i for t in ts for i in t['es']})
    L = max(t['ls'].length for t in ts)
    if L < 40: continue
    x, y = np.mean([t['mid'][0] for t in ts]), np.mean([t['mid'][1] for t in ts])
    di = dong(x, y)
    if di < 0: continue  # 용인시 밖
    names = [t['nm'] for t in ts if t['nm']]
    nm = next((n for n in names if '지하' in n or '굴다리' in n), None)
    road = next((n for n in names if n), None) or next((R['names'][E[i][4]] for i in es if R['names'][E[i][4]]), '')
    named = nm is not None
    if not nm: nm = (road + ' ' if road else '') + '지하 구간'
    zz = z(x, y)
    out.append(dict(nm=nm, named=named, road=road if road != nm else '', d=di, es=es, x=round(x), y=round(y), L=round(L),
                    z=None if np.isnan(zz) else round(zz), low=round(lowrank(x, y), 2), cls=min(E[i][3] % 10 for i in es)))
out.sort(key=lambda u: (not u['named'], u['cls'], -u['L']))
json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(len(out), 'named', sum(u['named'] for u in out))
for u in out: print(u['nm'], R['dongs'][u['d']]['nm'], u['L'], 'low', u['low'], 'z', u['z'], 'es', len(u['es']))
