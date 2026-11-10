"""Keep the shipped UI accessible and compatible with the settings contract."""
from html.parser import HTMLParser
from pathlib import Path
from openanchor.settings import Settings


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = {}
        self.labels = set()
        self.controls = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if 'id' in attrs:
            assert attrs['id'] not in self.ids, f"Duplicate ID: {attrs['id']}"
            self.ids[attrs['id']] = attrs
        if tag == 'label' and 'for' in attrs:
            self.labels.add(attrs['for'])
        if tag in {'input', 'select', 'textarea'}:
            self.controls.append(attrs)


def test_page_labels_and_descriptions():
    page = Page()
    page.feed(Path('openanchor/page.html').read_text(encoding='utf-8'))
    for control in page.controls:
        assert control['id'] in page.labels
        for reference in control.get('aria-describedby', '').split():
            assert reference in page.ids
    assert page.ids['errors']['tabindex'] == '-1'
    assert page.ids['errors']['role'] == 'alert'
    assert page.ids['status']['aria-live'] == 'polite'


def test_numeric_fields_match_engine_settings():
    page = Page()
    page.feed(Path('openanchor/page.html').read_text(encoding='utf-8'))
    settings = Settings()
    for control in page.controls:
        if control.get('type') == 'number':
            value = float(control['value'])
            assert value == getattr(settings, control['id'])
            assert float(control['min']) <= value <= float(control['max'])
            assert control.get('aria-describedby'), 'Every dimension needs accessible units'


def test_advanced_mode_has_boolean_control_and_serialization():
    html=Path('openanchor/page.html').read_text(encoding='utf-8')
    page=Page();page.feed(html)
    assert page.ids['advanced_anchor']['type']=='checkbox'
    assert 'checked' not in page.ids['advanced_anchor']
    for name in ('beam_width','beam_spacing','beam_model_gap'):
        assert name in page.ids and name in page.labels
