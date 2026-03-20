namespace CivilAI.Core.Contracts;

public interface ISecretStore
{
    Task SaveSecretAsync(string key, string value, CancellationToken cancellationToken = default);
    Task<string?> GetSecretAsync(string key, CancellationToken cancellationToken = default);
}
