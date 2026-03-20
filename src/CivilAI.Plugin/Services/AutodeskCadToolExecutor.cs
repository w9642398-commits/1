using System.Collections.Concurrent;
using System.Text.Json;
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

public sealed class AutodeskCadToolExecutor : ICadToolExecutor
{
    private static readonly ConcurrentDictionary<string, CadExecutionScope> ActiveScopes = new(StringComparer.OrdinalIgnoreCase);
    private readonly ILogSink _logSink;
    private readonly NativeCommandCatalogService _nativeCommandCatalog;

    public AutodeskCadToolExecutor(ILogSink logSink, NativeCommandCatalogService nativeCommandCatalog)
    {
        _logSink = logSink;
        _nativeCommandCatalog = nativeCommandCatalog;
    }

    public Task BeginExecutionScopeAsync(ExecutionContext executionContext, CancellationToken cancellationToken)
    {
        if (executionContext.Mode == ExecutionMode.DryRun)
        {
            return Task.CompletedTask;
        }

        var doc = Application.DocumentManager.MdiActiveDocument ?? throw new InvalidOperationException("No active AutoCAD document.");
        var scope = ActiveScopes.GetOrAdd(executionContext.SessionId, _ =>
        {
            var docLock = doc.LockDocument();
            var transaction = doc.Database.TransactionManager.StartTransaction();
            doc.SendStringToExecute("._UNDO _GROUP ", true, false, false);
            return new CadExecutionScope(doc, docLock, transaction);
        });

        if (!ReferenceEquals(scope.Document, doc))
        {
            throw new InvalidOperationException("Execution scope was opened for a different active document.");
        }

        return Task.CompletedTask;
    }

    public async Task<ToolExecutionResult> ExecuteAsync(ToolInvocation invocation, ExecutionContext executionContext, CancellationToken cancellationToken)
    {
        var doc = Application.DocumentManager.MdiActiveDocument ?? throw new InvalidOperationException("No active AutoCAD document.");
        var useSharedScope = executionContext.Mode == ExecutionMode.Execute && !invocation.PreviewOnly;
        var sharedScope = useSharedScope ? GetRequiredScope(executionContext.SessionId) : null;

        if (sharedScope is not null)
        {
            var result = ExecuteInternal(doc, sharedScope.Transaction, invocation, executionContext);
            await _logSink.WriteAsync(LogEntry.ForToolResult(executionContext.SessionId, result), cancellationToken).ConfigureAwait(false);
            return result;
        }

        using var docLock = doc.LockDocument();
        using var transaction = doc.Database.TransactionManager.StartTransaction();
        var previewResult = ExecuteInternal(doc, transaction, invocation, executionContext);
        await _logSink.WriteAsync(LogEntry.ForToolResult(executionContext.SessionId, previewResult), cancellationToken).ConfigureAwait(false);
        return previewResult;
    }

    public Task CompleteExecutionScopeAsync(ExecutionContext executionContext, CancellationToken cancellationToken)
    {
        if (executionContext.Mode == ExecutionMode.DryRun)
        {
            return Task.CompletedTask;
        }

        if (ActiveScopes.TryRemove(executionContext.SessionId, out var scope))
        {
            try
            {
                scope.Transaction.Commit();
                scope.Document.SendStringToExecute("._UNDO _END ", true, false, false);
            }
            finally
            {
                scope.Dispose();
            }
        }

        return Task.CompletedTask;
    }

    public Task AbortExecutionScopeAsync(ExecutionContext executionContext, string reason, CancellationToken cancellationToken)
    {
        if (executionContext.Mode == ExecutionMode.DryRun)
        {
            return Task.CompletedTask;
        }

        if (ActiveScopes.TryRemove(executionContext.SessionId, out var scope))
        {
            try
            {
                scope.Transaction.Abort();
                scope.Document.SendStringToExecute("._UNDO _END ", true, false, false);
                scope.Document.Editor.WriteMessage($"\nCivilAI rollback: {reason}");
            }
            finally
            {
                scope.Dispose();
            }
        }

        return Task.CompletedTask;
    }

    private static CadExecutionScope GetRequiredScope(string sessionId)
    {
        if (!ActiveScopes.TryGetValue(sessionId, out var scope))
        {
            throw new InvalidOperationException("No active CAD execution scope exists for the current AI session.");
        }

        return scope;
    }

