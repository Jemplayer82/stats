using System.Text.Json;
using System.Windows;
using CSS.WidgetExtension.Core;
using CSS.WidgetExtension.Core.Interfaces;
using StatsUsageWidget.Widgets.Usage.ViewModels;
using StatsUsageWidget.Widgets.Usage.Views;

namespace StatsUsageWidget.Widgets.Usage;

public sealed class StatsUsageExtension : IWidgetExtension, ISettings, IExiting, IRefreshing, ILog
{
    private readonly SettingsViewModel _settings = new();
    private readonly MainViewModel _main;

    public StatsUsageExtension()
    {
        _main = new MainViewModel(_settings);
    }

    public int RefreshInterval => _settings.RefreshSeconds;
    public bool RefreshOnBackground => true;
    public bool AllowUserManualRefresh => true;
    public Action<string, string>? Logger { get; set; }

    public FrameworkElement GetWidgetControl()
    {
        return new MainUserControl { DataContext = _main };
    }

    public FrameworkElement GetSettingsControl()
    {
        _settings.LoadTempSettings();
        return new SettingsUserControl { DataContext = _settings };
    }

    public string GetSaveableData()
    {
        return JsonSerializer.Serialize(_settings.ToSettings());
    }

    public void LoadSavedData(string data)
    {
        if (string.IsNullOrWhiteSpace(data)) return;
        try
        {
            var saved = JsonSerializer.Deserialize<WidgetSettings>(data);
            if (saved is not null) _settings.Load(saved);
        }
        catch (JsonException ex)
        {
            Logger?.Invoke("Settings", "Could not read saved widget settings: " + ex.Message);
        }
    }

    public void ConfirmSettings()
    {
        _settings.ApplySettings();
    }

    public void RejectSettings()
    {
        _settings.DiscardSettings();
    }

    public void OnRefresh()
    {
        _ = _main.RefreshAsync();
    }

    public void OnExit()
    {
        _main.Dispose();
    }
}
