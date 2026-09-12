using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using StatsUsageWidget.Widgets.Usage.Services;

namespace StatsUsageWidget.Widgets.Usage.ViewModels;

public partial class SettingsViewModel : ObservableObject
{
    private readonly StatsUsageClient _client = new();

    public IReadOnlyList<int> RefreshOptions { get; } = [30, 60, 120, 300, 600];

    public string StatsBaseUrl { get; private set; } = "https://stats.txferguson.net";
    public bool ShowCodex { get; private set; } = true;
    public bool ShowClaude { get; private set; } = true;
    public bool ShowOllama { get; private set; } = true;
    public bool ShowGemini { get; private set; } = true;
    public int RefreshSeconds { get; private set; } = 60;

    [ObservableProperty]
    private string _tempStatsBaseUrl = "https://stats.txferguson.net";

    [ObservableProperty]
    private bool _tempShowCodex = true;

    [ObservableProperty]
    private bool _tempShowClaude = true;

    [ObservableProperty]
    private bool _tempShowOllama = true;

    [ObservableProperty]
    private bool _tempShowGemini = true;

    [ObservableProperty]
    private int _tempRefreshSeconds = 60;

    [ObservableProperty]
    private string _connectionStatus = string.Empty;

    [ObservableProperty]
    private bool _isTesting;

    public event EventHandler? SettingsApplied;

    public WidgetSettings ToSettings(bool useTemporary = false)
    {
        return new WidgetSettings
        {
            StatsBaseUrl = useTemporary ? TempStatsBaseUrl : StatsBaseUrl,
            ShowCodex = useTemporary ? TempShowCodex : ShowCodex,
            ShowClaude = useTemporary ? TempShowClaude : ShowClaude,
            ShowOllama = useTemporary ? TempShowOllama : ShowOllama,
            ShowGemini = useTemporary ? TempShowGemini : ShowGemini,
            RefreshSeconds = useTemporary ? TempRefreshSeconds : RefreshSeconds
        };
    }

    public void Load(WidgetSettings settings)
    {
        StatsBaseUrl = string.IsNullOrWhiteSpace(settings.StatsBaseUrl)
            ? "https://stats.txferguson.net"
            : settings.StatsBaseUrl.Trim();
        ShowCodex = settings.ShowCodex;
        ShowClaude = settings.ShowClaude;
        ShowOllama = settings.ShowOllama;
        ShowGemini = settings.ShowGemini;
        RefreshSeconds = RefreshOptions.Contains(settings.RefreshSeconds)
            ? settings.RefreshSeconds
            : 60;
        LoadTempSettings();
        OnPropertyChanged(string.Empty);
        SettingsApplied?.Invoke(this, EventArgs.Empty);
    }

    public void LoadTempSettings()
    {
        TempStatsBaseUrl = StatsBaseUrl;
        TempShowCodex = ShowCodex;
        TempShowClaude = ShowClaude;
        TempShowOllama = ShowOllama;
        TempShowGemini = ShowGemini;
        TempRefreshSeconds = RefreshSeconds;
        ConnectionStatus = string.Empty;
    }

    public void ApplySettings()
    {
        if (!TempShowCodex && !TempShowClaude && !TempShowOllama && !TempShowGemini)
            TempShowCodex = true;

        StatsBaseUrl = TempStatsBaseUrl.Trim();
        ShowCodex = TempShowCodex;
        ShowClaude = TempShowClaude;
        ShowOllama = TempShowOllama;
        ShowGemini = TempShowGemini;
        RefreshSeconds = RefreshOptions.Contains(TempRefreshSeconds)
            ? TempRefreshSeconds
            : 60;
        OnPropertyChanged(string.Empty);
        SettingsApplied?.Invoke(this, EventArgs.Empty);
    }

    public void DiscardSettings()
    {
        LoadTempSettings();
    }

    [RelayCommand]
    private async Task TestConnectionAsync()
    {
        IsTesting = true;
        ConnectionStatus = "Testing…";
        try
        {
            var result = await _client.GetUsageAsync(ToSettings(useTemporary: true));
            ConnectionStatus = $"Connected · {result.Services.Count} service(s) returned";
        }
        catch (Exception ex)
        {
            ConnectionStatus = "Could not connect: " + ex.Message;
        }
        finally
        {
            IsTesting = false;
        }
    }
}