    private ToolExecutionResult ExecuteInternal(Document doc, Transaction transaction, ToolInvocation invocation, ExecutionContext executionContext) => invocation.ToolName switch
    {
        "GetActiveDocumentContext" => ToolExecutionResult.Failed(invocation.ToolName, "Context retrieval is served by ICadContextProvider and should not be executed as a mutating tool."),
        "GetCurrentSelection" => BuildSelectionResult(doc),
        "GetVisibleEntities" => BuildVisibleResult(doc, transaction),
        "QueryEntitiesByType" => QueryByType(doc, transaction, invocation.Arguments),
        "QueryEntitiesByLayer" => QueryByLayer(doc, transaction, invocation.Arguments),
        "QueryCivilObjects" => QueryCivilObjects(invocation.Arguments),
        "CreateLine" => CreateLine(doc, transaction, invocation),
        "CreatePolyline" => CreatePolyline(doc, transaction, invocation),
        "CreateArc" => CreateArc(doc, transaction, invocation),
        "CreateCircle" => CreateCircle(doc, transaction, invocation),
        "CreateText" => CreateText(doc, transaction, invocation, false),
        "CreateMText" => CreateText(doc, transaction, invocation, true),
        "CreateBlockReference" => CreateBlockReference(doc, transaction, invocation),
        "MoveEntity" => TransformEntity(doc, transaction, invocation, TransformKind.Move),
        "CopyEntity" => TransformEntity(doc, transaction, invocation, TransformKind.Copy),
        "RotateEntity" => RotateEntity(doc, transaction, invocation),
        "EraseEntity" => EraseEntity(doc, transaction, invocation, executionContext),
        "ChangeLayer" => ChangeLayer(doc, transaction, invocation),
        "SetProperties" => SetProperties(doc, transaction, invocation),
        "ZoomToObjects" => ZoomToObjects(doc, transaction, invocation),
        "StartUndoScope" => new ToolExecutionResult(invocation.ToolName, true, "Execution scope already opened by orchestrator.", Array.Empty<string>()),
        "CommitTransaction" => new ToolExecutionResult(invocation.ToolName, true, "Execution scope will be committed by orchestrator.", Array.Empty<string>()),
        "RollbackTransaction" => ToolExecutionResult.Failed(invocation.ToolName, invocation.Arguments.GetProperty("reason").GetString() ?? "Rollback requested by plan."),
        "CreateAlignmentFromPolyline" => CreateAlignmentFromPolyline(doc, transaction, invocation),
        "CreateProfile" => ControlledFailure(invocation.ToolName, "Profile creation requires a template-aware design profile workflow and cannot be safely generalized yet."),
        "CreateFeatureLine" => ControlledFailure(invocation.ToolName, "Feature line creation is template-dependent and should be resolved against the project style/site configuration first."),
        "CreateSurfaceTin" => CreateTinSurface(transaction, invocation),
        "AddLabelsToAlignment" => ControlledFailure(invocation.ToolName, "Alignment labeling requires template-specific label set resolution before automation."),
        "AddLabelsToProfile" => ControlledFailure(invocation.ToolName, "Profile labeling requires template-specific label set resolution before automation."),
        "QueryAlignmentGeometry" => QueryAlignment(doc, transaction, invocation),
        "QuerySurfaceInfo" => QuerySurface(doc, transaction, invocation),
        "QueryProfileInfo" => ControlledFailure(invocation.ToolName, "Profile info querying is not yet wired to a safe Autodesk API adapter in this build."),
        "QueryParcelInfo" => ControlledFailure(invocation.ToolName, "Parcel info querying is not yet wired to a safe Autodesk API adapter in this build."),
        "QueryPointGroups" => QueryPointGroups(transaction),
        "CreateOffsetAlignmentIfSupportedByWorkflow" => ControlledFailure(invocation.ToolName, "Offset alignment creation requires project standards and offset-side resolution before execution."),
        "ExtractStationingData" => ControlledFailure(invocation.ToolName, "Station extraction should be implemented against profile/alignment sample lines configured in the project template."),
        "AnalyzeGeometryContinuity" => AnalyzeGeometryContinuity(doc, transaction, invocation),
        "ListNativeCommands" => ListNativeCommands(),
        "DescribeNativeCommand" => DescribeNativeCommand(invocation),
        "ExecuteNativeCommand" => ExecuteNativeCommand(doc, invocation, executionContext),
        "ExecuteNativeCommandSequence" => ExecuteNativeCommandSequence(doc, invocation, executionContext),
        _ => ControlledFailure(invocation.ToolName, $"Tool '{invocation.ToolName}' is registered but not implemented in the Autodesk executor.")
    };


    private ToolExecutionResult ListNativeCommands()
    {
        var names = _nativeCommandCatalog.GetAll().Select(x => x.Name).ToArray();
        return new ToolExecutionResult("ListNativeCommands", true, $"Native command bridge exposes {names.Length} cataloged Civil 3D/AutoCAD commands.", names);
    }

