using CivilAI.Core.Models;
using CivilAI.Core.Safety;
using CivilAI.Core.Tools;
using FluentAssertions;

namespace CivilAI.Tests;

public sealed class EndToEndScenarioTests
{
    [Fact]
    public void DryRunAlignmentScenario_ShouldPassValidation()
    {
        var plan = new OperationPlan(
            "Create alignment from polyline",
            new[] { "exactly one polyline selected" },
            new[] { "AB12" },
            new[]
            {
                new PlanStep(1, "Open undo scope", "StartUndoScope", "{\"label\":\"AI alignment\"}", false, true),
                new PlanStep(2, "Create alignment", "CreateAlignmentFromPolyline", "{\"polylineHandle\":\"AB12\",\"alignmentName\":\"AI_Main\",\"siteName\":\"\",\"styleName\":\"Standard\",\"labelSetName\":\"_No Labels\"}", true, true)
            },
            new[] { "StartUndoScope", "CreateAlignmentFromPolyline" },
            SafetyLevel.Moderate,
            false,
            new[] { "selected object must be a writable polyline" },
            "Alignment exists with project default style.",
            Array.Empty<string>());

        var validation = new PlanValidator().Validate(plan, new ToolRegistry().GetAll(), ExecutionMode.DryRun);
        validation.IsValid.Should().BeTrue();
    }
}
