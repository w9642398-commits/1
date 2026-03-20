using System.Net.Http.Headers;
using System.Runtime.CompilerServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using CivilAI.Core.Contracts;
using CivilAI.Core.Models;

namespace CivilAI.Core.OpenAI;

public sealed class ResponsesApiClient
{
    private readonly HttpClient _httpClient;
    private readonly ISecretStore _secretStore;

    public ResponsesApiClient(HttpClient httpClient, ISecretStore secretStore)
    {
        _httpClient = httpClient;
        _secretStore = secretStore;
    }

    public async Task<JsonDocument> CreateResponseAsync(ResponsesApiRequest request, AssistantSettings settings, CancellationToken cancellationToken)
    {
        using var httpRequest = await BuildRequestAsync(request, settings, cancellationToken).ConfigureAwait(false);
        using var response = await _httpClient.SendAsync(httpRequest, HttpCompletionOption.ResponseHeadersRead, cancellationToken).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
        return await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken).ConfigureAwait(false);
    }

    public async IAsyncEnumerable<ResponsesApiChunk> StreamResponseAsync(ResponsesApiRequest request, AssistantSettings settings, [EnumeratorCancellation] CancellationToken cancellationToken)
    {
        using var httpRequest = await BuildRequestAsync(request with { Stream = true }, settings, cancellationToken).ConfigureAwait(false);
        using var response = await _httpClient.SendAsync(httpRequest, HttpCompletionOption.ResponseHeadersRead, cancellationToken).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();

        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
        using var reader = new StreamReader(stream, Encoding.UTF8);

        while (!reader.EndOfStream)
        {
            var line = await reader.ReadLineAsync(cancellationToken).ConfigureAwait(false);
            if (string.IsNullOrWhiteSpace(line) || !line.StartsWith("data:", StringComparison.Ordinal))
            {
                continue;
            }

            var payload = line[5..].Trim();
            if (payload.Equals("[DONE]", StringComparison.OrdinalIgnoreCase))
            {
                yield break;
            }

            var node = JsonNode.Parse(payload)?.AsObject();
            if (node is null)
            {
                continue;
            }

            var eventName = node["type"]?.GetValue<string>() ?? "unknown";
            yield return new ResponsesApiChunk(eventName, node);
        }
    }

    private async Task<HttpRequestMessage> BuildRequestAsync(ResponsesApiRequest request, AssistantSettings settings, CancellationToken cancellationToken)
    {
        var apiKey = await _secretStore.GetSecretAsync(settings.ApiKeySecretName, cancellationToken).ConfigureAwait(false);
        if (string.IsNullOrWhiteSpace(apiKey))
        {
            throw new InvalidOperationException("OpenAI API key has not been configured.");
        }

        var json = JsonSerializer.Serialize(request, new JsonSerializerOptions(JsonSerializerDefaults.Web)
        {
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
        });

        var message = new HttpRequestMessage(HttpMethod.Post, settings.ApiBaseUrl)
        {
            Content = new StringContent(json, Encoding.UTF8, "application/json")
        };
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);
        message.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("text/event-stream"));
        return message;
    }
}
