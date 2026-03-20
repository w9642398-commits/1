using System.Text.Json;
using CivilAI.Core.Contracts;
using CivilAI.Core.Telemetry;

namespace CivilAI.Plugin.Services;

public sealed class FileLogSink : ILogSink
{
    private readonly SettingsStore _settingsStore;

    public FileLogSink(SettingsStore settingsStore)
    {
        _settingsStore = settingsStore;
    }

    public async Task WriteAsync(LogEntry entry, CancellationToken cancellationToken = default)
    {
        var logDirectory = Path.Combine(_settingsStore.GetStorageFolder(), "logs");
        Directory.CreateDirectory(logDirectory);
        var path = Path.Combine(logDirectory, $"civilai-{DateTime.UtcNow:yyyyMMdd}.log");
        var json = JsonSerializer.Serialize(entry);
        await File.AppendAllTextAsync(path, json + Environment.NewLine, cancellationToken).ConfigureAwait(false);
    }
}
