# Guards

## Zweck
- Stellt Eingabe- und Ausgabepruefungen fuer den DIY-Flow bereit.
- Verhindert fachfremde Anfragen bzw. nicht-DIY-konforme Berichte.

## Schnittstellen / Vertraege
- `validate_input(raw) -> (bool, str)` – trimmt und prueft leere Eingaben.
- `is_diy(query) -> bool` – Keyword-Heuristik fuer Heimwerkerbezug.
- `audit_output(text) -> (bool, str)` – Rueckgabewert `False` bei Guard-Verletzung.
- `validate_report(md) -> bool` – ermittelt, ob Markdown DIY-Schluesselwoerter enthaelt.

## Beispielablauf
1. `plan_searches` ruft `is_diy`, um fachfremde Queries direkt abzulehnen.
2. `write_report` prueft mit `validate_report`, ob der generierte Markdown DIY-Aspekte enthaelt.
3. `send_email` nutzt `validate_report`, bevor HTML versendet wird.

## Grenzen & Annahmen
- Heuristik basiert auf statischer Keyword-Liste → regelmaessig aktualisieren.
- Kann false positives bzw. negatives liefern; KI-Modelle sollen Guardrail-Hinweise ebenfalls beachten.

## Wartungshinweise
- Erweiterungen der Keyword-Listen sorgfaeltig pruefen (Tests ergaenzen).
- Bei komplexeren Anforderungen zukünftig mit regelbasierten oder modellgestuetzten Klassifikatoren kombinieren.
