"""Candidate transitions; oracle module does not import this module."""
FAMILIES=("heap_separation","graph_gc","partition_retry","quorum","fulfillment","rolling_upgrade","ffi_buffer")
VARIANTS=("reference","mutation","alternative")
ACTIONS={
 "heap_separation":("detach0","detach1","attach0","attach1","write0","write1"),
 "graph_gc":("drop0","drop3","root0","root3","collect"),
 "partition_retry":("partition","heal","deliver","ack","crash","recover"),
 "quorum":tuple("vote"+v+str(i) for v in "AB" for i in range(3))+("commitA","commitB"),
 "fulfillment":("reserve","pay","ship","cancel","retry_pay"),
 "rolling_upgrade":("upgrade0","upgrade1","send_old","send_false","send_true","deliver"),
 "ffi_buffer":("grant","revoke","write_ok","write_oob","write_zero","release")}
DEPTH={"heap_separation":5,"graph_gc":4,"partition_retry":6,"quorum":6,"fulfillment":5,"rolling_upgrade":5,"ffi_buffer":4}
CONTRACTS={
 "heap_separation":"Roots 0 and 2 own disjoint reachable heap regions; attach cannot acquire another region; writes affect only a reachable node of the acting owner.",
 "graph_gc":"Collection preserves exactly the live nodes reachable from current roots, including transitive paths and reachable cycles; unreachable cycles are reclaimed.",
 "partition_retry":"A single durable request is credited at most once despite lost acknowledgements, partitions and receiver crash/recovery; acknowledgements require delivery.",
 "quorum":"Three voters durably vote for at most one value; a majority is required for commit and different values cannot both commit.",
 "fulfillment":"Inventory reservation, payment and fulfillment compose: shipment requires reserved and paid order; cancellation before shipment releases stock and refunds; payment retries never double charge.",
 "rolling_upgrade":"Old records without enabled default true; explicit false survives delivery after either receiver version is upgraded; old receiver rejects incompatible new records without changing accepted state.",
 "ffi_buffer":"A foreign write requires a live buffer and capability; valid offset writes only selected cell, zero-length write changes nothing, out-of-bounds writes are rejected."}


def initial(f,k):
    return {
      "heap_separation":{"left":1<<1,"right":1<<3,"v1":k,"v3":k+1},
      "graph_gc":{"alive":31,"roots":9,"payload":k},
      "partition_retry":{"network":1,"online":1,"seen":0,"credits":k,"ack":0},
      "quorum":{"a":0,"b":0,"committedA":0,"committedB":0,"epoch":k},
      "fulfillment":{"stock":k,"held":0,"charged":0,"shipped":0,"cancelled":0,"price":k+1},
      "rolling_upgrade":{"version0":0,"version1":0,"pending":-1,"accepted":-1,"id":k},
      "ffi_buffer":{"live":1,"cap":0,"cell0":k,"cell1":k+1}}[f]


def closure(alive,roots,alt=False):
    # Static graph 0->1->2, 3<->4; links to freed nodes are ignored.
    edges={0:(1,),1:(2,),2:(),3:(4,),4:(3,)}
    if alt:
        reached=roots&alive
        while True:
            nxt=reached
            for node,targets in edges.items():
                if reached&(1<<node):
                    for t in targets: nxt|=(1<<t)&alive
            if nxt==reached: return reached
            reached=nxt
    stack=[i for i in range(5) if roots&alive&(1<<i)]; seen=set()
    while stack:
        i=stack.pop()
        if i not in seen:
            seen.add(i); stack.extend(j for j in edges[i] if alive&(1<<j))
    return sum(1<<i for i in seen)


