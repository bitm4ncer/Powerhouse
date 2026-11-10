# Design-Skill Integration

`magpie-manager` is not a visual designer. It calls specialized design skills at the right moments, then translates their output into block options + custom CSS.

---

## Skill lookup table

| Trigger | Skill to call | What you do with the result |
|---|---|---|
| Vague brief → need concept (sections, mood, layout) | `frontend-design` | Translate the design proposal into Magpie sections + blocks. The skill describes look-and-feel; you map to existing blocks + tokens, escalating to custom CSS only if unavoidable. |
| UX/UI planning (typo hierarchy, spacing rhythm, color application) | `frontend-design` | Use proposal as guidance for which `display-*`/`lead`/`eyebrow` classes to apply, which section spacing tokens, which colors. |
| Need creative CSS that block options can't express (complex hover, multi-step animation, special layout) | `frontend-design` | Take the CSS the skill writes, **trim to scope**, paste into `page_custom_css` (page-scoped) or `custom_css` (site-scoped). Always add a comment header. |
| Need UX copy (headline, button label, error message, empty state, microcopy) | `design:ux-copy` | Use copy directly in `text` block `text`, `button` `button_text`, etc. |
| End-of-task visual critique | `design:design-critique` | Pass screenshot. Use findings to decide if a fix iteration is needed. |
| Suspect accessibility issue (contrast, tap targets, keyboard nav) | `design:accessibility-review` | Implement fixes via block options or custom CSS. |
| User asks for research input ("how do other portfolio sites handle X?") | `design:user-research` (lite) | Use insights for the concept, not as an actual research project (overkill for content work). |

---

## When to call `frontend-design`

**Call it when:**
- Brief is vague and you need a design direction before building
- You hit a wall with block options (need real CSS magic)
- User explicitly asks for "design help" or "make it look better"

**Don't call it for:**
- Simple block additions ("add a contact section") — just pick the right block
- Reordering / moving existing blocks
- Single-field changes
- Anything where the answer is "use the block's existing option"

**How to call it:**
Pass the skill these inputs:
- Current site context (theme colors, fonts, existing tone read from `site.txt`)
- The brief or what you're trying to achieve
- Constraint: "Output should be either (a) a structural concept I can map to existing Magpie blocks, OR (b) scoped CSS that can live in a `page_custom_css` field. No HTML to write directly."

**Translate the output:**
The skill might output HTML+CSS. You don't paste the HTML — you:
1. Read the structural intent (what sections, what hierarchy)
2. Map to Magpie blocks (consult `block-catalog.md`, `use-case-mapping.md`)
3. Extract any CSS that's truly necessary (hover animations, special layouts)
4. Place CSS in `page_custom_css` or `custom_css` with a comment header explaining intent

---

## When to call `design:ux-copy`

For any user-facing text that needs to be sharp:
- Page headlines
- Button labels (especially CTA verbs: "Get started" vs "Sign up" vs "Try it")
- Empty states ("No projects yet" vs "Your portfolio starts here")
- Error/confirmation copy
- Microcopy (placeholder text, helpers)

Pass the skill: context (what's the page/section), audience tone, length constraint.

---

## When to call `design:design-critique`

**Always at end of a non-trivial task.** Pass:
- Full-page screenshot (use Preview / Chrome DevTools MCP)
- Brief description of what you built/changed
- Ask for: hierarchy, contrast, spacing rhythm, visual weight balance

Use findings:
- Blocking issue (broken layout, illegible text) → fix iteration (up to 2)
- Minor polish suggestion → note in the report to user, don't auto-fix unless they say so
- Subjective taste call → mention in report, let user decide

---

## When to call `design:accessibility-review`

**When you've changed:**
- Color palette (contrast risk)
- Tap targets (button sizes)
- Form/interactive elements
- Anything with hover-only behavior (no keyboard alternative?)
- Heading structure (h1, h2 hierarchy)

**Findings → block options:**
- Low contrast → adjust `text_color` / `background_color` (or theme accent)
- Small tap target → `button_size: large`
- Missing alt → set on `image` block or media-library file metadata
- Heading skip → reorder Markdown `#`/`##`/`###` in text blocks

---

## When the design skill conflicts with Magpie constraints

`frontend-design` might propose a brutalist layout with overlapping elements, custom grid, or a unique component that doesn't map to any block. When that happens:

1. **First try to approximate** with existing blocks + Section column widths + custom_class CSS hooks.
2. If approximation is 80% there: do it, note the gap in the report.
3. If approximation is <50%: stop, report to user.

You don't build custom blocks. That's theme work.

---

## Custom code quality bar (when adding CSS/JS from design output)

Always include:

```css
/* ============================================================
   <Section / page>: <what this does>
   Added: <date>
   Reason: <why block options weren't enough>
   Adjustable: <which parts the user can safely tweak>
   ============================================================ */
.scoped-class {
  /* readable, formatted */
}
```

For JS:

```javascript
// ============================================================
//   <What this does>
//   Added: <date>
//   Reason: <why this needs JS>
//   Adjustable: <variables / parameters the user might tweak>
// ============================================================
(function () {
  'use strict';
  const TARGET = '.scoped-class';
  // …
})();
```

The user reads this in 2 weeks. They need to know what it is, why it's there, and what they can change.

---

## Anti-pattern to avoid

Don't call `frontend-design`, get a big chunk of HTML+CSS, paste the CSS verbatim into `custom_css`, and call it a day. That re-introduces the AI-look the user explicitly doesn't want.

Instead:
1. Get the design idea
2. Map structure to existing Magpie patterns
3. Use blocks for everything you can
4. Trim CSS to **only what blocks can't do**
5. Document why
