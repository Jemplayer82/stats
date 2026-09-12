using CommunityToolkit.Mvvm.ComponentModel;

namespace StatsUsageWidget.Widgets.SystemMonitor.ViewModels;

public sealed class SystemMonitorSettingsViewModel : ObservableObject
{
    private const int MinimumScalePercent = 50;
    private const int MaximumScalePercent = 125;
    private int _scalePercent = 75;
    private int _tempScalePercent = 75;

    public int ScalePercent
    {
        get => _scalePercent;
        private set => SetProperty(ref _scalePercent, value);
    }

    public int TempScalePercent
    {
        get => _tempScalePercent;
        set
        {
            if (SetProperty(ref _tempScalePercent, Math.Clamp(value, MinimumScalePercent, MaximumScalePercent)))
                ScaleChanged?.Invoke(this, EventArgs.Empty);
        }
    }

    public double UiScale => TempScalePercent / 100d;

    public event EventHandler? SettingsApplied;
    public event EventHandler? ScaleChanged;

    public void Load(SystemMonitorWidgetSettings settings)
    {
        // Settings written before the version field used a much larger default.
        // Start those installs compact so an old saved value cannot reopen huge.
        ScalePercent = settings.SettingsVersion < 1
            ? 75
            : Math.Clamp(settings.ScalePercent, MinimumScalePercent, MaximumScalePercent);
        LoadTempSettings();
    }

    public void LoadTempSettings()
    {
        TempScalePercent = ScalePercent;
    }

    public void ApplySettings()
    {
        ScalePercent = Math.Clamp(TempScalePercent, MinimumScalePercent, MaximumScalePercent);
        SettingsApplied?.Invoke(this, EventArgs.Empty);
    }

    public void DiscardSettings()
    {
        LoadTempSettings();
    }

    public SystemMonitorWidgetSettings ToSettings()
    {
        return new SystemMonitorWidgetSettings
        {
            SettingsVersion = 1,
            ScalePercent = ScalePercent
        };
    }
}
