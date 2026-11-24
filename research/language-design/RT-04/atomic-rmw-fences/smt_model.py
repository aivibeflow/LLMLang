from itertools import product


def conjunction(parts):
    terms = tuple(parts)
    return f"(and {' '.join(terms)})" if len(terms) > 1 else next(iter(terms), "true")


def disjunction(parts):
    terms = tuple(parts)
    return f"(or {' '.join(terms)})" if len(terms) > 1 else next(iter(terms), "false")


def smt(case, *, globally_ordered=False):
    events = {event.name: event for thread in case.threads for event in thread}
    positions = {event.name: (thread_index, index) for thread_index, thread in enumerate(case.threads)
                 for index, event in enumerate(thread)}
    locations = sorted({e.location for e in events.values() if e.location})
    initial = {loc: f"initial_{loc}" for loc in locations}
    writes = {loc: [initial[loc]] + [name for name, e in events.items() if e.writes and e.location == loc]
              for loc in locations}
    reads = {name: e.location for name, e in events.items() if e.reads}
    modified_location = {name: loc for loc, names in writes.items() for name in names}
    all_names = [*initial.values(), *events]
    lines = ["(set-logic QF_LIA)"]
    mo = {name: "mo_" + name for name in modified_location}
    rf = {name: "rf_" + name for name in reads}
    value = {name: "value_" + name for name in modified_location}
    result = {name: "observed_" + name for name in reads}
    hb = {(first, second): f"hb_{i}_{j}" for i, first in enumerate(all_names)
          for j, second in enumerate(all_names)}

    def declare(symbols, sort):
        lines.extend(f"(declare-const {symbol} {sort})" for symbol in symbols)

    def require(term):
        lines.append(f"(assert {term})")

    def require_if(guard, conclusion):
        require(f"(=> {guard} {conclusion})")

    def before(first, second):
        return first in positions and second in positions and (
            positions[first][0] == positions[second][0] and positions[first][1] < positions[second][1])

    declare([*mo.values(), *rf.values(), *value.values(), *result.values()], "Int")
    declare(hb.values(), "Bool")
    for names in writes.values():
        require(f"(= {mo[names[0]]} 0)")
        require(f"(= {value[names[0]]} 0)")
        if len(names) > 1:
            require(f"(distinct {' '.join(mo[name] for name in names)})")
        for name in names[1:]:
            require(f"(and (<= 1 {mo[name]}) (< {mo[name]} {len(names)}))")
            body = events[name]
            written = f"(mod (+ {result[name]} {body.value}) 256)" if body.reads else str(body.value)
            require(f"(= {value[name]} {written})")

    for name, loc in reads.items():
        source_options = writes[loc]
        require(disjunction(f"(= {rf[name]} {mo[writer]})" for writer in source_options))
        for writer in source_options:
            require_if(f"(= {rf[name]} {mo[writer]})", f"(= {result[name]} {value[writer]})")
        if events[name].writes:
            relation = f"(= (+ {rf[name]} 1) {mo[name]})" if case.adjacent_rmw else f"(< {rf[name]} {mo[name]})"
            require(relation)

    for name in all_names:
        require(f"(not {hb[name, name]})")
    for first, second in product(all_names, repeat=2):
        if (first in initial.values() and second in positions) or before(first, second):
            require(hb[first, second])
    for first, middle, last in product(all_names, repeat=3):
        require_if(f"(and {hb[first, middle]} {hb[middle, last]})", hb[first, last])

    releases = {"release", "acq_rel"}
    acquires = {"acquire", "acq_rel"}
    for reader, loc in reads.items():
        acquire_points = [f for f, e in events.items() if e.kind == "fence" and e.order in acquires
                          and events[reader].kind == "load" and before(reader, f)]
        if events[reader].order in acquires:
            acquire_points.append(reader)
        plain = [w for w in writes[loc] if w in events and not events[w].reads]
        for head in writes[loc][1:]:
            release_points = [f for f, e in events.items() if e.kind == "fence" and e.order in releases
                              and before(f, head)]
            if events[head].order in releases:
                release_points.append(head)
            if not release_points or not acquire_points:
                continue
            interval = conjunction([
                f"(<= {mo[head]} {rf[reader]})",
                *(f"(not (and (< {mo[head]} {mo[w]}) (<= {mo[w]} {rf[reader]})))" for w in plain),
            ])
            for source_point, observer_point in product(release_points, acquire_points):
                require_if(interval, hb[source_point, observer_point])

    for loc in locations:
        relevant = set(writes[loc]) | {reader for reader in reads if reads[reader] == loc}
        for first, second in product(sorted(relevant), repeat=2):
            sources = ([mo[first]] if first in mo else []) + ([rf[first]] if first in rf else [])
            for source_rank in sources:
                if second in mo:
                    require_if(hb[first, second], f"(< {source_rank} {mo[second]})")
                if second in rf:
                    require_if(hb[first, second], f"(<= {source_rank} {rf[second]})")

    if globally_ordered:
        order = {name: "position_" + name for name in all_names}
        declare(order.values(), "Int")
        require(f"(distinct {' '.join(order.values())})")
        for first, second in product(all_names, repeat=2):
            if before(first, second) or (first in initial.values() and second in positions):
                require(f"(< {order[first]} {order[second]})")
        for names in writes.values():
            for first, second in product(names, repeat=2):
                require_if(f"(< {mo[first]} {mo[second]})", f"(< {order[first]} {order[second]})")
        for reader, loc in reads.items():
            for writer in writes[loc]:
                if writer != reader:
                    require_if(f"(= {rf[reader]} {mo[writer]})", f"(< {order[writer]} {order[reader]})")
                    require_if(f"(< {rf[reader]} {mo[writer]})", f"(< {order[reader]} {order[writer]})")

    for reader, observed in case.outcome.items():
        require(f"(= {result[reader]} {observed})")
    return "\n".join([*lines, "(check-sat)", ""])
