using Autodesk.AutoCAD.Runtime;
using CivilAI.Plugin.Composition;

[assembly: CommandClass(typeof(CivilAI.Plugin.Commands.AICommands))]

namespace CivilAI.Plugin.Host;

public sealed class CivilAiPluginEntry : IExtensionApplication
{
    internal static PluginCompositionRoot? CompositionRoot { get; private set; }

    public void Initialize()
    {
        CompositionRoot = new PluginCompositionRoot();
        CompositionRoot.RibbonBuilder.BuildRibbon();
    }

    public void Terminate()
    {
        CompositionRoot?.PaletteHost.Dispose();
        CompositionRoot = null;
    }
}
