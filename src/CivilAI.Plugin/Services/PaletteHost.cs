using Autodesk.AutoCAD.Windows;
using CivilAI.Plugin.UI.Controls;
using CivilAI.Plugin.UI.ViewModels;

namespace CivilAI.Plugin.Services;

public sealed class PaletteHost : IDisposable
{
    private readonly Lazy<AssistantViewModel> _viewModelFactory;
    private PaletteSet? _paletteSet;

    public PaletteHost(Lazy<AssistantViewModel> viewModelFactory)
    {
        _viewModelFactory = viewModelFactory;
    }

    public void Show()
    {
        _paletteSet ??= CreatePalette();
        _paletteSet.Visible = true;
    }

    public void Dispose()
    {
        _paletteSet?.Dispose();
    }

    private PaletteSet CreatePalette()
    {
        var palette = new PaletteSet("AI Civil Assistant")
        {
            DockEnabled = DockSides.Left | DockSides.Right,
            Style = PaletteSetStyles.ShowAutoHideButton | PaletteSetStyles.ShowCloseButton | PaletteSetStyles.ShowPropertiesMenu,
            MinimumSize = new System.Drawing.Size(480, 700)
        };
        var control = new AssistantControl { DataContext = _viewModelFactory.Value };
        palette.AddVisual("Assistant", control);
        return palette;
    }
}
