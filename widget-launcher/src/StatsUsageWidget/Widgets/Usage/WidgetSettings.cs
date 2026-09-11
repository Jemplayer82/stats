namespace StatsUsageWidget.Widgets.Usage;

public sealed class WidgetSettings
{
    public string StatsBaseUrl { get; set; } = "http://cleo";
    public bool ShowCodex { get; set; } = true;
    public bool ShowClaude { get; set; } = true;
    public bool ShowOllama { get; set; } = true;
    public bool ShowGemini { get; set; } = true;
    public int RefreshSeconds { get; set; } = 60;
}