    private ToolExecutionResult DescribeNativeCommand(ToolInvocation invocation)
    {
        var commandName = invocation.Arguments.GetProperty("commandName").GetString() ?? string.Empty;
        if (!_nativeCommandCatalog.TryResolve(commandName, out var descriptor))
        {
            return ToolExecutionResult.Failed(invocation.ToolName, $"Native command '{commandName}' is not present in the bridge catalog.", "Enable uncataloged command mode in settings if you intentionally need a raw command macro.");
        }

        return new ToolExecutionResult(invocation.ToolName, true, $"{descriptor.Name}: {descriptor.Description} [{descriptor.Safety}]", new[] { descriptor.Name });
    }

    private ToolExecutionResult ExecuteNativeCommand(Document doc, ToolInvocation invocation, ExecutionContext context)
    {
        if (!context.Settings.EnableNativeCommandBridge)
        {
            return ToolExecutionResult.Failed(invocation.ToolName, "Native command bridge is disabled in settings.");
        }

        var commandName = invocation.Arguments.GetProperty("commandName").GetString() ?? string.Empty;
        var macro = invocation.Arguments.GetProperty("macro").GetString() ?? commandName;
        if (invocation.PreviewOnly)
        {
            return Preview(invocation.ToolName, $"Preview native command {commandName}: {macro}");
        }

        if (!_nativeCommandCatalog.TryResolve(commandName, out var descriptor))
        {
            if (!context.Settings.AllowUncatalogedNativeCommands)
            {
                return ToolExecutionResult.Failed(invocation.ToolName, $"Native command '{commandName}' is not cataloged.", "Either add it to the command catalog or enable uncataloged command mode explicitly.");
            }

            descriptor = new NativeCommandDescriptor(commandName, "Uncataloged native command.", NativeCommandSafety.HighImpact);
        }

        if ((descriptor.Safety == NativeCommandSafety.Destructive || descriptor.Safety == NativeCommandSafety.HighImpact) && !context.AutoExecute)
        {
            return new ToolExecutionResult(invocation.ToolName, false, $"Native command '{commandName}' requires explicit confirmation.", Array.Empty<string>(), null, true);
        }

        doc.SendStringToExecute(macro.EndsWith(" ", StringComparison.Ordinal) ? macro : macro + " ", true, false, false);
        return new ToolExecutionResult(invocation.ToolName, true, $"Native command '{commandName}' queued for execution.", new[] { commandName });
    }

    private ToolExecutionResult ExecuteNativeCommandSequence(Document doc, ToolInvocation invocation, ExecutionContext context)
    {
        if (invocation.PreviewOnly)
        {
            var count = invocation.Arguments.GetProperty("commands").GetArrayLength();
            return Preview(invocation.ToolName, $"Preview native command sequence with {count} commands.");
        }

        foreach (var cmd in invocation.Arguments.GetProperty("commands").EnumerateArray())
        {
            var result = ExecuteNativeCommand(doc, new ToolInvocation("ExecuteNativeCommand", cmd.Clone(), invocation.Reason, false), context);
            if (!result.Success)
            {
                return result;
            }
        }

        var queued = invocation.Arguments.GetProperty("commands").EnumerateArray().Select(x => x.GetProperty("commandName").GetString() ?? string.Empty).ToArray();
        return new ToolExecutionResult(invocation.ToolName, true, $"Queued {queued.Length} native commands.", queued);
    }

    private static ToolExecutionResult BuildSelectionResult(Document doc)
    {
        var selection = doc.Editor.SelectImplied();
        var handles = selection.Status == PromptStatus.OK ? selection.Value.GetObjectIds().Select(id => id.Handle.ToString()).ToArray() : Array.Empty<string>();
        return new ToolExecutionResult("GetCurrentSelection", true, $"Selected objects: {handles.Length}", handles);
    }

    private static ToolExecutionResult BuildVisibleResult(Document doc, Transaction transaction)
    {
        var btr = (BlockTableRecord)transaction.GetObject(doc.Database.CurrentSpaceId, OpenMode.ForRead);
        var handles = btr.Cast<ObjectId>().Take(100).Select(id => id.Handle.ToString()).ToArray();
        return new ToolExecutionResult("GetVisibleEntities", true, $"Visible entities sampled: {handles.Length}", handles);
    }

    private static ToolExecutionResult QueryByType(Document doc, Transaction transaction, JsonElement args)
    {
        var typeName = args.GetProperty("entityType").GetString() ?? string.Empty;
        var btr = (BlockTableRecord)transaction.GetObject(doc.Database.CurrentSpaceId, OpenMode.ForRead);
        var matches = btr.Cast<ObjectId>()
            .Select(id => transaction.GetObject(id, OpenMode.ForRead) as Entity)
            .Where(entity => entity is not null && entity.GetType().Name.Equals(typeName, StringComparison.OrdinalIgnoreCase))
            .Select(entity => entity!.Handle.ToString())
            .ToArray();
        return new ToolExecutionResult("QueryEntitiesByType", true, $"Found {matches.Length} {typeName} entities.", matches);
    }

