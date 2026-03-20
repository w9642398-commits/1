namespace CivilAI.Core.Models;

public sealed record PlanGenerationRequest(
    string UserPrompt,
    DrawingContextSnapshot DrawingContext,
    IReadOnlyList<ToolDefinition> AvailableTools,
    AssistantSettings Settings,
    ExecutionMode Mode,
    string SafetyRules,
    string? ConversationSummary);

public sealed record OperationPlan(
    string Intent,
    IReadOnlyList<string> Assumptions,
    IReadOnlyList<string> TargetObjects,
    IReadOnlyList<PlanStep> OrderedSteps,
    IReadOnlyList<string> RequiredTools,
    SafetyLevel SafetyLevel,
    bool ConfirmationRequired,
    IReadOnlyList<string> ValidationRules,
    string ExpectedResult,
    IReadOnlyList<string> ClarifyingQuestions)
{
    public bool RequiresClarification => ClarifyingQuestions.Count > 0;
}

public sealed record PlanStep(
    int Index,
    string Description,
    string ToolName,
    string ToolArgumentsJson,
    bool MutatesDrawing,
    bool PreviewAvailable);
