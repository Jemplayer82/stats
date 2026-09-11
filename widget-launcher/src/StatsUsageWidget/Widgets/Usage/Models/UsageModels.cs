using System.Text.Json;
using System.Text.Json.Serialization;

namespace StatsUsageWidget.Widgets.Usage.Models;

public sealed class StatsWidgetResponse
{
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; set; } = string.Empty;

    [JsonPropertyName("timestamp")]
    public long Timestamp { get; set; }

    [JsonPropertyName("services")]
    public List<StatsServiceEnvelope> Services { get; set; } = [];
}

public sealed class StatsServiceEnvelope
{
    [JsonPropertyName("service_id")]
    public string ServiceId { get; set; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;

    [JsonPropertyName("payload")]
    public JsonElement Payload { get; set; }
}

public sealed class ServiceUsageGroup
{
    public string Name { get; init; } = string.Empty;
    public string Accent { get; init; } = "#FF6EE7B7";
    public string StatusText { get; init; } = string.Empty;
    public List<UsageMetric> Metrics { get; init; } = [];
}

public sealed class UsageMetric
{
    public string Label { get; init; } = string.Empty;
    public string ValueText { get; init; } = string.Empty;
    public double Percent { get; init; }
    public bool HasPercent { get; init; }
    public string Detail { get; init; } = string.Empty;
}