def step(f,k,v,s,a):
    mut=v=="mutation"; alt=v=="alternative"
    e=["noop"]
    if f=="heap_separation":
        owner=int(a[-1]); own="left" if owner==0 else "right"; other="right" if owner==0 else "left"
        target=3 if owner==0 else 1; bit=1<<target
        if a.startswith("detach"): s[own]=0; e=["detach",owner]
        elif a.startswith("attach"):
            allowed=mut or not (s[other]&bit)
            if alt: allowed=target not in [i for i in (1,3) if s[other]&(1<<i)]
            if allowed: s[own]|=bit; e=["attach",owner,target]
            else: e=["reject",owner]
        elif s[own]&bit:
            s["v"+str(target)]+=1; e=["write",owner,target]
        else: e=["reject",owner]
    elif f=="graph_gc":
        if a.startswith("drop"): s["roots"]&=~(1<<int(a[-1]))
        elif a.startswith("root"): s["roots"]|=s["alive"]&(1<<int(a[-1]))
        else:
            if mut: s["alive"]&=s["roots"] # only roots, missing descendants
            else: s["alive"]=closure(s["alive"],s["roots"],alt)
            e=["collected",s["alive"]]
    elif f=="partition_retry":
        if a=="partition": s["network"]=0
        elif a=="heal": s["network"]=1
        elif a=="crash":
            s["online"]=0
            if mut: s["seen"]=0
        elif a=="recover": s["online"]=1
        elif a=="deliver" and s["network"] and s["online"]:
            if not s["seen"]: s["credits"]+=1
            s["seen"]=1; e=["delivered"]
            if alt: s["credits"]=k+s["seen"]
        elif a=="ack" and s["network"] and s["online"] and s["seen"]:
            s["ack"]=1; e=["ack"]
    elif f=="quorum":
        if a.startswith("vote"):
            which=a[4].lower(); other="b" if which=="a" else "a"; bit=1<<int(a[-1])
            if mut or not s[other]&bit:
                s[which]|=bit; e=["vote",a[4],int(a[-1])]
            else: e=["reject"]
        else:
            which=a[-1]; mask=s[which.lower()]
            enough=any(mask&p==p for p in (3,5,6)) if alt else mask.bit_count()>=2
            if enough: s["committed"+which]=1; e=["commit",which]
            else: e=["reject"]
    elif f=="fulfillment":
        if a=="reserve" and not s["held"] and not s["cancelled"] and not s["shipped"] and s["stock"]>0:
            s["held"]=1; s["stock"]-=1; e=["reserved"]
        elif a in ("pay","retry_pay") and s["held"] and not s["cancelled"] and not s["shipped"]:
            if not s["charged"]: s["charged"]=s["price"]; e=["paid",s["price"]]
            else: e=["already_paid"]
        elif a=="ship" and s["held"] and not s["cancelled"] and not s["shipped"] and (mut or s["charged"]==s["price"]):
            s["shipped"]=1; s["held"]=0; e=["shipped"]
        elif a=="cancel" and not s["shipped"] and not s["cancelled"]:
            if alt: s["stock"]+=s["held"]
            elif s["held"]: s["stock"]+=1
            refund=s["charged"]; s.update(held=0,charged=0,cancelled=1); e=["cancelled",refund]
        else: e=["reject"]
    elif f=="rolling_upgrade":
        if a.startswith("upgrade"): s["version"+a[-1]]=1
        elif a.startswith("send"):
            payload={"send_old":0,"send_false":1,"send_true":2}[a]
            if payload==0 or s["version0"]:
                s["pending"]=payload; e=["sent",payload]
            else: e=["reject"]
        elif s["pending"]!=-1:
            p=s["pending"]; s["pending"]=-1
            if p!=0 and not s["version1"]: e=["incompatible"]
            else:
                s["accepted"]=(1 if mut else int(p!=1)) if not alt else {0:1,1:0,2:1}[p]
                e=["accepted",s["accepted"]]
    elif f=="ffi_buffer":
        if a=="grant" and s["live"]: s["cap"]=1
        elif a=="revoke": s["cap"]=0
        elif a=="release": s.update(live=0,cap=0)
        elif a.startswith("write"):
            if s["live"] and s["cap"] and a!="write_oob":
                if a=="write_ok": s["cell0"]+=1; e=["written",1]
                else: e=["written",0]
            elif mut and a=="write_oob" and s["live"] and s["cap"]:
                s["cell1"]+=1; e=["written",1]
            else: e=["reject"]
        if alt and a=="write_ok" and e==["written",1]:
            s["cell0"]=(s["cell0"]-k)+k
    else: raise ValueError(f)
    return s,e
