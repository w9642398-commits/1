using System.Collections.ObjectModel;
using CivilAI.Core.Contracts;
using CivilAI.Core.Models;
using CivilAI.Core.Runtime;
using CivilAI.Core.Telemetry;
using CivilAI.Core.Tools;
using CivilAI.Core.Utilities;
using CivilAI.Plugin.Services;

namespace CivilAI.Plugin.UI.ViewModels;

public sealed class AssistantViewModel : ObservableObject
{
    private readonly AssistantOrchestrator _orchestrator;
    private readonly ToolRegistry _toolRegistry;
    private readonly SettingsStore _settingsStore;
    private readonly ISecretStore _secretStore;
    private readonly ILogSink _logSink;
    private AssistantSettings _settings;
    private string _prompt = string.Empty;
    private string _status = "Ready";
    private bool _isBusy;
    private OperationPlan? _currentPlan;
    private DrawingContextSnapshot? _currentContext;
    private string _apiKey = string.Empty;

    public AssistantViewModel(
        AssistantOrchestrator orchestrator,
        ToolRegistry toolRegistry,
        SettingsStore settingsStore,
        ISecretStore secretStore,
        ILogSink logSink)
    {
        _orchestrator = orchestrator;
        _toolRegistry = toolRegistry;
        _settingsStore = settingsStore;
        _secretStore = secretStore;
        _logSink = logSink;
        _settings = _settingsStore.Load();

        BuildPlanCommand = new AsyncRelayCommand(() => BuildPlanAsync(ExecutionMode.DryRun), () => !IsBusy && !string.IsNullOrWhiteSpace(Prompt));
        ExecutePlanCommand = new AsyncRelayCommand(() => ExecuteCurrentPlanAsync(ExecutionMode.Execute), () => !IsBusy && CurrentPlan is not null);
        AnalyzeDrawingCommand = new AsyncRelayCommand(AnalyzeDrawingAsync, () => !IsBusy);
        SaveSettingsCommand = new AsyncRelayCommand(SaveSettingsAsync, () => !IsBusy);
        RollbackCommand = new AsyncRelayCommand(RollbackAsync, () => !IsBusy);
        CancelCommand = new AsyncRelayCommand(CancelAsync, () => !IsBusy);
    }

    public ObservableCollection<ConversationMessageViewModel> Conversation { get; } = new();
    public ObservableCollection<PlanStepViewModel> PlannedSteps { get; } = new();
    public ObservableCollection<string> ToolHistory { get; } = new();
    public ObservableCollection<string> ModifiedObjects { get; } = new();
    public ObservableCollection<string> ValidationMessages { get; } = new();

    public AsyncRelayCommand BuildPlanCommand { get; }
    public AsyncRelayCommand ExecutePlanCommand { get; }
    public AsyncRelayCommand AnalyzeDrawingCommand { get; }
    public AsyncRelayCommand SaveSettingsCommand { get; }
    public AsyncRelayCommand RollbackCommand { get; }
    public AsyncRelayCommand CancelCommand { get; }

    public string Prompt
    {
        get => _prompt;
        set
        {
            if (SetProperty(ref _prompt, value))
            {
                BuildPlanCommand.RaiseCanExecuteChanged();
            }
        }
    }

    public string Status
    {
        get => _status;
        private set => SetProperty(ref _status, value);
    }

    public bool IsBusy
    {
        get => _isBusy;
        private set => SetProperty(ref _isBusy, value);
    }

    public OperationPlan? CurrentPlan
    {
        get => _currentPlan;
        private set
        {
            if (SetProperty(ref _currentPlan, value))
            {
                ExecutePlanCommand.RaiseCanExecuteChanged();
            }
        }
    }

    public DrawingContextSnapshot? CurrentContext
    {
        get => _currentContext;
        private set => SetProperty(ref _currentContext, value);
    }

    public string ApiKey
    {
        get => _apiKey;
        set => SetProperty(ref _apiKey, value);
    }

    public string PrimaryModel
    {
        get => _settings.PrimaryModel;
        set => _settings = _settings with { PrimaryModel = value };
    }

    public string RoutingModel
    {
        get => _settings.RoutingModel;
        set => _settings = _settings with { RoutingModel = value };
    }

    public bool DryRunByDefault
    {
        get => _settings.DryRunByDefault;
        set => _settings = _settings with { DryRunByDefault = value };
    }

    public int TimeoutSeconds
    {
        get => (int)_settings.Timeout.TotalSeconds;
        set => _settings = _settings with { Timeout = TimeSpan.FromSeconds(Math.Max(5, value)) };
    }

    public int MaxOutputTokens
    {
        get => _settings.MaxOutputTokens;
        set => _settings = _settings with { MaxOutputTokens = Math.Max(256, value) };
    }

    public string ConfirmationPolicyValue
    {
        get => _settings.ConfirmationPolicy.ToString();
        set
        {
            if (Enum.TryParse<ConfirmationPolicy>(value, true, out var parsed))
            {
                _settings = _settings with { ConfirmationPolicy = parsed };
            }
        }
    }

    public bool EnableNativeCommandBridge
    {
        get => _settings.EnableNativeCommandBridge;
        set => _settings = _settings with { EnableNativeCommandBridge = value };
    }

    public bool AllowUncatalogedNativeCommands
    {
        get => _settings.AllowUncatalogedNativeCommands;
        set => _settings = _settings with { AllowUncatalogedNativeCommands = value };
    }