    private static ToolExecutionResult QueryByLayer(Document doc, Transaction transaction, JsonElement args)
    {
        var layerName = args.GetProperty("layerName").GetString() ?? string.Empty;
        var btr = (BlockTableRecord)transaction.GetObject(doc.Database.CurrentSpaceId, OpenMode.ForRead);
        var matches = btr.Cast<ObjectId>()
            .Select(id => transaction.GetObject(id, OpenMode.ForRead) as Entity)
            .Where(entity => entity is not null && entity.Layer.Equals(layerName, StringComparison.OrdinalIgnoreCase))
            .Select(entity => entity!.Handle.ToString())
            .ToArray();
        return new ToolExecutionResult("QueryEntitiesByLayer", true, $"Found {matches.Length} entities on {layerName}.", matches);
    }

    private static ToolExecutionResult QueryCivilObjects(JsonElement args)
    {
        var category = args.GetProperty("category").GetString() ?? string.Empty;
        var civilDoc = CivilApplication.ActiveDocument;
        var matches = new List<string>();

        if (category.Contains("alignment", StringComparison.OrdinalIgnoreCase))
        {
            matches.AddRange(civilDoc.GetAlignmentIds().Cast<ObjectId>().Select(id => id.Handle.ToString()));
        }

        if (category.Contains("surface", StringComparison.OrdinalIgnoreCase))
        {
            matches.AddRange(civilDoc.GetSurfaceIds().Cast<ObjectId>().Select(id => id.Handle.ToString()));
        }

        return new ToolExecutionResult("QueryCivilObjects", true, $"Found {matches.Count} Civil 3D objects for category '{category}'.", matches);
    }

    private static ToolExecutionResult CreateLine(Document doc, Transaction transaction, ToolInvocation invocation)
    {
        var start = ReadPoint(invocation.Arguments.GetProperty("startPoint"));
        var end = ReadPoint(invocation.Arguments.GetProperty("endPoint"));
        if (invocation.PreviewOnly) return Preview(invocation.ToolName, $"Preview line from {start} to {end}.");
        var line = new Line(start, end) { Layer = invocation.Arguments.GetProperty("layer").GetString() ?? "0" };
        AppendEntity(doc, transaction, line);
        return new ToolExecutionResult(invocation.ToolName, true, "Line created.", new[] { line.Handle.ToString() });
    }

    private static ToolExecutionResult CreatePolyline(Document doc, Transaction transaction, ToolInvocation invocation)
    {
        var polyline = new Polyline();
        var index = 0;
        foreach (var vertex in invocation.Arguments.GetProperty("vertices").EnumerateArray())
        {
            var point = ReadPoint(vertex);
            polyline.AddVertexAt(index++, new Point2d(point.X, point.Y), 0, 0, 0);
        }

        polyline.Closed = invocation.Arguments.GetProperty("closed").GetBoolean();
        polyline.Layer = invocation.Arguments.GetProperty("layer").GetString() ?? "0";
        if (invocation.PreviewOnly) return Preview(invocation.ToolName, $"Preview polyline with {polyline.NumberOfVertices} vertices.");
        AppendEntity(doc, transaction, polyline);
        return new ToolExecutionResult(invocation.ToolName, true, "Polyline created.", new[] { polyline.Handle.ToString() });
    }

    private static ToolExecutionResult CreateArc(Document doc, Transaction transaction, ToolInvocation invocation)
    {
        var center = ReadPoint(invocation.Arguments.GetProperty("center"));
        var radius = invocation.Arguments.GetProperty("radius").GetDouble();
        var startAngle = invocation.Arguments.GetProperty("startAngleRadians").GetDouble();
        var endAngle = invocation.Arguments.GetProperty("endAngleRadians").GetDouble();
        if (invocation.PreviewOnly) return Preview(invocation.ToolName, $"Preview arc r={radius:F3}.");
        var arc = new Arc(center, radius, startAngle, endAngle) { Layer = invocation.Arguments.GetProperty("layer").GetString() ?? "0" };
        AppendEntity(doc, transaction, arc);
        return new ToolExecutionResult(invocation.ToolName, true, "Arc created.", new[] { arc.Handle.ToString() });
    }

