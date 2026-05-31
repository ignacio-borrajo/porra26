from django.template import Context, Template


def test_icon_renders_check():
    t = Template("{% load icons %}{% icon 'check' width=20 %}")
    out = t.render(Context({}))
    assert "<svg" in out
    assert 'width="20"' in out
