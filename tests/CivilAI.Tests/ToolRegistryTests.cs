using CivilAI.Core.Tools;
using FluentAssertions;

namespace CivilAI.Tests;

public sealed class ToolRegistryTests
{
    [Fact]
    public void Registry_ShouldExposeRequiredCadAndCivilTools()
    {
        var registry = new ToolRegistry();
        var tools = registry.GetAll();

        tools.Should().Contain(tool => tool.Name == "GetActiveDocumentContext");
        tools.Should().Contain(tool => tool.Name == "CreatePolyline");
        tools.Should().Contain(tool => tool.Name == "CreateAlignmentFromPolyline");
        tools.Should().Contain(tool => tool.Name == "CreateSurfaceTin");
        tools.Should().Contain(tool => tool.Name == "AnalyzeGeometryContinuity");
        tools.Should().Contain(tool => tool.Name == "ExecuteNativeCommand");
        tools.Should().Contain(tool => tool.Name == "ExecuteNativeCommandSequence");
    }
}
