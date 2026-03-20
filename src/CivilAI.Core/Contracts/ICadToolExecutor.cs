using CivilAI.Core.Models;

namespace CivilAI.Core.Contracts;

public interface ICadToolExecutor
{
    Task BeginExecutionScopeAsync(ExecutionContext executionContext, CancellationToken cancellationToken);
    Task<ToolExecutionResult> ExecuteAsync(ToolInvocation invocation, ExecutionContext executionContext, CancellationToken cancellationToken);
    Task CompleteExecutionScopeAsync(ExecutionContext executionContext, CancellationToken cancellationToken);
    Task AbortExecutionScopeAsync(ExecutionContext executionContext, string reason, CancellationToken cancellationToken);
}
