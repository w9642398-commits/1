using System.Text.Json;
using CivilAI.Core.Models;
using CivilAI.Core.Tools;
using FluentAssertions;

namespace CivilAI.Tests;

public sealed class ToolMappingTests
{
    [Fact]
    public void ToolRegistry_ShouldExposeSchemasForPlannerToolMapping()
    {
        var registry = new ToolRegistry();
        var tool = registry.Find("CreatePolyline");

        tool.Should().NotBeNull();
        tool!.IsMutating.Should().BeTrue();
        tool.InputSchema["properties"]!.ToJsonString().Should().Contain("vertices");
        tool.InputSchema["required"]!.ToJsonString().Should().Contain("closed");
    }


    [Fact]
    public void NativeCommandBridgeTools_ShouldRequireExplicitConfirmation()
    {
        var registry = new ToolRegistry();

        registry.Find("ExecuteNativeCommand")!.RequiresConfirmation.Should().BeTrue();
        registry.Find("ExecuteNativeCommandSequence")!.RequiresConfirmation.Should().BeTrue();
    }

    [Fact]
    public void ToolInvocation_ShouldRoundTripArgumentsJson()
    {
        using var args = JsonDocument.Parse("{\"handle\":\"AB12\",\"targetLayer\":\"C-ROAD\"}");
        var invocation = new ToolInvocation("ChangeLayer", args.RootElement.Clone(), "Move selected entity to target layer");

        invocation.ToolName.Should().Be("ChangeLayer");
        invocation.Arguments.GetProperty("targetLayer").GetString().Should().Be("C-ROAD");
    }
}
