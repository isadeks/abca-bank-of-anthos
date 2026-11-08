"""The home template labels the balance "Available Balance"."""
from pathlib import Path


def test_home_template_labels_available_balance():
    html = (Path(__file__).resolve().parent.parent / "templates" / "index.html").read_text()
    assert 'id="balance-label">Available Balance<' in html
