namespace StatsUsageWidget.Widgets.Usage;

public sealed class WidgetSettings
{
    public string StatsBaseUrl { get; set; } = "https://stats.txferguson.net";
    public bool ShowCodex { get; set; } = true;
    public bool ShowClaude { get; set; } = true;
    public bool ShowOllama { get; set; } = true;
    public bool ShowGemini { get; set; } = true;
    public int RefreshSeconds { get; set; } = 60;
    public int TransparencyPercent { get; set; } = 5;
}
