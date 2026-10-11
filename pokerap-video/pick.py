import json,sys,os,urllib.request
D=sys.argv[1]; out=sys.argv[2]; names=sys.argv[3].split(",")
order=["base1","base2","base3","base5","gym1","gym2","base4"]
cards={s:json.load(open(f"{D}/{s}.json")) for s in order}
res=[]
for n in names:
    hit=None
    for s in order:
        for c in cards[s]:
            if c["name"].lower().replace(" ","")==n.lower().replace(" ",""):
                hit=(s,c); break
        if hit: break
    if not hit: print("MISSING",n); continue
    s,c=hit; fn=f"{out}/{c['id']}.png"
    if not os.path.exists(fn):
        import subprocess; subprocess.run(["curl","-sS","-m","30","-o",fn,c["images"]["large"]],check=True)
    res.append({"name":n,"id":c["id"],"file":fn})
    print(n,c["id"],c["name"])
json.dump(res,open(f"{out}/stanza.json","w"),ensure_ascii=False,indent=1)
