using System.Net.Http;
using CivilAI.Core.Contracts;
using CivilAI.Core.OpenAI;
using CivilAI.Core.Planning;
using CivilAI.Core.Runtime;
using CivilAI.Core.Safety;
using CivilAI.Core.Tools;
using CivilAI.Plugin.Host;
using CivilAI.Plugin.Ribbon;
using CivilAI.Plugin.Services;
using CivilAI.Plugin.UI.ViewModels;

namespace CivilAI.Plugin.Composition;

public sealed class PluginCompositionRoot
{
    private readonly Lazy<AssistantViewModel> _assistantViewModel;

    public PluginCompositionRoot()
    {
        var settingsStore = new SettingsStore();
        var secretStore = new WindowsCredentialManagerSecretStore();
        var logSink = new FileLogSink(settingsStore);
        var nativeCommandCatalog = new NativeCommandCatalogService();
        var contextProvider = new AutodeskCadContextProvider(logSink);
        var toolExecutor = new AutodeskCadToolExecutor(logSink, nativeCommandCatalog);
        var httpClient = new HttpClient { Timeout = Timeout.InfiniteTimeSpan };
        var responsesApiClient = new ResponsesApiClient(httpClient, secretStore);
        var registry = new ToolRegistry();
        var orchestrator = new AssistantOrchestrator(contextProvider, toolExecutor, registry, responsesApiClient, new PlanParser(), new PlanValidator(), logSink);

        _assistantViewModel = new Lazy<AssistantViewModel>(() => new AssistantViewModel(orchestrator, registry, settingsStore, secretStore, logSink));
        PaletteHost = new PaletteHost(_assistantViewModel);
        RibbonBuilder = new RibbonBuilder(PaletteHost);
    }

    public PaletteHost PaletteHost { get; }
    public RibbonBuilder RibbonBuilder { get; }
    public AssistantViewModel AssistantViewModel => _assistantViewModel.Value;
}
