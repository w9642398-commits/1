using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.Civil.ApplicationServices;
using Autodesk.Civil.DatabaseServices;
using CivilAI.Core.Contracts;
using CivilAI.Core.Models;
using CivilAI.Core.Telemetry;

namespace CivilAI.Plugin.Services;

public sealed class AutodeskCadContextProvider : ICadContextProvider
{
    private readonly ILogSink _logSink;

    public AutodeskCadContextProvider(ILogSink logSink)
    {
        _logSink = logSink;
    }

    public Task<DrawingContextSnapshot> GetActiveDocumentContextAsync(CancellationToken cancellationToken)
    {
        var document = Application.DocumentManager.MdiActiveDocument ?? throw new InvalidOperationException("No active AutoCAD document.");
        using var documentLock = document.LockDocument();
        var db = document.Database;
        var editor = document.Editor;

        using var transaction = db.TransactionManager.StartOpenCloseTransaction();
        var viewport = editor.GetCurrentView();
        var layerTable = (LayerTable)transaction.GetObject(db.LayerTableId, OpenMode.ForRead);
        var layers = layerTable.Cast<ObjectId>()
            .Select(id => (LayerTableRecord)transaction.GetObject(id, OpenMode.ForRead))
            .Select(layer => new LayerSnapshot(layer.Name, layer.IsLocked, layer.IsFrozen, layer.IsOff, layer.Color.ColorIndex))
            .OrderBy(layer => layer.Name)
            .ToArray();

        var selection = BuildSelectionSnapshot(editor, transaction);
        var visible = QueryVisibleEntities(transaction, db.CurrentSpaceId, 250);
        var civilObjects = QueryCivilObjectsInternal(transaction);

        var snapshot = new DrawingContextSnapshot(
            document.Name,
            db.Filename,
            db.Insunits.ToString(),
            db.TileMode ? "Model" : "Paper",
            ((LayerTableRecord)transaction.GetObject(db.Clayer, OpenMode.ForRead)).Name,
            new ViewportSnapshot(viewport.CenterPoint.X, viewport.CenterPoint.Y, viewport.Width, viewport.Height, viewport.CustomScale),
            layers,
            Array.Empty<string>(),
            selection,
            visible,
            civilObjects,
            null,
            DateTimeOffset.UtcNow);

        return Task.FromResult(snapshot);
    }

    public Task<SelectionSnapshot> GetCurrentSelectionAsync(CancellationToken cancellationToken)
    {
        var document = Application.DocumentManager.MdiActiveDocument ?? throw new InvalidOperationException("No active AutoCAD document.");
        using var documentLock = document.LockDocument();
        using var transaction = document.Database.TransactionManager.StartOpenCloseTransaction();
        return Task.FromResult(BuildSelectionSnapshot(document.Editor, transaction));
    }

    public Task<IReadOnlyList<EntitySnapshot>> GetVisibleEntitiesAsync(CancellationToken cancellationToken)
    {
        var document = Application.DocumentManager.MdiActiveDocument ?? throw new InvalidOperationException("No active AutoCAD document.");
        using var documentLock = document.LockDocument();
        using var transaction = document.Database.TransactionManager.StartOpenCloseTransaction();
        return Task.FromResult<IReadOnlyList<EntitySnapshot>>(QueryVisibleEntities(transaction, document.Database.CurrentSpaceId, 250));
    }

    public Task<IReadOnlyList<EntitySnapshot>> QueryEntitiesByTypeAsync(string typeName, CancellationToken cancellationToken)
    {
        return Task.FromResult<IReadOnlyList<EntitySnapshot>>(QueryEntities(entity => entity.GetType().Name.Equals(typeName, StringComparison.OrdinalIgnoreCase)));
    }

    public Task<IReadOnlyList<EntitySnapshot>> QueryEntitiesByLayerAsync(string layerName, CancellationToken cancellationToken)
    {
        return Task.FromResult<IReadOnlyList<EntitySnapshot>>(QueryEntities(entity => entity.Layer.Equals(layerName, StringComparison.OrdinalIgnoreCase)));
    }

    public Task<IReadOnlyList<CivilObjectSnapshot>> QueryCivilObjectsAsync(string category, CancellationToken cancellationToken)
    {
        var all = QueryCivilObjectsInternal(null);
        return Task.FromResult<IReadOnlyList<CivilObjectSnapshot>>(all.Where(x => x.Kind.Contains(category, StringComparison.OrdinalIgnoreCase)).ToArray());
    }

