---
name: craft-anything
description: Study how any website, app, or game works and rebuild it with Craft Anything (ArtCraft). Use when the user wants to inspect a target's UI or behaviour, recreate a site or game in another stack, compare a rebuild against the original, or run clean-room reverse engineering with evidence. Trigger on "craft anything", "recreate this website", "rebuild this game", "how does this app work", "clean room", "ArtCraft".
---

# Craft Anything

Craft Anything is a standalone Rust engine with a CLI and an MCP server. It is
not an OpenCode plugin: the binary `craft-anything-cli` must be installed.
Use the CLI for one-off work and the MCP tools when the server is registered.

## Check the install

```sh
craft-anything-cli capabilities      # toolsets, engines, agent backends
craft-anything-cli doctor            # install, registrations, engines, MCP
craft-anything-cli commands          # every tool, grouped by toolset
```

## Core workflows

```sh
# Study a target and answer a question, with evidence
craft-anything-cli chat https://example.com "How is the hero section built?"

# Study, build, check, refine (needs a signed-in coding agent)
craft-anything-cli rebuild https://example.com "Recreate this website"
craft-anything-cli rebuild - "A snake game in Rust" --rounds 1

# Continue or edit an existing project
craft-anything-cli rebuild https://example.com "Make the header blue" --continue-in "<project folder>"

# First look at an unknown file
craft-anything-cli triage <file>

# MCP server for an agent client
craft-anything-cli mcp
```

Projects live in `Documents/Craft Anything` by default. Each project holds
`craft.json`, `capture/`, `app/`, `checks/`, `investigation.cany/`, and `inbox/`.

## Clean room vs Deep

- **Clean room (default):** only what a visitor can see. Tools that read inside
  the target are refused and say how to enable Deep mode.
- **Deep:** reads code, files, and page source. Use it only on software you own
  or are explicitly allowed to examine. Enable per run with `--deep`, or in
  settings with `settings_set deep_mode true`.

Never switch to Deep silently. Tell the user what changes and why.

## MCP tools

The server starts with the **Essentials** toolset only. Call `list_toolsets`
and `enable_toolset` to add native, Android, web, firmware, or other tools.
Start with `core_investigation_show` and `core_session_show`; open a target with
`core_target_open` (absolute path). Cite evidence ids, keep observations apart
from inferences, and record unknowns.

## Rules

- Only target software you own or are allowed to examine.
- Never bypass DRM, logins, or anti-cheat.
- Ask before any command that runs code or changes a device (`--allow-run`).
- A rebuild needs a coding agent signed in on the machine; OpenCode can be used
  as the ACP backend.
- Do not copy logos, photos, or text from the target unless the user confirms
  they own them or have permission.