    private static ToolExecutionResult CreateCircle(Document doc, Transaction transaction, ToolInvocation invocation)
    {
        var center = ReadPoint(invocation.Arguments.GetProperty("center"));
        var radius = invocation.Arguments.GetProperty("radius").GetDouble();
        if (invocation.PreviewOnly) return Preview(invocation.ToolName, $"Preview circle r={radius:F3}.");
        var circle = new Circle(center, Vector3d.ZAxis, radius) { Layer = invocation.Arguments.GetProperty("layer").GetString() ?? "0" };
        AppendEntity(doc, transaction, circle);
        return new ToolExecutionResult(invocation.ToolName, true, "Circle created.", new[] { circle.Handle.ToString() });
    }

    private static ToolExecutionResult CreateText(Document doc, Transaction transaction, ToolInvocation invocation, bool multiline)
    {
        var position = ReadPoint(invocation.Arguments.GetProperty("position"));
        var text = invocation.Arguments.GetProperty("text").GetString() ?? string.Empty;
        if (invocation.PreviewOnly) return Preview(invocation.ToolName, $"Preview text '{text}'.");

        Entity entity = multiline
            ? new MText { Contents = text, Location = position, Width = invocation.Arguments.GetProperty("width").GetDouble(), Layer = invocation.Arguments.GetProperty("layer").GetString() ?? "0" }
            : new DBText { TextString = text, Position = position, Height = invocation.Arguments.GetProperty("height").GetDouble(), Layer = invocation.Arguments.GetProperty("layer").GetString() ?? "0" };

        AppendEntity(doc, transaction, entity);
        return new ToolExecutionResult(invocation.ToolName, true, multiline ? "MText created." : "Text created.", new[] { entity.Handle.ToString() });
    }

    private static ToolExecutionResult CreateBlockReference(Document doc, Transaction transaction, ToolInvocation invocation)
    {
        var blockName = invocation.Arguments.GetProperty("name").GetString() ?? string.Empty;
        var blockTable = (BlockTable)transaction.GetObject(doc.Database.BlockTableId, OpenMode.ForRead);
        if (!blockTable.Has(blockName))
        {
            return ToolExecutionResult.Failed(invocation.ToolName, $"Block '{blockName}' not found in drawing.");
        }

        var position = ReadPoint(invocation.Arguments.GetProperty("position"));
        if (invocation.PreviewOnly) return Preview(invocation.ToolName, $"Preview block {blockName}.");
        var blockReference = new BlockReference(position, blockTable[blockName])
        {
            ScaleFactors = new Scale3d(invocation.Arguments.GetProperty("scale").GetDouble()),
            Rotation = invocation.Arguments.GetProperty("rotationRadians").GetDouble(),
            Layer = invocation.Arguments.GetProperty("layer").GetString() ?? "0"
        };
        AppendEntity(doc, transaction, blockReference);
        return new ToolExecutionResult(invocation.ToolName, true, $"Block '{blockName}' inserted.", new[] { blockReference.Handle.ToString() });
    }

    private static ToolExecutionResult TransformEntity(Document doc, Transaction transaction, ToolInvocation invocation, TransformKind kind)
    {
        var entity = OpenEntityByHandle(doc, transaction, invocation.Arguments.GetProperty("handle").GetString() ?? string.Empty, OpenMode.ForWrite);
        if (entity is null) return ToolExecutionResult.Failed(invocation.ToolName, "Entity not found.");
        if (entity.IsFromExternalReference) return ToolExecutionResult.Failed(invocation.ToolName, "Cannot modify XREF entities.");
        var delta = invocation.Arguments.GetProperty("delta");
        var transform = Matrix3d.Displacement(new Vector3d(delta.GetProperty("x").GetDouble(), delta.GetProperty("y").GetDouble(), delta.GetProperty("z").GetDouble()));
        if (invocation.PreviewOnly) return Preview(invocation.ToolName, $"Preview {kind} of {entity.Handle}.");

        switch (kind)
        {
            case TransformKind.Move:
                entity.TransformBy(transform);
                return new ToolExecutionResult(invocation.ToolName, true, "Entity moved.", new[] { entity.Handle.ToString() });
            case TransformKind.Copy:
                var clone = (Entity)entity.Clone();
                clone.TransformBy(transform);
                AppendEntity(doc, transaction, clone);
                return new ToolExecutionResult(invocation.ToolName, true, "Entity copied.", new[] { entity.Handle.ToString(), clone.Handle.ToString() });
            default:
                throw new ArgumentOutOfRangeException(nameof(kind), kind, null);
        }
    }

