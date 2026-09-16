# d0rbu — Interactive TUI UX Refinements

**Status:** Approved 2026-05-29 (user feedback + 3 clarifying answers). Lands as
additional commits on **PR #3** (still unmerged — maintainer reviews & merges).
Spec + plan kept UNTRACKED. Builds on the schema-hardened card + demos work.

## Scope — 7 user-requested UX changes (interactive TUI + content)

1. **Demos grayed + unselectable** while under construction; auto-enable + name
   the new demos once a release actually adds them (the prior demos-badge
   feature, now gated on selectability).
2. **Open-in-browser items** (Blog, Twitter, project links): first activation
   opens the browser and shows *"Opened in browser. Didn't open? Press enter
   again for a URL."*; pressing enter again **on the same item without moving
   the highlight** prints the URL (and keeps printing it); **moving the
   highlight away and back re-arms to open** (true cursor-movement reset).
3. Remove the **"(Use arrow keys)"** instruction.
4. Pressing enter must **not reset the highlight to About** — the cursor stays
   on the last-activated item.
5. **Blog** → `https://substack.com/@d0rb`.
6. **Twitter** (`@henrycstllo`) → `https://x.com/henrycstllo`; shown in Contact
   AND openable as its own menu item.
7. **Projects becomes a submenu**: selecting Projects lists the projects;
   selecting one opens its repo link (same #2 behavior); a *← Back* entry
   returns to the main menu.

Non-interactive subcommands (`about`, `projects --tag`, `resume --open`,
`contact`, `blog`) are unchanged (one-shot; the press-again-for-URL behavior is
interactive-menu only).

## Architecture — testable to the 100%/zero-pragma bar

The interactive menu is rewritten from a `questionary.select` loop to a thin
**custom prompt_toolkit menu** (in the questionary/prompt_toolkit family — NOT
Textual, per the maintainer's stated preference). Split into two layers so the
zero-pragma/100%-branch bar holds:

- **Logic layer (`tui.run`)** — keeps injected, side-effect-free seams so it is
  driven by a fake prompt in tests (mirroring the current injectable `select`):
  - The collaborator seam changes from `select(message, choices) -> str|None`
    to `prompt(message, items, default_index) -> (item, moved)` where `item` is
    the selected menu item (or `None` to quit) and `moved: bool` is whether the
    highlight moved during that prompt invocation. (`moved` is exactly what #2
    needs: a fresh prompt starts at the armed item; if the user pressed enter
    without arrowing, `moved` is False → print URL; if they arrowed away/back,
    `moved` is True → re-open.)
  - `open_url` and `console` remain injected.
  - `run` holds the arming state machine, section rendering, the Demos
    enabled/disabled/named logic, cursor persistence (passes the last selected
    index as `default_index`), and the Projects submenu (a recursive prompt
    loop over project items + Back). All of this is covered via an injected
    `prompt` returning scripted `(item, moved)` tuples — no real terminal.
- **Prompt layer (`_default_prompt`)** — the real prompt_toolkit `Application`:
  renders items with a pointer (disabled items dimmed/unselectable), key
  bindings: ↑/↓ move the pointer (skipping disabled, setting a `moved` flag),
  Enter accepts a non-disabled item (Enter on a disabled item is ignored),
  `q`/Ctrl-C/Ctrl-D return `None`. No "(Use arrow keys)" text. Covered by
  dedicated **pipe-input tests** (`create_pipe_input` + `DummyOutput` +
  `create_app_session`, feeding `\x1b[A`/`\x1b[B`/`\r`/`q`), asserting the
  returned `(item, moved)`, disabled-skip, and quit paths.

### Arming state machine (the #2 core — a small, pure decision)
State: `armed` = the item id we last opened a browser for (or `None`).
On each selected `item` (with its `moved` flag):
- **link item** (Blog/Twitter/project URL): if `item.id == armed and not moved`
  → print the URL (keep `armed`); else → open browser, print the hint, set
  `armed = item.id`.
- **section** (About/Contact/Résumé): render the section panel (armed unchanged
  — harmless; `moved`/id-mismatch already prevents a wrong URL print).
- **submenu** (Projects): run the submenu loop (its own local arming for
  project links); Back returns.
- **demos**: if enabled (new demos) → render the named list; if disabled →
  unreachable (Enter ignored at the prompt layer).
- **quit / None**: return.
This decision is factored as a pure helper so its branches are unit-tested
directly, independent of the prompt.

## Data / content changes (#5, #6)
- `content.Links` gains `twitter: str` (sentinel `""` = not configured, mirroring
  `blog`). `_parse_profile` adds `"twitter"` to the links allowed/required keys;
  built via `_opt`. New `render.twitter_url(profile)` helper (like `blog_url`).
- `render.contact` adds a `Twitter:  <url>` line (when set) alongside Email/GitHub.
- `card.schema.json` `profile.links`: add `twitter` to `required` + `properties`
  (`{"type":"string"}`, like `blog`). The drift property + every card fixture +
  the contact render test update accordingly.
- `web/data/card.json`: `links.blog = "https://substack.com/@d0rb"`,
  `links.twitter = "https://x.com/henrycstllo"`.

## Menu items after the change
About (section) · Projects (submenu) · Résumé (section) · Contact (section) ·
Blog (link) · Twitter (link) · Demos (disabled when empty / named when new
demos) · Quit. Banner still printed once.

## Testing / gate (unchanged bar)
- Logic-layer tests via injected `prompt`: the arming truth table (first-open →
  hint; stay+enter → URL; move-away-and-back → re-open; different item → open),
  section render, submenu navigation + Back + project-link open, Demos
  disabled-vs-named, cursor persistence (default_index threaded), Quit/None.
- Prompt-layer pipe-input tests: navigation sets `moved`, Enter selects, Enter
  on disabled ignored, `q`/Ctrl-C/Ctrl-D quit, no instruction text.
- Data tests: schema `twitter` required + drift agreement; contact renders
  Twitter; web card validates; markup-safety on twitter/blog strings.
- Exactly 100% line+branch, zero `# pragma: no cover` in `src/`, ruff/ruff-format
  /ty/pre-commit(+check-jsonschema)/dependency-age/uv-lock, Python 3.10-safe,
  all 13 CI checks green. If `questionary` becomes unused after the rewrite,
  remove it from `[project.dependencies]` + `uv.lock`; otherwise keep it.

## Delivery
Additional conventional commits on `milestone-2-cli` / PR #3 (unmerged).
Per-task two-stage reviews + corrective loops + a capstone, then push, all CI
green, then real smoke. Spec + plan untracked.
