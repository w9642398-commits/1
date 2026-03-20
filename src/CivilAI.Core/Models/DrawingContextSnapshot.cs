namespace CivilAI.Core.Models;

public sealed record DrawingContextSnapshot(
    string DocumentName,
    string DatabasePath,
    string Units,
    string ActiveSpace,
    string CurrentLayer,
    ViewportSnapshot Viewport,
    IReadOnlyList<LayerSnapshot> Layers,
    IReadOnlyList<string> Styles,
    SelectionSnapshot Selection,
    IReadOnlyList<EntitySnapshot> VisibleEntities,
    IReadOnlyList<CivilObjectSnapshot> CivilObjects,
    string? ScreenshotBase64,
    DateTimeOffset CapturedAtUtc)
{
    public string ToCompactSummary(int maxEntities = 25)
    {
        var entitySummary = string.Join(", ", VisibleEntities.Take(maxEntities).Select(e => $"{e.Kind}:{e.Handle}@{e.Layer}"));
        var selectionSummary = Selection.Entities.Count == 0
            ? "no selection"
            : string.Join(", ", Selection.Entities.Select(e => $"{e.Kind}:{e.Handle}"));

        return $"doc={DocumentName}; units={Units}; layer={CurrentLayer}; space={ActiveSpace}; selection={selectionSummary}; visible={entitySummary}; civil={CivilObjects.Count}";
    }
}

public sealed record ViewportSnapshot(double CenterX, double CenterY, double Width, double Height, double Scale);
public sealed record LayerSnapshot(string Name, bool IsLocked, bool IsFrozen, bool IsOff, int ColorIndex);
public sealed record SelectionSnapshot(IReadOnlyList<EntitySnapshot> Entities, string Scope);
public sealed record EntitySnapshot(string Handle, string Kind, string Layer, string? Name, string? Description, IReadOnlyDictionary<string, string?> Properties, bool IsFromExternalReference = false, bool IsLockedLayer = false);
public sealed record CivilObjectSnapshot(string Handle, string Kind, string Name, IReadOnlyDictionary<string, string?> Properties);
