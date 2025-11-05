"""Verifiziert das gebrandete HTML-Template des Emailers."""

from __future__ import annotations

from agents.emailer import _render_structured_email
from agents.schemas import ReportData
from models.report_payload import (
    FAQItem,
    NarrativeSection,
    ReportMeta,
    ReportPayload,
    ReportTOCEntry,
    ShoppingItem,
    ShoppingList,
    StepDetail,
    StepsSection,
    TimeCostRow,
    TimeCostSection,
)


def _sample_payload() -> ReportPayload:
    return ReportPayload(
        title="Projekt X",
        teaser="Motivierender Teaser für das Projekt.",
        meta=ReportMeta(difficulty="Anfänger", duration="10–12 h", budget="300–400 €", region="DE"),
        toc=[ReportTOCEntry(title="Vorbereitung", anchor="vorbereitung", level=2)],
        preparation=NarrativeSection(
            heading="Vorbereitung",
            paragraphs=["Arbeitsplatz freiräumen und Untergrund prüfen."],
            bullets=["PSA bereitlegen", "Werkzeuge sortieren"],
            note=None,
        ),
        shopping_list=ShoppingList(
            heading="Einkaufsliste (Bauhaus-Links)",
            intro="Alle Produkte geprüft.",
            items=[
                ShoppingItem(
                    position=1,
                    category="Material",
                    product="MDF Platte",
                    quantity="2 Stück",
                    rationale="Zuschneiden für Regalböden",
                    price="ca. 45 €",
                    url="https://www.bauhaus.info/p/abc",
                ),
                ShoppingItem(
                    position=2,
                    category="Schrauben",
                    product="Spanplattenschrauben",
                    quantity="1 Pack",
                    rationale="Montage",
                    price="ca. 9,95 €",
                    url="https://www.bauhaus.info/p/def",
                ),
            ],
            empty_hint="Keine geprüften Bauhaus-Produkte verfügbar.",
        ),
        step_by_step=StepsSection(
            heading="Schritt-für-Schritt",
            steps=[
                StepDetail(
                    title="Untergrund vorbereiten",
                    bullets=["Lose Teile entfernen", "Fläche schleifen"],
                    check="Untergrund sauber und glatt",
                    tip="Staub mit leicht feuchtem Tuch aufnehmen.",
                    warning=None,
                ),
                StepDetail(
                    title="Regalkorpus montieren",
                    bullets=["Seitenwände verschrauben", "Böden einsetzen"],
                    check="Korpus im rechten Winkel",
                    tip=None,
                    warning="Nicht überdrehen, um Holz zu schützen.",
                ),
            ],
        ),
        quality_safety=NarrativeSection(
            heading="Qualität & Sicherheit",
            paragraphs=["PSA tragen und Arbeitsplatz lüften."],
            bullets=["Schutzbrille nutzen", "Gehörschutz bereitlegen"],
            note=None,
        ),
        time_cost=TimeCostSection(
            heading="Zeit & Kosten",
            rows=[
                TimeCostRow(work_package="Vorbereitung", duration="2 h", cost="30 €", buffer="0.5 h"),
                TimeCostRow(work_package="Montage", duration="3 h", cost="120 €", buffer="40 €"),
            ],
            summary="Plane zusätzlich einen Sicherheitspuffer ein.",
        ),
        options_upgrades=None,
        maintenance=None,
        faq=[
            FAQItem(question="Wie lange dauert das Projekt?", answer="Etwa ein Wochenende."),
            FAQItem(question="Brauche ich Spezialwerkzeug?", answer="Nein, Standardwerkzeug reicht."),
            FAQItem(question="Kann ich das Holz lackieren?", answer="Ja, nach gründlicher Reinigung."),
            FAQItem(question="Welche Schrauben eignen sich?", answer="Spanplattenschrauben mit Senkkopf."),
            FAQItem(question="Wie sichere ich den Korpus?", answer="Mit Winkeln an der Wand verankern."),
        ],
        followups=[
            "Als Nächstes: Materiallieferung terminieren",
            "Als Nächstes: Werkzeug-Check durchführen",
            "Als Nächstes: Arbeitsbereich abkleben",
            "Als Nächstes: Probemontage planen",
        ],
        search_summary="Fokus auf robusten Innenausbau und sichere Verschraubung.",
    )


def _sample_report() -> ReportData:
    payload = _sample_payload()
    return ReportData(
        short_summary="Zusammenfassung",
        markdown_report="# Platzhalter",
        followup_questions=payload.followups,
        payload=payload,
    )


def test_email_branding_contains_header_toC_and_styling() -> None:
    report = _sample_report()
    html, subject, meta = _render_structured_email(report, report.payload, brand=None, meta_override=None)

    assert "class=\"brand-header\"" in html
    assert "Home Task AI" in html
    assert "max-width: 720px" in html
    assert "class=\"button-primary\"" in html
    assert "#0f766e" in html
    assert html.count("https://www.bauhaus") >= 2
    assert "mail.google.com" not in html
    assert '<a id="vorbereitung"' in html
    assert subject.startswith("Projekt X")
    assert "10–12 h" in subject
    assert "300–400 €" in subject
    assert meta.get("level") == "Anfänger"

