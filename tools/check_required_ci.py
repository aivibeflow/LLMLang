#!/usr/bin/env python3
"""Check the required CI workflow even when its own jobs are skipped."""

import sys
from pathlib import Path

import yaml


WORKFLOW = Path('.github/workflows/ci-required.yml')
REQUIRED_SUITES = {
    'logos-binding',
    'package-identity',
    'package-index',
    'qf-lia-profile',
    'repository-structure',
    'semantic-dependency-index',
    'toolchain-workspace',
}


def validate(workflow):
    # BaseLoader keeps GitHub's YAML key `on` as a string.
    triggers = workflow.get('on', {})
    jobs = workflow.get('jobs', {})
    gate = jobs.get('ci-required', {})
    errors = []

    if triggers.get('pull_request') != {'branches': ['main']}:
        errors.append('run required CI for every pull request targeting main')
    if triggers.get('push') != {'branches': ['main']}:
        errors.append('run required CI after every push to main')
    if gate.get('name') != 'ci-required' or gate.get('if') != '${{ always() }}':
        errors.append('the ci-required job must keep its name and run even when a suite fails')
    if gate.get('continue-on-error', 'false') != 'false':
        errors.append('ci-required must propagate its failure')

    suites = jobs.keys() - {'ci-required'}
    if not REQUIRED_SUITES <= suites or set(gate.get('needs', [])) != suites:
        errors.append('ci-required must depend on all required suites and any newly added jobs')

    for name in sorted(suites):
        job = jobs[name]
        if 'if' in job or job.get('continue-on-error', 'false') != 'false':
            errors.append(f'{name} must run unconditionally and propagate failure')

    return errors


def main():
    try:
        workflow = yaml.load(WORKFLOW.read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
        errors = validate(workflow)
    except (OSError, yaml.YAMLError, AttributeError, TypeError) as exc:
        print(f'{WORKFLOW}: {exc}', file=sys.stderr)
        return 1

    for error in errors:
        print(f'{WORKFLOW}: {error}', file=sys.stderr)
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
