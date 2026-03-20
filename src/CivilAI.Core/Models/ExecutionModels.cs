using System.Text.Json;

namespace CivilAI.Core.Models;

public enum ExecutionMode
{
    DryRun,
    Execute
}

public enum SafetyLevel
{
    Low,
    Moderate,
    High,
    Destructive
}

public sealed record AssistantSettings(
    string ApiBaseUrl,
    string ApiKeySecretName,
    string PrimaryModel,
    string RoutingModel,
    TimeSpan Timeout,
    int MaxOutputTokens,
    bool DryRunByDefault,
    ConfirmationPolicy ConfirmationPolicy,
    bool EnableViewportScreenshot,
    bool EnableNativeCommandBridge,
    bool AllowUncatalogedNativeCommands)
{
    public static AssistantSettings Default => new(
        "https://api.openai.com/v1/responses",
        "CivilAI:OpenAI:ApiKey",
        "gpt-5",
        "gpt-5-mini",
        TimeSpan.FromSeconds(90),
        4000,
        true,
        ConfirmationPolicy.DestructiveOperations,
        false,
        true,
        false);
}

public enum ConfirmationPolicy
{
    Always,
    DestructiveOperations,
    Never
}

public sealed record ExecutionContext(
    string SessionId,
    ExecutionMode Mode,
    bool AutoExecute,
    AssistantSettings Settings,
    DrawingContextSnapshot Drawing,
    DateTimeOffset StartedAtUtc,
    string UserPrompt,
    string? PreviousConversationSummary);

public sealed record ToolInvocation(string ToolName, JsonElement Arguments, string Reason, bool PreviewOnly = false);

public sealed record ToolExecutionResult(
    string ToolName,
    bool Success,
    string Message,
    IReadOnlyList<string> AffectedHandles,
    JsonDocument? Payload = null,
    bool ConfirmationRequired = false,
    string? AlternativeSuggestion = null)
{
    public static ToolExecutionResult Failed(string toolName, string message, string? alternative = null) =>
        new(toolName, false, message, Array.Empty<string>(), null, false, alternative);
}

public sealed record ExecutionReport(
    string SessionId,
    bool Success,
    string Summary,
    IReadOnlyList<ToolExecutionResult> ToolResults,
    IReadOnlyList<string> ModifiedHandles,
    IReadOnlyList<string> ValidationMessages,
    string UndoMarker,
    DateTimeOffset FinishedAtUtc);
