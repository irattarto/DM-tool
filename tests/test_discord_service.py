"""Discord REST client against a local fake Discord server."""
import asyncio
import json

import pytest
from aiohttp import web

from services import discord_service as ds
from services.discord_service import (DiscordClient, DiscordAuthError, DiscordPermissionError,
                                      DiscordNotFoundError, DiscordFileTooLargeError, DiscordRateLimitError,
                                      DiscordNetworkError, DiscordError)

TOKEN = "MTIzNDU2Nzg5MDEyMzQ1Njc4.Gabcde.abcdefghijklmnopqrstuvwxyz0123456789"


class FakeDiscord:
    def __init__(self):
        self.messages = []          # (channel_id, payload dict, attachments list of (filename, bytes))
        self.fail_with = {}         # channel_id -> status
        self.rate_limits_left = 0
        self.auth_headers = []

    def app(self):
        app = web.Application()
        r = app.router
        r.add_get('/api/v10/users/@me', self.me)
        r.add_get('/api/v10/users/@me/guilds', self.guilds)
        r.add_get('/api/v10/guilds/{gid}/channels', self.channels)
        r.add_post('/api/v10/channels/{cid}/messages', self.post_message)
        return app

    def _check(self, request):
        self.auth_headers.append(request.headers.get('Authorization'))
        if request.headers.get('Authorization') != f"Bot {TOKEN}":
            return web.json_response({'message': '401: Unauthorized'}, status=401)

    async def me(self, request):
        return self._check(request) or web.json_response({'id': '1', 'username': 'RollBot'})

    async def guilds(self, request):
        return self._check(request) or web.json_response([{'id': '100000000000000010', 'name': 'My Campaign'}])

    async def channels(self, request):
        bad = self._check(request)
        if bad:
            return bad
        return web.json_response([
            {'id': '100000000000000022', 'name': 'rolls', 'type': 0, 'position': 2},
            {'id': '100000000000000021', 'name': 'handouts', 'type': 0, 'position': 1},
            {'id': '100000000000000023', 'name': 'Voice', 'type': 2, 'position': 0},
            {'id': '100000000000000024', 'name': 'Category', 'type': 4, 'position': 0},
            {'id': '100000000000000025', 'name': 'news', 'type': 5, 'position': 3},
        ])

    async def post_message(self, request):
        bad = self._check(request)
        if bad:
            return bad
        cid = request.match_info['cid']
        if self.rate_limits_left > 0:
            self.rate_limits_left -= 1
            return web.json_response({'message': 'You are being rate limited.', 'retry_after': 0.01}, status=429)
        if cid in self.fail_with:
            return web.json_response({'message': 'nope'}, status=self.fail_with[cid])
        attachments = []
        if request.content_type.startswith('multipart/'):
            payload = {}
            async for part in await request.multipart():
                body = await part.read()
                if part.name == 'payload_json':
                    payload = json.loads(body)
                else:
                    attachments.append((part.filename, body))
        else:
            payload = await request.json()
        self.messages.append((cid, payload, attachments))
        return web.json_response({'id': str(len(self.messages))})


async def _with_server(fake, coro_factory):
    runner = web.AppRunner(fake.app())
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        return await coro_factory(f"http://127.0.0.1:{port}/api/v10")
    finally:
        await runner.cleanup()


def run(fake, factory):
    return asyncio.run(_with_server(fake, factory))


async def _no_sleep(_seconds):
    return None


# --- pure helpers ----------------------------------------------------------
def test_split_message_prefers_paragraph_and_respects_limit():
    text = ("a" * 900 + "\n\n" + "b" * 900 + "\n\n" + "c" * 900)
    chunks = ds.split_message(text, 2000)
    assert [len(c) for c in chunks] == [1802, 900]
    assert all(len(c) <= 2000 for c in chunks)
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_split_message_handles_one_huge_word_and_empty_input():
    assert ds.split_message("") == [] and ds.split_message("   ") == []
    chunks = ds.split_message("x" * 4500, 2000)
    assert [len(c) for c in chunks] == [2000, 2000, 500]


def test_clean_text_strips_html_and_control_characters_but_keeps_markdown():
    assert ds.clean_text("<p>Hello <b>**world**</b></p>\x00\x07") == "Hello **world**"


def test_caption_is_the_name_only():
    assert ds.build_caption("  Aria the Bold ") == "Aria the Bold"


@pytest.mark.parametrize("bad", ["", "   ", "short", "has space in the token 123456789012345"])
def test_validate_token_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        ds.validate_token(bad)


def test_validate_token_accepts_pasted_bot_prefix():
    assert ds.validate_token("Bot " + TOKEN + "\n") == TOKEN


def test_prepare_image_rejects_non_images_and_shrinks_big_ones(tmp_path):
    text = tmp_path / "notes.txt"
    text.write_text("x")
    with pytest.raises(DiscordError):
        ds.prepare_image(str(text))

    from PIL import Image
    import os
    big = tmp_path / "big.png"
    Image.frombytes('RGB', (900, 900), os.urandom(900 * 900 * 3)).save(big)  # incompressible noise
    assert big.stat().st_size > 1_000_000
    name, data, content_type = ds.prepare_image(str(big), max_bytes=300_000)
    assert len(data) <= 300_000 and name == "big.jpg" and content_type == "image/jpeg"


# --- against the fake server ---------------------------------------------------
def test_queries_return_servers_and_only_text_channels_in_order():
    fake = FakeDiscord()

    async def go(base):
        client = DiscordClient(TOKEN, base_url=base)
        assert (await client.get_me())['username'] == 'RollBot'
        assert await client.list_guilds() == [{'id': '100000000000000010', 'name': 'My Campaign'}]
        return await client.list_text_channels('100000000000000010')

    channels = run(fake, go)
    assert [(c.id, c.name) for c in channels] == [('100000000000000021', 'handouts'), ('100000000000000022', 'rolls'), ('100000000000000025', 'news')]
    assert set(fake.auth_headers) == {f"Bot {TOKEN}"}


