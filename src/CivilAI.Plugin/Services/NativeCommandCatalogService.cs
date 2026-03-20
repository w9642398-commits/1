namespace CivilAI.Plugin.Services;

public sealed class NativeCommandCatalogService
{
    private readonly IReadOnlyDictionary<string, NativeCommandDescriptor> _commands;

    public NativeCommandCatalogService()
    {
        _commands = Build().ToDictionary(x => x.Name, StringComparer.OrdinalIgnoreCase);
    }

    public IReadOnlyCollection<NativeCommandDescriptor> GetAll() => _commands.Values.OrderBy(x => x.Name).ToArray();

    public bool TryResolve(string commandName, out NativeCommandDescriptor descriptor) => _commands.TryGetValue(commandName, out descriptor!);

    private static IReadOnlyList<NativeCommandDescriptor> Build() =>
    [
        new("ALIGNMENTCREATE", "Create or edit alignments.", NativeCommandSafety.Interactive),
        new("PROFILECREATE", "Create or edit profiles.", NativeCommandSafety.Interactive),
        new("CREATEFEATURELINE", "Create feature lines.", NativeCommandSafety.Interactive),
        new("CREATESURFACE", "Create Civil 3D surfaces.", NativeCommandSafety.Interactive),
        new("POINTGROUP", "Manage point groups.", NativeCommandSafety.Interactive),
        new("PARCELCREATE", "Create or edit parcels.", NativeCommandSafety.Interactive),
        new("CORRIDORCREATE", "Create or rebuild corridors.", NativeCommandSafety.Interactive),
        new("PIPECREATE", "Create pipe networks.", NativeCommandSafety.Interactive),
        new("SECTIONVIEWCREATE", "Create section views.", NativeCommandSafety.Interactive),
        new("SAMPLELINECREATE", "Create sample lines.", NativeCommandSafety.Interactive),
        new("SURVEYIMPORT", "Import survey data.", NativeCommandSafety.HighImpact),
        new("ERASE", "Native erase command.", NativeCommandSafety.Destructive),
        new("PURGE", "Remove unused definitions.", NativeCommandSafety.Destructive),
        new("AUDIT", "Audit drawing database.", NativeCommandSafety.HighImpact)
    ];
}

public sealed record NativeCommandDescriptor(string Name, string Description, NativeCommandSafety Safety);

public enum NativeCommandSafety
{
    Interactive,
    HighImpact,
    Destructive
}
