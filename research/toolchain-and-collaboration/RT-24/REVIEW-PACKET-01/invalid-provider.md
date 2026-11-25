# Review bundle for invalid provider

## Revision pair

| Role | Commit | Tree |
| --- | --- | --- |
| Base | `8d670b067e63dacd9a7eb57db5839c33b62159ec` | `0dd85fb74a4af317eea862a06d6742d99c6537f8` |
| Candidate | `9edbe18941ca90abb96c4eb6d656db0db0bf4ee4` | `ed4a40c78309aaad3f1893c5980bf40768f5286e` |

Review bundle SHA-256 `3f107199dd4994b40dcf7cc5e25fa457453ed35a3e2f6e1c7c0d7b32740d5273`.

## Semantic changes

Semantic comparison unavailable. unknown implementation: absent.

Interpreter observations unavailable for the candidate.

## Exact source patch

Patch SHA-256 `79ce6b6884a9be0c80d4e5e98ce9d2c456543a423406602e2e856f959717acbe`.

````diff
diff --git a/program.json b/program.json
index 066a5d2..e702a92 100644
--- a/program.json
+++ b/program.json
@@ -1 +1 @@
-{"surface": "infix", "entry": "op(\"compute\", x)", "binding": "plus"}
+{"surface": "infix", "entry": "op(\"compute\", x)", "binding": "absent"}
````
