using CivilAI.Core.Models;

namespace CivilAI.Core.Telemetry;

public sealed record LogEntry(DateTimeOffset TimestampUtc, string Category, string Message, IReadOnlyDictionary<string, string> Properties)
{
    public static LogEntry ForPlan(string prompt, string contextSummary, string rawPlan, IReadOnlyList<string> validationMessages) =>
        new(DateTimeOffset.UtcNow, "plan", "Plan generated", new Dictionary<string, string>
        {
            ["prompt"] = prompt,
            ["context"] = contextSummary,
            ["rawPlan"] = rawPlan,
            ["validation"] = string.Join(" | ", validationMessages)
        });

    public static LogEntry ForToolResult(string sessionId, ToolExecutionResult result) =>
        new(DateTimeOffset.UtcNow, "tool", result.Message, new Dictionary<string, string>
        {
            ["sessionId"] = sessionId,
            ["tool"] = result.ToolName,
            ["success"] = result.Success.ToString(),
            ["affected"] = string.Join(",", result.AffectedHandles)
        });
}
