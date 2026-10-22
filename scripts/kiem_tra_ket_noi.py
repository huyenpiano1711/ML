"""
tools/kiem_tra_ket_noi.py - KIỂM TRA MÔI TRƯỜNG TRƯỚC KHI CRAWL (chỉ dùng thư viện có sẵn)

Kiểm tra: Python đang dùng, SSL, API giải mã VIN (NHTSA), Wikimedia Commons, Wikidata,
và link ảnh gốc của tin đăng Craigslist (cột image_url) còn sống hay không.
Kết quả in ra màn hình và lưu vào reports/kiem_tra_ket_noi.txt
"""
import csv
import json
import random
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT.parent / "archive" / "vehicles.csv"
OUT = ROOT / "reports" / "kiem_tra_ket_noi.txt"
UA = "AutoWiseAcademicProject/1.0 (UEL student project; khadlqk24416@st.uel.edu.vn)"
lines = []

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def log(s=""):
    print(s, flush=True)
    lines.append(str(s))


def get(url, data=None, timeout=25):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def test(name, fn):
    t0 = time.time()
    try:
        msg = fn()
        log(f"[OK]   {name}: {msg} ({time.time() - t0:.1f}s)")
        return True
    except Exception as e:
        log(f"[LỖI]  {name}: {type(e).__name__}: {str(e)[:150]}")
        return False


def nhtsa_single():
    _, b = get("https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/1FMJU1JT1HEA52352?format=json")
    r = json.loads(b)["Results"][0]
    return f"{r['ModelYear']} {r['Make']} {r['Model']} {r['Trim']} | {r['DriveType']} | {r['EngineCylinders']} xi-lanh"


def nhtsa_batch():
    data = urllib.parse.urlencode({"format": "json", "data": "1FMJU1JT1HEA52352;5TFTX4CN3EX042751"}).encode()
    _, b = get("https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVINValuesBatch/", data=data)
    res = json.loads(b)["Results"]
    return f"{len(res)} VIN: " + "; ".join(f"{r['ModelYear']} {r['Make']} {r['Model']}" for r in res)


def commons():
    q = urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": "2015 Ford F-150",
                                "srnamespace": 6, "srlimit": 5, "format": "json"})
    _, b = get("https://commons.wikimedia.org/w/api.php?" + q)
    hits = json.loads(b)["query"]["search"]
    return f"{len(hits)} kết quả, vd {hits[0]['title'] if hits else '-'}"


def wikidata():
    sparql = 'SELECT ?x WHERE { ?x rdfs:label "Ford F-150"@en } LIMIT 1'
    _, b = get("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(sparql))
    return f"{len(json.loads(b)['results']['bindings'])} kết quả"


def craigslist_images(n_rows=40000, n_test=30):
    csv.field_size_limit(2 ** 31 - 1)
    urls = []
    with open(RAW_CSV, encoding="utf-8", newline="") as f:
        for i, row in enumerate(csv.DictReader(f)):
            if row.get("image_url"):
                urls.append(row["image_url"])
            if i >= n_rows:
                break
    random.seed(42)
    sample = random.sample(urls, min(n_test, len(urls)))
    ok, codes = 0, {}
    for u in sample:
        try:
            st, b = get(u, timeout=15)
            ok += st == 200 and len(b) > 1000
            codes[st] = codes.get(st, 0) + 1
        except urllib.error.HTTPError as e:
            codes[e.code] = codes.get(e.code, 0) + 1
        except Exception as e:
            codes[type(e).__name__] = codes.get(type(e).__name__, 0) + 1
    log(f"       vd link: {sample[0]}")
    return f"{ok}/{len(sample)} link ảnh còn sống | mã trả về: {codes}"


log("=== KIỂM TRA KẾT NỐI - AutoWise AI ===")
log(f"Python : {sys.executable} ({sys.version.split()[0]})")
log(f"OpenSSL: {ssl.OPENSSL_VERSION}")
for mod in ("pandas", "requests", "PIL"):
    try:
        __import__(mod)
        log(f"Thư viện {mod}: có")
    except ImportError:
        log(f"Thư viện {mod}: không có")
log()
test("NHTSA giải mã 1 VIN", nhtsa_single)
test("NHTSA giải mã theo lô", nhtsa_batch)
test("Wikimedia Commons", commons)
test("Wikidata", wikidata)
test("Ảnh gốc Craigslist (image_url)", craigslist_images)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
log(f"\nĐã lưu kết quả vào {OUT}")
