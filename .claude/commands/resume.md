---
description: Clear memory/HALT.md after a Section 12 halt — human confirmation required. Never run automatically.
---

`memory/HALT.md` is QMS-01's kill-switch (Section 12). No cloud routine
may ever clear it — only this local, human-invoked command may.

1. If `memory/HALT.md` does not exist, say so and stop — nothing to resume.
2. Print the full contents of `memory/HALT.md` (reason, timestamp,
   triggering routine/condition) so the reason is visible before clearing it.
3. Explicitly ask: "Clear the halt and resume trading? This does not
   undo whatever caused it — only you can decide the underlying issue is
   actually resolved. Type 'yes, resume' to confirm." Do not proceed on
   an ambiguous or implicit yes — require that exact phrase.
4. On explicit confirmation only:
   - Delete `memory/HALT.md`
   - Append a note to `memory/EXCEPTIONS-LOG.md` recording who/what
     resumed it and when, referencing the original halt reason
   - `git add memory/EXCEPTIONS-LOG.md && git rm memory/HALT.md`
   - Commit: `git commit -m "resume trading after halt: <one-line reason>"`
   - Push: `git push origin main` (rebase-and-retry on failure, never force)
5. Confirm to the user that routines will resume normal operation on
   their next scheduled firing.
