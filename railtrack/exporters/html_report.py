"""HTML validation report exporter."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Template

from railtrack.domain.alignment import Alignment
from railtrack.domain.validation_types import ValidationIssue

_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<title>RailTrack - Raport walidacji: {{ alignment_name }}</title>
<style>
body { font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #f5f5f5; }
h1 { color: #1a237e; }
h2 { color: #283593; border-bottom: 2px solid #c5cae9; padding-bottom: 5px; }
table { border-collapse: collapse; width: 100%; margin-bottom: 20px; background: white; }
th { background: #3f51b5; color: white; padding: 10px; text-align: left; }
td { padding: 8px 10px; border-bottom: 1px solid #e0e0e0; }
tr:hover { background: #e8eaf6; }
.error { color: #c62828; font-weight: bold; }
.warning { color: #f57f17; font-weight: bold; }
.info { color: #1565c0; }
.summary { display: flex; gap: 20px; margin-bottom: 20px; }
.summary-card { padding: 15px 25px; border-radius: 8px; color: white; font-size: 1.2em; }
.card-error { background: #c62828; }
.card-warning { background: #f57f17; }
.card-info { background: #1565c0; }
.card-ok { background: #2e7d32; }
.meta { color: #666; margin-bottom: 20px; }
</style>
</head>
<body>
<h1>RailTrack - Raport walidacji</h1>
<p class="meta">Oś: <strong>{{ alignment_name }}</strong> | Długość: {{ total_length }} m | Elementy: {{ element_count }}</p>

<div class="summary">
{% if error_count == 0 and warning_count == 0 %}
<div class="summary-card card-ok">Brak problemów</div>
{% endif %}
{% if error_count > 0 %}
<div class="summary-card card-error">Błędy: {{ error_count }}</div>
{% endif %}
{% if warning_count > 0 %}
<div class="summary-card card-warning">Ostrzeżenia: {{ warning_count }}</div>
{% endif %}
{% if info_count > 0 %}
<div class="summary-card card-info">Informacje: {{ info_count }}</div>
{% endif %}
</div>

{% if issues %}
<h2>Lista problemów</h2>
<table>
<tr>
  <th>Ważność</th>
  <th>Kod</th>
  <th>Tytuł</th>
  <th>Opis</th>
  <th>Kilometraż</th>
  <th>Oczekiwane</th>
  <th>Rzeczywiste</th>
  <th>Sugestia</th>
</tr>
{% for issue in issues %}
<tr>
  <td class="{{ issue.severity.value }}">{{ issue.severity.value | upper }}</td>
  <td>{{ issue.code }}</td>
  <td>{{ issue.title }}</td>
  <td>{{ issue.message }}</td>
  <td>{{ issue.chainage_display }}</td>
  <td>{{ issue.expected_value }}</td>
  <td>{{ issue.actual_value }}</td>
  <td>{{ issue.suggestion }}</td>
</tr>
{% endfor %}
</table>
{% endif %}

<h2>Elementy geometrii poziomej</h2>
<table>
<tr><th>#</th><th>Typ</th><th>Km pocz.</th><th>Km końc.</th><th>Długość</th><th>Promień</th></tr>
{% for elem in h_elements %}
<tr>
  <td>{{ loop.index0 }}</td>
  <td>{{ elem.element_type.value }}</td>
  <td>{{ "%.3f"|format(elem.start_chainage) }}</td>
  <td>{{ "%.3f"|format(elem.end_chainage) }}</td>
  <td>{{ "%.3f"|format(elem.length) }}</td>
  <td>{{ elem.radius_display }}</td>
</tr>
{% endfor %}
</table>

<p class="meta">Wygenerowano przez RailTrack v0.1.0</p>
</body>
</html>
""")


class _ElemProxy:
    """Proxy for template rendering with radius_display."""
    def __init__(self, elem):
        self._elem = elem

    def __getattr__(self, name):
        if name == "radius_display":
            r = self._elem.radius_at(self._elem.start_chainage)
            import math
            if math.isinf(r):
                return "∞"
            return f"{r:.1f}"
        return getattr(self._elem, name)


def export_validation_html(
    alignment: Alignment,
    issues: list[ValidationIssue],
    path: Path | str,
) -> None:
    """Export validation report as HTML."""
    error_count = sum(1 for i in issues if i.severity.value == "error")
    warning_count = sum(1 for i in issues if i.severity.value == "warning")
    info_count = sum(1 for i in issues if i.severity.value == "info")

    h_elements = [_ElemProxy(e) for e in alignment.horizontal_elements]

    html = _TEMPLATE.render(
        alignment_name=alignment.name,
        total_length=f"{alignment.total_length:.1f}",
        element_count=len(alignment.horizontal_elements),
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        issues=issues,
        h_elements=h_elements,
    )

    Path(path).write_text(html, encoding="utf-8")
