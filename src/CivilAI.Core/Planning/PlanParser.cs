using System.Text.Json;
using CivilAI.Core.Models;

namespace CivilAI.Core.Planning;

public sealed class PlanParser
{
    public OperationPlan Parse(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;

        var steps = root.GetProperty("ordered_steps")
            .EnumerateArray()
            .Select(step => new PlanStep(
                step.GetProperty("index").GetInt32(),
                step.GetProperty("description").GetString() ?? string.Empty,
                step.GetProperty("tool_name").GetString() ?? string.Empty,
                step.GetProperty("tool_arguments_json").GetString() ?? "{}",
                step.GetProperty("mutates_drawing").GetBoolean(),
                step.GetProperty("preview_available").GetBoolean()))
            .OrderBy(step => step.Index)
            .ToArray();

        return new OperationPlan(
            root.GetProperty("intent").GetString() ?? string.Empty,
            root.GetProperty("assumptions").EnumerateArray().Select(x => x.GetString() ?? string.Empty).ToArray(),
            root.GetProperty("target_objects").EnumerateArray().Select(x => x.GetString() ?? string.Empty).ToArray(),
            steps,
            root.GetProperty("required_tools").EnumerateArray().Select(x => x.GetString() ?? string.Empty).ToArray(),
            Enum.Parse<SafetyLevel>(root.GetProperty("safety_level").GetString() ?? nameof(SafetyLevel.Moderate), ignoreCase: true),
            root.GetProperty("confirmation_required").GetBoolean(),
            root.GetProperty("validation_rules").EnumerateArray().Select(x => x.GetString() ?? string.Empty).ToArray(),
            root.GetProperty("expected_result").GetString() ?? string.Empty,
            root.GetProperty("clarifying_questions").EnumerateArray().Select(x => x.GetString() ?? string.Empty).ToArray());
    }
}
