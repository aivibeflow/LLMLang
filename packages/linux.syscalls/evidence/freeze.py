#!/usr/bin/env python3
"""Replay and freeze scoped admission subjects for this exact provider checkout."""

import argparse
import json
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from package import (  # noqa: E402
    ADMISSIONS, PACKAGE, PROVIDER, PackageError, admission_identity, command,
    current_bindings, evidence_inputs, file_hash, load_contracts, provider_files, rust_tools,
    unique_object,
)

from guest.run import KERNEL_RELEASE, KERNEL_SHA256, QUOTA_IMAGE_SHA256, module_hashes  # noqa: E402
from guest.run_bochs import BOOT_FILE_PINS, CASE as SHADOW_STACK_CASE  # noqa: E402

CASES = Path(__file__).with_name("cases.json")
BOCHS_SUITE = "shadow_stack"
QEMU_BIOS_SHA256 = "fc6d2ea888862e6b26d53fb877ab712324726eb8f44eb6baf076c64a31f1c3fb"
VM_CPUS = {"memory_keys": "max"}
VM_NUMA = {"numa_relocation"}
VM_QUOTA = {"quota_format"}
VM_MODULES = {
    "quota_format": ("loop.ko", "quota_tree.ko", "quota_v2.ko"),
    "kernel_modules": ("loop.ko",),
    "swap": ("loop.ko",),
}
AIO_CANCEL_CASE = "legacy_aio_cancel_acknowledges_queued_empty_pipe_poll_and_reaps_matching_completion"
VM_SUITES = {
    "legacy_aio_cancel": ("legacy_aio_cancel_guest", {
        "io_cancel": (AIO_CANCEL_CASE,),
        "io_submit_cancellable_pipe_poll": (AIO_CANCEL_CASE,),
        "io_getevents_cancelled_pipe_poll": (AIO_CANCEL_CASE,),
    }),
    BOCHS_SUITE: ("shadow_stack_guest", {"map_shadow_stack": (SHADOW_STACK_CASE,)}),
    "uretprobe": ("uretprobe_guest", {
        "uretprobe": ("uretprobe_kernel_trampoline_returns_exact_value",
                      "uretprobe_preserves_unprivileged_perf_denial"),
    }),
    "quota_format": ("quota_format_guest", {
        "quotactl_get_format": ("quotactl_reads_active_format_by_owned_device_path",),
        "quotactl_fd_get_format": ("quotactl_fd_reads_active_format_through_o_path",),
    }),
    "kernel_modules": ("kernel_modules_guest", {
        "init_module": ("init_module_guest_loads_signed_loop_and_reports_duplicate",
                        "init_module_guest_rejects_short_image", "kernel_modules_guest_preserves_permission_errors"),
        "finit_module": ("finit_module_guest_loads_signed_loop_and_preserves_offset",
                         "kernel_modules_guest_preserves_permission_errors"),
        "delete_module": ("delete_module_guest_unloads_loop_and_reports_absence",
                          "kernel_modules_guest_preserves_permission_errors"),
    }),
    "swap": ("swap_guest", {
        "swapon": ("swap_activates_and_releases_only_owned_guest_device",
                   "swap_invalid_header_and_inactive_area_preserve_state",
                   "swap_denial_preserves_owned_guest_device_state"),
        "swapoff": ("swap_activates_and_releases_only_owned_guest_device",
                    "swap_invalid_header_and_inactive_area_preserve_state",
                    "swap_denial_preserves_owned_guest_device_state"),
    }),
    "rseq": ("rseq_guest", {
        "rseq": ("rseq_registers_observes_cpu_and_unregisters_on_own_thread",),
        "rseq_unregister": ("rseq_registers_observes_cpu_and_unregisters_on_own_thread",),
    }),
    "numa_relocation": ("numa_relocation_guest", {
        "move_pages": ("numa_guest_queries_owned_pages_in_order_with_per_page_errno",),
        "migrate_pages": ("numa_guest_migrates_current_process_between_nodes",
                          "numa_guest_migrate_pages_checks_allowed_masks"),
        "set_mempolicy_home_node": ("numa_guest_home_node_applies_to_owned_bind_policy",
                                    "numa_guest_home_node_preserves_policy_errnos"),
    }),
    "file_page_mapping": ("file_page_mapping_guest", {
        "remap_file_pages": ("remap_file_pages_replaces_readonly_owned_page",),
        "restart_syscall": ("restart_syscall_preserves_inactive_thread_eintr",),
    }),
    "pty_hangup": ("pty_hangup_guest", {
        "vhangup_private_pty": ("vhangup_revokes_live_owned_private_tty",
                                "vhangup_errno_preserves_session_and_pty_endpoints"),
    }),
    "process_advice": ("process_advice_guest", {
        "process_madvise": ("process_madvise_guest_cold_preserves_readonly_mapping",
                            "process_madvise_guest_willneed_preserves_owned_bytes"),
        "process_mrelease": ("process_mrelease_guest_preserves_running_and_reaped_errors",
                             "process_mrelease_guest_releases_exiting_tracked_child"),
    }),
    "uts": ("uts_guest", {
        "unshare_uts_pinned": ("setns_rejoins_exact_owned_uts_and_invalidates_old_tokens",
                               "setns_capture_failure_returns_live_new_uts_authority"),
        "setns_uts": ("setns_rejoins_exact_owned_uts_and_invalidates_old_tokens",
                      "setns_permission_denial_preserves_current_uts_and_authority"),
        "setdomainname": ("domain_name_updates_only_private_namespace", "domain_name_permission_denied"),
        "sethostname": (
            "hostname_embedded_nul", "hostname_empty", "hostname_exact_64",
            "hostname_overlength_rejected", "hostname_permission_denied", "uts_inheritance_and_isolation",
        ),
        "unshare_uts": ("uts_inheritance_and_isolation", "uts_permission_denied"),
    }),
    "bpf_array": ("bpf_array_guest", {
        "bpf_map_create_u64": ("bpf_array_initial_zero",),
        "bpf_map_lookup_u64": ("bpf_array_initial_zero", "bpf_array_rejects_invalid_index"),
        "bpf_map_update_u64": ("bpf_array_update_preserves_other_entries", "bpf_array_rejects_invalid_index"),
    }),
    "lsm_queries": ("lsm_queries_guest", {
        "lsm_list_modules": ("lsm_guest_lists_modules_and_reports_required_capacity",),
        "lsm_get_self_attr": ("lsm_guest_reads_bounded_current_contexts",),
        "lsm_set_self_attr": ("lsm_guest_rechecks_own_apparmor_profile_without_transition",),
    }),
    "credential_changes": ("credential_changes_guest", {
        "capset_clear": ("capability_clear_does_not_change_sibling",),
        "prctl_set_no_new_privs": ("no_new_privs_is_monotone_and_thread_local",),
        "setgroups": ("credential_setgroups_exact_and_empty", "credential_post_drop_denials_preserve_state"),
        "setregid": ("credential_setregid_keeps_effective",),
        "setresgid": ("credential_setresgid_updates_filesystem_id",),
        "setgid": ("credential_setgid_privileged_updates_triplet",),
        "setreuid": ("credential_setreuid_keeps_effective",),
        "setresuid": ("credential_setresuid_updates_saved", "credential_transition_is_calling_thread_only"),
        "setuid": ("credential_setuid_drops_privileged_triplet", "credential_post_drop_denials_preserve_state"),
    }),
    "landlock": ("landlock_guest", {
        "landlock_create_ruleset_version": ("landlock_version_and_ruleset_cloexec",),
        "landlock_create_ruleset": ("landlock_version_and_ruleset_cloexec",),
        "landlock_add_rule": ("landlock_rejects_nonfilesystem_parent", "landlock_read_policy_enters_allowlist_and_denies_unlisted"),
        "landlock_restrict_self": (
            "landlock_read_policy_enters_allowlist_and_denies_unlisted",
            "landlock_existing_open_descriptor_remains_readable",
            "landlock_later_layer_cannot_relax_restriction",
        ),
    }),
    "self_memory_transfer": ("self_memory_transfer_guest", {
        "process_vm_readv": ("self_memory_guest_reads_exact_prefix",),
        "process_vm_writev": ("self_memory_guest_writes_exact_prefix",),
    }),
    "mounts": ("mounts_guest", {
        "chroot_tmpfs": ("chroot_sets_owned_root_and_cwd_and_preserves_open_fd", "chroot_kernel_denial_restores_original_cwd"),
        "pivot_root_tmpfs": ("pivot_root_moves_previous_attached_root_into_owned_tmpfs", "pivot_root_rejects_symlink_and_restores_cwd_on_rootfs"),
        "open_tree": ("open_tree_cloexec_clone_outlives_detachment", "mount_extensions_reject_detached_handle"),
        "fspick": ("fspick_owns_cloexec_context_without_reconfiguring", "mount_extensions_reject_detached_handle"),
        "mount_setattr": ("mount_setattr_tightens_only_owned_attachment", "mount_extensions_reject_detached_handle"),
        "unshare_mount_private": ("mount_namespace_rejects_parent_target",),
        "mount_tmpfs": ("mount_namespace_rejects_parent_target", "tmpfs_restricted_attachment"),
        "umount2_tmpfs": ("tmpfs_exact_detach_restores_cwd", "tmpfs_drop_detaches"),
    }),
    "sealed_memory": ("sealed_memory_guest", {
        "userfaultfd": ("userfaultfd_creates_only_user_mode_descriptor",),
        "memfd_secret": ("memfd_secret_returns_owned_cloexec_file",),
        "mseal": ("mseal_preserves_bytes_and_blocks_unmap",),
        "ptrace_trace_me": ("ptrace_traceme_voluntarily_stops_own_child",),
    }),
    "memory_keys": ("memory_keys_guest", {
        "pkey_alloc": ("pkey_alloc_has_finite_owned_capacity",),
        "pkey_free": ("pkey_free_explicit_and_drop_restore_capacity", "pkey_free_denial_returns_owned_key_for_retry"),
        "pkey_mprotect": ("pkey_mprotect_default_key_preserves_mapping",),
    }),
    "child_descriptor": ("child_descriptor_guest", {
        "kcmp": ("kcmp_guest_compares_only_own_open_file_descriptions",),
        "pidfd_getfd": ("pidfd_getfd_guest_copies_known_inheritance_and_preserves_cloexec",
                        "pidfd_getfd_guest_rejects_replaced_slot_and_discards_candidate"),
    }),
    "ustat": ("ustat_guest", {
        "ustat": ("ustat_matches_owned_tmpfs_and_observes_allocation",),
    }),
    "exec_descriptors": ("exec_descriptors_guest", {
        "prepare_execveat_fd": ("execveat_guest_runs_sealed_descriptor_with_exact_arguments",
                                "execveat_guest_preserves_invalid_image_error_and_child_fallback"),
        "execveat": ("execveat_guest_runs_sealed_descriptor_with_exact_arguments",
                     "execveat_guest_preserves_invalid_image_error_and_child_fallback"),
        "fork_execveat": ("execveat_guest_runs_sealed_descriptor_with_exact_arguments",
                         "execveat_guest_preserves_invalid_image_error_and_child_fallback"),
        "vfork_execve_masked": ("vfork_guest_inherits_blocked_mask_and_restores_parent",),
    }),
    "filesystem_handles": ("filesystem_handles_guest", {
        "sync": ("sync_completes_for_disposable_guest",),
        "name_to_handle_at": ("file_handle_resolution_stays_within_owned_tmpfs", "file_handle_reopens_original_inode_read_only_after_rename"),
        "open_by_handle_at": ("file_handle_reopens_original_inode_read_only_after_rename",),
    }),
    "thread_architecture": ("thread_architecture_guest", {
        "modify_ldt_read": ("modify_ldt_reads_empty_current_table",),
        "iopl_drop": ("iopl_drop_succeeds_in_disposable_guest",),
        "ioperm_revoke": ("ioperm_revokes_valid_guest_ranges",),
    }),
    "guest_controls": ("guest_controls_guest", {
        "acct": ("accounting_records_exit_and_disables_cleanly",),
        "reboot_cad_control": ("reboot_cad_flags_change_only_guest_policy",),
        "kexec_load_unload": ("kexec_unload_native_entries_are_idempotent_for_empty_guest",
                              "kexec_unload_denial_preserves_guest_staging_state"),
        "kexec_file_unload": ("kexec_unload_native_entries_are_idempotent_for_empty_guest",
                              "kexec_unload_denial_preserves_guest_staging_state"),
    }),
    "system_legacy": ("system_legacy_guest", {
        "syslog_buffer_size": ("syslog_observes_capacity_without_reading_contents",),
        "sysfs_count": ("sysfs_reports_filesystem_type_count",),
        "mlockall_current_onfault": ("memory_lockall_and_unlockall_preserve_owned_bytes",),
        "munlockall": ("memory_lockall_and_unlockall_preserve_owned_bytes",),
    }),
    "clock_setting": ("clock_setting_guest", {
        "clock_settime": ("clock_settime_updates_disposable_realtime", "guest_realtime_restores_from_monotonic_elapsed",
                          "clock_setters_preserve_invalid_and_unprivileged_errno"),
        "settimeofday": ("settimeofday_updates_microseconds_without_timezone",
                          "clock_setters_preserve_invalid_and_unprivileged_errno"),
    }),
    "clone_launch": ("clone_launch_guest", {
        "clone_execve": ("clone_guest_runs_exec_with_exact_arguments",),
        "clone3_execve": ("clone3_guest_runs_exec_with_exact_arguments",),
    }),
    "fanotify": ("fanotify_guest", {
        "fanotify_init": ("fanotify_selects_one_inode_and_delivers_owned_event_fds", "fanotify_descriptor_mode_requires_privilege"),
        "fanotify_mark": ("fanotify_selects_one_inode_and_delivers_owned_event_fds", "fanotify_removes_exact_mark_and_preserves_empty_queue_errno"),
        "read_fanotify_event": ("fanotify_selects_one_inode_and_delivers_owned_event_fds", "fanotify_removes_exact_mark_and_preserves_empty_queue_errno"),
    }),
    "keyring": ("keyring_guest", {
        "keyctl_join_session": ("keyring_creates_one_anonymous_session",),
        "add_key": ("keyring_rejects_unscoped_key_input", "keyring_queries_and_reads_exact_owned_value",
                    "keyring_drop_removes_only_owned_link"),
        "request_key": ("keyring_queries_and_reads_exact_owned_value", "keyring_unlink_consumes_owned_link"),
        "keyctl_read": ("keyring_queries_and_reads_exact_owned_value", "keyring_unlink_consumes_owned_link"),
        "keyctl_unlink": ("keyring_unlink_consumes_owned_link", "keyring_drop_removes_only_owned_link"),
    }),
    "numa": ("numa_guest", {
        "get_mempolicy": ("numa_guest_observes_allowed_nodes_and_thread_policy", "numa_guest_preserves_invalid_policy_errno"),
        "get_mempolicy_allowed": ("numa_guest_observes_allowed_nodes_and_thread_policy",),
        "get_mempolicy_mapping": ("numa_guest_updates_only_owned_mapping_policy",),
        "set_mempolicy": ("numa_guest_observes_allowed_nodes_and_thread_policy", "numa_guest_preserves_invalid_policy_errno"),
        "mbind": ("numa_guest_updates_only_owned_mapping_policy",),
    }),
    "complex": ("complex_guest", {
        "perf_event_open_task_clock": ("perf_task_clock_ticks",),
        "io_uring_setup": ("io_uring_setup_returns_owned_ring",),
        "io_uring_register_probe": ("io_uring_probe_reports_nop",),
        "io_uring_nop": ("io_uring_nop_completes",),
    }),
}


