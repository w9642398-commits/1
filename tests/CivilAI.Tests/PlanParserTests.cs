using CivilAI.Core.Models;
using CivilAI.Core.Planning;
using FluentAssertions;

namespace CivilAI.Tests;

public sealed class PlanParserTests
{
    [Fact]
    public void Parse_ShouldMaterializeOperationPlan()
    {
        var json = """
        {
          "intent": "Create alignment",
          "assumptions": ["selection contains one polyline"],
          "target_objects": ["AB12"],
          "ordered_steps": [
            {
              "index": 2,
              "description": "Create alignment from source polyline",
              "tool_name": "CreateAlignmentFromPolyline",
              "tool_arguments_json": "{\"polylineHandle\":\"AB12\",\"alignmentName\":\"AI-CL\",\"siteName\":\"\",\"styleName\":\"Standard\",\"labelSetName\":\"_No Labels\"}",
              "mutates_drawing": true,
              "preview_available": true
            },
            {
              "index": 1,
              "description": "Open undo scope",
              "tool_name": "StartUndoScope",
              "tool_arguments_json": "{\"label\":\"AI batch\"}",
              "mutates_drawing": false,
              "preview_available": true
            }
          ],
          "required_tools": ["StartUndoScope", "CreateAlignmentFromPolyline"],
          "safety_level": "Moderate",
          "confirmation_required": false,
          "validation_rules": ["polyline must exist"],
          "expected_result": "An alignment is created.",
          "clarifying_questions": []
        }
        """;

        var plan = new PlanParser().Parse(json);

        plan.Intent.Should().Be("Create alignment");
        plan.OrderedSteps.Should().HaveCount(2);
        plan.OrderedSteps[0].ToolName.Should().Be("StartUndoScope");
        plan.SafetyLevel.Should().Be(SafetyLevel.Moderate);
    }
}
