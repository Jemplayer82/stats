using CommunityToolkit.Mvvm.ComponentModel;

namespace StatsUsageWidget.Widgets.SystemMonitor.ViewModels;

public sealed class SystemMonitorSettingsViewModel : ObservableObject
{
    private int _scalePercent = 100;
    private int _tempScalePercent = 100;

    public int ScalePercent
    {
        get => _scalePercent;
        private set => SetProperty(ref _scalePercent, value);
    }

    public int TempScalePercent
    {
        get => _tempScalePercent;
        set => SetProperty(ref _tempScalePercent, Math.Clamp(value, 75, 150));
    }

    public double UiScale => ScalePercent / 100d;

    public event EventHandler? SettingsApplied;

    public void Load(SystemMonitorWidgetSettings settings)
    {
        ScalePercent = Math.Clamp(settings.ScalePercent, 75, 150);
        LoadTempSettings();
    }

    public void LoadTempSettings()
    {
        TempScalePercent = ScalePercent;
    }

    public void ApplySettings()
    {
        ScalePercent = Math.Clamp(TempScalePercent, 75, 150);
        SettingsApplied?.Invoke(this, EventArgs.Empty);
    }

    public void DiscardSettings()
    {
        LoadTempSettings();
    }

    public SystemMonitorWidgetSettings ToSettings()
    {
        return new SystemMonitorWidgetSettings { ScalePercent = ScalePercent };
    }
}
