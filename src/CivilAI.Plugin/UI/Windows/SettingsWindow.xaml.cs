using System.Windows;
using CivilAI.Plugin.UI.ViewModels;

namespace CivilAI.Plugin.UI.Windows;

public partial class SettingsWindow : Window
{
    public SettingsWindow()
    {
        InitializeComponent();
    }

    private void ApiKeyBox_OnPasswordChanged(object sender, RoutedEventArgs e)
    {
        if (DataContext is AssistantViewModel vm)
        {
            vm.ApiKey = ApiKeyBox.Password;
        }
    }
}
