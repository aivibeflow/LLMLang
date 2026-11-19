# Contributing

## Install repository Git hooks

Run this once in your checkout to enable the repository's local hooks:

```sh
git config core.hooksPath .githooks
```

The pre-commit hook checks the staged contents of every Markdown file for valid UTF-8 and disallowed control characters. It reports failures and blocks the commit; it does not modify files. CI runs the same checker as a required merge gate.