def guest_observations(files, evidence_files):
    expected_sources = {name: file_hash(data) for name, data in files.items()}
    operations = {}
    for suite, (example, cases) in VM_SUITES.items():
        source = PACKAGE / "guest" / f"{suite}-evidence.json"
        report = json.loads(source.read_bytes(), object_pairs_hook=unique_object)
        expected_tests = {
            name: evidence_files[name]
            for name in ("guest/init.c", "guest/run.py", f"provider/examples/{example}.rs")
        }
        if suite == BOCHS_SUITE:
            expected_tests.update({name: evidence_files[name] for name in ("guest/init_bochs.c", "guest/run_bochs.py")})
            expected_profile = {"boot_files_sha256": BOOT_FILE_PINS, "cpu": "tigerlake"}
        else:
            expected_profile = {
                "firmware_sha256": QEMU_BIOS_SHA256,
                "cpu": VM_CPUS.get(suite),
                "numa": suite in VM_NUMA,
                "quota_image_sha256": QUOTA_IMAGE_SHA256 if suite in VM_QUOTA else None,
                "module_fixtures_sha256": module_hashes(VM_MODULES.get(suite, ())),
            }
        if (
            report["guest_status"] != 0
            or report["kernel_sha256"] != KERNEL_SHA256
            or report["kernel_release"] != KERNEL_RELEASE
            or any(key not in report or report[key] != value for key, value in expected_profile.items())
            or report["provider_source_sha256"] != expected_sources
            or report["test_source_sha256"] != expected_tests
            or set(report["cases"]) != {case for matching in cases.values() for case in matching}
        ):
            raise PackageError(f"{suite} VM evidence does not apply to the exact provider and cases")
        for name, matching in cases.items():
            operations[name] = report["kernel_release"], matching
    return operations