def test_send_text_splits_and_suppresses_mentions():
    fake = FakeDiscord()

    async def go(base):
        return await DiscordClient(TOKEN, base_url=base).send_text('100000000000000021', "@everyone " + "word " * 700)

    count = run(fake, go)
    assert count == 2 and len(fake.messages) == 2
    for cid, payload, attachments in fake.messages:
        assert cid == '100000000000000021' and payload['allowed_mentions'] == {'parse': []}
        assert len(payload['content']) <= 2000 and not attachments


def test_send_image_uploads_the_real_file_with_the_name_as_caption(tmp_path):
    from PIL import Image
    path = tmp_path / "aria.png"
    Image.new('RGB', (20, 20), (200, 30, 30)).save(path)
    fake = FakeDiscord()

    async def go(base):
        await DiscordClient(TOKEN, base_url=base).send_image('100000000000000022', str(path), "Aria the Bold")

    run(fake, go)
    cid, payload, attachments = fake.messages[0]
    assert cid == '100000000000000022' and payload['content'] == "Aria the Bold"
    assert payload['allowed_mentions'] == {'parse': []}
    assert attachments[0][0] == "aria.png" and attachments[0][1] == path.read_bytes()


@pytest.mark.parametrize("status, error", [(403, DiscordPermissionError), (404, DiscordNotFoundError),
                                           (413, DiscordFileTooLargeError)])
def test_http_errors_become_plain_messages(status, error):
    fake = FakeDiscord()
    fake.fail_with['100000000000000021'] = status

    async def go(base):
        await DiscordClient(TOKEN, base_url=base).send_text('100000000000000021', "hi")

    with pytest.raises(error):
        run(fake, go)


def test_wrong_token_is_reported_without_leaking_it():
    fake = FakeDiscord()

    async def go(base):
        await DiscordClient("X" * 60, base_url=base).get_me()

    with pytest.raises(DiscordAuthError) as info:
        run(fake, go)
    assert "X" * 60 not in str(info.value)


def test_rate_limit_is_retried_then_succeeds():
    fake = FakeDiscord()
    fake.rate_limits_left = 2

    async def go(base):
        return await DiscordClient(TOKEN, base_url=base, sleep=_no_sleep).send_text('100000000000000021', "hi")

    assert run(fake, go) == 1
    assert len(fake.messages) == 1


def test_persistent_rate_limit_gives_up_with_a_clear_error():
    fake = FakeDiscord()
    fake.rate_limits_left = 99

    async def go(base):
        await DiscordClient(TOKEN, base_url=base, sleep=_no_sleep).send_text('100000000000000021', "hi")

    with pytest.raises(DiscordRateLimitError):
        run(fake, go)


def test_unreachable_server_is_a_network_error():
    async def go():
        await DiscordClient(TOKEN, base_url="http://127.0.0.1:9/api/v10").get_me()

    with pytest.raises(DiscordNetworkError):
        asyncio.run(go())


# --- embed cards -----------------------------------------------------------
def test_embed_title_and_text_are_cleaned_and_limited():
    assert ds.build_embed_title("<b>Aria</b> the Bold") == "Aria the Bold"
    assert len(ds.build_embed_title("x" * 500)) == ds.EMBED_TITLE_LIMIT
    assert ds.build_embed_text(["Aria", "Bram"]) == "Aria, Bram"
    assert len(ds.build_embed_text(["y" * 900] * 5)) <= ds.MESSAGE_LIMIT


def test_batch_embeds_respects_card_count_and_total_size():
    entry = lambda n, size: (f"n{n}", "a.png", b"x" * size, "image/png")
    assert [len(b) for b in ds.batch_embeds([entry(i, 1) for i in range(25)])] == [10, 10, 5]
    assert [len(b) for b in ds.batch_embeds([entry(i, 6) for i in range(3)], max_bytes=10)] == [1, 1, 1]
    assert [len(b) for b in ds.batch_embeds([entry(i, 4) for i in range(5)], max_bytes=10)] == [2, 2, 1]
    assert ds.batch_embeds([]) == []


def test_send_embeds_posts_cards_with_name_titles_and_attachments(tmp_path):
    from PIL import Image
    paths = []
    for i in range(12):
        path = tmp_path / f"p{i}.png"
        Image.new("RGB", (8, 8), "red").save(path)
        paths.append(str(path))
    fake = FakeDiscord()
    sent = []

    async def go(base):
        client = DiscordClient(TOKEN, base_url=base)
        entries = [(f"NPC {i} @everyone", p) for i, p in enumerate(paths)]
        return await client.send_embeds("100000000000000022", entries, on_batch_sent=sent.append)

    assert run(fake, go) == 2
    assert sent == [10, 2]
    (_, first, files), (_, second, files2) = fake.messages
    assert len(first['embeds']) == 10 and len(second['embeds']) == 2 and len(files) == 10 and len(files2) == 2
    assert first['embeds'][0] == {'title': 'NPC 0 @everyone', 'image': {'url': 'attachment://npc0.png'}}
    assert first['allowed_mentions'] == {'parse': []}
    assert files[0][0] == 'npc0.png' and first['attachments'][0] == {'id': 0, 'filename': 'npc0.png'}
    assert first['content'].startswith("NPC 0 @everyone, NPC 1")


def test_send_embeds_with_nothing_is_an_error():
    async def go(base):
        await DiscordClient(TOKEN, base_url=base).send_embeds("100000000000000022", [])

    with pytest.raises(DiscordError):
        run(FakeDiscord(), go)
