# Discord integration (planned feature)

Status: **version 1 implemented** (bot REST API). Not yet tried against a real Discord server; see "Manual test" below.

## Requirements (from the owner)

1. **Send images to Discord.** From a module's entities (NPCs, sessions, locations, items, ...) send one or
   more images to a Discord channel. The channel can be **selected at send time or preselected**.
   The **name of the entity is sent together with the picture** (the picture and its name stay linked,
   e.g. as the caption/title of the message).
2. **Send selected text to Discord** as a text message, again to a **preselected or selected channel**.
3. **Link every module to a specific Discord channel.** Each module has a default channel that is
   preselected whenever something is sent from that module.

## Decisions (owner, after the first draft)

- **Transport: use the bot that is already invited** (the dice-roll bot), through Discord's REST API only
  (no gateway connection, so it does not interfere with the running bot). Webhooks stay a possible fallback.
  Both webhooks and bots can post real image files; the bot is chosen because it needs no per-channel
  setup and can list the channels.
- **No session recap bundling.** Images are sent one by one on request.
- **Caption = the entity name only.**
- **Warn before sending anything.** Every send shows a preview and asks for confirmation; entities marked
  secret/DM-only get an extra, explicit warning.

## Design

### Transport: bot REST API
- `POST /channels/{channel_id}/messages` with `multipart/form-data`: `payload_json` (content/embeds,
  `allowed_mentions: {parse: []}`) plus `files[0]` (the image). Text-only messages are plain JSON.
- Channel picker: `GET /users/@me/guilds` then `GET /guilds/{id}/channels` (text channels only), cached
  per session. The default server is picked once in Settings; each campaign can link its own server and channel.
- Needs the bot permissions **View Channel, Send Messages, Attach Files** (and Embed Links if embeds are used)
  in the target channels. No privileged intents are needed for sending.
- Reusing the roll bot's token is simplest; a second bot (own token) limits the damage if the token leaks.
  Decision needed when building.

### Data model (schema v9)
- `app_meta` (existing) or a small `discord_settings` row: bot token (**encrypted with `SecureStorage`**, never
  in plain text, logs or backups), selected server (guild) id.
- `modules.discord_channel_id` (nullable text, the Discord channel snowflake) and
  `modules.discord_channel_name` (display name cached for the UI): the module's default channel.
- Backups keep the module's channel id/name but never the token.

### Where it appears in the UI
- **Settings > Discord**: bot token field (masked), "Test connection", server dropdown.
- **Campaign manager > Discord**: "Server" and "Channel" dropdowns (the campaign's own server and default channel; a campaign without a server uses the default one from Settings).
- **Image gallery**: "Send to Discord..." for the selected image(s): channel preselected from the module,
  changeable; preview; caption = entity name (not editable in v1).
- **Document viewer / text editors**: "Send selection to Discord..." with the same channel picker and preview.

### Message format
- Image: the file attached with the entity name as the message text (or embed title).
- Text: plain message, split on paragraph boundaries at 2000 characters; HTML stripped, Markdown kept.
- Mentions are suppressed so a pasted `@everyone`/role mention never pings anyone.

### Limits and safety
- Upload size limit (about 10 MB for most servers): the app checks it and offers to downscale.
- Rate limits: respect `429` / `Retry-After`, send multiple images sequentially.
- Runs on a worker thread (same pattern as the backup workers) with clear errors: bad token (401), missing
  permission (403), unknown channel (404), file too large (413), offline.
- Only images that belong to the module can be sent; no arbitrary file paths.

### Out of scope for v1
Reading messages, bot commands, two-way sync, scheduled posts, session recap bundling.

## Test plan
- Unit: message splitting, caption building, mention escaping, rate-limit queue, encrypted webhook storage,
  v8 -> v9 migration.
- Integration: a local fake Discord REST server (aiohttp test server) receives text and multipart image
  uploads and serves the guild/channel lists; error paths (401/403/404/413/429).
- GUI (offscreen): channel picker preselects the module channel; send dialog preview; settings editor rules.
- Manual: a real test server with the real bot before release.

## How to use it (version 1)

1. **Bot token.** In the Discord Developer Portal open your bot > Bot > *Reset Token* and copy it. Use the bot you
   already have (shared) or create a dedicated one; the app treats both the same. The bot must be in your
   server and have *View Channel, Send Messages, Attach Files* in the channels you post to.
2. **Preferences > Discord.** Paste the token, press *Connect and load servers*, choose the server, press OK.
   The token is stored encrypted (OS keyring protected) and is never shown again.
3. **Module channel.** Module manager > select a module > *Discord channel...* > pick the channel. It is
   preselected whenever you send something from that module.
4. **Send images.** In an entity's image gallery: right-click an image > *Send to Discord...*, or the
   *Send to Discord...* button to send all images of the entity. The caption is the entity name.
5. **Send text.** Select text in a document > right-click > *Send Selection to Discord...*.
6. Every send opens a preview that names the channel and server and asks for confirmation.

## Manual test (needs a real server)
- Connect with the real token, check the server and channel list.
- Send one image and one long text (more than 2000 characters) to a test channel; check caption, split and
  that `@everyone` in the text does not ping.
- Remove the bot's *Attach Files* permission and check the message ("The bot is not allowed to do that").
- Wrong token, deleted channel, and no network each show a plain message.

## Where the code is
`services/discord_service.py` (REST client), `services/discord_settings.py` (token/server storage),
`gui/dialogs/discord_send_dialog.py`, `discord_settings_widget.py`, `module_discord_channel_dialog.py`,
`gui/workers/discord_worker.py`, `gui/discord_actions.py`; schema v9 (`modules.discord_channel_id/name`).
Tests: `tests/test_discord_*.py` (a local fake Discord API stands in for the real one).
