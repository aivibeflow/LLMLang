from itertools import permutations, product

from cases import Event


def closure(nodes, edges):
    reach = {(a, b) for a, b in edges}
    for middle in nodes:
        reach.update((left, right) for left in nodes for right in nodes
                     if (left, middle) in reach and (middle, right) in reach)
    return reach


def common(case):
    events = tuple(op for thread in case.threads for op in thread)
    locations = sorted({op.location for op in events if op.location})
    initial = tuple(Event(f"initial_{loc}", "init", loc) for loc in locations)
    before = {(left.name, right.name) for thread in case.threads
              for index, left in enumerate(thread) for right in thread[index + 1:]}
    initialization = {(init.name, op.name) for init in initial for op in events}
    return initial + events, before, initialization


def allowed_witnesses(case):
    operations, before, initialization = common(case)
    nodes = tuple(op.name for op in operations)
    writes_by_location = {
        loc: tuple(op for op in operations if op.writes and op.location == loc)
        for loc in sorted({op.location for op in operations if op.location})
    }
    reads = tuple(op for op in operations if op.reads)
    release = {"release", "acq_rel"}
    acquire = {"acquire", "acq_rel"}

    for orders in product(*(tuple((writes[0],) + suffix for suffix in permutations(writes[1:]))
                            for writes in writes_by_location.values())):
        rank = {op.name: index for order in orders for index, op in enumerate(order)}
        order_for = {order[0].location: order for order in orders}
        source_options = []
        for reader in reads:
            candidates = order_for[reader.location]
            if reader.writes:
                # A valid RMW reads the predecessor. The negative control can choose any earlier value.
                end = rank[reader.name]
                start = end - 1 if case.adjacent_rmw else 0
                candidates = candidates[start:end]
            source_options.append(candidates)

        for sources in product(*source_options):
            read_from = dict(zip((op.name for op in reads), sources, strict=True))
            values = {}
            for order in orders:
                for writer in order:
                    values[writer.name] = ((values[read_from[writer.name].name] + writer.value) & 255
                                           if writer.reads else writer.value)
            observed = {op.name: values[read_from[op.name].name] for op in reads}
            if any(observed[name] != value for name, value in case.outcome.items()):
                continue
            sync = set()
            for reader, source in zip(reads, sources, strict=True):
                order = order_for[reader.location]
                for head in order[:rank[source.name] + 1]:
                    if any(op.kind != "add" for op in order[rank[head.name] + 1:rank[source.name] + 1]):
                        continue
                    release_points = [op.name for op in operations if op.kind == "fence" and op.order in release
                                      and (op.name, head.name) in before]
                    acquire_points = [op.name for op in operations if reader.kind == "load" and op.kind == "fence"
                                      and op.order in acquire and (reader.name, op.name) in before]
                    if head.order in release:
                        release_points.append(head.name)
                    if reader.order in acquire:
                        acquire_points.append(reader.name)
                    sync.update(product(release_points, acquire_points))

            hb = closure(nodes, before | initialization | sync)
            if any((name, name) in hb for name in nodes):
                continue

            def coherent():
                for first in operations:
                    for second in operations:
                        if not first.location or first.location != second.location or (first.name, second.name) not in hb:
                            continue
                        first_ranks = ([rank[first.name]] if first.writes else [])
                        second_read = rank[read_from[second.name].name] if second.reads else None
                        if first.reads:
                            first_ranks.append(rank[read_from[first.name].name])
                        if second.writes and any(pos >= rank[second.name] for pos in first_ranks):
                            return False
                        if second.reads and any(pos > second_read for pos in first_ranks):
                            return False
                return True

            if not coherent():
                continue
            next_write = {first.name: second.name for order in orders for first, second in zip(order, order[1:])}
            global_before = before | initialization | set(next_write.items())
            for reader, source in zip(reads, sources, strict=True):
                global_before.add((source.name, reader.name))
                following = next_write.get(source.name)
                if following and following != reader.name:
                    global_before.add((reader.name, following))
            globally_orderable = not any((name, name) in closure(nodes, global_before) for name in nodes)
            yield {"mo": [[op.name for op in order] for order in orders],
                   "rf": {name: source.name for name, source in read_from.items()},
                   "sw": sorted(sync), "observed": observed, "global_order": globally_orderable}
