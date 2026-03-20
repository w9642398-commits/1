using System.Windows.Input;
using Autodesk.AutoCAD.ApplicationServices;
using CivilAI.Plugin.Services;

namespace CivilAI.Plugin.Ribbon;

public sealed class RibbonCommandHandler : ICommand
{
    private readonly PaletteHost _paletteHost;
    private readonly bool _showPalette;

    public RibbonCommandHandler(PaletteHost paletteHost, bool showPalette)
    {
        _paletteHost = paletteHost;
        _showPalette = showPalette;
    }

    public bool CanExecute(object? parameter) => true;
    public event EventHandler? CanExecuteChanged;

    public void Execute(object? parameter)
    {
        if (_showPalette)
        {
            _paletteHost.Show();
        }

        if (parameter is string command)
        {
            Application.DocumentManager.MdiActiveDocument?.SendStringToExecute(command + " ", true, false, false);
        }
    }
}
