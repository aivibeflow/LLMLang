"""Independent-method relational and invariant checks, no candidate imports."""


def check(f,k,b,a,s,e):
    # Match the exact permitted frame as well as the distinguishing system property.
    n=dict(b); event=["noop"]
    if f=="heap_separation":
        actor=int(a[-1]); own,other=("left","right") if actor==0 else ("right","left")
        node=3 if actor==0 else 1; bit=2**node
        if a.startswith("detach"): n[own]=0; event=["detach",actor]
        elif a.startswith("attach"):
            if b[other]&bit: event=["reject",actor]
            else: n[own]=b[own]|bit; event=["attach",actor,node]
        elif b[own]&bit: n["v"+str(node)]+=1; event=["write",actor,node]
        else: event=["reject",actor]
        return {"separation":not bool(s["left"]&s["right"]),
                "frame":s==n,"authority_effect":e==event}
    if f=="graph_gc":
        # Transitive closure by a fixed adjacency matrix, independently of DFS.
        reach=[[int(i==j and bool(b["alive"]&(1<<i))) for j in range(5)] for i in range(5)]
        for i,j in ((0,1),(1,2),(3,4),(4,3)):
            reach[i][j]=int(bool(b["alive"]&(1<<i) and b["alive"]&(1<<j)))
        for z in range(5):
            for i in range(5):
                for j in range(5): reach[i][j]=int(bool(reach[i][j] or (reach[i][z] and reach[z][j])))
        wanted=sum(1<<j for j in range(5) if any(b["roots"]&(1<<i) and reach[i][j] for i in range(5)))
        if a=="collect": n["alive"]=wanted; event=["collected",wanted]
        elif a.startswith("drop"): n["roots"]=b["roots"]&~(1<<int(a[-1]))
        else: n["roots"]=b["roots"]|(b["alive"]&(1<<int(a[-1])))
        return {"preservation":a!="collect" or s["alive"]&wanted==wanted,
                "reclamation":a!="collect" or s["alive"]&~wanted==0,
                "frame_effect":s==n and e==event}
    if f=="partition_retry":
        if a in ("partition","heal"): n["network"]=int(a=="heal")
        elif a in ("crash","recover"): n["online"]=int(a=="recover")
        elif a=="deliver" and b["network"]==b["online"]==1:
            n["seen"]=1; n["credits"]=k+1; event=["delivered"]
        elif a=="ack" and b["network"]==b["online"]==b["seen"]==1:
            n["ack"]=1; event=["ack"]
        return {"durability":s["seen"]>=b["seen"],"at_most_once":s["credits"] in (k,k+1) and s["credits"]==k+s["seen"],
                "ack_validity":not s["ack"] or s["seen"]==1,"transition_effect":s==n and e==event}
    if f=="quorum":
        if a.startswith("vote"):
            value=a[4].lower(); other="b" if value=="a" else "a"; i=int(a[-1]); bit=2**i
            if b[other]&bit: event=["reject"]
            else: n[value]=b[value]|bit; event=["vote",a[4],i]
        else:
            value=a[-1]; votes={i for i in range(3) if b[value.lower()]&(1<<i)}
            if len(votes)>=2: n["committed"+value]=1; event=["commit",value]
            else: event=["reject"]
        return {"non_equivocation":not bool(s["a"]&s["b"]),
                "agreement":not(s["committedA"] and s["committedB"]),
                "quorum":all(not s["committed"+v] or sum(bool(s[v.lower()]&(1<<i)) for i in range(3))>=2 for v in "AB"),
                "transition_effect":s==n and e==event}
    if f=="fulfillment":
        active=not(b["cancelled"] or b["shipped"])
        if a=="reserve" and active and b["held"]==0 and b["stock"]>0:
            n.update(held=1,stock=b["stock"]-1); event=["reserved"]
        elif a in ("pay","retry_pay") and active and b["held"]:
            if b["charged"]==0: n["charged"]=b["price"]; event=["paid",b["price"]]
            else: event=["already_paid"]
        elif a=="ship" and active and b["held"] and b["charged"]==b["price"]:
            n.update(shipped=1,held=0); event=["shipped"]
        elif a=="cancel" and active:
            n.update(stock=b["stock"]+b["held"],held=0,charged=0,cancelled=1); event=["cancelled",b["charged"]]
        else: event=["reject"]
        return {"inventory":s["stock"]>=0 and s["stock"]+s["held"]+s["shipped"]==k,
                "payment":s["charged"] in (0,s["price"]),
                "shipment":not s["shipped"] or (s["charged"]==s["price"] and not s["cancelled"]),
                "cancel":not s["cancelled"] or (s["charged"]==s["held"]==s["shipped"]==0),
                "component_transition":s==n and e==event}
    if f=="rolling_upgrade":
        if a.startswith("upgrade"): n["version"+a[-1]]=1
        elif a.startswith("send"):
            payload={"send_old":0,"send_false":1,"send_true":2}[a]
            if payload and not b["version0"]: event=["reject"]
            else: n["pending"]=payload; event=["sent",payload]
        elif b["pending"]!=-1:
            p=b["pending"]; n["pending"]=-1
            if p and not b["version1"]: event=["incompatible"]
            else: n["accepted"]=0 if p==1 else 1; event=["accepted",n["accepted"]]
        return {"compatibility":s["accepted"]==n["accepted"],"frame_effect":s==n and e==event}
    if f=="ffi_buffer":
        if a=="grant" and b["live"]: n["cap"]=1
        elif a=="revoke": n["cap"]=0
        elif a=="release": n.update(live=0,cap=0)
        elif a.startswith("write"):
            permitted=b["live"]==b["cap"]==1 and a in ("write_ok","write_zero")
            if permitted:
                n["cell0"]+=int(a=="write_ok"); event=["written",int(a=="write_ok")]
            else: event=["reject"]
        return {"bounds_frame":s["cell1"]==b["cell1"],"authority":(s["cell0"]==b["cell0"] and s["cell1"]==b["cell1"]) or (b["live"]==b["cap"]==1 and a=="write_ok"),
                "lifetime":not s["cap"] or s["live"]==1,"transition_effect":s==n and e==event}
    raise ValueError(f)
