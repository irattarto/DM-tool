# HTML Module Guide

This guide explains how to write an adventure module as an HTML file that **RPG Database Manager** can import with **File > Import HTML Module...**. It is for people who write modules by hand and for scripts or AI tools that generate them.

The importer reads **element ids and a few class names**. Colours, fonts, scripts and layout are free, so the file can look however you like in a browser. A single `.html` file is enough. A module folder may also contain `images/`, `audio/` and a `module-export.json`.

In the app: **Help > Guides...** opens this guide. There you can also save this guide and a ready-made example module to any folder.

## 1. Quick start

1. In the guide window, click **Save example module as...** and save `module_template.html` into a new folder.
2. Open it in a text editor. Change the title (`h1`), the line above it (`.eyebrow`), and the texts of the cards.
3. Add your own cards by copying one. Give each card a **unique id** with the right prefix (see the table in section 2).
4. Put pictures in an `images/` folder next to the HTML file and refer to them with relative paths such as `images/portraits/c-boss.jpg`.
5. In the app, choose **File > Import HTML Module...** and pick the file.
6. Read the preview. Warnings tell you what to fix (see section 9). Then click **Import**.

You can import the same file again after changing it. Unchanged entries are skipped and changed ones are updated (section 10).

## 2. The id prefix decides what a card becomes

Every entry needs a **unique id** that starts with one of these prefixes. Ids are how the app recognises an entry when you import again and how links find their target, so **never rename an id** once you have imported the module.

| Prefix | Becomes | Markup |
|---|---|---|
| `c-` | NPC | `details.npc-card` (any `*-card` class works), or a table row |
| `g-` | NPC (minor) | table `tr` (first cell = name; a `Courier` cell or a column headed "prompt" = image prompt) |
| `m-` | NPC (monster) | `details.creature-card` |
| `f-` | Faction | `div.card` with an `h4` title |
| `l-` | Location | `details.room` with an `h4` title |
| `item-`, `gift-`, `pw-` | Item (normal, gift, spell) | `details.card` or `div.card` with an `h4` |
| `h-` | Item (handout) | `details.room` |
| `hook-` | Character (hook) | `div.hook-box`, optionally `data-character="Name"` (one per player character) |
| `j-` | Event (scene) | `div.scene` with `.scene-no` and `h4` |

Ids on `h2`, `h3`, `a` and `span` are only anchors for links. They do **not** create entries.

## 3. Page skeleton

| Element | Used for |
|---|---|
| `<html lang="hu">` | the language of the module |
| `.eyebrow` | a line `Rule system · Campaign · Part`; the text before the first `·` is the **rule system** |
| `h1` | the module title (the first one on the page) |
| `.sub` | subtitle or pitch |
| `.warn` | an optional notice, kept as a quote at the top of the module document |
| `.toc` or `nav` with `<a href="#section-id">` | readable section titles |
| `<section id="...">` with `.section-header h2` | one `## Heading` block of the module document per section |

Everything that is not an entry or a scene (prose, boxes, tables, lists, read-aloud text `.readaloud`) ends up in the **module document**, grouped by section (at most 60,000 characters per section).

## 4. Anatomy of a card

```html
<details class="npc-card" id="c-boss" data-faction="f-guild">
  <summary class="card-summary">
    <div class="npc-name">Big Boss</div>                 <!-- title (else first h4/h3/h2/strong, else the id) -->
    <div class="npc-epithet">The head of the guild</div> <!-- shown in italics at the top of the notes -->
    <div class="npc-meta"><span class="tag">Human</span><span class="badge b-strong">Strong</span></div>
  </summary>
  <div class="card-body"> ... paragraphs, lists, tables, <a class="xref" href="#l-yard">links</a> ... </div>
  <img class="gen-image gen-portrait" data-gen-id="c-boss" src="images/portraits/c-boss.jpg">
  <details class="prompt-toggle"><div class="imgprompt">image prompt text</div></details>
</details>
```

- **Tags** are the text of `.tag`, `.room-tag`, `.rank` and `.badge` inside the summary (a `span.badge` in the body of a card that is not a `details` counts too). They become the entry's tags and a `**Tags:**` line. The colour class of a badge (`b-ally`, `b-foe`, ...) is not interpreted, only its text.
- **Body** is `.card-body`. Without it, everything except `summary`, `h3` and `h4` is used.
- **Labelled fields**: `<div class="gear"><span class="lbl">Gear</span> ...</div>` becomes `**Gear:** ...` (the same for `.loot`, `.foes`, `.appearance`, `.haven-note`, `.disc-list`). They stay as text lines in the notes. In addition, each `<li>` of a `.gear` list on an NPC card becomes an **inventory item** of that NPC (title = the first `<b>`, text = the whole line, item type "misc"). Put one notable item per `<li>`. Common things (ammunition, a plain knife, food, money) may share one `<li>`. `.loot` on a location stays text, because locations have no inventory.
- **Read-aloud**: `.readaloud` becomes a quote block.
- **Tables** become real tables (use `<th>` cells in the first row for a header). Table rows with an id that starts with `c-` or `g-` become NPCs. Rows without an id stay text.
- **One card is one person.** Named or specific people (an escort, a bodyguard, a soldier with a role) each get their own card and id. Generic extras with no story role (thugs, minions) are **one** `g-` card with `data-count="N"`: in the app it is one minor NPC with the tag `×N`.

