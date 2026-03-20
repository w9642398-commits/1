# CivilAI for Autodesk Civil 3D 2026

Produkcyjna architektura i implementacja dodatku AI dla Autodesk Civil 3D 2026 / AutoCAD 2026, dostępnego jako własna karta Ribbon oraz dockowalna paleta robocza. Rozwiązanie nie pozwala modelowi bezpośrednio modyfikować DWG: model generuje wyłącznie plan i wywołania do kontrolowanego katalogu lokalnych narzędzi.

---

## ETAP 1 — Architektura, założenia, drzewo projektu, lista narzędzi

### Cele architektoniczne

- **Natywny host Civil 3D 2026**: biblioteka .NET ładowana przez `NETLOAD`, z bootstrapem `IExtensionApplication`, własną kartą Ribbon i `PaletteSet`.
- **Bezpieczny AI orchestration**: OpenAI Responses API odpowiada wyłącznie za planowanie; lokalny executor wykonuje operacje CAD/Civil 3D w transakcji.
- **Warstwowość i testowalność**: separacja hosta Autodesk od logiki planowania, walidacji, modeli i testów jednostkowych.
- **MVVM UI**: dockowalny panel z promptem, planem, historią, listą narzędzi, walidacją i raportem wykonania.
- **Production-ready operability**: logowanie JSONL, ustawienia per-user, DPAPI dla klucza API, tryb dry-run, pojedynczy undo scope i raport po wykonaniu.

### Założenia implementacyjne

1. **Host pluginu** targetuje `net8.0-windows` z WPF i wymaga lokalnej instalacji Civil 3D 2026 / AutoCAD 2026 SDK DLL (`AcMgd`, `AcDbMgd`, `AeccDbMgd`, `AdWindows`).
2. **Core** jest niezależny od Autodesk API i może być testowany bez Civil 3D.
3. **Responses API** jest obsługiwane przez `HttpClient`, z przygotowaną ścieżką na odpowiedzi synchroniczne i SSE streaming.
4. **Structured outputs** są wymuszane przez ścisły JSON schema planu (`civil_ai_operation_plan`).
5. **Tool registry** opisuje wszystkie narzędzia JSON schema + semantykę bezpieczeństwa; model może użyć tylko tych narzędzi.
6. **Pełne sterowanie Civil 3D** jest realizowane dwiema drogami: przez bezpieczne managed wrappers tam, gdzie API jest stabilne, oraz przez kontrolowany native command bridge dla funkcji dostępnych tylko jako komendy Civil 3D/AutoCAD.
7. **Operacje destrukcyjne** są oznaczone jako confirmation-gated. `EraseEntity` nigdy nie wykonuje się bez jawnej zgody lub polityki auto-execute.
8. **Nieobsługiwane workflow** nie są halucynowane: executor zwraca jawny błąd + alternatywny workflow, jeśli API/template workflow wymaga dodatkowej konfiguracji.
9. **Native command bridge** może kolejkować katalogowane lub jawnie dopuszczone makra Civil 3D, dzięki czemu system może sterować także funkcjami spoza bezpośrednich wrapperów .NET.

### Warstwy rozwiązania

- **CivilAI.Plugin**
  - bootstrap hosta AutoCAD/Civil 3D,
  - Ribbon (`AI Civil`),
  - `PaletteSet` z panelem WPF,
  - adaptery Autodesk API,
  - ustawienia i magazyn sekretów.
- **CivilAI.Core**
  - modele domenowe planu i wykonania,
  - klient OpenAI Responses API,
  - parser structured output,
  - walidacja bezpieczeństwa,
  - orkiestrator AI,
  - rejestr narzędzi.
- **CivilAI.Tests**
  - testy parsera planu,
  - testy walidacji bezpieczeństwa,
  - testy katalogu narzędzi,
  - scenariusze end-to-end dry-run.

### Pipeline wykonania

1. UI zbiera prompt i tryb (`DryRun` / `Execute`).
2. `ICadContextProvider` buduje zwięzły snapshot rysunku: dokument, jednostki, warstwy, selection, viewport, widoczne encje, obiekty Civil 3D.
3. `AssistantOrchestrator` buduje request do OpenAI Responses API z:
   - promptem użytkownika,
   - snapshotem technicznym,
   - listą dostępnych tools,
   - regułami bezpieczeństwa,
   - JSON schema planu.
4. Model zwraca **strict JSON plan**.
5. `PlanParser` materializuje plan, a `PlanValidator` odrzuca nieznane narzędzia, błędne JSON-y, niespójności bezpieczeństwa i niedozwolone mutacje.
6. UI prezentuje plan, kroki, walidację i listę potencjalnych zmian.
7. `ICadToolExecutor` wykonuje wyłącznie zatwierdzone kroki, transakcyjnie i z jednym logicznym undo scope.
8. Po wykonaniu powstaje `ExecutionReport` z logiem, listą zmodyfikowanych obiektów i walidacją post-execution.

