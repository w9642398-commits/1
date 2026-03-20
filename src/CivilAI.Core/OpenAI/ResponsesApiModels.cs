using System.Text.Json.Nodes;

namespace CivilAI.Core.OpenAI;

public sealed record ResponsesApiRequest(
    string Model,
    JsonArray Input,
    JsonObject? Text,
    JsonArray? Tools,
    bool Stream,
    int MaxOutputTokens);

public sealed record ResponsesApiChunk(string Event, JsonObject Data);
