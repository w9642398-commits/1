using CivilAI.Core.Models;
using CivilAI.Core.Safety;
using CivilAI.Core.Tools;
using FluentAssertions;

namespace CivilAI.Tests;

public sealed class PlanValidatorTests
{
    [Fact]
    public void Validate_ShouldRejectUnknownToolsAndUnsafeDestructivePlans()
    {
        var plan = new OperationPlan(
            "Erase bad geometry",
            Array.Empty<string>(),
            new[] { "FF10" },
            new[] { new PlanStep(1, "Erase entity", "EraseEntity", "{\"handle\":\"FF10\"}", true, true) },
            new[] { "EraseEntity", "NonExistingTool" },
            SafetyLevel.Destructive,
            false,
            Array.Empty<string>(),
            "Entity erased.",
            Array.Empty<string>());

        var validator = new PlanValidator();
        var result = validator.Validate(plan, new ToolRegistry().GetAll(), ExecutionMode.Execute);

        result.IsValid.Should().BeFalse();
        result.Messages.Should().Contain(message => message.Contains("Unknown tool requested"));
        result.Messages.Should().Contain(message => message.Contains("Destructive plans must require confirmation"));
    }
}