### Drzewo projektu

```text
CivilAI.sln
├── src/
│   ├── CivilAI.Core/
│   │   ├── Contracts/
│   │   ├── Models/
│   │   ├── OpenAI/
│   │   ├── Planning/
│   │   ├── Runtime/
│   │   ├── Safety/
│   │   ├── Telemetry/
│   │   ├── Tools/
│   │   ├── Utilities/
│   │   └── CivilAI.Core.csproj
│   └── CivilAI.Plugin/
│       ├── Commands/
│       ├── Composition/
│       ├── Host/
│       ├── Ribbon/
│       ├── Services/
│       ├── UI/
│       │   ├── Controls/
│       │   ├── ViewModels/
│       │   └── Windows/
│       └── CivilAI.Plugin.csproj
├── tests/
│   └── CivilAI.Tests/
│       ├── EndToEndScenarioTests.cs
│       ├── PlanParserTests.cs
│       ├── PlanValidatorTests.cs
│       ├── ToolRegistryTests.cs
│       └── CivilAI.Tests.csproj
└── README.md
```

### Lista lokalnych narzędzi (tool registry)

#### AutoCAD / host tools
- `GetActiveDocumentContext`
- `GetCurrentSelection`
- `GetVisibleEntities`
- `QueryEntitiesByType`
- `QueryEntitiesByLayer`
- `QueryCivilObjects`
- `CreateLine`
- `CreatePolyline`
- `CreateArc`
- `CreateCircle`
- `CreateText`
- `CreateMText`
- `CreateBlockReference`
- `MoveEntity`
- `CopyEntity`
- `RotateEntity`
- `EraseEntity`
- `ChangeLayer`
- `SetProperties`
- `ZoomToObjects`
- `StartUndoScope`
- `CommitTransaction`
- `RollbackTransaction`

#### Civil 3D tools
- `CreateAlignmentFromPolyline`
- `CreateProfile`
- `CreateFeatureLine`
- `CreateSurfaceTin`
- `AddLabelsToAlignment`
- `AddLabelsToProfile`
- `QueryAlignmentGeometry`
- `QuerySurfaceInfo`
- `QueryProfileInfo`
- `QueryParcelInfo`
- `QueryPointGroups`
- `CreateOffsetAlignmentIfSupportedByWorkflow`
- `ExtractStationingData`
- `AnalyzeGeometryContinuity`
- `ListNativeCommands`
- `DescribeNativeCommand`
- `ExecuteNativeCommand`
- `ExecuteNativeCommandSequence`

#### Status implementacyjny
- **W pełni zaimplementowane w executorze**: podstawowe tworzenie/edycja obiektów AutoCAD, query, zoom, alignment from polyline, TIN from point group, query alignment/surface/point groups, analiza ciągłości.
- **Jawnie ograniczone / template-dependent**: profile, feature lines, alignment labels, profile labels, offset alignment. Zwracają kontrolowany błąd i alternatywę zamiast deklarować fałszywe wykonanie.
- **Pełne sterowanie funkcjami Civil 3D**: gdy nie istnieje bezpieczny wrapper managed API, AI może użyć `ExecuteNativeCommand` / `ExecuteNativeCommandSequence`, aby sterować natywnymi komendami Civil 3D w sposób audytowalny i objęty polityką potwierdzeń.

#### Macierz zgodności z promptem
- **Ribbon + dockowalna paleta** — wdrożone.
- **Prompt natural language + analiza kontekstu rysunku** — wdrożone.
- **Structured JSON plan + walidacja bezpieczeństwa** — wdrożone.
- **Dry run / execute / undo scope / rollback on failure** — wdrożone na poziomie orkiestratora i wykonawcy.
- **Streaming API do warstwy integracyjnej** — wdrożone w kliencie Responses API; pełny incremental UX streaming w panelu można dalej rozbudować.
- **Sterowanie wszystkimi funkcjami Civil 3D** — wdrożone przez połączenie managed tools + native command bridge z katalogiem komend i trybem uncataloged po jawnej zgodzie.
- **Screenshot aktywnego widoku jako dodatkowy kontekst** — przewidziane architektonicznie, ale wymaga dołożenia dedykowanego adaptera Autodesk do capture view.

---

## ETAP 2 — Implementacja plik po pliku

### Core

