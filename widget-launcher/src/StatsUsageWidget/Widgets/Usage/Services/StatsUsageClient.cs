using System.Globalization;
using System.Net.Http;
using System.Text.Json;
using StatsUsageWidget.Widgets.Usage.Models;

namespace StatsUsageWidget.Widgets.Usage.Services;

public sealed class StatsUsageClient
{
    private static readonly HttpClient Http = new()
    {
        Timeout = TimeSpan.FromSeconds(25)
    };

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public async Task<StatsWidgetResponse> GetUsageAsync(
        WidgetSettings settings,
        CancellationToken cancellationToken = default)
    {
        var requestUri = BuildRequestUri(settings);
        using var response = await Http.GetAsync(requestUri, cancellationToken);
        response.EnsureSuccessStatusCode();
        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        var result = await JsonSerializer.DeserializeAsync<StatsWidgetResponse>(
            stream,
            JsonOptions,
            cancellationToken);

        if (result is null || result.SchemaVersion != "stats-widget-v1")
            throw new InvalidOperationException("The server did not return the Stats widget API format.");

        return result;
    }

    public static Uri BuildRequestUri(WidgetSettings settings)
    {
        var rawUrl = settings.StatsBaseUrl.Trim();
        if (string.IsNullOrWhiteSpace(rawUrl))
            throw new InvalidOperationException("Enter the web address for Stats.");

        if (!rawUrl.StartsWith("http://", StringComparison.OrdinalIgnoreCase) &&
            !rawUrl.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
        {
            rawUrl = "http://" + rawUrl;
        }

        if (!Uri.TryCreate(rawUrl, UriKind.Absolute, out var baseUri))
            throw new InvalidOperationException("The Stats web address is not valid.");

        var services = new List<string>();
        if (settings.ShowCodex) services.Add("codex");
        if (settings.ShowClaude) services.Add("claude");
        if (settings.ShowOllama) services.Add("ollama");
        if (settings.ShowGemini) services.Add("gemini");

        if (services.Count == 0)
            throw new InvalidOperationException("Select at least one service.");

        var builder = new UriBuilder(new Uri(baseUri, "/api/widget/usage"))
        {
            Query = "services=" + Uri.EscapeDataString(string.Join(',', services))
        };
        return builder.Uri;
    }

    public static List<ServiceUsageGroup> ToDisplayGroups(StatsWidgetResponse response)
    {
        return response.Services.Select(ToDisplayGroup).ToList();
    }

    private static ServiceUsageGroup ToDisplayGroup(StatsServiceEnvelope service)
    {
        if (!string.Equals(service.Status, "ok", StringComparison.OrdinalIgnoreCase))
        {
            var error = TryGetString(service.Payload, "error") ?? "usage unavailable";
            return CreateGroup(service.ServiceId, FriendlyError(error), []);
        }

        var metrics = service.ServiceId switch
        {
            "codex" => ParseCodex(service.Payload),
            "claude" => ParseClaude(service.Payload),
            "ollama" => ParseOllama(service.Payload),
            "gemini" => ParseGemini(service.Payload),
            _ => []
        };

        return CreateGroup(
            service.ServiceId,
            metrics.Count == 0 ? "No usage was reported" : string.Empty,
            metrics);
    }

    private static ServiceUsageGroup CreateGroup(
        string serviceId,
        string status,
        List<UsageMetric> metrics)
    {
        return new ServiceUsageGroup
        {
            Name = serviceId switch
            {
                "codex" => "Codex",
                "claude" => "Claude",
                "ollama" => "Ollama",
                "gemini" => "Gemini",
                _ => CultureInfo.InvariantCulture.TextInfo.ToTitleCase(serviceId)
            },
            Accent = serviceId switch
            {
                "codex" => "#FF34D399",
                "claude" => "#FFF59E0B",
                "ollama" => "#FF60A5FA",
                "gemini" => "#FFA78BFA",
                _ => "#FF94A3B8"
            },
            StatusText = status,
            Metrics = metrics
        };
    }

    private static List<UsageMetric> ParseCodex(JsonElement payload)
    {
        var result = new List<UsageMetric>();
        if (!payload.TryGetProperty("windows", out var windows) ||
            windows.ValueKind != JsonValueKind.Array)
            return result;

        foreach (var item in windows.EnumerateArray())
        {
            var percent = TryGetDouble(item, "used_percent");
            if (percent is null) continue;
            var name = TryGetString(item, "name") ?? "Codex";
            var windowMinutes = TryGetDouble(item, "window_minutes");
            var windowLabel = windowMinutes switch
            {
                <= 300 when windowMinutes is not null => "5 hour",
                <= 10080 when windowMinutes is not null => "weekly",
                _ => TryGetString(item, "slot") ?? "limit"
            };
            result.Add(PercentMetric(
                $"{name} · {windowLabel}",
                percent.Value,
                FormatReset(item, "resets_at", true)));
        }
        return result;
    }

    private static List<UsageMetric> ParseClaude(JsonElement payload)
    {
        var result = new List<UsageMetric>();
        if (!payload.TryGetProperty("usage", out var usage) ||
            usage.ValueKind != JsonValueKind.Object)
            return result;

        foreach (var property in usage.EnumerateObject())
        {
            if (property.Value.ValueKind != JsonValueKind.Object) continue;
            var percent = TryGetDouble(property.Value, "utilization");
            if (percent is null) continue;
            result.Add(PercentMetric(
                FriendlyLabel(property.Name),
                percent.Value,
                FormatReset(property.Value, "resets_at", false)));
        }
        return result;
    }

    private static List<UsageMetric> ParseOllama(JsonElement payload)
    {
        var result = new List<UsageMetric>();
        if (!payload.TryGetProperty("data", out var data) || data.ValueKind != JsonValueKind.Array)
            return result;

        foreach (var item in data.EnumerateArray())
        {
            var percent = TryGetDouble(item, "pct");
            if (percent is null) continue;
            result.Add(PercentMetric(
                TryGetString(item, "label") ?? "Usage",
                percent.Value,
                FormatReset(item, "resets_at", false)));
        }
        return result;
    }

    private static List<UsageMetric> ParseGemini(JsonElement payload)
    {
        var result = new List<UsageMetric>();
        if (!payload.TryGetProperty("data", out var data) || data.ValueKind != JsonValueKind.Array)
            return result;

        foreach (var item in data.EnumerateArray())
        {
            var usage = TryGetDouble(item, "usage");
            if (usage is null) continue;
            result.Add(new UsageMetric
            {
                Label = TryGetString(item, "label") ?? "Requests",
                ValueText = usage.Value.ToString("N0", CultureInfo.CurrentCulture),
                Detail = "last 24 hours",
                HasPercent = false
            });
        }
        return result;
    }

    private static UsageMetric PercentMetric(string label, double percent, string detail)
    {
        var clamped = Math.Clamp(percent, 0, 100);
        return new UsageMetric
        {
            Label = label,
            Percent = clamped,
            ValueText = $"{Math.Round(clamped):0}%",
            Detail = detail,
            HasPercent = true
        };
    }

    private static string FriendlyLabel(string value)
    {
        return CultureInfo.InvariantCulture.TextInfo.ToTitleCase(value.Replace('_', ' '));
    }

    private static string FriendlyError(string value)
    {
        return value switch
        {
            "login_required" => "Sign in to Codex on Stats",
            "not_installed" => "Codex is not installed on Stats",
            "no_cookie" => "Session cookie is not configured",
            "auth_failed" => "Session expired",
            "no_config" => "Service is not configured",
            "storage_unavailable" => "Stats storage is unavailable",
            _ => FriendlyLabel(value)
        };
    }

    private static string? TryGetString(JsonElement element, string propertyName)
    {
        return element.ValueKind == JsonValueKind.Object &&
               element.TryGetProperty(propertyName, out var property) &&
               property.ValueKind == JsonValueKind.String
            ? property.GetString()
            : null;
    }

    private static double? TryGetDouble(JsonElement element, string propertyName)
    {
        if (element.ValueKind != JsonValueKind.Object ||
            !element.TryGetProperty(propertyName, out var property))
            return null;
        if (property.ValueKind == JsonValueKind.Number && property.TryGetDouble(out var value))
            return value;
        if (property.ValueKind == JsonValueKind.String &&
            double.TryParse(property.GetString(), NumberStyles.Any, CultureInfo.InvariantCulture, out value))
            return value;
        return null;
    }

    private static string FormatReset(JsonElement element, string propertyName, bool unixSeconds)
    {
        if (!element.TryGetProperty(propertyName, out var value)) return string.Empty;
        DateTimeOffset reset;
        if (unixSeconds && value.ValueKind == JsonValueKind.Number && value.TryGetInt64(out var timestamp))
        {
            reset = DateTimeOffset.FromUnixTimeSeconds(timestamp);
        }
        else if (value.ValueKind == JsonValueKind.String &&
                 DateTimeOffset.TryParse(value.GetString(), out var parsed))
        {
            reset = parsed;
        }
        else
        {
            return string.Empty;
        }

        var remaining = reset - DateTimeOffset.Now;
        if (remaining <= TimeSpan.Zero) return "reset pending";
        if (remaining.TotalDays >= 1) return $"resets in {(int)remaining.TotalDays}d {remaining.Hours}h";
        if (remaining.TotalHours >= 1) return $"resets in {(int)remaining.TotalHours}h {remaining.Minutes}m";
        return $"resets in {Math.Max(1, remaining.Minutes)}m";
    }
}
