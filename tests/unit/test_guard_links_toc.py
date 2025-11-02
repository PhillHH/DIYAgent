"""Tests fuer den Output-Guard bezueglich Links und ToC."""

from __future__ import annotations

from guards import llm_output_guard


def test_collect_static_checks_warns_external_toc_link() -> None:
    markdown = "## Inhaltsverzeichnis\n- [Extern](https://example.com)\n\n## Abschnitt"
    blockers, warnings = llm_output_guard._collect_static_checks(markdown)
    assert blockers == []
    assert any("Inhaltsverzeichnis" in issue for issue in warnings)


def test_collect_static_checks_warns_tracking_links() -> None:
    markdown = "[Produkt](https://www.bauhaus.info/item?utm_source=test)"
    blockers, warnings = llm_output_guard._collect_static_checks(markdown)
    assert blockers == []
    assert any("Tracking" in issue for issue in warnings)


def test_collect_static_checks_detects_mail_link() -> None:
    markdown = "[Test](https://mail.google.com/mail/u/0/#search/test)"
    blockers, warnings = llm_output_guard._collect_static_checks(markdown)
    assert any("mail.google.com" in issue.lower() for issue in blockers)
    assert warnings == []