- `Contracts/ICadContextProvider.cs` — kontrakt dostarczający snapshot rysunku.
- `Contracts/ICadToolExecutor.cs` — brama wykonawcza dla lokalnych operacji CAD.
- `Contracts/ILogSink.cs`, `Contracts/ISecretStore.cs` — logi i bezpieczny storage sekretów.
- `Models/DrawingContextSnapshot.cs` — kompaktowy model stanu rysunku, selection i Civil objects.
- `Models/ExecutionModels.cs` — ustawienia, tryby wykonania, raporty i wynik narzędzia.
- `Models/PlanningModels.cs` — request planowania, `OperationPlan`, `PlanStep`.
- `Models/ToolDefinition.cs` — definicje narzędzi i JSON schema wejścia.
- `OpenAI/ResponsesApiClient.cs` — integracja z Responses API, także SSE streaming.
- `Planning/PlanJsonSchemaFactory.cs` — strict schema odpowiedzi modelu.
- `Planning/PlanParser.cs` — parser JSON → `OperationPlan`.
- `Safety/PlanValidator.cs` — walidacja bezpieczeństwa i kompletności planu.
- `Runtime/AssistantOrchestrator.cs` — pipeline planowania i wykonania.
- `Telemetry/LogEntry.cs` — ustrukturyzowany log planów i wywołań tools.
- `Tools/ToolRegistry.cs` — pełny katalog narzędzi z JSON schema.
- `Utilities/*` — infrastruktura MVVM (`ObservableObject`, `AsyncRelayCommand`).

### Plugin / host Autodesk

- `Host/CivilAiPluginEntry.cs` — entrypoint `IExtensionApplication`, bootstrap całego pluginu.
- `Composition/PluginCompositionRoot.cs` — składanie usług, orkiestratora, UI i hosta palety.
- `Commands/AICommands.cs` — komendy `CIVILAI_OPEN`, `CIVILAI_SETTINGS`.
- `Ribbon/RibbonBuilder.cs` + `RibbonCommandHandler.cs` — karta `AI Civil` na Ribbonie.
- `Services/PaletteHost.cs` — dockowalny `PaletteSet`.
- `Services/SettingsStore.cs` — ustawienia per-user w `%LOCALAPPDATA%\CivilAI2026`.
- `Services/WindowsCredentialManagerSecretStore.cs` — bezpieczne przechowywanie klucza API przez Windows DPAPI.
- `Services/FileLogSink.cs` — JSONL logi lokalne.
- `Services/AutodeskCadContextProvider.cs` — odczyt aktywnego dokumentu, warstw, selection, widocznych encji i Civil 3D summaries.
- `Services/AutodeskCadToolExecutor.cs` — kontrolowane, transakcyjne wykonanie lokalnych narzędzi.
- `UI/Controls/AssistantControl.xaml` — główny panel AI.
- `UI/ViewModels/AssistantViewModel.cs` — logika MVVM: prompt, analiza, dry run, execute, log, status, walidacja.
- `UI/Windows/SettingsWindow.xaml` — ustawienia OpenAI i polityk wykonania.

### Testy

- `PlanParserTests.cs` — poprawność parsera response planu.
- `PlanValidatorTests.cs` — walidacja destrukcyjnych i nieznanych narzędzi.
- `ToolRegistryTests.cs` — obecność wymaganych tools.
- `EndToEndScenarioTests.cs` — przykładowy dry-run alignment workflow.

---

## ETAP 3 — Instrukcja uruchomienia, integracja z OpenAI, scenariusze

### Wymagania środowiskowe

- Windows 11 / Windows 10
- Autodesk Civil 3D 2026
- Visual Studio 2022 17.10+
- .NET 8 SDK
- Civil 3D 2026 / AutoCAD 2026 managed SDK assemblies

### Konfiguracja build

1. Ustaw zmienną środowiskową `C3D_2026_SDK` na katalog zawierający:
   - `AcMgd.dll`
   - `AcDbMgd.dll`
   - `AcCoreMgd.dll`
   - `AeccDbMgd.dll`
   - `AeccPressurePipesMgd.dll`
   - `AdWindows.dll`
2. Otwórz `CivilAI.sln` w Visual Studio.
3. Zbuduj `Release | Any CPU`.
4. Skopiuj `CivilAI.Plugin.dll` do katalogu deploymentowego lub bezpośrednio `NETLOAD` w Civil 3D.

### Deploy do Civil 3D 2026

#### Opcja 1 — ręcznie
1. Uruchom Civil 3D 2026.
2. Wpisz `NETLOAD`.
3. Wskaż `CivilAI.Plugin.dll`.
4. Na Ribbonie pojawi się zakładka **AI Civil**.
5. Kliknij **Open Assistant** lub użyj komendy `CIVILAI_OPEN`.

