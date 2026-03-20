using CivilAI.Core.Telemetry;

namespace CivilAI.Core.Contracts;

public interface ILogSink
{
    Task WriteAsync(LogEntry entry, CancellationToken cancellationToken = default);
}
