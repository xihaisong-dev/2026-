"""Exact DAG contraction checks without rebuilding every operator assignment."""


def can_contract(pred, succ, a, b):
    # Contracting two vertices creates a cycle iff either direction contains
    # an a-to-b path with at least one intermediate vertex. Direct edges vanish.
    for source, target in [(a,b),(b,a)]:
        stack=list(succ[source]-{target});seen=set()
        while stack:
            u=stack.pop()
            if u==target:return False
            if u not in seen:
                seen.add(u);stack.extend(succ[u]-seen)
    return True


def contract(pred, succ, a, b):
    incoming=(pred[a]|pred[b])-{a,b}
    outgoing=(succ[a]|succ[b])-{a,b}
    for u in incoming:
        succ[u].discard(b);succ[u].add(a)
    for v in outgoing:
        pred[v].discard(b);pred[v].add(a)
    pred[a]=incoming;succ[a]=outgoing
    del pred[b];del succ[b]
