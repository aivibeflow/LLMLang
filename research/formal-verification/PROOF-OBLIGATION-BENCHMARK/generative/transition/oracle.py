"""Direct transition specification and independent invariant predicates.

No AST construction, interpretation, or variant labels are used here.
"""
def expected(f,k,override,trace):
    initial={
        "transfer":{"a":k,"b":0},
        "lifetime":{"generation":k,"captured":k,"live":1,"value":k},
        "reservation":{"capacity":k,"used":k-1,"held0":0,"held1":0},
        "authorized_effect":{"value":k},
        "cancel_cleanup":{"live":1,"weight":k,"done":0},
        "retry":{"balance":k,"seen0":0,"seen1":0},
        "deadline":{"clock":k,"deadline":k+2,"status":0},
        "interleaving":{"counter":k,"read0":k,"read1":k},
        "security_trace":{"public":k,"secret":0}}[f]
    s={**initial,**override}
    history=[]
    for a in trace:
        events=[]
        if f=="transfer":
            ok=a=="transfer" and s["a"]>0
            if ok: s["a"],s["b"]=s["a"]-1,s["b"]+1
            events=[["commit",1]] if ok else [["reject",0]]
        elif f=="lifetime":
            if a=="free": s["live"]=0
            elif a=="allocate" and not s["live"]:
                s.update(live=1,generation=s["generation"]+1,value=s["value"]+1)
            elif a=="read":
                events=[["value",s["value"]]] if s["live"] and s["generation"]==s["captured"] else [["absent",0]]
        elif f=="reservation":
            t=int(a[-1]); n="held"+str(t)
            held={j for j in (0,1) if s["held"+str(j)]}
            if a.startswith("acquire"):
                if t not in held and len(held)<1:
                    held.add(t); events=[["grant",t]]
                else: events=[["reject",t]]
            elif t in held:
                held.remove(t); events=[["release",t]]
            s.update(held0=int(0 in held),held1=int(1 in held),used=k-1+len(held))
        elif f=="authorized_effect":
            if a=="authorized":
                s["value"]+=1; events=[["write",s["value"]]]
            else: events=[["denied",0]]
        elif f=="cancel_cleanup":
            if s["done"]==0:
                s["live"]=0; s["done"]=1 if a=="complete" else 2
                events=[["release",k],["completed" if a=="complete" else "cancelled",0]]
        elif f=="retry":
            t=int(a[-1]); s["seen"+str(t)]=1
            s["balance"]=k+s["seen0"]+s["seen1"]
            events=[["ack",t]]
        elif f=="deadline":
            if a=="tick":
                s["clock"]+=1
                if s["status"]==0 and s["clock"]>=k+2:
                    s["status"]=2; events=[["timeout",s["clock"]]]
            elif s["status"]==0:
                s["status"]=1; events=[["served",s["clock"]]]
        elif f=="interleaving":
            t=int(a[-1])
            if a.startswith("read"): s[a]=s["counter"]
            else: s["counter"]+=1; events=[["done",t]]
        elif f=="security_trace":
            if a=="advance": s["public"]+=1
            else: events=[["output",s["public"]]]
        else: raise ValueError(f)
        history.append({"state":dict(s),"events":events})
    return history


def invariants(f,k,override,trace,actual):
    """Separate history predicates; checks every observable action boundary."""
    total=override.get("a",k)
    for i,step in enumerate(actual):
        s=step["state"]; prefix=trace[:i+1]
        if f=="transfer": ok=s["a"]>=0 and s["a"]+s["b"]==total
        elif f=="lifetime": ok=s["generation"]>=s["captured"] and (not any(e[0]=="value" for e in step["events"]) or (s["live"]==1 and s["generation"]==s["captured"]))
        elif f=="reservation": ok=0<=s["used"]<=s["capacity"] and s["used"]==k-1+s["held0"]+s["held1"]
        elif f=="authorized_effect": ok=s["value"]==k+prefix.count("authorized") and (prefix[-1]!="unauthorized" or all(e[0]!="write" for e in step["events"]))
        elif f=="cancel_cleanup": ok=s["done"]==0 or s["live"]==0
        elif f=="retry": ok=s["balance"]==k+len(set(prefix))
        elif f=="deadline": ok=s["status"]!=0 or s["clock"]<s["deadline"]
        elif f=="interleaving": ok=s["counter"]==k+sum(a.startswith("write") for a in prefix)
        elif f=="security_trace": ok=all(e==["output",s["public"]] for e in step["events"])
        else: raise ValueError(f)
        if not ok: return False
    return True
