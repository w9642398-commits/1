using System.Text.Json.Nodes;

namespace CivilAI.Core.Planning;

public static class PlanJsonSchemaFactory
{
    public static JsonObject Create() => new()
    {
        ["name"] = "civil_ai_operation_plan",
        ["schema"] = new JsonObject
        {
            ["type"] = "object",
            ["additionalProperties"] = false,
            ["required"] = new JsonArray("intent", "assumptions", "target_objects", "ordered_steps", "required_tools", "safety_level", "confirmation_required", "validation_rules", "expected_result", "clarifying_questions"),
            ["properties"] = new JsonObject
            {
                ["intent"] = Schema("string"),
                ["assumptions"] = ArrayOf("string"),
                ["target_objects"] = ArrayOf("string"),
                ["ordered_steps"] = new JsonObject
                {
                    ["type"] = "array",
                    ["items"] = new JsonObject
                    {
                        ["type"] = "object",
                        ["additionalProperties"] = false,
                        ["required"] = new JsonArray("index", "description", "tool_name", "tool_arguments_json", "mutates_drawing", "preview_available"),
                        ["properties"] = new JsonObject
                        {
                            ["index"] = Schema("integer"),
                            ["description"] = Schema("string"),
                            ["tool_name"] = Schema("string"),
                            ["tool_arguments_json"] = Schema("string"),
                            ["mutates_drawing"] = Schema("boolean"),
                            ["preview_available"] = Schema("boolean")
                        }
                    }
                },
                ["required_tools"] = ArrayOf("string"),
                ["safety_level"] = new JsonObject { ["type"] = "string", ["enum"] = new JsonArray("Low", "Moderate", "High", "Destructive") },
                ["confirmation_required"] = Schema("boolean"),
                ["validation_rules"] = ArrayOf("string"),
                ["expected_result"] = Schema("string"),
                ["clarifying_questions"] = ArrayOf("string")
            }
        },
        ["strict"] = true
    };

    private static JsonObject Schema(string type) => new() { ["type"] = type };
    private static JsonObject ArrayOf(string type) => new() { ["type"] = "array", ["items"] = new JsonObject { ["type"] = type } };
}
