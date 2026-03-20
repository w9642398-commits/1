using System.Security.Cryptography;
using System.Text;
using CivilAI.Core.Contracts;

namespace CivilAI.Plugin.Services;

public sealed class WindowsCredentialManagerSecretStore : ISecretStore
{
    private readonly SettingsStore _settingsStore = new();

    public async Task SaveSecretAsync(string key, string value, CancellationToken cancellationToken = default)
    {
        Directory.CreateDirectory(_settingsStore.GetStorageFolder());
        var protectedBytes = ProtectedData.Protect(Encoding.UTF8.GetBytes(value), null, DataProtectionScope.CurrentUser);
        await File.WriteAllBytesAsync(Path.Combine(_settingsStore.GetStorageFolder(), Sanitize(key) + ".secret"), protectedBytes, cancellationToken).ConfigureAwait(false);
    }

    public async Task<string?> GetSecretAsync(string key, CancellationToken cancellationToken = default)
    {
        var path = Path.Combine(_settingsStore.GetStorageFolder(), Sanitize(key) + ".secret");
        if (!File.Exists(path))
        {
            return null;
        }

        var protectedBytes = await File.ReadAllBytesAsync(path, cancellationToken).ConfigureAwait(false);
        var rawBytes = ProtectedData.Unprotect(protectedBytes, null, DataProtectionScope.CurrentUser);
        return Encoding.UTF8.GetString(rawBytes);
    }

    private static string Sanitize(string key) => string.Join("_", key.Split(Path.GetInvalidFileNameChars(), StringSplitOptions.RemoveEmptyEntries));
}
