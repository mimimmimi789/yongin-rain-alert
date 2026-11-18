import math
def latlon_to_grid(lat, lon):
    RE,GRID,SLAT1,SLAT2,OLON,OLAT,XO,YO=6371.00877,5.0,30.0,60.0,126.0,38.0,43,136
    D=math.pi/180; re=RE/GRID; s1=SLAT1*D; s2=SLAT2*D; ol=OLON*D; oa=OLAT*D
    sn=math.log(math.cos(s1)/math.cos(s2))/math.log(math.tan(math.pi/4+s2/2)/math.tan(math.pi/4+s1/2))
    sf=math.tan(math.pi/4+s1/2)**sn*math.cos(s1)/sn
    ro=re*sf/math.tan(math.pi/4+oa/2)**sn
    ra=re*sf/math.tan(math.pi/4+lat*D/2)**sn
    th=lon*D-ol
    th=(th+2*math.pi) if th<-math.pi else (th-2*math.pi) if th>math.pi else th
    th*=sn
    return int(math.floor(ra*math.sin(th)+XO+0.5)), int(math.floor(ro-ra*math.cos(th)+YO+0.5))
