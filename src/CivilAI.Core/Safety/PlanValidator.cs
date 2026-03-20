using System.Text.Json;
using CivilAI.Core.Models;

namespace CivilAI.Core.Safety;

public sealed class PlanValidator
{
    public ValidationResult Validate(OperationPlan plan, IReadOnlyList<ToolDefinition> tools, ExecutionMode mode)
    {
        var messages = new List<string>();
        var knownTools = tools.ToDictionary(t => t.Name, StringComparer.OrdinalIgnoreCase);

        if (plan.OrderedSteps.Count == 0)
        {
            messages.Add("Plan does not contain executable steps.");
        }

        foreach (var toolName in plan.RequiredTools)
        {
            if (!knownTools.ContainsKey(toolName))
            {
                messages.Add($"Unknown tool requested by model: {toolName}.");
            }
        }

        foreach (var step in plan.OrderedSteps)
        {
            if (!knownTools.TryGetValue(step.ToolName, out var tool))
            {
                messages.Add($"Step {step.Index} references unavailable tool '{step.ToolName}'.");
                continue;
            }

            try
            {
                JsonDocument.Parse(step.ToolArgumentsJson).Dispose();
            }
            catch (JsonException ex)
            {
                messages.Add($"Step {step.Index} has invalid tool JSON: {ex.Message}");
            }

            if (mode == ExecutionMode.DryRun && step.MutatesDrawing && !step.PreviewAvailable)
            {
                messages.Add($"Step {step.Index} mutates the drawing without preview support in dry-run mode.");
            }

            if (tool.RequiresConfirmation && !plan.ConfirmationRequired && mode == ExecutionMode.Execute)
            {
                messages.Add($"Step {step.Index} uses confirmation-gated tool '{step.ToolName}' but the plan does not require confirmation.");
            }
        }

        if (plan.SafetyLevel == SafetyLevel.Destructive && !plan.ConfirmationRequired)
        {
            messages.Add("Destructive plans must require confirmation.");
        }

        return new ValidationResult(messages.Count == 0, messages);
    }
}

public sealed record ValidationResult(bool IsValid, IReadOnlyList<string> Messages);
