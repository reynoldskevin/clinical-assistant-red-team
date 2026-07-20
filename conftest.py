"""Repo-root conftest.

Its presence at the repository root puts the root directory on ``sys.path`` during
test collection (pytest prepend import mode), so ``import forge`` resolves to the
package in this repo without requiring an editable install. Test infrastructure —
owned by the orchestrator, not to be edited by the implementer.
"""
