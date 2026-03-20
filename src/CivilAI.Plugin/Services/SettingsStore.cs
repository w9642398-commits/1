using System.Text.Json;
using CivilAI.Core.Models;

namespace CivilAI.Plugin.Services;

public sealed class SettingsStore
{
    private const string FileName = "settings.json";

    public AssistantSettings Load()
    {
        var path = GetSettingsPath();
        if (!File.Exists(path))
        {
            return AssistantSettings.Default;
        }

        var json = File.ReadAllText(path);
        return JsonSerializer.Deserialize<AssistantSettings>(json) ?? AssistantSettings.Default;
    }

    public void Save(AssistantSettings settings)
    {
        Directory.CreateDirectory(GetStorageFolder());
        File.WriteAllText(GetSettingsPath(), JsonSerializer.Serialize(settings, new JsonSerializerOptions { WriteIndented = true }));
    }

    public string GetStorageFolder() => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "CivilAI2026");
    private string GetSettingsPath() => Path.Combine(GetStorageFolder(), FileName);
}
