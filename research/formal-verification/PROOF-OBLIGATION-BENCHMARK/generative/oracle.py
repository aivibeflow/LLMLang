"""Separate direct finite relation oracle; never reads a generated AST."""
from itertools import product


def direct(family,k,width,variant):
    d=tuple(range(k,k+width+1))
    mut=variant=="mutation"
    if family=="interval":
        valid=set(range(k,k+width+1-int(mut)))
        return set(d)<=valid
    if family=="sum":
        return all((v+k)+width==v+k+width+int(mut) for v in d)
    if family=="forall_exists":
        relation={(a,b) for a,b in product(d,repeat=2) if b-a==int(mut)}
        return {a for a,b in relation}==set(d)
    if family=="exists_forall":
        candidates={a for a in d if all(b-a>=int(mut) for b in d)}
        return bool(candidates)
    if family=="unique":
        hits=[a for a in d if a-k<1+int(mut)]
        return len(hits)==1
    if family=="composition":
        admitted=d[1:]
        outputs=[(a-int(mut)>=k+1, a-int(mut)+1==a+1) for a in admitted]
        return bool(admitted) and all(guard and post for guard,post in outputs)
    raise ValueError("unknown oracle family")
