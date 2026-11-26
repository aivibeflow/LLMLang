"""Regression tests for exact syscall-contract identity and admission checks."""

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from contracts import COMMANDS_PATH, CONTRACTS_PATH, ContractError, load_commands, load_contracts, refinement, render


class SyscallContracts(unittest.TestCase):
    def setUp(self):
        self.operations = load_contracts()
        self.read = self.operations["read"]

    def revised_contracts(self, mutate):
        bundle = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
        mutate(bundle)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "contracts.json"
            path.write_text(json.dumps(bundle, sort_keys=True), encoding="utf-8")
            return load_contracts(path)

    def test_exact_role_and_interface_revisions(self):
        self.assertNotEqual(self.read.public.id, self.read.provided.id)
        modified = self.revised_contracts(lambda value: value["operations"][0]["provided"]["guarantees"].append({
            "id": "extended-claim", "statement": "This candidate has an additional provider guarantee.",
        }))["read"]
        self.assertEqual(self.read.public.id, modified.public.id)
        self.assertEqual(self.read.interface_revision, modified.interface_revision)
        self.assertNotEqual(self.read.provided.id, modified.provided.id)
        self.assertEqual(refinement(modified.public, modified.provided), [])

    def test_public_type_changes_invalidate_interface(self):
        modified = self.revised_contracts(lambda value: value["types"]["Count"].update({
            "description": "Candidate alternate count semantics.",
        }))["read"]
        self.assertNotEqual(self.read.public.id, modified.public.id)
        self.assertNotEqual(self.read.interface_revision, modified.interface_revision)

    def test_contract_identity_ignores_format_and_object_field_order(self):
        equivalent = self.revised_contracts(lambda value: value["operations"][0]["public"]["guarantees"].reverse())
        self.assertEqual(self.read, equivalent["read"])

    def test_refinement_rejects_strengthening_and_extra_effects(self):
        public = self.read.public
        provided = replace(
            self.read.provided,
            preconditions={"special-handle": "Only regular files are supported."},
            assumptions={**public.assumptions, "extra-premise": "No interrupts occur."},
            guarantees={"eof": public.guarantees["eof"]},
            effects={**public.effects, "replace-process": "Replace the current process."},
        )
        errors = refinement(public, provided)
        self.assertEqual(len(errors), 4)
        for prefix, detail in (
            ("added provider preconditions", "special-handle"), ("added provider assumptions", "extra-premise"),
            ("missing public guarantees", "progress-count"), ("additional provider effects", "replace-process"),
        ):
            self.assertTrue(any(error.startswith(prefix) and detail in error for error in errors), errors)

    def test_unrecognized_types_and_versions_are_rejected(self):
        with self.assertRaisesRegex(ContractError, "undeclared type"):
            self.revised_contracts(lambda value: value["operations"][0]["signature"]["parameters"][0].update({
                "type": "RawUntrackedPointer",
            }))
        with self.assertRaisesRegex(ContractError, "unsupported syscall contract schema"):
            self.revised_contracts(lambda value: value.update({"schema": "future"}))

    def test_duplicate_json_field_is_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "contracts.json"
            path.write_text('{"schema":"first","schema":"second"}', encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "duplicate JSON object field"):
                load_contracts(path)

    def test_review_preserves_open_kernel_premises(self):
        report = render(self.read)
        self.assertEqual(report["refinement"]["status"], "CONDITIONAL")
        self.assertEqual(report["provider_conformance"]["status"], "UNSUPPORTED")
        self.assertIn("native-linux-abi", report["contracts"]["public"]["assumptions"])

    def test_command_operation_can_cover_multiple_selectors_in_one_family(self):
        inventory = load_commands(self.operations)
        entries = inventory["families"]["reboot"]["commands"]
        self.assertEqual(
            [(entry["value"], entry["operation"]) for entry in entries],
            [(0, "reboot_cad_control"), (0x89ABCDEF, "reboot_cad_control")],
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / COMMANDS_PATH.name
            inventory["families"]["fcntl"]["commands"][0]["operation"] = "reboot_cad_control"
            path.write_text(json.dumps(inventory), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "also belongs to another native family"):
                load_commands(self.operations, path)

    def test_runtime_command_selector_distinguishes_the_native_event_type(self):
        inventory = load_commands(self.operations)
        commands = inventory["families"]["perf_event_open"]["commands"]
        task_clock, return_probe = commands
        self.assertEqual(task_clock["value"], return_probe["value"])
        self.assertEqual(return_probe["runtime_selector"], "/sys/bus/event_source/devices/uprobe/type")
        with TemporaryDirectory() as directory:
            path = Path(directory) / COMMANDS_PATH.name
            return_probe["runtime_selector"] = "/sys/../proc/self/exe"
            path.write_text(json.dumps(inventory), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "invalid token"):
                load_commands(self.operations, path)
            del return_probe["runtime_selector"]
            path.write_text(json.dumps(inventory), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "duplicate entries"):
                load_commands(self.operations, path)

    def test_command_inventory_requires_exact_typed_operation_and_uapi(self):
        inventory = load_commands(self.operations)
        families = inventory["families"]
        self.assertEqual(families["fcntl"]["commands"][0]["operation"], "fcntl_getfd")
        self.assertEqual([command["value"] for command in families["bpf"]["commands"]], [0, 1, 2])
        self.assertEqual(
            [(entry["name"], entry["value"], entry["operation"]) for entry in families["io_uring_enter"]["commands"]],
            [("IORING_ENTER_GETEVENTS", 1, "io_uring_nop")],
        )
        self.assertEqual([command["value"] for command in families["get_mempolicy"]["commands"]], [0, 2, 4])
        with self.assertRaisesRegex(ContractError, "missing qualified operation"):
            load_commands({name: operation for name, operation in self.operations.items() if name != "fcntl_getfd"})
        families["fcntl"]["commands"][0]["uapi"] = "https://github.com/torvalds/linux/blob/master/include/uapi/asm-generic/fcntl.h"
        with TemporaryDirectory() as directory:
            path = Path(directory) / COMMANDS_PATH.name
            path.write_text(json.dumps(inventory), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "immutable reference"):
                load_commands(self.operations, path)
