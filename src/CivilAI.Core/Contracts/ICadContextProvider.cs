using CivilAI.Core.Models;

namespace CivilAI.Core.Contracts;

public interface ICadContextProvider
{
    Task<DrawingContextSnapshot> GetActiveDocumentContextAsync(CancellationToken cancellationToken);
    Task<SelectionSnapshot> GetCurrentSelectionAsync(CancellationToken cancellationToken);
    Task<IReadOnlyList<EntitySnapshot>> GetVisibleEntitiesAsync(CancellationToken cancellationToken);
    Task<IReadOnlyList<EntitySnapshot>> QueryEntitiesByTypeAsync(string typeName, CancellationToken cancellationToken);
    Task<IReadOnlyList<EntitySnapshot>> QueryEntitiesByLayerAsync(string layerName, CancellationToken cancellationToken);
    Task<IReadOnlyList<CivilObjectSnapshot>> QueryCivilObjectsAsync(string category, CancellationToken cancellationToken);
}
