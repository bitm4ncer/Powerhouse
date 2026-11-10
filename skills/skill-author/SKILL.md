---
name: skill-author
description: Write, test, and maintain OpenCode skills. Use when the user says "write a skill", "new skill", "turn this into a skill", "improve this skill", "why did the skill not trigger", or when a repeated workflow should become reusable. Covers frontmatter, trigger phrases, progressive disclosure, verification, and installation into a harness.
---

# Skill author

A skill is a small, tested operating manual for one job. If it does not change
what the agent does, it is documentation, not a skill.

## Where skills live

- Global: `~/.config/opencode/skills/<name>/SKILL.md`
- Project: `<project>/.opencode/skills/<name>/SKILL.md`
- Harness repo: `skills/<name>/SKILL.md` (installed by the setup script)

One directory per skill. Extra material goes in `references/` and is loaded only
when the skill points to it.

## Frontmatter

```yaml
---
name: lower-case-hyphenated
description: One sentence on what it does, then the exact phrases a user says when they need it. Include the nouns: tool names, file types, commands.
---
```

The **description is the trigger**. If it does not contain the words the user
actually types, the skill will not load. Put the verbs first ("Audit…",
"Deploy…"), then the triggers.

## Body structure

1. **Purpose** — one paragraph, no history.
2. **Hard rules** — the things that prevent damage. Short, imperative.
3. **Workflow** — numbered steps with commands that run as written.
4. **Verification** — how to prove it worked, not just that it ran.
5. **Failure modes** — what usually goes wrong and what to do.
6. **References** — links to deeper files, if any.

Keep `SKILL.md` under ~150 lines. Move long tables, API notes, and recipes into
`references/<topic>.md`.

## Writing rules

- One job per skill. If the trigger list needs "and", split it.
- Commands must be copy-pasteable, with placeholders in `<angle-brackets>`.
- Prefer absolute paths or documented variables; never hardcode a machine path.
- State what **not** to do: destructive commands, silent mode switches, secrets.
- No secrets, tokens, customer names, or personal paths in examples.
- Verify claims; do not describe a tool you have not run.

## Test it

1. Start a fresh session and say a trigger phrase. Confirm the skill appears in
   the loaded list.
2. Run the happy path end to end.
3. Run one failure path (missing tool, wrong input) and check that the skill
   tells the agent to stop rather than guess.
4. Check the token cost: the skill should not be a 400-line dump.

## Version and ship

- Keep the skill in the harness repo so it survives a machine change.
- Add it to the README inventory and, if third-party, to `THIRD_PARTY.md`.
- Commit message: `feat(skills): add <name>`.
- Bump or date a breaking change in a `CHANGELOG` only if the skill has consumers
  beyond the user.

## Checklist

- [ ] Trigger phrases match real user language
- [ ] One job, no "and"
- [ ] Commands run as written
- [ ] Verification step included
- [ ] Failure modes and stop conditions included
- [ ] No secrets, PII, or machine paths
- [ ] Under ~150 lines; details in `references/`
- [ ] Tested with a real prompt
- [ ] Listed in the harness README
