using Autodesk.AutoCAD.Runtime;
using CivilAI.Plugin.Host;
using CivilAI.Plugin.UI.Windows;

namespace CivilAI.Plugin.Commands;

public sealed class AICommands
{
    [CommandMethod("CIVILAI_OPEN", CommandFlags.Session)]
    public void OpenAssistant() => CivilAiPluginEntry.CompositionRoot?.PaletteHost.Show();

    [CommandMethod("CIVILAI_SETTINGS", CommandFlags.Session)]
    public void OpenSettings()
    {
        var vm = CivilAiPluginEntry.CompositionRoot?.AssistantViewModel;
        if (vm is null)
        {
            return;
        }

        var window = new SettingsWindow { DataContext = vm };
        window.ShowDialog();
    }
}