#### Opcja 2 — AutoLoader package
W kolejnym kroku rozwoju można dołożyć `PackageContents.xml`, aby dystrybuować plugin jako pakiet AutoLoader do `%ProgramData%\Autodesk\ApplicationPlugins`.

### Integracja z OpenAI

1. Otwórz **Settings** z Ribbon lub komendą `CIVILAI_SETTINGS`.
2. Wprowadź **OpenAI API key**.
3. Ustaw model główny i routingowy.
4. Zapisz ustawienia.
5. Klucz jest przechowywany lokalnie, per-user, z użyciem **Windows DPAPI**, nie jest hardcodowany i nie trafia do kodu ani plików konfiguracyjnych w postaci jawnej.

### Zalecana konfiguracja modeli

- **Primary model**: najnowszy stabilny model flagowy zgodny z Responses API, np. `gpt-5`.
- **Routing / classification model**: mniejszy model klasy `gpt-5-mini` do intent classification lub szybkiego routingu.

### Przykładowe scenariusze użytkownika

#### AutoCAD workflows
- `Narysuj oś jako polilinię przez wskazane punkty na warstwie AI_AXIS.`
- `Dodaj tekst z nazwą profilu przy każdym końcu linii.`
- `Przenieś wszystkie okręgi z warstwy TEMP na warstwę C-TOPO.`
- `Przeanalizuj zaznaczenie i wskaż przerwy geometrii większe niż 2 mm.`

#### Civil 3D workflows
- `Utwórz alignment z zaznaczonej polilinii i nazwij go AI_Main_Axis.`
- `Z grupy punktów EG utwórz powierzchnię TIN o nazwie EG_AI.`
- `Pobierz geometrię alignmentu MAIN i pokaż stacjonowanie charakterystycznych punktów.`
- `Znajdź konflikty ciągłości na zaznaczonych krzywych i przygotuj plan naprawy.`

### Przebieg wykonania w UI

1. Użytkownik wpisuje prompt.
2. Klik **Dry Run** dla samego planu i preview.
3. Panel pokaże:
   - historię rozmowy,
   - plan krok po kroku,
   - walidację bezpieczeństwa,
   - listę narzędzi,
   - przewidywane obiekty docelowe.
4. Klik **Execute** po weryfikacji.
5. Plugin wykonuje plan w transakcji i raportuje zmienione obiekty.
6. Cofnięcie zmian odbywa się logicznie jako jedna grupa `UNDO`.

---

## ETAP 4 — Lista ryzyk i dalsze rozszerzenia

### Ryzyka techniczne

1. **Różnice środowisk Civil 3D** — style, label sets i site workflows są silnie zależne od template projektu.
2. **Warianty API Autodesk** — część operacji Civil 3D wymaga bardziej szczegółowego template-aware workflow niż da się bezpiecznie uogólnić.
3. **Koszt i latencja LLM** — duże snapshoty rysunku należy agresywnie kompresować i filtrować.
4. **Bezpieczeństwo operacji** — tryb auto-execute powinien być ograniczony polityką administratora lub profilem użytkownika.
5. **Obsługa screenshotów** — screenshot widoku może poprawić rozumienie kontekstu, ale wykonanie nadal musi opierać się na API i identyfikowalnych obiektach.

### Proponowane rozszerzenia

1. **AutoLoader packaging** z `PackageContents.xml` i installerem MSI.
2. **Streaming tokenów do UI** z live plan trace i incremental preview.
3. **Template/style resolvers** dla alignment/profile labels oraz feature lines.
4. **Advanced validators**: locked-layer policy, XREF policy, clash heuristics, tolerancje geometryczne per-standard.
5. **Rozszerzany katalog natywnych komend** z gotowymi makrami firmowymi i profilem bezpieczeństwa per-komenda.
5. **Screenshot capture service** dla kontekstu multimodalnego Responses API.
6. **Telemetry adapter** do Application Insights / OTLP / SIEM.
7. **Role-based safety policy**: projektant / checker / BIM manager.
8. **Undo/rollback UX** z automatycznym snapshotem identyfikatorów obiektów i raportem zmian przed/po.

---

## Dodatkowe uwagi wdrożeniowe

- Rozwiązanie zostało przygotowane tak, aby **Core** był rozwijany niezależnie od hosta Autodesk.
- Jeśli konkretna operacja Civil 3D nie jest bezpiecznie automatyzowalna bez znajomości standardu biura projektowego, executor zwraca **kontrolowany failure** z alternatywą, zamiast udawać sukces.
- To repozytorium zawiera kompletny foundation package dla produkcyjnego dodatku i jest gotowe do dalszego utwardzania pod konkretny standard deploymentu, template i polityki firmy.
