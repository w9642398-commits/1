using System.Text.Json.Nodes;

namespace CivilAI.Core.Models;

public sealed record ToolDefinition(
    string Name,
    string Description,
    JsonObject InputSchema,
    bool IsMutating,
    bool RequiresConfirmation,
    string? Notes = null);