### Examples for the other entries

A faction, a location and an item:

```html
<div class="card" id="f-guild"><h4>Iron Guild</h4><p>Hires <a class="xref" href="#c-boss">the boss</a>.</p></div>

<details class="room" id="l-yard">
  <summary class="card-summary"><span class="room-tag">Town</span><h4>The Yard</h4></summary>
  <div class="card-body"><p>A dusty yard.</p></div>
</details>

<details class="card" id="item-key">
  <summary class="card-summary"><h4>Rusty Key</h4></summary>
  <div class="card-body"><p>Opens the cellar.</p></div>
</details>
```

A minor NPC as a table row, and a scene:

```html
<table>
  <tr><th>Name</th><th>Role</th></tr>
  <tr id="g-guard"><td>Gate guard</td><td>Watches the gate</td></tr>
</table>

<div class="scene" id="j-1"><span class="scene-no">1. scene · The Yard</span><h4>Arrival</h4>
  <p>The party arrives at <a class="xref" href="#l-yard">the yard</a>.</p></div>
```

## 5. Links

- `<a href="#c-boss">` (any entry id) becomes a link between the two entries and shows as a clickable link in the notes. Link only to ids that exist.
- Links to plain section anchors become links to the module document.
- External `http(s)` links are kept. Other relative links keep their text only.

## 6. Factions

**Every NPC, minor NPC and creature card should carry a visible faction line** with `data-faction`:

```html
<div class="npc-faction" data-faction="f-alfa">Faction: <a class="xref" href="#f-alfa">Alfa Company</a></div>
```

| `data-faction` | Meaning | At import |
|---|---|---|
| `f-xxx` | member of that faction card | linked, no question asked |
| `none` | deliberately in no faction | in the faction table, "(no faction)" preselected |
| `unknown` | the faction is not known (yet) | preselected "Unknown faction"; tag `faction: unknown`, nothing linked |
| `undecided` | the author has not decided yet | preselected "Undecided yet"; tag `faction: undecided`, nothing linked |

The line can also be a `span.npc-faction` in a table-row cell, or just a `data-faction` attribute on the card. A `#f-...` link inside the `.npc-faction` line names the faction when the attribute is missing. Older modules without the line still work: the importer looks for a `#f-...` link in the card, a faction name in the tags or epithet, or a faction card that links to the NPC.

The **faction table** in the import preview lists every NPC without a real faction. Hover over a name to read a short description. The drop-down offers the faction cards, "(no faction)", "Unknown faction", "Undecided yet", the automatic factions (if ticked) and **+ New faction...**. A faction set on an earlier import or by hand is kept and never asked again.

**Tip for authors:** make catch-all faction cards yourself (for example `f-independent` "Independents" and `f-monsters` "Monsters"), so nearly every NPC and creature belongs somewhere.

## 7. Scenes and sessions

`<div class="scene" id="j-1"><span class="scene-no">1. scene · Place</span><h4>Title</h4> ... </div>` becomes an **event** entry titled "1. Title". Entries nested inside the scene or linked from it are attached to it. The import creates one first session, and the preview lets you choose where the scene texts go (into that session, into an existing session, or nowhere).

## 8. Pictures, audio and maps

- **Pictures** live under `images/` next to the HTML file, as relative paths that stay inside the module folder. The main picture of a card is, in this order: the `<img>` with `data-gen-id="<card id>"`; an `<img>` with class `gen-portrait`, `gen-room` or `gen-creature`; the first `<img>` that is not `gen-item`; or the file `images/{portraits,rooms,items,creatures}/<id>.{jpg,jpeg,png,webp}`. It becomes the entry's primary picture.
- Other pictures of the card (for example `gen-item`, the belongings) are attached as **secondary pictures** (Images tab, caption "Gear" for `gen-item`).
- **Image prompt**: the `.imgprompt` that follows the main picture. It is stored in the notes only when "Import image prompts" is ticked in the preview.
- **Audio**: `<audio src="audio/x.mp3">` becomes a link to the file in the module folder. **Ctrl+click** it in a document to play it in your default audio player (after a confirmation; only existing local `.mp3 .wav .ogg .m4a .flac` files open). The file is not copied into the database, so keep the module folder where it is and import again if you move it. Put a short label before the player.
- **Maps**: an inline `<svg>` becomes a "Map image" line with the path of the `<image>` inside it, plus a list of the `#l-...` locations it links to. Keep the base picture as `<image href="images/maps/x.jpg">` inside the svg and wrap place labels in `<a href="#l-id">`. A `.svg-legend` of coloured spans is kept as a text legend. The drawing itself is not imported.

