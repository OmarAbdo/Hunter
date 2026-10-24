from hunter.adapters.html_text import plain_text


def test_paragraphs_and_line_breaks_become_lines() -> None:
    assert plain_text("<p>Build the backend.</p><p>Ship it.<br>Daily.</p>") == (
        "Build the backend.\n\nShip it.\nDaily."
    )


def test_list_items_become_dashes() -> None:
    assert plain_text("<h3>You bring</h3><ul><li>Python</li><li>SQL</li></ul>") == (
        "You bring\n\n- Python\n- SQL"
    )


def test_entities_are_decoded_even_when_escaped_twice() -> None:
    assert plain_text("&lt;p&gt;Caf&amp;eacute; &amp;amp; Co&lt;/p&gt;") == "Café & Co"


def test_scripts_styles_and_extra_spaces_are_dropped() -> None:
    text = "<style>p {color: red}</style><p>  Remote   <b>first</b> </p><script>x()</script>"
    assert plain_text(text) == "Remote first"


def test_nothing_is_empty_text() -> None:
    assert plain_text("") == ""
    assert plain_text(None) == ""
