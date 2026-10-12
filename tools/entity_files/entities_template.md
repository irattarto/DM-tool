---
format: dm-entities
pack: raton-pass-example     # names this file; ids in two files never clash
modules: [Raton Pass]        # optional: the modules every entry below joins
---
## Faction: Iron Guild {#f-guild}
A guild of dockworkers and smugglers that runs the harbour.

## NPC: Big Boss {#c-boss}
race: Human
faction: Iron Guild
tags: Human, Strong
image: images/c-boss.jpg
modules: [Raton Pass, Docks of Despair]

Runs the guild from [the yard](#l-yard). He trusts nobody who has not [[Kaz the Quick]] vouched for.

## NPC: Kaz the Quick {#c-kaz}
race: Halfling
faction: Iron Guild

A courier who knows every back alley of the harbour.

## Location: The Yard {#l-yard}
modules: [Raton Pass]

A dusty yard behind the warehouse. [Big Boss](#c-boss) holds court here.

## Item: Iron Key {#item-key}
The key to the guild cellar.

## Quest: Find the cellar {#q-cellar}
Find the hidden cellar under the yard and the [Iron Key](#item-key) that opens it.

## Session: Arrival {#s-1}
date: 2026-10-12
status: planned
participants: Ana, Ben

The party arrives at [the yard](#l-yard) and meets [Big Boss](#c-boss).