def replay():
    rust_tools()
    operations = load_contracts()
    files = provider_files()
    bindings = current_bindings(operations, files)
    cases = json.loads(CASES.read_bytes(), object_pairs_hook=unique_object)
    expected = set(cases)
    evidence_files = evidence_inputs()
    guest = guest_observations(files, evidence_files)
    operation_names = {name for tested in cases.values() for name in tested} | guest.keys()
    if operation_names != operations.keys():
        raise PackageError(
            f"contract/case mapping mismatch: missing {sorted(operations.keys() - operation_names)}, "
            f"unknown {sorted(operation_names - operations.keys())}"
        )
    args = ["--offline", "--locked", "--manifest-path", str(PROVIDER / "Cargo.toml")]
    with tempfile.TemporaryDirectory(prefix="llmlang-syscall-evidence-") as temporary:
        paths = Path(temporary)
        args += ["--target-dir", str(paths / "target")]
        layout = paths / "layout"
        command([
            "cc", "-std=gnu17", "-Wall", "-Wextra", "-Werror",
            str(PACKAGE / "evidence/layout.c"), "-o", str(layout),
        ])
        command([str(layout)])
        native_report = command(["cargo", "test", *args, "--lib", "--tests", "--", "--test-threads=1"])
        observed = re.findall(r"(?m)^test (?:[\w]+::)*([\w]+) \.\.\. ok$", native_report)
        missing = expected - set(observed)
        if missing:
            raise PackageError(f"native cases absent from passing run: {', '.join(sorted(missing))}")

        command(["cargo", "test", *args, "--doc"])
        command(["cargo", "build", *args, "--example", "decoder"])
        model = paths / "return-model.json"
        command([
            sys.executable, "-B", str(PACKAGE / "evidence/check.py"),
            "--decoder", str(paths / "target/debug/examples/decoder"),
            "--subject", str(PROVIDER / "src/io.rs"),
            "--subject", str(PROVIDER / "src/lib.rs"),
            "--subject", str(PACKAGE / "contracts/syscalls.json"),
            "--report", str(model),
        ])
        model_report = json.loads(model.read_bytes())
    if model_report["status"] != "MODEL_CHECKED" or model_report["native_correspondence"]["status"] != "BOUNDED_AGREEMENT":
        raise PackageError("return model did not pass model and native cross-checks")

    result = {}
    for name, binding in bindings.items():
        native = sorted(case for case, tested in cases.items() if name in tested)
        result[name] = {
            "subject": admission_identity(binding, evidence_files),
            "body": "BOUNDED_NATIVE_TEST",
            "cases": native,
        }
        if name in guest:
            kernel, matching = guest[name]
            result[name]["body"] = "BOUNDED_DISPOSABLE_VM_TEST"
            result[name]["cases"] = list(matching)
            result[name]["guest_kernel"] = kernel
            result[name]["host_cases"] = native
        if name in ("read", "write"):
            result[name]["formal_model"] = "MODEL_CHECKED_WITH_BOUNDED_NATIVE_DECODER_AGREEMENT"
    return {
        "schema": "llmlang.linux.syscalls.admissions.v1",
        "evidence_inputs": evidence_files,
        "operations": result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--verify", action="store_true")
    action.add_argument("--output", type=Path)
    parser.add_argument("--retain", type=Path, help="retain an earlier exact admission manifest")
    args = parser.parse_args()
    if args.retain and args.verify:
        parser.error("--retain requires --output")
    try:
        record = replay()
        if args.verify:
            existing = json.loads(ADMISSIONS.read_bytes(), object_pairs_hook=unique_object)
            if any(existing.get(key) != value for key, value in record.items()):
                raise PackageError("replayed evidence differs from recorded admissions")
        else:
            if args.retain:
                previous = json.loads(args.retain.read_bytes(), object_pairs_hook=unique_object)
                if previous["schema"] != record["schema"]:
                    raise PackageError("incompatible historical manifest")
                historical = {key: previous[key] for key in ("evidence_inputs", "operations")}
                record["history"] = [historical, *previous.get("history", [])]
            with args.output.open("x", encoding="utf-8") as output:
                json.dump(record, output, indent=2, sort_keys=True)
                output.write("\n")
    except (OSError, ValueError, KeyError, PackageError) as error:
        parser.exit(1, f"freeze: {error}\n")
    print(f"{len(record['operations'])} exact bounded admission subjects replayed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