    public string CurrentDrawingSummary => CurrentContext?.ToCompactSummary() ?? "No drawing context loaded.";
    public string SelectionSummary => CurrentContext?.Selection.Entities.Count > 0 ? string.Join(", ", CurrentContext.Selection.Entities.Select(x => x.Handle)) : "No active selection.";
    public string ScopeSummary => CurrentContext?.Selection.Scope ?? "Current view";

    private async Task AnalyzeDrawingAsync()
    {
        await SetBusyAsync("Analyzing drawing", async () =>
        {
            var planTuple = await _orchestrator.BuildPlanAsync("Analyze the current drawing and summarize actionable AI scope.", _settings, ExecutionMode.DryRun, null, CancellationToken.None).ConfigureAwait(false);
            CurrentContext = planTuple.Context;
            Conversation.Add(new ConversationMessageViewModel("system", CurrentDrawingSummary));
            OnDependentPropertiesChanged();
        }).ConfigureAwait(false);
    }

    private async Task BuildPlanAsync(ExecutionMode mode)
    {
        await SetBusyAsync("Planning", async () =>
        {
            Conversation.Add(new ConversationMessageViewModel("user", Prompt));
            var (plan, validation, context) = await _orchestrator.BuildPlanAsync(Prompt, _settings, mode, BuildConversationSummary(), CancellationToken.None).ConfigureAwait(false);
            CurrentPlan = plan;
            CurrentContext = context;
            PlannedSteps.Clear();
            foreach (var step in plan.OrderedSteps)
            {
                PlannedSteps.Add(new PlanStepViewModel(step));
            }

            ValidationMessages.Clear();
            foreach (var message in validation.Messages.DefaultIfEmpty("Plan validation passed."))
            {
                ValidationMessages.Add(message);
            }

            var assistantMessage = plan.RequiresClarification
                ? string.Join(Environment.NewLine, plan.ClarifyingQuestions)
                : $"Intent: {plan.Intent}{Environment.NewLine}Expected result: {plan.ExpectedResult}";
            Conversation.Add(new ConversationMessageViewModel("assistant", assistantMessage));
            OnDependentPropertiesChanged();
        }).ConfigureAwait(false);
    }

    private async Task ExecuteCurrentPlanAsync(ExecutionMode mode)
    {
        if (CurrentPlan is null || CurrentContext is null)
        {
            return;
        }

        await SetBusyAsync("Executing plan", async () =>
        {
            var executionContext = new ExecutionContext(
                Guid.NewGuid().ToString("N"),
                mode,
                _settings.ConfirmationPolicy == ConfirmationPolicy.Never,
                _settings,
                CurrentContext,
                DateTimeOffset.UtcNow,
                Prompt,
                BuildConversationSummary());

            var report = await _orchestrator.ExecutePlanAsync(CurrentPlan, executionContext, CancellationToken.None).ConfigureAwait(false);
            ToolHistory.Clear();
            foreach (var tool in report.ToolResults)
            {
                ToolHistory.Add($"{tool.ToolName}: {tool.Message}");
            }

            ModifiedObjects.Clear();
            foreach (var handle in report.ModifiedHandles)
            {
                ModifiedObjects.Add(handle);
            }

            ValidationMessages.Clear();
            foreach (var message in report.ValidationMessages)
            {
                ValidationMessages.Add(message);
            }

            Conversation.Add(new ConversationMessageViewModel("assistant", report.Summary));
            Status = report.Success ? "Execution completed" : "Execution failed";
        }).ConfigureAwait(false);
    }

    private async Task SaveSettingsAsync()
    {
        await SetBusyAsync("Saving settings", async () =>
        {
            _settingsStore.Save(_settings);
            if (!string.IsNullOrWhiteSpace(ApiKey))
            {
                await _secretStore.SaveSecretAsync(_settings.ApiKeySecretName, ApiKey).ConfigureAwait(false);
            }
            Status = "Settings saved";
        }).ConfigureAwait(false);
    }

    private Task RollbackAsync()
    {
        Conversation.Add(new ConversationMessageViewModel("system", "Use AutoCAD UNDO to rollback the last grouped operation. The plugin keeps a single logical undo scope per execution."));
        return Task.CompletedTask;
    }

    private Task CancelAsync()
    {
        Status = "Cancelled";
        return Task.CompletedTask;
    }

    private async Task SetBusyAsync(string status, Func<Task> action)
    {
        IsBusy = true;
        Status = status;
        try
        {
            await action().ConfigureAwait(true);
        }
        finally
        {
            IsBusy = false;
            BuildPlanCommand.RaiseCanExecuteChanged();
            ExecutePlanCommand.RaiseCanExecuteChanged();
            AnalyzeDrawingCommand.RaiseCanExecuteChanged();
            SaveSettingsCommand.RaiseCanExecuteChanged();
            RollbackCommand.RaiseCanExecuteChanged();
            CancelCommand.RaiseCanExecuteChanged();
        }
    }

    private string BuildConversationSummary() => string.Join("\n", Conversation.TakeLast(10).Select(x => $"{x.Role}: {x.Text}"));

    private void OnDependentPropertiesChanged()
    {
        OnPropertyChanged(nameof(CurrentDrawingSummary));
        OnPropertyChanged(nameof(SelectionSummary));
        OnPropertyChanged(nameof(ScopeSummary));
    }
}

public sealed record ConversationMessageViewModel(string Role, string Text);
public sealed record PlanStepViewModel(PlanStep Step)
{
    public int Index => Step.Index;
    public string Description => Step.Description;
    public string ToolName => Step.ToolName;
    public string ToolArgumentsJson => Step.ToolArgumentsJson;
    public bool PreviewAvailable => Step.PreviewAvailable;
}