    private static ToolExecutionResult RotateEntity(Document doc, Transaction transaction, ToolInvocation invocation)
    {
        var entity = OpenEntityByHandle(doc, transaction, invocation.Arguments.GetProperty("handle").GetString() ?? string.Empty, OpenMode.ForWrite);
        if (entity is null) return ToolExecutionResult.Failed(invocation.ToolName, "Entity not found.");
        var basePoint = ReadPoint(invocation.Arguments.GetProperty("basePoint"));
        var angle = invocation.Arguments.GetProperty("angleRadians").GetDouble();
        if (invocation.PreviewOnly) return Preview(invocation.ToolName, $"Preview rotation of {entity.Handle} by {angle:F3} rad.");
        entity.TransformBy(Matrix3d.Rotation(angle, Vector3d.ZAxis, basePoint));
        return new ToolExecutionResult(invocation.ToolName, true, "Entity rotated.", new[] { entity.Handle.ToString() });
    }

    private static ToolExecutionResult EraseEntity(Document doc, Transaction transaction, ToolInvocation invocation, ExecutionContext context)
    {
        if (context.Mode == ExecutionMode.Execute && !context.AutoExecute)
        {
            return new ToolExecutionResult(invocation.ToolName, false, "Erase requires explicit confirmation or auto-execute.", Array.Empty<string>(), null, true);
        }

        var entity = OpenEntityByHandle(doc, transaction, invocation.Arguments.GetProperty("handle").GetString() ?? string.Empty, OpenMode.ForWrite);
        if (entity is null) return ToolExecutionResult.Failed(invocation.ToolName, "Entity not found.");
        if (entity.IsFromExternalReference) return ToolExecutionResult.Failed(invocation.ToolName, "Cannot erase XREF entity.");
        if (invocation.PreviewOnly) return Preview(invocation.ToolName, $"Preview erase {entity.Handle}.");
        entity.Erase();
        return new ToolExecutionResult(invocation.ToolName, true, "Entity erased.", new[] { entity.Handle.ToString() }, confirmationRequired: true);
    }

    private static ToolExecutionResult ChangeLayer(Document doc, Transaction transaction, ToolInvocation invocation)
    {
        var entity = OpenEntityByHandle(doc, transaction, invocation.Arguments.GetProperty("handle").GetString() ?? string.Empty, OpenMode.ForWrite);
        if (entity is null) return ToolExecutionResult.Failed(invocation.ToolName, "Entity not found.");
        var targetLayer = invocation.Arguments.GetProperty("targetLayer").GetString() ?? "0";
        var layerTable = (LayerTable)transaction.GetObject(doc.Database.LayerTableId, OpenMode.ForRead);
        if (!layerTable.Has(targetLayer)) return ToolExecutionResult.Failed(invocation.ToolName, $"Layer '{targetLayer}' does not exist.");
        var layerRecord = (LayerTableRecord)transaction.GetObject(layerTable[targetLayer], OpenMode.ForRead);
        if (layerRecord.IsLocked) return ToolExecutionResult.Failed(invocation.ToolName, $"Layer '{targetLayer}' is locked.");
        if (invocation.PreviewOnly) return Preview(invocation.ToolName, $"Preview move {entity.Handle} to layer {targetLayer}.");
        entity.Layer = targetLayer;
        return new ToolExecutionResult(invocation.ToolName, true, "Layer changed.", new[] { entity.Handle.ToString() });
    }

    private static ToolExecutionResult SetProperties(Document doc, Transaction transaction, ToolInvocation invocation)
    {
        var entity = OpenEntityByHandle(doc, transaction, invocation.Arguments.GetProperty("handle").GetString() ?? string.Empty, OpenMode.ForWrite);
        if (entity is null) return ToolExecutionResult.Failed(invocation.ToolName, "Entity not found.");
        if (entity.IsFromExternalReference) return ToolExecutionResult.Failed(invocation.ToolName, "Cannot modify XREF entity.");
        if (invocation.PreviewOnly) return Preview(invocation.ToolName, $"Preview property change for {entity.Handle}.");
        foreach (var property in invocation.Arguments.GetProperty("properties").EnumerateObject())
        {
            switch (property.Name)
            {
                case "ColorIndex":
                    entity.ColorIndex = property.Value.GetInt16();
                    break;
                case "Linetype":
                    entity.Linetype = property.Value.GetString() ?? entity.Linetype;
                    break;
            }
        }
        return new ToolExecutionResult(invocation.ToolName, true, "Properties updated.", new[] { entity.Handle.ToString() });
    }

