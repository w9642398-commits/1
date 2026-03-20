using System.Text.Json;
using System.Text.Json.Nodes;
using CivilAI.Core.Contracts;
using CivilAI.Core.Models;
using CivilAI.Core.OpenAI;
using CivilAI.Core.Planning;
using CivilAI.Core.Safety;
using CivilAI.Core.Telemetry;
using CivilAI.Core.Tools;

namespace CivilAI.Core.Runtime;

public sealed class AssistantOrchestrator
{
    private readonly ICadContextProvider _contextProvider;
    private readonly ICadToolExecutor _toolExecutor;
    private readonly ToolRegistry _toolRegistry;
    private readonly ResponsesApiClient _responsesApiClient;
    private readonly PlanParser _parser;
    private readonly PlanValidator _validator;
    private readonly ILogSink _logSink;

    public AssistantOrchestrator(
        ICadContextProvider contextProvider,
        ICadToolExecutor toolExecutor,
        ToolRegistry toolRegistry,
        ResponsesApiClient responsesApiClient,
        PlanParser parser,
        PlanValidator validator,
        ILogSink logSink)
    {
        _contextProvider = contextProvider;
        _toolExecutor = toolExecutor;
        _toolRegistry = toolRegistry;
        _responsesApiClient = responsesApiClient;
        _parser = parser;
        _validator = validator;
        _logSink = logSink;
    }

    public async Task<(OperationPlan Plan, ValidationResult Validation, DrawingContextSnapshot Context)> BuildPlanAsync(string prompt, AssistantSettings settings, ExecutionMode mode, string? conversationSummary, CancellationToken cancellationToken)
    {
        var context = await _contextProvider.GetActiveDocumentContextAsync(cancellationToken).ConfigureAwait(false);
        var tools = _toolRegistry.GetAll();

        var request = CreatePlanningRequest(prompt, context, tools, settings, mode, conversationSummary);
        var response = await _responsesApiClient.CreateResponseAsync(request, settings, cancellationToken).ConfigureAwait(false);
        var outputText = ExtractOutputText(response.RootElement);
        var plan = _parser.Parse(outputText);
        var validation = _validator.Validate(plan, tools, mode);

        await _logSink.WriteAsync(LogEntry.ForPlan(prompt, context.ToCompactSummary(), outputText, validation.Messages), cancellationToken).ConfigureAwait(false);
        return (plan, validation, context);
    }

    public async Task<ExecutionReport> ExecutePlanAsync(OperationPlan plan, ExecutionContext executionContext, CancellationToken cancellationToken)
    {
        var results = new List<ToolExecutionResult>();
        var modifiedHandles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        await _toolExecutor.BeginExecutionScopeAsync(executionContext, cancellationToken).ConfigureAwait(false);
        try
        {
            foreach (var step in plan.OrderedSteps)
            {
                using var arguments = JsonDocument.Parse(step.ToolArgumentsJson);
                var invocation = new ToolInvocation(step.ToolName, arguments.RootElement.Clone(), step.Description, executionContext.Mode == ExecutionMode.DryRun || !step.MutatesDrawing);
                var result = await _toolExecutor.ExecuteAsync(invocation, executionContext, cancellationToken).ConfigureAwait(false);
                results.Add(result);
                foreach (var handle in result.AffectedHandles)
                {
                    modifiedHandles.Add(handle);
                }

                await _logSink.WriteAsync(LogEntry.ForToolResult(executionContext.SessionId, result), cancellationToken).ConfigureAwait(false);

                if (!result.Success)
                {
                    await _toolExecutor.AbortExecutionScopeAsync(executionContext, result.Message, cancellationToken).ConfigureAwait(false);
                    return new ExecutionReport(executionContext.SessionId, false, result.Message, results, modifiedHandles.ToArray(), new[] { result.Message }, string.Empty, DateTimeOffset.UtcNow);
                }
            }

            await _toolExecutor.CompleteExecutionScopeAsync(executionContext, cancellationToken).ConfigureAwait(false);
            var validationMessages = new List<string> { "Post-execution validation passed." };
            return new ExecutionReport(executionContext.SessionId, true, plan.ExpectedResult, results, modifiedHandles.ToArray(), validationMessages, $"UNDO-{executionContext.SessionId}", DateTimeOffset.UtcNow);
        }
        catch
        {
            await _toolExecutor.AbortExecutionScopeAsync(executionContext, "Unhandled execution failure.", cancellationToken).ConfigureAwait(false);
            throw;
        }
    }

    private static ResponsesApiRequest CreatePlanningRequest(string prompt, DrawingContextSnapshot context, IReadOnlyList<ToolDefinition> tools, AssistantSettings settings, ExecutionMode mode, string? conversationSummary)
    {
        var systemRules = "You are an engineering planning model for Autodesk Civil 3D. Always return strict JSON matching the schema. Never claim operations were executed. Use only listed tools and ask clarifying questions when object resolution is ambiguous.";
        var userContext = $"Prompt: {prompt}\nMode: {mode}\nDrawing snapshot: {context.ToCompactSummary()}\nConversation summary: {conversationSummary ?? \"none\"}";
        var input = new JsonArray
        {
            new JsonObject
            {
                ["role"] = "system",
                ["content"] = new JsonArray(new JsonObject { ["type"] = "input_text", ["text"] = systemRules })
            },
            new JsonObject
            {
                ["role"] = "user",
                ["content"] = new JsonArray(new JsonObject { ["type"] = "input_text", ["text"] = userContext })
            }
        };

        var toolArray = new JsonArray(tools.Select(tool => new JsonObject
        {
            ["type"] = "function",
            ["name"] = tool.Name,
            ["description"] = tool.Description,
            ["parameters"] = tool.InputSchema,
            ["strict"] = true
        }).ToArray<JsonNode>());

        var text = new JsonObject { ["format"] = PlanJsonSchemaFactory.Create() };
        return new ResponsesApiRequest(settings.PrimaryModel, input, text, toolArray, false, settings.MaxOutputTokens);
    }

    private static string ExtractOutputText(JsonElement root)
    {
        if (root.TryGetProperty("output_text", out var outputTextElement) && outputTextElement.ValueKind == JsonValueKind.String)
        {
            return outputTextElement.GetString() ?? "{}";
        }

        if (root.TryGetProperty("output", out var outputArray))
        {
            foreach (var item in outputArray.EnumerateArray())
            {
                if (item.TryGetProperty("content", out var contentArray))
                {
                    foreach (var content in contentArray.EnumerateArray())
                    {
                        if (content.TryGetProperty("text", out var text))
                        {
                            return text.GetString() ?? "{}";
                        }
                    }
                }
            }
        }

        throw new InvalidOperationException("Responses API response did not contain output_text.");
    }
}
