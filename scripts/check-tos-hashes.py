"""CI helper: print SHA256 of TOS_TEXT and PRIVACY_TEXT (one per line).

Invoked from `.github/workflows/gpd-release.yml` tos-guard job. Broke out of
the workflow heredoc because YAML block-scalar indentation + shell heredoc
indentation don't compose — the heredoc body had to be flush-left inside
the `run: |` block, which terminated the YAML scalar early and made GitHub
report "Workflow does not have 'workflow_dispatch' trigger" on dispatch.

Separate script, zero heredocs, cleanly indent-compatible with YAML.

Output lines (stable order):
  <tos_text_sha256>
  <privacy_text_sha256>
"""
import hashlib
import pathlib
import re
import sys

SRC = pathlib.Path("packages/app/src/components/tos-content.tsx").read_text(
    encoding="utf-8"
)
tos = re.search(r"export const TOS_TEXT = `([^`]+)`", SRC)
priv = re.search(r"export const PRIVACY_TEXT = `([^`]+)`", SRC)
if not tos or not priv:
    print(
        "ERROR: TOS_TEXT / PRIVACY_TEXT template literal not found in tos-content.tsx",
        file=sys.stderr,
    )
    sys.exit(2)

print(hashlib.sha256(tos.group(1).encode("utf-8")).hexdigest())
print(hashlib.sha256(priv.group(1).encode("utf-8")).hexdigest())