    private static ToolExecutionResult ZoomToObjects(Document doc, Transaction transaction, ToolInvocation invocation)
    {
        var ids = invocation.Arguments.GetProperty("handles").EnumerateArray().Select(handle => HandleToObjectId(doc.Database, handle.GetString() ?? string.Empty)).Where(id => !id.IsNull).ToArray();
        if (ids.Length == 0) return ToolExecutionResult.Failed(invocation.ToolName, "No valid handles were supplied.");
        var extents = new Extents3d();
        var initialized = false;
        foreach (var id in ids)
        {
            if (transaction.GetObject(id, OpenMode.ForRead, false) is Entity entity)
            {
                if (!initialized)
                {
                    extents = entity.GeometricExtents;
                    initialized = true;
                }
                else
                {
                    extents.AddExtents(entity.GeometricExtents);
                }
            }
        }

        if (!initialized) return ToolExecutionResult.Failed(invocation.ToolName, "Selected objects do not expose extents.");
        doc.Editor.SetCurrentView(new ViewTableRecord
        {
            CenterPoint = new Point2d((extents.MinPoint.X + extents.MaxPoint.X) / 2.0, (extents.MinPoint.Y + extents.MaxPoint.Y) / 2.0),
            Width = Math.Abs(extents.MaxPoint.X - extents.MinPoint.X) * 1.2,
            Height = Math.Abs(extents.MaxPoint.Y - extents.MinPoint.Y) * 1.2
        });
        return new ToolExecutionResult(invocation.ToolName, true, "Zoomed to objects.", ids.Select(id => id.Handle.ToString()).ToArray());
    }

    private static ToolExecutionResult CreateAlignmentFromPolyline(Document doc, Transaction transaction, ToolInvocation invocation)
    {
        var polyline = OpenEntityByHandle(doc, transaction, invocation.Arguments.GetProperty("polylineHandle").GetString() ?? string.Empty, OpenMode.ForRead) as Polyline;
        if (polyline is null)
        {
            return ToolExecutionResult.Failed(invocation.ToolName, "Source polyline not found or is not a polyline.");
        }

        if (invocation.PreviewOnly) return Preview(invocation.ToolName, $"Preview alignment from polyline {polyline.Handle}.");
        var alignmentName = invocation.Arguments.GetProperty("alignmentName").GetString() ?? $"AI_{DateTime.Now:HHmmss}";
        var siteName = invocation.Arguments.GetProperty("siteName").GetString() ?? string.Empty;
        var styleName = invocation.Arguments.GetProperty("styleName").GetString() ?? "Standard";
        var labelSet = invocation.Arguments.GetProperty("labelSetName").GetString() ?? "_No Labels";
        var alignmentId = Alignment.Create(CivilApplication.ActiveDocument, polyline.ObjectId, alignmentName, siteName, styleName, labelSet);
        var alignment = (Alignment)transaction.GetObject(alignmentId, OpenMode.ForRead);
        return new ToolExecutionResult(invocation.ToolName, true, $"Alignment '{alignment.Name}' created.", new[] { alignment.Handle.ToString() });
    }

    private static ToolExecutionResult CreateTinSurface(Transaction transaction, ToolInvocation invocation)
    {
        var name = invocation.Arguments.GetProperty("surfaceName").GetString() ?? $"AI_TIN_{DateTime.Now:HHmmss}";
        var pointGroupName = invocation.Arguments.GetProperty("pointGroupName").GetString() ?? string.Empty;
        if (invocation.PreviewOnly) return Preview(invocation.ToolName, $"Preview TIN surface '{name}' from point group '{pointGroupName}'.");
        var surfaceId = TinSurface.Create(name, invocation.Arguments.GetProperty("styleName").GetString() ?? "Standard");
        var surface = (TinSurface)transaction.GetObject(surfaceId, OpenMode.ForWrite);
        var pointGroups = CivilApplication.ActiveDocument.PointGroups.Cast<ObjectId>().ToArray();
        var group = pointGroups.FirstOrDefault(pgId => ((PointGroup)transaction.GetObject(pgId, OpenMode.ForRead)).Name.Equals(pointGroupName, StringComparison.OrdinalIgnoreCase));
        if (group == ObjectId.Null)
        {
            return ToolExecutionResult.Failed(invocation.ToolName, $"Point group '{pointGroupName}' not found.");
        }
        surface.AddPointGroup(group);
        return new ToolExecutionResult(invocation.ToolName, true, $"TIN surface '{name}' created.", new[] { surface.Handle.ToString() });
    }

    private static ToolExecutionResult QueryAlignment(Document doc, Transaction transaction, ToolInvocation invocation)
    {
        var alignment = OpenDbObjectByHandle<Alignment>(doc, transaction, invocation.Arguments.GetProperty("alignmentHandle").GetString() ?? string.Empty, OpenMode.ForRead);
        if (alignment is null)
        {
            return ToolExecutionResult.Failed(invocation.ToolName, "Alignment not found.");
        }
        return new ToolExecutionResult(invocation.ToolName, true, $"Alignment '{alignment.Name}' length={alignment.Length:F3}.", new[] { alignment.Handle.ToString() });
    }

