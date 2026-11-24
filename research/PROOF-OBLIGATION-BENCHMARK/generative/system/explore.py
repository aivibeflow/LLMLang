"""Bounded reachable-state exploration with shortest witness reconstruction."""
from collections import deque


class Unsupported(ValueError):
    pass


def state_key(s,fields):
    if not isinstance(s,dict) or set(s)!=set(fields) or any(type(x) is not int or abs(x)>10**9 for x in s.values()):
        raise Unsupported("invalid state shape or integer bound")
    return tuple(s[k] for k in fields)


def explore(initial,actions,step,check,depth):
    if not isinstance(initial,dict) or not 0<len(initial)<=24 or any(not isinstance(k,str) for k in initial):
        raise Unsupported("initial shape")
    if type(depth) is not int or not 1<=depth<=8 or not isinstance(actions,(tuple,list)) or not 0<len(actions)<=16 or any(not isinstance(a,str) or not a for a in actions) or len(set(actions))!=len(actions):
        raise Unsupported("action/depth bound")
    fields=tuple(sorted(initial))
    start=state_key(initial,fields)
    queue=deque([(start,())]); visited={start}; edges=0; failures={}; obligations=None
    while queue:
        key,path=queue.popleft()
        if len(path)==depth: continue
        before=dict(zip(fields,key))
        for action in actions:
            after,event=step(dict(before),action)
            target=state_key(after,fields)
            if not isinstance(event,list) or len(event)>8 or any(type(x) not in (int,str) for x in event):
                raise Unsupported("observation shape")
            verdicts=check(before,action,after,event)
            if not isinstance(verdicts,dict) or not verdicts or any(not isinstance(k,str) or type(v) is not bool for k,v in verdicts.items()):
                raise Unsupported("obligation shape")
            if obligations is None: obligations=set(verdicts)
            if set(verdicts)!=obligations: raise Unsupported("inconsistent obligations")
            for name,ok in verdicts.items():
                if not ok and name not in failures:
                    failures[name]={"trace":list(path)+[action],"before":before,"after":after,"event":event}
            edges+=1
            if edges>32768: raise Unsupported("edge budget exceeded")
            if target not in visited:
                visited.add(target)
                if len(visited)>4096: raise Unsupported("state budget exceeded")
                queue.append((target,path+(action,)))
    if not edges or not obligations: raise Unsupported("empty exploration")
    return {"status":"disproven" if failures else "bounded_pass","states":len(visited),"edges":edges,
            "obligations":{o:{"status":"disproven" if o in failures else "bounded_pass","witness":failures.get(o)} for o in sorted(obligations)}}