**What is ignored:** `<script>`, `<style>`, `<head>`, `<button>`, `<noscript>`, regenerate buttons and prompt toggles. CSS variables, colours and emoji icons are not imported.

## 9. What the import warnings mean

The import preview shows a summary line and warnings. Fix the HTML, save it and open the import again.

| Message | What it means and what to do |
|---|---|
| No entities or scenes found | Nothing in the file has an id with a recognised prefix. Check the table in section 2. |
| Duplicate id ignored: `c-boss` | The same id is used twice. Only the first is imported. Give every card its own id. |
| Entity without a title skipped: `c-x` | A card has no `.npc-name`, `h4` or other title. Add one. |
| `<file>.json` present but unreadable; used the HTML | The `module-export.json` next to the file is broken, so the HTML markup was used instead. Fix or delete the JSON file. |
| N NPCs have no faction | These NPCs are listed in the faction table of the preview. Choose a faction there, or add the `.npc-faction` line to the card. |
| N edited here and left alone unless you tick them | You changed these entries in the app since the last import. Tick them in the preview only if the file should overwrite your changes. |
| N unchanged with new or changed pictures | The text did not change but the pictures did. Only the pictures are updated. |

The preview does **not** warn about a missing picture: a card whose picture file cannot be found simply gets no picture. If a picture does not show up, check the path in `src` and the `images/` folder. The command-line check at the end of this guide lists missing pictures and unknown links.

Entries in the preview are marked **New**, **Update**, **Unchanged** or **Edited here - overwrite?**.

## 10. Importing again

You can import the same file again after you change it. The app matches entries by their id: unchanged entries are skipped, changed ones are updated, and entries you edited in the app are only overwritten when you tick them in the preview. Gear you changed (item type, quantity, equipped) is kept. A faction you chose by hand is kept. This is why ids must never change.

## 11. Alternative: a JSON data block

Instead of relying on the markup, a generator can write the data itself, either inside the page as `<script type="application/json" id="dm-module-data">` or as `<file>.module-export.json` (or `module-export.json`) next to the HTML. The importer prefers it over the markup. Format (`formatVersion` 1; a newer version is rejected):

```json
{ "format": "dm-module", "formatVersion": 1,
  "module":   { "key": "my-module", "title": "", "eyebrow": "", "subtitle": "", "ruleSystem": "", "language": "", "content": "markdown" },
  "sessions": [ { "id": "j-1", "title": "", "label": "", "content": "markdown", "refs": ["c-boss"] } ],
  "entities": [ { "id": "c-boss", "type": "npc", "subtype": "", "title": "", "content": "markdown",
                  "tags": [], "factionRef": "f-guild", "factionHint": "", "imagePrompt": "",
                  "image": "images/portraits/c-boss.jpg", "extraImages": [], "extraImageCaptions": {},
                  "noFaction": false, "gear": [ { "title": "Rusty key", "content": "markdown" } ], "refs": [] } ] }
```

`type` is `npc`, `faction`, `location`, `item`, `character` or `event`.

## 12. Known limits

- **Gear**: a `<li>` that lists several items joined by "·" becomes one inventory item (use one `<li>` per item). The item type is always "misc" and the quantity 1, because the HTML carries no such data. Change them in the app; a new import keeps your changes.
- **Gear scope**: only NPC cards (`c-`) and character hooks get inventory items.
- **Audio** is linked, not stored: the link points to the file in the module folder.
- **Maps** are kept as text. The drawing is not imported.
- **Extra pictures** are attached to their own card only. There is no separate item entry for them.
- **Automatic factions** (an option in the preview, off by default) use two fixed names per language ("Unaffiliated" and "Monsters"; Hungarian modules get Hungarian names; any other language gets the English names). The importer never guesses a real faction from the story text, so your `data-faction` is the reliable way.
- **Several NPCs on one card** (older modules) import as one NPC. Write one card per person.

## 13. Checklist

- [ ] One `h1`, an `.eyebrow` starting with the rule system, `<html lang>` set
- [ ] Every entry has a unique id with a recognised prefix and a title (`.npc-name` or `h4`)
- [ ] Every `href="#..."` points to an id that exists
- [ ] Every NPC, minor NPC and creature has the visible `.npc-faction` line (`f-...`, `none`, `unknown` or `undecided`), and the module has catch-all faction cards
- [ ] Gear is a `.gear` list with one `<li>` per item, the item name in `<b>`
- [ ] Every picture exists under `images/` and is referenced with a relative path; the main picture has `data-gen-id` equal to the card id
- [ ] Scenes are `div.scene` with `.scene-no` and `h4`
- [ ] The import preview shows no warnings you did not expect

## For developers: checking a file from the command line

With the source code (Python needed), a module can be checked without opening the app:

```
python -m services.html_module_parser "Module.html"            # counts and warnings
python -m services.html_module_parser "Module.html" --export   # also writes module-export.json
python tools/html_module/validate_module.py "Module.html"      # unknown links, missing pictures, NPCs without a faction
```

The importer reference for developers is `docs/html_module_format.md`.
