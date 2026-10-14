# HTML adventure module format (importer reference)

`File > Import HTML Module...` reads the single-file HTML adventure modules written with the
Temple Dungeons toolchain. This page describes what the importer looks for, so the format can keep
evolving without breaking imports.

For people writing modules, the readable rules are in [html_module_guide.md](html_module_guide.md)
(also in the app: Help > Guides). This page is the importer reference for developers.

Check a file without opening the app:

```
python -m services.html_module_parser "path\to\Module.html"            # counts + warnings
python -m services.html_module_parser "path\to\Module.html" --export   # also writes module-export.json
```

## Terminology

| In the app | Meaning |
|---|---|
| **Campaign** | The top-level container you pick at startup (stored in the `modules` table; the name of the table is unchanged). |
| **Module** | An adventure inside a campaign. A `module` document is the backbone of an import. |
| **Session** | One sitting of play. A module has one or more sessions (one per scene on import). |

## What is created

* one **module** document with the introduction and all prose that is not an entity;
* one **session** per scene (`j-` id); a module without scenes gets a single placeholder session;
* **NPC, faction, location, item, event** documents;
* links in `document_relationships`: `belongs_to_module`, `appears_in_session`, `member_of`, `references`;
* `[text](#id)` cross references become `rpg://type/id` links in the notes.

Every imported document stores `module_doc_id` (its module) and `source_id` (its id in the HTML) in
its metadata. The entity lists show a **Module** column and a document window shows a module badge
and a **Connections** tab.

Re-importing matches on `source_id`: unchanged documents are skipped, changed ones are updated, and
documents you edited in the app since the last import are listed as "edited here" and are only
overwritten when you tick them in the preview.

## Id prefixes (the contract)

The importer recognises entities by the `id` of the element. Keep these prefixes stable and ids unique.

| Prefix | Becomes | Expected markup |
|---|---|---|
| `c-` | NPC | `details.npc-card` (also `vamp-card`, `werewolf-card`, ...) with `.npc-name`, optional `.npc-epithet`, `.tag`, `.card-body`; or a table row |
| `g-` | NPC (minor) | table row; first cell is the name, a `Courier` cell or a "prompt" column is the image prompt |
| `m-` | NPC (monster) | `details.creature-card` with `.npc-name` |
| `f-` | Faction | `div.card` with an `h4` title |
| `l-` | Location | `details.room` with an `h4` title |
| `item-`, `gift-`, `pw-` | Item | `details.card` / `div.card` with an `h4` title |
| `h-` | Item (handout) | `details.room` |
| `hook-` | Character (hook) | `div.hook-box`, optional `data-character="Name"` |
| `q-` | Quest | `details.card` / `div.card` with an `h4` title |
| `goal-` | Quest (subtype goal) | `details.card` / `div.card` with an `h4` title |
| `j-` | Session | `div.scene` with `.scene-no` and an `h4` title |

Other conventions used:

* `.imgprompt` inside `details.prompt-toggle` is the image prompt (kept as a note, optional);
* `a.xref[href="#id"]` is a cross reference; the first `f-` reference inside an NPC (or the NPC's
  `.tag` / `.npc-epithet` text naming a faction) sets the NPC's faction;
* `.toc` / `nav` links give readable section titles;
* `data-faction="f-id"` on an NPC card sets its faction explicitly (wins over the text heuristics);
* pictures: the main picture is the `<img>` whose `data-gen-id` equals the card id, else a
  `gen-portrait` / `gen-room` / `gen-creature` image, else the first image that is not `gen-item`;
  other pictures (belongings, `gen-item`) are attached as secondary images (caption "Gear"); fallback files are
  `images/{portraits,rooms,items,creatures}/<id>.jpg`; the `.imgprompt` that follows the main picture is its prompt;
* every NPC card carries a faction line `<div class="npc-faction" data-faction="...">` (also allowed: `data-faction` on the card, a `span.npc-faction` in a table-row cell, or a `#f-...` link in the line). The value is a faction id or `none`, `unknown`, `undecided`: `unknown`/`undecided` link nothing and add the tag `faction: unknown`/`faction: undecided`; all four states are preselected in the preview faction table and can be changed there;
* `data-count="N"` on a card (or row) marks one entry that stands for N identical extras; it gets the tag `×N`;
* `data-located-in="l-id"` on a location card sets its "Located in" (a `located_in` relationship); JSON `locatedIn`;
  an id that is not a location card of the module is a plan warning (`ImportPlan.warnings`);
* a card that no entry of this module has yet is matched to an existing campaign entry of the same type and
  title (casefold; npc, faction, location, item, quest, character; not scenes, sessions, gear, or `g-` cards with
  `data-count`). Choices `use` (default: text kept, `belongs_to_module` added, links and factions point to it),
  `overwrite` and `new`; saved on the module document as `metadata.linked_entries` (source id -> document id),
  which a re-import reads before matching titles. A used entry's import keys (`module_doc_id`, `source_id`,
  hashes) are never changed; its faction, "Located in" and picture are only filled in when it has none;
* each `li` of a `.gear` list on a `c-` card becomes an inventory item of that NPC (`inventory_item` document,
  metadata `parent_document_id`, source id `<npc id>#gear-N`); re-imports update the text but keep the type, quantity
  and equipped flag the user set;
* the preview offers a faction drop-down for NPCs left without a faction and an optional automatic
  "Unaffiliated" / "Monsters" faction (`f-auto-unaffiliated`, `f-auto-monsters`, created only when used);
* `<audio src>` becomes a `🔊 Audio: <path>` link to the file in the module folder (Ctrl+click opens it in the default player), an inline `<svg>` map becomes a "Map image" line plus a
  list of the `#l-` locations it links to (the audio/map files themselves are not copied);
* tables become markdown tables (a header row of `th` cells gets a separator); `.warn` becomes a quote in the module document.
* `tools/html_module/validate_module.py <file>` lists broken links, missing pictures and NPCs without faction.

Anything that is not an entity stays readable in the module document, grouped by `<section>`.

## `dm-module` JSON (optional)

If the HTML contains `<script type="application/json" id="dm-module-data">` or a
`module-export.json` sits next to the file, the importer uses that instead of scraping the markup
(`format: "dm-module"`, `formatVersion: 1`). Generate one with `--export` and edit it by hand when a new
module format is not recognised yet. Files with a newer `formatVersion` than the app supports are rejected.
