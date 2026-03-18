# RailTrack - Railway Track Geometry Design System

Production-grade MVP for designing railway track geometry with validation against ST-T1-A6 rules.

## Features

### Geometry Engine
- **Horizontal alignment**: Straights, circular arcs, clothoid transition curves
- **Vertical profile**: Constant grades, parabolic vertical curves
- **Cant (superelevation)**: Automatic generation, linear ramps, equilibrium/deficiency calculations
- **Tangency enforcement**: Automatic propagation ensuring geometric continuity
- **S-T-C-T-S builder**: Standard straight-transition-curve-transition-straight pattern

### Validation (ST-T1-A6 Rule Engine)
- Configurable rules in YAML (no code changes needed to update limits)
- Speed-category-based checks (40-250 km/h)
- Checks: tangency breaks, radius limits, transition lengths, cant limits, gradient limits, element sequence, chainage continuity
- Detailed issue reports with severity, code, expected/actual values, and suggestions

### Import/Export
- **CSV/TXT**: Survey points, horizontal elements with column mapping
- **XLSX**: Full alignment data import/export
- **DXF**: True geometric export (LINE for straights, ARC for arcs, polyline for clothoids)
- **LandXML 1.2**: Standard exchange format with Line/Curve/Spiral elements
- **HTML**: Validation report with color-coded issue table

### Desktop UI (PySide6)
- Project tree with alignment hierarchy
- Element table with add/remove controls
- Interactive plan view (pyqtgraph) with color-coded element types
- Vertical profile + cant diagram
- Validation panel with sortable issue list
- Properties panel showing alignment info and design criteria
- Full menu: project management, export, validation

## Quick Start

```bash
# Install dependencies
pip install numpy scipy PySide6 pyqtgraph ezdxf pandas openpyxl lxml pyyaml jinja2

# Run the desktop application
python -m railtrack

# Run sample project (generates all export formats)
python examples/create_sample_project.py

# Run tests
python -m pytest railtrack/tests/ -v
```

## Project Structure

```
railtrack/
├── domain/                  # Domain model
│   ├── primitives.py        # Point2D, Point3D, ChainageRange
│   ├── horizontal.py        # Straight, CircularArc, TransitionCurve
│   ├── vertical.py          # VerticalGrade, VerticalCurve
│   ├── cant.py              # CantSegment, CantRamp, equilibrium_cant
│   ├── turnout.py           # Turnout data model
│   ├── alignment.py         # Alignment, Project, DesignCriteria
│   └── validation_types.py  # ValidationIssue, Severity
├── geometry_engine/         # Computation engine
│   ├── horizontal_engine.py # Propagation, tangency, SCS builder
│   ├── vertical_engine.py   # Vertical propagation, profiles
│   └── cant_engine.py       # Cant generation, profiles
├── validation/              # Rule-based validation
│   ├── rule_loader.py       # YAML rule loader
│   └── validator.py         # AlignmentValidator with 10+ check types
├── importers/               # Data import
│   ├── csv_importer.py
│   ├── xlsx_importer.py
│   └── landxml_importer.py
├── exporters/               # Data export
│   ├── csv_exporter.py
│   ├── xlsx_exporter.py
│   ├── dxf_exporter.py
│   ├── landxml_exporter.py
│   └── html_report.py
├── application/             # Application layer
│   └── project_manager.py   # Project coordination, save/load
├── config/                  # Configuration
│   └── rules_st_t1_a6.yaml # ST-T1-A6 design rules
├── ui/                      # PySide6 desktop UI
│   ├── main_window.py
│   ├── widgets/
│   │   ├── element_table.py
│   │   ├── project_tree.py
│   │   ├── properties_panel.py
│   │   └── validation_panel.py
│   └── views/
│       ├── plan_view.py
│       └── profile_view.py
└── tests/                   # Test suite (58 tests)
    ├── unit/
    │   ├── test_primitives.py
    │   ├── test_horizontal.py
    │   ├── test_vertical.py
    │   ├── test_cant.py
    │   └── test_validation.py
    └── integration/
        └── test_export_import.py
```

## Architecture Decisions

- **True railway geometry**: Circular arcs are real arcs, clothoids are numerically integrated Euler spirals. No spline substitution.
- **Configurable rules**: ST-T1-A6 parameters in YAML. Change limits without touching code.
- **Clean layer separation**: Domain → Engine → Validation → Application → UI
- **Survey coordinate system**: x=easting, y=northing, azimuths from north CW

## Roadmap

The following features are architecturally prepared but not yet fully implemented:

1. **Advanced turnouts**: Full geometric modelling of switch components (data model ready)
2. **Rail profiles**: Cross-section geometry
3. **Clearance gauge**: Structure gauge checking
4. **Drainage**: Track drainage design
5. **Extended CAD/BIM export**: IFC, further DXF layers
6. **Undo/redo**: Command pattern for edit operations
7. **Multi-alignment coordination**: Cross-referencing between alignments
