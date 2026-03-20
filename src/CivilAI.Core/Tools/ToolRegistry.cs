using System.Text.Json.Nodes;
using CivilAI.Core.Models;

namespace CivilAI.Core.Tools;

public sealed class ToolRegistry
{
    private readonly IReadOnlyList<ToolDefinition> _tools;

    public ToolRegistry()
    {
        _tools = Build();
    }

    public IReadOnlyList<ToolDefinition> GetAll() => _tools;

    public ToolDefinition? Find(string name) => _tools.FirstOrDefault(tool => tool.Name.Equals(name, StringComparison.OrdinalIgnoreCase));

    private static IReadOnlyList<ToolDefinition> Build()
    {
        static JsonObject ObjectSchema(params (string Name, JsonNode Schema)[] props) => new()
        {
            ["type"] = "object",
            ["additionalProperties"] = false,
            ["properties"] = new JsonObject(props.ToDictionary(x => x.Name, x => x.Schema)),
            ["required"] = new JsonArray(props.Select(p => p.Name).ToArray())
        };

        JsonObject Number() => new() { ["type"] = "number" };
        JsonObject String() => new() { ["type"] = "string" };
        JsonObject Bool() => new() { ["type"] = "boolean" };
        JsonObject StringArray() => new() { ["type"] = "array", ["items"] = String() };

        return new List<ToolDefinition>
        {
            new("GetActiveDocumentContext", "Return active drawing, units, layers and Civil 3D summaries.", ObjectSchema(), false, false),
            new("GetCurrentSelection", "Return current AutoCAD selection snapshot.", ObjectSchema(), false, false),
            new("GetVisibleEntities", "Return entities visible in the current viewport.", ObjectSchema(), false, false),
            new("QueryEntitiesByType", "Find entities by AutoCAD type name.", ObjectSchema(("entityType", String())), false, false),
            new("QueryEntitiesByLayer", "Find entities on a given layer.", ObjectSchema(("layerName", String())), false, false),
            new("QueryCivilObjects", "Find Civil 3D objects by category.", ObjectSchema(("category", String())), false, false),
            new("CreateLine", "Create a line between two points.", ObjectSchema(("startPoint", PointSchema()), ("endPoint", PointSchema()), ("layer", String())), true, false),
            new("CreatePolyline", "Create a polyline through ordered vertices.", ObjectSchema(("vertices", PointArraySchema()), ("closed", Bool()), ("layer", String())), true, false),
            new("CreateArc", "Create an arc using center, radius, start angle and end angle.", ObjectSchema(("center", PointSchema()), ("radius", Number()), ("startAngleRadians", Number()), ("endAngleRadians", Number()), ("layer", String())), true, false),
            new("CreateCircle", "Create a circle using center and radius.", ObjectSchema(("center", PointSchema()), ("radius", Number()), ("layer", String())), true, false),
            new("CreateText", "Create DBText at a position.", ObjectSchema(("position", PointSchema()), ("height", Number()), ("text", String()), ("layer", String())), true, false),
            new("CreateMText", "Create MTEXT at a position.", ObjectSchema(("position", PointSchema()), ("width", Number()), ("text", String()), ("layer", String())), true, false),
            new("CreateBlockReference", "Insert block reference by name.", ObjectSchema(("name", String()), ("position", PointSchema()), ("scale", Number()), ("rotationRadians", Number()), ("layer", String())), true, false),
            new("MoveEntity", "Move entity by vector.", ObjectSchema(("handle", String()), ("delta", VectorSchema())), true, false),
            new("CopyEntity", "Copy entity by vector.", ObjectSchema(("handle", String()), ("delta", VectorSchema())), true, false),
            new("RotateEntity", "Rotate entity around base point.", ObjectSchema(("handle", String()), ("basePoint", PointSchema()), ("angleRadians", Number())), true, false),
            new("EraseEntity", "Erase entity by handle.", ObjectSchema(("handle", String())), true, true, "Never execute without confirmation unless auto-execute policy allows it."),
            new("ChangeLayer", "Move entity to another layer.", ObjectSchema(("handle", String()), ("targetLayer", String())), true, false),
            new("SetProperties", "Set supported entity properties.", ObjectSchema(("handle", String()), ("properties", new JsonObject { ["type"] = "object" })), true, false),
            new("ZoomToObjects", "Zoom viewport to target handles.", ObjectSchema(("handles", StringArray())), false, false),
            new("StartUndoScope", "Open a logical undo scope.", ObjectSchema(("label", String())), false, false),
            new("CommitTransaction", "Commit the current transaction.", ObjectSchema(), false, false),
            new("RollbackTransaction", "Rollback the current transaction.", ObjectSchema(("reason", String())), false, false),
            new("CreateAlignmentFromPolyline", "Create Civil 3D alignment from an existing polyline handle.", ObjectSchema(("polylineHandle", String()), ("alignmentName", String()), ("siteName", String()), ("styleName", String()), ("labelSetName", String())), true, false),
            new("CreateProfile", "Create a profile view/profile workflow using alignment context.", ObjectSchema(("alignmentHandle", String()), ("profileName", String()), ("profileStyle", String())), true, false),
            new("CreateFeatureLine", "Create feature line from geometry handle(s).", ObjectSchema(("sourceHandles", StringArray()), ("name", String()), ("siteName", String())), true, false),
            new("CreateSurfaceTin", "Create TIN surface from point group or entity handles.", ObjectSchema(("surfaceName", String()), ("pointGroupName", String()), ("styleName", String())), true, false),
            new("AddLabelsToAlignment", "Apply label set to alignment.", ObjectSchema(("alignmentHandle", String()), ("labelSetName", String())), true, false),
            new("AddLabelsToProfile", "Apply label set to profile.", ObjectSchema(("profileHandle", String()), ("labelSetName", String())), true, false),
            new("QueryAlignmentGeometry", "Read alignment geometric summary.", ObjectSchema(("alignmentHandle", String())), false, false),
            new("QuerySurfaceInfo", "Read TIN surface summary.", ObjectSchema(("surfaceHandle", String())), false, false),
            new("QueryProfileInfo", "Read profile summary.", ObjectSchema(("profileHandle", String())), false, false),
            new("QueryParcelInfo", "Read parcel summary.", ObjectSchema(("parcelHandle", String())), false, false),
            new("QueryPointGroups", "List point groups available in the drawing.", ObjectSchema(), false, false),
            new("CreateOffsetAlignmentIfSupportedByWorkflow", "Create offset alignment from a source alignment.", ObjectSchema(("alignmentHandle", String()), ("offset", Number()), ("name", String())), true, false),
            new("ExtractStationingData", "Extract station/elevation data from alignment or profile.", ObjectSchema(("alignmentHandle", String())), false, false),
            new("AnalyzeGeometryContinuity", "Analyze selected geometry for gaps, overlaps or tangency breaks.", ObjectSchema(("handles", StringArray())), false, false),
            new("ListNativeCommands", "List native Autodesk Civil 3D / AutoCAD commands exposed through the command bridge.", ObjectSchema(), false, false),
            new("DescribeNativeCommand", "Describe a native Civil 3D / AutoCAD command from the command bridge catalog.", ObjectSchema(("commandName", String())), false, false),
            new("ExecuteNativeCommand", "Queue a native Civil 3D / AutoCAD command or macro when no managed wrapper exists.", ObjectSchema(("commandName", String()), ("macro", String()), ("requireUserInput", Bool())), true, true, "Use only when a managed tool does not exist. The command is queued and may run interactively inside Civil 3D."),
            new("ExecuteNativeCommandSequence", "Queue a sequence of native Civil 3D / AutoCAD commands/macros.", new JsonObject
            {
                ["type"] = "object",
                ["additionalProperties"] = false,
                ["properties"] = new JsonObject
                {
                    ["commands"] = new JsonObject
                    {
                        ["type"] = "array",
                        ["items"] = new JsonObject
                        {
                            ["type"] = "object",
                            ["additionalProperties"] = false,
                            ["properties"] = new JsonObject
                            {
                                ["commandName"] = String(),
                                ["macro"] = String(),
                                ["requireUserInput"] = Bool()
                            },
                            ["required"] = new JsonArray("commandName", "macro", "requireUserInput")
                        }
                    }
                },
                ["required"] = new JsonArray("commands")
            }, true, true, "Use only after explicit confirmation because command sequences can touch any Civil 3D functionality.")
        };
    }

    private static JsonObject PointSchema() => new() { ["type"] = "object", ["additionalProperties"] = false, ["required"] = new JsonArray("x", "y"), ["properties"] = new JsonObject { ["x"] = new JsonObject { ["type"] = "number" }, ["y"] = new JsonObject { ["type"] = "number" }, ["z"] = new JsonObject { ["type"] = "number" } } };
    private static JsonObject VectorSchema() => new() { ["type"] = "object", ["additionalProperties"] = false, ["required"] = new JsonArray("x", "y", "z"), ["properties"] = new JsonObject { ["x"] = new JsonObject { ["type"] = "number" }, ["y"] = new JsonObject { ["type"] = "number" }, ["z"] = new JsonObject { ["type"] = "number" } } };
    private static JsonObject PointArraySchema() => new() { ["type"] = "array", ["items"] = PointSchema() };
}
