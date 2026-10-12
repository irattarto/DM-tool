"""Tab completion of entry names, name matching helpers, and the link graph."""
import pytest

from utils.name_matching import NameEntry, find_new_names, link_known_names, suggest

ENTRIES = [NameEntry("Mira Thornwood", "npc", 1), NameEntry("Mikael Dross", "npc", 2),
           NameEntry("Mirewood Gate", "location", 3), NameEntry("Iron Guild", "faction", 4),
           NameEntry("Éva Kovács", "npc", 5, priority=0)]


def test_suggest_needs_three_letters_and_a_word_end():
    assert suggest("Mi", ENTRIES) == (0, [])
    typed, found = suggest("The party meets Mir", ENTRIES)
    assert typed == 3 and [e.title for e in found] == ["Mirewood Gate", "Mira Thornwood"]      # shorter names first
    assert suggest("meets Mira ", ENTRIES) == (0, [])               # a space ends the word


def test_suggest_prefers_the_longest_typed_text_and_ignores_case_and_accents():
    typed, found = suggest("then Mira Th", ENTRIES)
    assert typed == len("Mira Th") and [e.title for e in found] == ["Mira Thornwood"]
    assert [e.title for e in suggest("eva", ENTRIES)[1]] == ["Éva Kovács"]
    typed, found = suggest("the thorn", ENTRIES)                    # later word of a name
    assert typed == 5 and [e.title for e in found] == ["Mira Thornwood"]


def test_priority_puts_pinned_entries_first():
    pinned = [NameEntry("Mirewood Gate", "location", 3, priority=0), NameEntry("Mira Thornwood", "npc", 1, priority=1)]
    assert [e.title for e in suggest("Mir", pinned)[1]] == ["Mirewood Gate", "Mira Thornwood"]


def test_known_names_become_links_but_links_stay():
    text = "Mira met Iron Guild men. See [Mira](rpg://npc/1) and Mikael Dross."
    out = link_known_names(text, ENTRIES)
    assert "[Iron Guild](rpg://faction/4)" in out and "[Mikael Dross](rpg://npc/2)" in out
    assert out.count("rpg://npc/1") == 1                            # the existing link was not touched, "Mira" alone is no name


def test_new_names_are_found_only_when_they_look_like_names():
    text = ("The party meets Brannoch Gale at dawn. Then they visit the Pale Court. Kaz waits. They ask Kaz about it. "
            "Monday was cold. Race: Elf. Later Iron Guild men come. See [Mira Thornwood](rpg://npc/1).")
    found = find_new_names(text, ["Iron Guild", "Mira Thornwood"])
    assert "Brannoch Gale" in found and "Pale Court" in found or "The Pale Court" in found
    assert "Kaz" in found                                           # inside a sentence ('meets Kaz')
    assert not {"Monday", "Race", "Iron Guild", "Mira Thornwood", "The", "Later"} & set(found)
    assert "Brannoch Gale" not in find_new_names(text, [], ignored=["brannoch gale"])


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtCore import QStandardPaths
    from PyQt6.QtWidgets import QApplication
    QStandardPaths.setTestModeEnabled(True)
    return QApplication.instance() or QApplication([])


def _edit(entries):
    from gui.widgets.formatted_text_edit import FormattedTextEdit
    edit = FormattedTextEdit()
    edit.completer.enabled = True
    edit.completer._entries = lambda: entries
    edit.show()
    return edit


def _type(edit, text):
    from PyQt6.QtTest import QTest
    QTest.keyClicks(edit, text)


def test_tab_accepts_a_single_suggestion_as_a_link(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    edit = _edit([NameEntry("Iron Guild", "faction", 4)])
    try:
        _type(edit, "The Iron Gu")
        assert edit.completer.active and edit.completer.current().title == "Iron Guild"
        QTest.keyClick(edit, Qt.Key.Key_Tab)
        assert "[Iron Guild](rpg://faction/4)" in edit.toMarkdown()
        _type(edit, " rules")
        assert "rules" in edit.toMarkdown() and "[Iron Guild rules]" not in edit.toMarkdown()   # typing goes on outside the link
    finally:
        edit.close()


def test_a_list_opens_for_several_matches_and_arrows_choose(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    edit = _edit(ENTRIES[:3])
    try:
        _type(edit, "meets Mir")
        assert edit.completer.popup.isVisible() and edit.completer.popup.count() == 2
        QTest.keyClick(edit, Qt.Key.Key_Down)
        assert edit.completer.current().title == "Mira Thornwood"
        QTest.keyClick(edit, Qt.Key.Key_Tab)
        assert "rpg://npc/1" in edit.toMarkdown() and not edit.completer.popup.isVisible()
    finally:
        edit.close()


def test_escape_ignores_and_tab_without_a_suggestion_works_as_usual(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    edit = _edit([NameEntry("Iron Guild", "faction", 4)])
    try:
        _type(edit, "Iron Gu")
        QTest.keyClick(edit, Qt.Key.Key_Escape)
        assert not edit.completer.active
        QTest.keyClick(edit, Qt.Key.Key_Tab)
        assert "rpg://" not in edit.toMarkdown()                    # Tab did not link anything
        edit.completer.enabled = False
        edit.clear()
        _type(edit, "Iron Gu")
        assert not edit.completer.active
    finally:
        edit.close()


def test_short_forms_of_existing_names_are_not_new_but_inflected_forms_too():
    known = ["Dr. Walter Abernaty", "Iron Guild"]
    text = "They meet Abernaty at noon. Walter Abernaty agrees. Later they thank Abernatyval and Walter. Then Brannoch Gale comes."
    assert find_new_names(text, known) == ["Brannoch Gale"]
    assert "Abernaty" in find_new_names(text, [])                      # without the entry it is a new name


def test_words_that_only_start_sentences_are_not_names():
    text = "Lásd a térképet. Lásd a jegyzetet. Meanwhile it rains. Meanwhile it stops. HP and DC are fine. They meet Kaz."
    assert find_new_names(text, []) == ["Kaz"]
    assert find_new_names("**Goal:** find Mira Thornwood.\n**Reward:** gold.", []) == ["Mira Thornwood"]
