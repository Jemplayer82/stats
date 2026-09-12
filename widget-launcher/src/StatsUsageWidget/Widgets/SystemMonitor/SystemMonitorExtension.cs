using System.Text.Json;
using System.Windows;
using CSS.WidgetExtension.Core;
using CSS.WidgetExtension.Core.Interfaces;
using StatsUsageWidget.Widgets.SystemMonitor.ViewModels;
using StatsUsageWidget.Widgets.SystemMonitor.Views;

namespace StatsUsageWidget.Widgets.SystemMonitor;

public sealed class SystemMonitorExtension : IWidgetExtension, ISettings, IExiting, IRefreshing, ILog
{
    private readonly SystemMonitorSettingsViewModel _settings = new();
    private readonly SystemMonitorViewModel _viewModel;

    public SystemMonitorExtension()
    {
        _viewModel = new SystemMonitorViewModel(_settings);
    }

    public int RefreshInterval => 1;
    public bool RefreshOnBackground => true;
    public bool AllowUserManualRefresh => false;
    public Action<string, string>? Logger { get; set; }

    public FrameworkElement GetWidgetControl()
    {
        return new MainUserControl { DataContext = _viewModel };
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
            var saved = JsonSerializer.Deserialize<SystemMonitorWidgetSettings>(data);
            if (saved is not null) _settings.Load(saved);
        }
        catch (JsonException ex)
        {
            Logger?.Invoke("System Monitor settings", "Could not read saved settings: " + ex.Message);
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
        _viewModel.Update();
    }

    public void OnExit()
    {
        _viewModel.Dispose();
    }
}