    private static SelectionSnapshot BuildSelectionSnapshot(Editor editor, Transaction transaction)
    {
        var selection = editor.SelectImplied();
        if (selection.Status != PromptStatus.OK)
        {
            return new SelectionSnapshot(Array.Empty<EntitySnapshot>(), "current selection");
        }

        var entities = selection.Value.GetObjectIds()
            .Select(id => transaction.GetObject(id, OpenMode.ForRead, false) as Entity)
            .Where(entity => entity is not null)
            .Select(entity => ToSnapshot(entity!))
            .ToArray();
        return new SelectionSnapshot(entities, "current selection");
    }

    private static IReadOnlyList<EntitySnapshot> QueryVisibleEntities(Transaction transaction, ObjectId currentSpaceId, int maxCount)
    {
        var btr = (BlockTableRecord)transaction.GetObject(currentSpaceId, OpenMode.ForRead);
        return btr.Cast<ObjectId>()
            .Take(maxCount)
            .Select(id => transaction.GetObject(id, OpenMode.ForRead, false) as Entity)
            .Where(entity => entity is not null)
            .Select(entity => ToSnapshot(entity!))
            .ToArray();
    }

    private static IReadOnlyList<EntitySnapshot> QueryEntities(Func<Entity, bool> predicate)
    {
        var document = Application.DocumentManager.MdiActiveDocument ?? throw new InvalidOperationException("No active AutoCAD document.");
        using var documentLock = document.LockDocument();
        using var transaction = document.Database.TransactionManager.StartOpenCloseTransaction();
        var currentSpace = (BlockTableRecord)transaction.GetObject(document.Database.CurrentSpaceId, OpenMode.ForRead);
        return currentSpace.Cast<ObjectId>()
            .Select(id => transaction.GetObject(id, OpenMode.ForRead, false) as Entity)
            .Where(entity => entity is not null && predicate(entity))
            .Select(entity => ToSnapshot(entity!))
            .ToArray();
    }

    private static IReadOnlyList<CivilObjectSnapshot> QueryCivilObjectsInternal(Transaction? existingTransaction)
    {
        var document = Application.DocumentManager.MdiActiveDocument ?? throw new InvalidOperationException("No active AutoCAD document.");
        var civilDocument = CivilApplication.ActiveDocument;
        Transaction? ownedTransaction = null;
        try
        {
            var transaction = existingTransaction ?? (ownedTransaction = document.Database.TransactionManager.StartOpenCloseTransaction());
            var alignments = civilDocument.GetAlignmentIds()
                .Cast<ObjectId>()
                .Select(id => transaction.GetObject(id, OpenMode.ForRead) as Alignment)
                .Where(alignment => alignment is not null)
                .Select(alignment => new CivilObjectSnapshot(alignment!.Handle.ToString(), "Alignment", alignment.Name, new Dictionary<string, string?>
                {
                    ["Length"] = alignment.Length.ToString("F3"),
                    ["Style"] = alignment.StyleName
                }));

            var surfaces = civilDocument.GetSurfaceIds()
                .Cast<ObjectId>()
                .Select(id => transaction.GetObject(id, OpenMode.ForRead) as TinSurface)
                .Where(surface => surface is not null)
                .Select(surface => new CivilObjectSnapshot(surface!.Handle.ToString(), "TinSurface", surface.Name, new Dictionary<string, string?>
                {
                    ["Triangles"] = surface.TrianglesCount.ToString(),
                    ["Style"] = surface.StyleName
                }));

            return alignments.Concat(surfaces).ToArray();
        }
        finally
        {
            ownedTransaction?.Dispose();
        }
    }

    private static EntitySnapshot ToSnapshot(Entity entity) => new(
        entity.Handle.ToString(),
        entity.GetType().Name,
        entity.Layer,
        entity.GetRXClass().Name,
        entity.GetType().FullName,
        new Dictionary<string, string?>
        {
            ["ColorIndex"] = entity.ColorIndex.ToString(),
            ["Linetype"] = entity.Linetype,
            ["Visible"] = entity.Visible.ToString()
        },
        entity.IsFromExternalReference,
        entity.IsWriteEnabled is false && entity.LayerId.IsValid);
}
