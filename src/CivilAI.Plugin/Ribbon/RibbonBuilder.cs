using Autodesk.Windows;
using CivilAI.Plugin.Services;

namespace CivilAI.Plugin.Ribbon;

public sealed class RibbonBuilder
{
    private readonly PaletteHost _paletteHost;

    public RibbonBuilder(PaletteHost paletteHost)
    {
        _paletteHost = paletteHost;
    }

    public void BuildRibbon()
    {
        var ribbonControl = ComponentManager.Ribbon;
        if (ribbonControl is null || ribbonControl.Tabs.Cast<RibbonTab>().Any(tab => tab.Id == "CivilAI.Tab"))
        {
            return;
        }

        var tab = new RibbonTab { Title = "AI Civil", Id = "CivilAI.Tab" };
        var panelSource = new RibbonPanelSource { Title = "Assistant" };
        var panel = new RibbonPanel { Source = panelSource };

        panelSource.Items.Add(CreateButton("Open Assistant", "CIVILAI_OPEN", true));
        panelSource.Items.Add(CreateButton("Analyze Drawing", "^C^CCIVILAI_OPEN ", false));
        panelSource.Items.Add(CreateButton("Dry Run", "^C^CCIVILAI_OPEN ", false));
        panelSource.Items.Add(CreateButton("Execute", "^C^CCIVILAI_OPEN ", false));
        panelSource.Items.Add(CreateButton("Settings", "CIVILAI_SETTINGS", false));
        panelSource.Items.Add(CreateButton("History", "CIVILAI_OPEN", false));
        panelSource.Items.Add(CreateButton("Logs", "CIVILAI_OPEN", false));

        tab.Panels.Add(panel);
        ribbonControl.Tabs.Add(tab);
    }

    private RibbonButton CreateButton(string text, string command, bool keepPaletteVisible) => new()
    {
        Text = text,
        ShowText = true,
        CommandParameter = command,
        CommandHandler = new RibbonCommandHandler(_paletteHost, keepPaletteVisible)
    };
}
