using System.Text.Json;
using System.Windows;
using CSS.WidgetExtension.Core;
using CSS.WidgetExtension.Core.Interfaces;
using StatsUsageWidget.Widgets.Music.ViewModels;
using StatsUsageWidget.Widgets.Music.Views;

namespace StatsUsageWidget.Widgets.Music;

public sealed class AppleMusicExtension : IWidgetExtension, ISettings, IExiting, IRefreshing, ILog
{
    private readonly AppleMusicViewModel _viewModel = new();

    public int RefreshInterval => 5;
    public bool RefreshOnBackground => true;
    public bool AllowUserManualRefresh => false;
    public Action<string, string>? Logger { get; set; }

    public FrameworkElement GetWidgetControl()
    {
        _viewModel.Logger = Logger;
        _viewModel.Start();
        return new AppleMusicUserControl { DataContext = _viewModel };
    }

    public FrameworkElement GetSettingsControl()
    {
        _viewModel.LoadTemporarySettings();
        return new AppleMusicSettingsUserControl { DataContext = _viewModel };
    }

    public string GetSaveableData()
    {
        return JsonSerializer.Serialize(_viewModel.ToSettings());
    }

    public void LoadSavedData(string data)
    {
        if (string.IsNullOrWhiteSpace(data)) return;
        try
        {
            var settings = JsonSerializer.Deserialize<AppleMusicWidgetSettings>(data);
            if (settings is not null) _viewModel.LoadSettings(settings);
        }
        catch (JsonException ex)
        {
            Logger?.Invoke("Apple Music settings", "Could not read saved settings: " + ex.Message);
        }
    }

    public void ConfirmSettings()
    {
        _viewModel.ApplySettings();
    }

    public void RejectSettings()
    {
        _viewModel.DiscardSettings();
    }

    public void OnRefresh()
    {
        _ = _viewModel.RefreshAsync();
    }

    public void OnExit()
    {
        _viewModel.Dispose();
    }
}
