"""Build and verify the inventory for the native Linux x86-64 syscall ABI."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

DIRECTORY = Path(__file__).resolve().parent
TABLE = DIRECTORY / "syscall_64.tbl"
CATALOG = DIRECTORY / "catalog.json"
CLASSIFICATIONS = DIRECTORY / "classifications.json"
PACKAGE = DIRECTORY.parent
TAG = "v6.12"
COMMIT = "adc218676eef25575469234709c2d87185ca223a"
TABLE_HASH = "980ce3115028c71c5618e7864d262017bde8103bcfe7b413147a14fd312c92ac"
TABLE_PATH = "arch/x86/entry/syscalls/syscall_64.tbl"
TARGET = "linux-x86_64"
SCHEMA = "llmlang.linux.syscalls.catalog.v1"
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def parse_table(text):
    """Parse both the native records and the excluded x32 records."""
    native = []
    x32 = []
    previous_number = -1
    for line_number, line in enumerate(text.splitlines(), 1):
        columns = line.partition("#")[0].split()
        if not columns:
            continue
        if not 3 <= len(columns) <= 6 or not columns[0].isascii() or not columns[0].isdigit():
            raise ValueError(f"invalid syscall table row {line_number}")
        number, abi, name = int(columns[0]), columns[1], columns[2]
        if number <= previous_number or abi not in {"common", "64", "x32"}:
            raise ValueError(f"invalid syscall number or ABI on table row {line_number}")
        if not IDENTIFIER.fullmatch(name):
            raise ValueError(f"invalid syscall name on table row {line_number}")
        if any(symbol != "-" and not IDENTIFIER.fullmatch(symbol) for symbol in columns[3:5]):
            raise ValueError(f"invalid entry point on table row {line_number}")
        if len(columns) == 6 and columns[5] != "noreturn":
            raise ValueError(f"invalid return convention on table row {line_number}")
        row = {
            "number": number,
            "abi": abi,
            "name": name,
            "entry_point": columns[3] if len(columns) > 3 and columns[3] != "-" else None,
            "compat_entry_point": columns[4] if len(columns) > 4 and columns[4] != "-" else None,
            "noreturn": len(columns) == 6,
        }
        (x32 if abi == "x32" else native).append(row)
        previous_number = number
    if not native or len({row["name"] for row in native}) != len(native):
        raise ValueError("the syscall table must contain unique native operations")
    return native, x32


def placements(groups):
    values = {}
    for stage, names in groups.items():
        for name in names:
            if name in values:
                raise ValueError(f"{name} occurs in multiple stage assignments")
            values[name] = int(stage)
    return values


def by_call(rules, known):
    values = {}
    for rule in rules:
        names = rule["syscalls"]
        if not names or not set(names) <= known:
            raise ValueError(f"unrecognized syscall in configuration rule: {names}")
        condition = {key: value for key, value in rule.items() if key != "syscalls"}
        if not condition["requires"] or not condition["sources"]:
            raise ValueError(f"configuration rule has no condition or source: {names}")
        for name in names:
            values.setdefault(name, []).append(condition)
    return values


def number_ranges(ranges, native, x32):
    native_numbers = {row["number"] for row in native}
    x32_numbers = {row["number"] for row in x32}
    # Track the entire allocation window through the last named or x32 slot.
    remaining = set(range(max(native_numbers | x32_numbers) + 1)) - native_numbers
    for interval in ranges:
        numbers = set(range(interval["first"], interval["last"] + 1))
        if not numbers or not numbers <= remaining or interval["native_result"] != "ENOSYS":
            raise ValueError(f"invalid native coverage range: {interval}")
        expected_x32 = numbers if interval["status"] == "x32-only" else set()
        if numbers & x32_numbers != expected_x32:
            raise ValueError(f"incorrect x32 allocation in number range: {interval}")
        remaining -= numbers
    if remaining:
        raise ValueError(f"unclassified native numbers: {sorted(remaining)}")
    return ranges


def unique_fields(pairs):
    values = dict(pairs)
    if len(values) != len(pairs):
        raise ValueError("duplicate keys in the syscall catalog metadata")
    return values


def build_catalog():
    source = TABLE.read_bytes()
    if hashlib.sha256(source).hexdigest() != TABLE_HASH:
        raise ValueError("vendored Linux table differs from the pinned SHA-256")
    native, x32 = parse_table(source.decode("utf-8"))
    metadata = json.loads(CLASSIFICATIONS.read_text(encoding="utf-8"), object_pairs_hook=unique_fields)
    known = {row["name"] for row in native}
    stages = placements(metadata["stage_groups"])
    if set(stages) != known or set(stages.values()) != set(range(1, 8)):
        raise ValueError("stage assignments must cover the pinned native syscalls and stages 1–7")
    configuration = by_call(metadata["configuration_rules"], known)
    behavior = by_call(metadata["behavior_rules"], known)
    if any(len(rules) != 1 for rules in configuration.values()):
        raise ValueError("each configuration-dependent entry must have one combined availability rule")
    history = metadata["historical_entries"]
    command_families = metadata["command_families"]
    inactive = {row["name"] for row in native if row["entry_point"] in {None, "sys_ni_syscall"}}
    if set(history) != inactive or inactive & configuration.keys():
        raise ValueError("history must cover exactly the entries without a native handler")
    if not command_families.keys() <= known - inactive:
        raise ValueError("command families must refer to active native entries")
    primary_compounds = metadata["primary_compounds"]
    if not primary_compounds.keys() <= known - inactive:
        raise ValueError("primary compounds must refer to active native entries")
    for name, witness in primary_compounds.items():
        if witness.keys() != {"operation", "case"} or not all(
            isinstance(value, str) and IDENTIFIER.fullmatch(value) for value in witness.values()
        ):
            raise ValueError(f"invalid primary compound for {name}")
    calls = []
    for row in native:
        name = row["name"]
        if name in inactive:
            status = "historical-enosys"
        elif name in configuration:
            status = "config-dependent"
        else:
            status = "native-entry"
        calls.append({
            **row,
            "stage": stages[name],
            "kernel_status": status,
            "config": configuration.get(name, [None])[0],
            "behavior_dependencies": behavior.get(name, []),
            "history": history.get(name),
            **({"primary_compound": primary_compounds[name]} if name in primary_compounds else {}),
            "package_status": "kernel-no-handler" if name in inactive else "pending",
            "commands": (
                {"selector": command_families[name], "supported": []}
                if name in command_families else None
            ),
        })
    return {
        "schema": SCHEMA,
        "target": TARGET,
        "kernel": {
            "tag": TAG,
            "commit": COMMIT,
            "table_path": TABLE_PATH,
            "table_sha256": TABLE_HASH,
        },
        "excluded_x32_records": len(x32),
        "reserved_ranges": number_ranges(metadata["number_ranges"], native, x32),
        "syscalls": calls,
    }


def encode(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def load_catalog():
    """Read the versioned catalog, rejecting stale or changed inventory bytes."""
    expected = build_catalog()
    if CATALOG.read_bytes() != encode(expected).encode("utf-8"):
        raise ValueError("catalog.json differs from its pinned inputs, regenerate with catalog.py generate")
    return expected


def table_diff(old, new):
    """Compare native rows at the same ABI number, with additions and removals."""
    old_rows = {row["number"]: row for row in old}
    new_rows = {row["number"]: row for row in new}
    return {
        "added": [new_rows[number] for number in sorted(new_rows.keys() - old_rows.keys())],
        "removed": [old_rows[number] for number in sorted(old_rows.keys() - new_rows.keys())],
        "changed": [
            {"before": old_rows[number], "after": new_rows[number]}
            for number in sorted(old_rows.keys() & new_rows.keys())
            if old_rows[number] != new_rows[number]
        ],
    }


def package_coverage(catalog):
    """Attach only the exact scoped admissions valid for the checkout."""
    if not (PACKAGE / "admissions.json").exists():
        return catalog
    if str(PACKAGE) not in sys.path:
        sys.path.insert(0, str(PACKAGE))
    from contracts.contracts import load_commands
    from package import PackageError, check_evidence, current_bindings, load_contracts, provider_files

    operations = load_contracts()
    command_inventory = load_commands(operations)
    if any(command_inventory["kernel"][key] != catalog["kernel"][key] for key in ("tag", "commit")):
        raise ValueError("command coverage targets a different kernel")
    bindings = current_bindings(operations, provider_files())
    variants = {}
    for family, details in command_inventory["families"].items():
        for variant in details["commands"]:
            operation = variant["operation"]
            native_entries = bindings[operation]["implementation"]["native_entries"]
            if family not in native_entries:
                raise ValueError(f"{operation} command coverage names the wrong native family")
            variants.setdefault((family, operation), []).append(variant)
    try:
        admissions = check_evidence(bindings, operations, report_rejections=True)
    except (KeyError, OSError, ValueError, PackageError) as error:
        admissions = dict.fromkeys(bindings, {"diagnostic": str(error)})
    witnesses = {row["name"]: row["primary_compound"] for row in catalog["syscalls"] if "primary_compound" in row}
    for syscall, witness in witnesses.items():
        operation = witness["operation"]
        if operation in bindings and syscall not in bindings[operation]["implementation"]["native_entries"]:
            raise ValueError(f"{operation} primary compound does not call {syscall}")
    by_syscall = {}
    for name, binding in bindings.items():
        native_entries = binding["implementation"]["native_entries"]
        for syscall in native_entries:
            evidence = admissions[name]
            witness = witnesses.get(syscall)
            primary = name == syscall or len(native_entries) == 1
            if witness:
                cases = evidence.get("native_cases", []) + evidence.get("guest_cases", [])
                primary = name == witness["operation"] and witness["case"] in cases
            by_syscall.setdefault(syscall, []).append({"operation": name, "primary": primary, **evidence})
    limits = {name: details["limit"] for name, details in command_inventory["families"].items()}
    return attach_coverage(catalog, by_syscall, variants, limits)


def attach_coverage(catalog, by_syscall, variants, limits=None):
    limits = limits or {}
    rows = []
    for row in catalog["syscalls"]:
        name = row["name"]
        profiles = by_syscall.get(name)
        if profiles is None:
            rows.append(row)
            continue
        admitted = [profile for profile in profiles if "diagnostic" not in profile]
        primary = [profile["operation"] for profile in admitted if profile.get("primary")]
        commands = [
            {**variant, "status": "scoped-admission" if "diagnostic" not in profile else "unavailable-admission"}
            for profile in profiles
            for variant in variants.get((name, profile["operation"]), ())
        ]
        command_set_complete = (
            (row["commands"] is None or bool(commands))
            and all(command["status"] == "scoped-admission" for command in commands)
        )
        if primary and command_set_complete:
            status = "ready"
        elif admitted:
            status = "scoped-admission"
        else:
            status = "unavailable-admission"
        updated = {**row, "package_status": status, "primary_providers": primary, "profiles": profiles}
        if row["commands"] or commands:
            family = row["commands"] or {"selector": "Declared command or argument profiles."}
            updated["commands"] = {
                **family,
                **({"limit": limits[name], "unlisted": "unsupported"} if name in limits else {}),
                "supported": [item for item in commands if item["status"] == "scoped-admission"],
                "unavailable": [item for item in commands if item["status"] == "unavailable-admission"],
            }
        rows.append(updated)
    return {**catalog, "syscalls": rows}


def incomplete_operations(catalog):
    return [
        row["name"] for row in catalog["syscalls"]
        if row["package_status"] not in {"kernel-no-handler", "ready"}
    ]


def report(catalog, names=()):
    calls = catalog["syscalls"]
    if names:
        selected = [row for row in calls if row["name"] in names]
        if len(selected) != len(set(names)):
            raise ValueError(f"unknown native operation: {', '.join(sorted(set(names) - {row['name'] for row in selected}))}")
        calls = selected
    kernel = catalog["kernel"]
    yield f"Linux {kernel['tag']} ({kernel['commit']}), {catalog['target']}"
    counts = Counter(row["kernel_status"] for row in calls)
    yield ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    package_counts = Counter(row["package_status"] for row in calls)
    yield ", ".join(f"{key}={value}" for key, value in sorted(package_counts.items()))
    yield f"{len(calls)} named native rows, {catalog['excluded_x32_records']} x32 records excluded"
    for row in calls:
        line = (
            f"{row['number']:3} {row['name']:28} stage {row['stage']} "
            f"{row['kernel_status']:19} {row['package_status']}"
        )
        if row["config"]:
            line += f"  {row['config']['requires']}"
        yield line
        if row["history"]:
            yield f"      {row['history']}"
        for condition in row["behavior_dependencies"]:
            yield f"      {condition['requires']}: {condition['note']}"
        if row["commands"]:
            yield f"      Commands: {len(row['commands']['supported'])} supported. {row['commands']['selector']}"
            for command in row["commands"]["supported"]:
                origin = f" via {command['runtime_selector']}" if "runtime_selector" in command else ""
                yield f"        {command['name']} ({command['operation']}){origin}"
            if "limit" in row["commands"]:
                yield f"        {row['commands']['limit']}"
        for profile in row.get("profiles", []):
            if "diagnostic" in profile:
                yield f"      {profile['operation']}: {profile['diagnostic']}"
            else:
                yield f"      {profile['operation']}: {profile['scope']}"
    if not names:
        for interval in catalog["reserved_ranges"]:
            yield f"{interval['first']}–{interval['last']}: {interval['status']} ({interval['native_result']})"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("generate", help="update the tracked catalog from pinned inputs")
    check = commands.add_parser("check", help="reject drift from the pinned inputs")
    check.add_argument(
        "--require-complete", action="store_true",
        help="also require all active syscalls to satisfy the plan's readiness gate",
    )
    printer = commands.add_parser("report", help="show kernel and package coverage separately")
    printer.add_argument("names", nargs="*", help="limit report to named native calls")
    printer.add_argument("--json", action="store_true", help="emit the full catalog as JSON")
    diff = commands.add_parser("diff", help="compare the pin with a proposed syscall_64.tbl")
    diff.add_argument("table", type=Path, nargs="?", help="proposed table")
    diff.add_argument("--before", type=Path, help="previous table to compare with the current pin")
    diff.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            CATALOG.write_bytes(encode(build_catalog()).encode("utf-8"))
            return 0
        catalog = load_catalog()
        if args.command == "check":
            print(f"{len(catalog['syscalls'])} native records match the pinned Linux {TAG} table")
            if args.require_complete:
                missing = incomplete_operations(package_coverage(catalog))
                if missing:
                    raise ValueError(
                        f"{len(missing)} active entries lack complete readiness: {', '.join(missing)}"
                    )
        if args.command == "report":
            catalog = package_coverage(catalog)
            if args.json:
                if args.names:
                    raise ValueError("the JSON report expects no syscall names")
                print(encode(catalog), end="")
            else:
                print(*report(catalog, args.names), sep="\n")
        if args.command == "diff":
            if (args.table is None) == (args.before is None):
                raise ValueError("specify exactly one proposed table or --before previous table")
            old, _ = parse_table((args.before or TABLE).read_text(encoding="utf-8"))
            new, _ = parse_table((args.table or TABLE).read_text(encoding="utf-8"))
            changes = table_diff(old, new)
            if args.json:
                print(encode(changes), end="")
            elif any(changes.values()):
                for kind in ("added", "removed"):
                    for row in changes[kind]:
                        print(f"{kind:7} {row['number']:3} {row['abi']:6} {row['name']} ({row['entry_point']})")
                for change in changes["changed"]:
                    before, after = change["before"], change["after"]
                    fields = ", ".join(f"{key} {before[key]!r} → {after[key]!r}" for key in before if before[key] != after[key])
                    print(f"changed {before['number']:3} {before['name']}: {fields}")
            else:
                print("No native syscall table changes")
    except (OSError, ValueError) as error:
        parser.exit(1, f"catalog: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
