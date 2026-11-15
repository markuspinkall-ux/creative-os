import hashlib, json, sys, urllib.request
d=json.load(open("ki/stimmen.json"))
for k,v in d.items():
    for f in v["dateien"]:
        data=urllib.request.urlopen(urllib.request.Request(f["url"],headers={"User-Agent":"CreativeOS"}),timeout=120).read()
        f["groesse"]=len(data); f["sha256"]=hashlib.sha256(data).hexdigest()
        print("PRUEFSUMME", k, f["datei"], len(data), f["sha256"], flush=True)
print("STIMMEN_JSON_BEGIN"); print(json.dumps(d,ensure_ascii=False,indent=2)); print("STIMMEN_JSON_END")
