"""Download a small thumbnail for every lot in ./lots.json -> ./thumbs.json (base64 data URIs).
Uses Git's curl (Windows' own curl.exe gets a different TLS fingerprint and is sometimes refused)."""
import json, base64, subprocess, time, os
from concurrent.futures import ThreadPoolExecutor

CURL = r"C:\Program Files\Git\mingw64\bin\curl.exe" if os.path.exists(r"C:\Program Files\Git\mingw64\bin\curl.exe") else "curl"
lots = json.load(open("lots.json"))
old = json.load(open("thumbs.json")) if os.path.exists("thumbs.json") else {}


def get(l):
    if not l["img"]: return l["id"], None
    if old.get(l["id"]): return l["id"], old[l["id"]]
    u = l["img"].replace("/image/upload/", "/image/upload/w_112,h_74,c_fill,q_40,f_jpg/")
    for a in range(3):
        r = subprocess.run([CURL, "-s", "-f", "--max-time", "30", "-A", "Mozilla/5.0", u], capture_output=True)
        if r.returncode == 0 and r.stdout: return l["id"], "data:image/jpeg;base64," + base64.b64encode(r.stdout).decode()
        time.sleep(1 + a)
    return l["id"], None


t0 = time.time()
with ThreadPoolExecutor(12) as ex: T = dict(ex.map(get, lots))
json.dump(T, open("thumbs.json", "w"))
ok = sum(1 for v in T.values() if v)
print("thumbs", ok, "of", len(lots), "in", round(time.time() - t0), "s")
