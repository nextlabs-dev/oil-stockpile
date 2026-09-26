import json, math
W,H=1000,720
LON0,LON1=124.0,151.0
s=W/math.radians(LON1-LON0)
def merc(lat): return math.log(math.tan(math.pi/4+math.radians(lat)/2))
midlat=37.2
ym=merc(midlat)
def proj(lon,lat):
    return ((math.radians(lon-LON0))*s, H/2-(merc(lat)-ym)*s)
# report lat range
def inv(y): return math.degrees(2*math.atan(math.exp((H/2-y)/s+ym))-math.pi/2)
print("lat range",inv(H),inv(0))
M=25
BB=(-M,-M,W+M,H+M)
def clip(poly):
    def inside(p,e):
        x,y=p
        return {0:x>=BB[0],1:y>=BB[1],2:x<=BB[2],3:y<=BB[3]}[e]
    def inter(a,b,e):
        (x1,y1),(x2,y2)=a,b
        if e in(0,2):
            xe=BB[e]; t=(xe-x1)/(x2-x1); return (xe,y1+t*(y2-y1))
        ye=BB[e]; t=(ye-y1)/(y2-y1); return (x1+t*(x2-x1),ye)
    out=poly
    for e in range(4):
        inp=out; out=[]
        if not inp: break
        S=inp[-1]
        for P in inp:
            if inside(P,e):
                if not inside(S,e): out.append(inter(S,P,e))
                out.append(P)
            elif inside(S,e): out.append(inter(S,P,e))
            S=P
    return out
def dp(pts,eps):
    if len(pts)<3: return pts
    (x1,y1),(x2,y2)=pts[0],pts[-1]
    dx,dy=x2-x1,y2-y1; L=math.hypot(dx,dy)
    imax,dmax=0,0
    for i in range(1,len(pts)-1):
        x,y=pts[i]
        d=abs(dy*x-dx*y+x2*y1-y2*x1)/L if L else math.hypot(x-x1,y-y1)
        if d>dmax: imax,dmax=i,d
    if dmax>eps:
        return dp(pts[:imax+1],eps)[:-1]+dp(pts[imax:],eps)
    return [pts[0],pts[-1]]
def area(p): return abs(sum(p[i][0]*p[(i+1)%len(p)][1]-p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p))))/2
d=json.load(open('ne_50m_land.geojson'))
paths=[];npts=0
for f in d['features']:
    g=f['geometry']; polys=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
    for poly in polys:
        for ring in poly:
            pr=[proj(*c[:2]) for c in ring]
            if pr[0]!=pr[-1]: pr.append(pr[0])
            c=clip(pr)
            if len(c)<3 or area(c)<6: continue
            sp=dp(c+[c[0]],1.1)[:-1]
            if len(sp)<3 or area(sp)<6: continue
            npts+=len(sp)
            paths.append("M"+" ".join(f"{x:.1f},{y:.1f}" for x,y in sp)+"Z")
path="".join(paths)
open('coast.txt','w').write(path)
print(len(paths),"rings",npts,"pts",len(path),"chars")
