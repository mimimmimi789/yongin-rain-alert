"""기상청 단기예보 조회서비스(VilageFcstInfoService_2.0)에서 용인시 격자 강수량을 받아
행정동별 시간 강수량(관측 1시간 + 예보 시계열)으로 묶어 JSON으로 출력한다.

사용: KMA_SERVICE_KEY=<일반 인증키(Decoding)> python3 fetch_kma.py [out.json]
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
KST = timezone(timedelta(hours=9))
BASE_DATAGO = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/"
BASE_HUB = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/"
BASE, KEYPARAM = BASE_DATAGO, "serviceKey"


def use_key(key):
    """기상청 API허브 인증키(22자 내외)는 apihub 주소와 authKey 파라미터를, 공공데이터포털 키는 data.go.kr 주소를 쓴다."""
    global BASE, KEYPARAM
    if len(key) < 40:
        BASE, KEYPARAM = BASE_HUB, "authKey"
    else:
        BASE, KEYPARAM = BASE_DATAGO, "serviceKey"


def parse_mm(v):
    """'강수없음', '1mm 미만', '1.0mm 미만', '6.2mm', '30.0~50.0mm', '50.0mm 이상', '0', '-' -> float mm"""
    if v is None:
        return 0.0
    s = str(v).strip()
    if s in ("", "-", "강수없음", "0"):
        return 0.0
    if "미만" in s:
        return 0.5
    m = re.match(r"([\d.]+)\s*~\s*([\d.]+)", s)
    if m:
        return (float(m.group(1)) + float(m.group(2))) / 2
    m = re.match(r"([\d.]+)", s)
    if not m:
        return 0.0
    x = float(m.group(1))
    return x if x >= 0 else 0.0  # 결측(-998.9 등) 방어


def bases(now):
    n = now - timedelta(minutes=40)  # 초단기실황: 정시 자료, 약 40분 후 제공
    ncst = n.replace(minute=0, second=0, microsecond=0)
    u = now - timedelta(minutes=45)  # 초단기예보: HH30 발표, 약 45분 후 제공
    ultra = u.replace(minute=30, second=0, microsecond=0)
    if u.minute < 30:
        ultra -= timedelta(hours=1)
    v = now - timedelta(minutes=10)  # 단기예보: 02,05,...,23시 발표, 약 10분 후 제공
    h = max([x for x in (2, 5, 8, 11, 14, 17, 20, 23) if x <= v.hour], default=None)
    if h is None:
        vil = (v - timedelta(days=1)).replace(hour=23, minute=0, second=0, microsecond=0)
    else:
        vil = v.replace(hour=h, minute=0, second=0, microsecond=0)
    return ncst, ultra, vil


def call(key, op, base_dt, nx, ny, rows):
    q = {KEYPARAM: key}
    q.update(pageNo=1, numOfRows=rows, dataType="JSON",
             base_date=base_dt.strftime("%Y%m%d"), base_time=base_dt.strftime("%H%M"), nx=nx, ny=ny)
    url = BASE + op + "?" + urllib.parse.urlencode(q)
    last = None
    for attempt in range(3):
        try:
            try:
                with urllib.request.urlopen(url, timeout=20) as r:
                    body = r.read().decode("utf-8")
            except urllib.error.HTTPError as he:  # 오류 본문의 사유만 남기고 키가 든 URL은 남기지 않는다
                raise RuntimeError(f"{op} {nx},{ny}: HTTP {he.code} {he.read()[:200].decode('utf-8', 'replace')}") from None
            j = json.loads(body)
            hdr = j["response"]["header"]
            if hdr["resultCode"] != "00":
                raise RuntimeError(f"{op} {nx},{ny}: {hdr['resultCode']} {hdr['resultMsg']}")
            return j["response"]["body"]["items"]["item"]
        except Exception as e:  # noqa
            last = e
            time.sleep(1 + attempt)
    raise RuntimeError(f"{op} {nx},{ny} failed: {last}")


def main():
    key = os.environ.get("KMA_SERVICE_KEY", "").strip()
    if "%" in key:  # Encoding 키를 넣은 경우 이중 인코딩 방지
        key = urllib.parse.unquote(key)
    if not key:
        sys.exit("KMA_SERVICE_KEY 환경 변수가 없습니다.")
    use_key(key)
    gm = json.load(open(os.path.join(HERE, "kma_grid_map.json"), encoding="utf-8"))
    cells = [tuple(c) for c in gm["cells"]]
    now = datetime.now(KST)
    ncst_b, ultra_b, vil_b = bases(now)
    errors = []

    def fetch_cell(c):
        nx, ny = c
        out = {"obs": None, "fc": {}}
        try:
            for it in call(key, "getUltraSrtNcst", ncst_b, nx, ny, 10):
                if it["category"] == "RN1":
                    out["obs"] = parse_mm(it["obsrValue"])
        except Exception as e:
            errors.append(str(e))
        try:
            for it in call(key, "getVilageFcst", vil_b, nx, ny, 1000):
                if it["category"] == "PCP":
                    out["fc"][it["fcstDate"] + it["fcstTime"]] = parse_mm(it["fcstValue"])
        except Exception as e:
            errors.append(str(e))
        try:  # 초단기예보가 겹치는 시간은 더 최신 값으로 덮어씀
            for it in call(key, "getUltraSrtFcst", ultra_b, nx, ny, 60):
                if it["category"] == "RN1":
                    out["fc"][it["fcstDate"] + it["fcstTime"]] = parse_mm(it["fcstValue"])
        except Exception as e:
            errors.append(str(e))
        return c, out

    with ThreadPoolExecutor(max_workers=6) as ex:
        res = dict(ex.map(fetch_cell, cells))

    start = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%Y%m%d%H%M")
    keys = sorted({k for r in res.values() for k in r["fc"] if k >= start})
    times = [datetime.strptime(k, "%Y%m%d%H%M").replace(tzinfo=KST).isoformat() for k in keys]
    dongs, obs = {}, {}
    for d in gm["dongs"]:
        series = []
        for k in keys:
            s = w = 0.0
            for nx, ny, wt in d["cells"]:
                v = res.get((nx, ny), {}).get("fc", {}).get(k)
                if v is not None:
                    s += v * wt; w += wt
            series.append(round(s / w, 2) if w else None)
        dongs[d["cd"]] = series
        s = w = 0.0
        for nx, ny, wt in d["cells"]:
            v = res.get((nx, ny), {}).get("obs")
            if v is not None:
                s += v * wt; w += wt
        obs[d["cd"]] = round(s / w, 2) if w else None

    doc = {
        "updated": now.isoformat(timespec="seconds"),
        "ncst_base": ncst_b.isoformat(), "ultra_base": ultra_b.isoformat(), "village_base": vil_b.isoformat(),
        "times": times, "dongs": dongs,
        "obs": {"time": (ncst_b).isoformat(), "dongs": obs},
        "cells": len(cells), "errors": errors[:10], "error_count": len(errors),
    }
    out = sys.argv[1] if len(sys.argv) > 1 else None
    s = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if out:
        open(out, "w", encoding="utf-8").write(s)
    else:
        print(s)
    print(f"cells={len(cells)} hours={len(times)} errors={len(errors)}", file=sys.stderr)


if __name__ == "__main__":
    main()