    private static ToolExecutionResult QuerySurface(Document doc, Transaction transaction, ToolInvocation invocation)
    {
        var surface = OpenDbObjectByHandle<TinSurface>(doc, transaction, invocation.Arguments.GetProperty("surfaceHandle").GetString() ?? string.Empty, OpenMode.ForRead);
        if (surface is null)
        {
            return ToolExecutionResult.Failed(invocation.ToolName, "TIN surface not found.");
        }
        return new ToolExecutionResult(invocation.ToolName, true, $"Surface '{surface.Name}' triangles={surface.TrianglesCount}.", new[] { surface.Handle.ToString() });
    }

    private static ToolExecutionResult QueryPointGroups(Transaction transaction)
    {
        var groups = CivilApplication.ActiveDocument.PointGroups.Cast<ObjectId>()
            .Select(id => (PointGroup)transaction.GetObject(id, OpenMode.ForRead))
            .Select(group => group.Handle.ToString())
            .ToArray();
        return new ToolExecutionResult("QueryPointGroups", true, $"Point groups available: {groups.Length}", groups);
    }

    private static ToolExecutionResult AnalyzeGeometryContinuity(Document doc, Transaction transaction, ToolInvocation invocation)
    {
        var handles = invocation.Arguments.GetProperty("handles").EnumerateArray().Select(x => x.GetString() ?? string.Empty).ToArray();
        var entities = handles.Select(handle => OpenEntityByHandle(doc, transaction, handle, OpenMode.ForRead)).Where(entity => entity is Curve).Cast<Curve>().ToArray();
        if (entities.Length < 2)
        {
            return ToolExecutionResult.Failed(invocation.ToolName, "At least two curve entities are required for continuity analysis.");
        }

        var gaps = new List<string>();
        for (var i = 0; i < entities.Length - 1; i++)
        {
            var distance = entities[i].EndPoint.DistanceTo(entities[i + 1].StartPoint);
            if (distance > 0.001)
            {
                gaps.Add($"Gap between {entities[i].Handle} and {entities[i + 1].Handle}: {distance:F4}");
            }
        }

        var message = gaps.Count == 0 ? "Geometry continuity check passed." : string.Join("; ", gaps);
        return new ToolExecutionResult(invocation.ToolName, gaps.Count == 0, message, entities.Select(e => e.Handle.ToString()).ToArray());
    }

    private static Point3d ReadPoint(JsonElement element) => new(
        element.GetProperty("x").GetDouble(),
        element.GetProperty("y").GetDouble(),
        element.TryGetProperty("z", out var z) ? z.GetDouble() : 0.0);

    private static void AppendEntity(Document doc, Transaction transaction, Entity entity)
    {
        var btr = (BlockTableRecord)transaction.GetObject(doc.Database.CurrentSpaceId, OpenMode.ForWrite);
        btr.AppendEntity(entity);
        transaction.AddNewlyCreatedDBObject(entity, true);
    }

    private static Entity? OpenEntityByHandle(Document doc, Transaction transaction, string handleString, OpenMode mode)
    {
        var id = HandleToObjectId(doc.Database, handleString);
        return id.IsNull ? null : transaction.GetObject(id, mode, false) as Entity;
    }

    private static T? OpenDbObjectByHandle<T>(Document doc, Transaction transaction, string handleString, OpenMode mode) where T : DBObject
    {
        var id = HandleToObjectId(doc.Database, handleString);
        return id.IsNull ? null : transaction.GetObject(id, mode, false) as T;
    }

    private static ObjectId HandleToObjectId(Database db, string handleString)
    {
        if (!long.TryParse(handleString, System.Globalization.NumberStyles.HexNumber, null, out var handleValue))
        {
            return ObjectId.Null;
        }

        try
        {
            return db.GetObjectId(false, new Handle(handleValue), 0);
        }
        catch
        {
            return ObjectId.Null;
        }
    }

    private static ToolExecutionResult Preview(string toolName, string message) => new(toolName, true, message, Array.Empty<string>());
    private static ToolExecutionResult ControlledFailure(string toolName, string message) => ToolExecutionResult.Failed(toolName, message, "Run the workflow in dry-run mode and refine the plan with a template-specific adapter.");

    private enum TransformKind
    {
        Move,
        Copy
    }

    private sealed class CadExecutionScope : IDisposable
    {
        public CadExecutionScope(Document document, DocumentLock documentLock, Transaction transaction)
        {
            Document = document;
            DocumentLock = documentLock;
            Transaction = transaction;
        }

        public Document Document { get; }
        public DocumentLock DocumentLock { get; }
        public Transaction Transaction { get; }

        public void Dispose()
        {
            Transaction.Dispose();
            DocumentLock.Dispose();
        }
    }
}
