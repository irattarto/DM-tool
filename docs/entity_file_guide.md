# Entity File Guide

An entity file holds only entries: NPCs, factions, locations, items, quests, events and sessions. It has no module page. You can write one by hand, or let another program generate it, and bring it in with **File > Import Entities...**. This guide is also in the program: **Help > Guides**, tab "Entity file".

## 1. Quick start

1. Click **Save example as...** below and choose Markdown.
2. Change the names and texts, keep the `## Type: Title {#id}` lines.
3. **File > Import Entities...**, choose the file, check the preview, choose where the entries go, click Import.

You can import the same file again after you change it: new entries are added, changed ones are updated, and entries you edited in the program since are left alone unless you tick them.

## 2. Where entries go: campaign and modules

Every entry belongs to the campaign you import into. On top of that an entry can belong to **no module, one module or several modules**. The import preview asks:

- **the modules named in the file** (the `modules:` lines, see section 5),
- **one module I choose**,
- **a new module** with the name you type,
- **none**.

Modules are adventure modules of the campaign; the **Scope** button in the top bar and the **Module** box of each list filter by them.

## 3. File layout (Markdown)

```
---
format: dm-entities
pack: raton-pass-npcs
modules: [Raton Pass]
---
## NPC: Big Boss {#c-boss}
faction: Iron Guild
tags: Human, Strong

The text of the entry.
```

- The part between the two `---` lines is the **front matter**. It is optional, but `pack:` is strongly recommended.
- Each entry starts with a line `## Type: Title {#id}`.
- Directly under that line come the **property lines** (`key: value`), then an empty line, then the text. The first line that is not a property ends the properties.
- A `##` line whose type word is not known is just part of the text of the entry above it. Use `###` or deeper for your own headings.
- Text may use normal Markdown: bold, lists, tables, images from the web, links.

## 4. Types

Write the type word as in the program, in any letter case: `NPC`, `Faction`, `Location`, `Item`, `Quest`, `Event`, `Session`, `Character`, `Setting`. Types you added yourself work too (use their name).

## 5. Properties

| Property | For | Meaning |
|---|---|---|
| `faction` | NPC, Character | Name of a faction: one in the file, or one that exists in the campaign. A faction that exists nowhere is created at the import (you can switch that off in the preview). |
| `race` and any other `key: value` | any | Kept as a line `Key: value` at the top of the text (the lists read `Race:` from it). |
| `located_in` | Location | Name of the place this place is inside: a street in a district, a district in a city. One in the file or in the campaign. |
| `tags` | any | Comma separated words. |
| `image` | any | Picture path, relative to the file (`images/boss.jpg`). It becomes the main picture. Only .jpg, .png and .webp inside the file's folder. |
| `modules` | any | Modules of this entry (added to those in the front matter). |
| `date` | Session | `YYYY-MM-DD`. Today if missing. |
| `status` | Session | `planned`, `active` or `played`. |
| `participants` | Session | Comma separated names. |

## 6. Ids, packs and importing again

`{#c-boss}` is the entry's **id**. Choose short ids without spaces (letters, digits, `-`, `_`, `.`). The **pack** is the name of the file (`pack:` in the front matter, otherwise the file name). The program remembers `pack + id`, so:

- two files may both contain `{#c-boss}` without clashing, as long as their packs differ;
- importing the file again updates the same entries instead of creating copies;
- an entry **without an id** is matched by type and title. If an entry with that title already exists and was made by hand, the preview shows it as "exists - overwrite?" and leaves it unticked.

## 7. Links between entries

- `[text](#id)` links to the entry with that id in the same file.
- `[[Title]]` or `[[Title|shown text]]` links to any entry by title: one in the file or one already in the campaign.
- A link whose target does not exist becomes plain text.

Links become real links in the program. They also fill the **Mentioned in** list of each entry and the cast of each session.

## 8. JSON and HTML

- **JSON**: `{"format": "dm-entities", "pack": "...", "modules": [...], "entities": [{"type": "npc", "id": "c-boss", "title": "Big Boss", "faction": "...", "content": "..."}]}`. The same properties as in section 5 are keys of the entry. Use **Save example as...** and choose JSON.
- **HTML cards**: the card format of the HTML module guide (Help > Guides, tab "HTML module"). A file without a module page also works. Its cards are imported as entries; its title is offered as the name of a new module.
- A JSON file with `"format": "dm-module"` is read like an HTML module.

## 9. What the warnings mean

- *No entries found*: no line looked like `## NPC: Name`. Check the `##` and the colon.
- *The id is used twice*: the second entry was skipped. Give it another id.
- *Date / status not valid*: the value was replaced by the default.
- *Picture not found*: the file is not next to the entry file, or it is not a .jpg, .png or .webp.

## 10. Exporting entries

**File > Export Entities...** saves entries as an entity file that this program (or another campaign) imports again. In a list, select rows (Ctrl+click, Shift+click) and use File > Export Entities..., or right-click them and choose **Export as entity file...**; with nothing selected the whole open list is exported. Choose Markdown (`.md`) or JSON (`.json`).

- The file has the format of this guide: `pack`, one `## Type: Title {#id}` block per entry, with faction, tags, modules and, for sessions, date, status and participants.
- Links between exported entries become `[text](#id)` links; links to entries that were not exported become plain text.
- The main picture of each entry is copied to an `images` folder next to the file.
- Importing the file into the **same** campaign finds the entries by title and lists them as "exists - overwrite?", so nothing is duplicated.

## 11. For other programs (generators)

Write UTF-8 text. Always write `format: dm-entities`, a `pack` that is stable for your generator, and a stable id for every entry; then importing again updates instead of duplicating. The program never needs the file again after the import.
