using System.Windows.Threading;
using CommunityToolkit.Mvvm.ComponentModel;
using StatsUsageWidget.Widgets.SystemMonitor.Services;

namespace StatsUsageWidget.Widgets.SystemMonitor.ViewModels;

public partial class SystemMonitorViewModel : ObservableObject, IDisposable
{
    private const double BaseWidgetWidth = 300;
    private const double BaseWidgetHeight = 290;
    private readonly SystemMonitorSettingsViewModel _settings;
    private readonly SystemMetricsService _metrics = new();
    private readonly DispatcherTimer _timer;

    [ObservableProperty]
    private double _cpuPercent;

    [ObservableProperty]
    private double _memoryPercent;

    [ObservableProperty]
    private double _diskMegabytesPerSecond;

    [ObservableProperty]
    private double _diskReadMegabytesPerSecond;

    [ObservableProperty]
    private double _diskWriteMegabytesPerSecond;

    [ObservableProperty]
    private double _networkMegabitsPerSecond;

    [ObservableProperty]
    private string _diskDetail = "R 0.0 · W 0.0 MB/s";

    [ObservableProperty]
    private string _networkDetail = "↓ 0.0 · ↑ 0.0 Mb/s";

    [ObservableProperty]
    private string _statusText = "Starting monitor…";

    public double DiskDialPercent => ToDialPercent(DiskMegabytesPerSecond, 100);
    public double DiskReadDialPercent => ToDialPercent(DiskReadMegabytesPerSecond, 100);
    public double DiskWriteDialPercent => ToDialPercent(DiskWriteMegabytesPerSecond, 100);
    public double NetworkDialPercent => ToDialPercent(NetworkMegabitsPerSecond, 1000);
    public string CpuText => $"{Math.Round(CpuPercent):0}%";
    public string MemoryText => $"{Math.Round(MemoryPercent):0}%";
    public string DiskText => $"{DiskMegabytesPerSecond:0.0} MB/s";
    public string DiskReadText => $"{DiskReadMegabytesPerSecond:0.0} MB/s";
    public string DiskWriteText => $"{DiskWriteMegabytesPerSecond:0.0} MB/s";
    public string NetworkText => $"{NetworkMegabitsPerSecond:0.0} Mb/s";
    public double UiScale => _settings.UiScale;
    public double WidgetWidth => BaseWidgetWidth * UiScale;
    public double WidgetHeight => BaseWidgetHeight * UiScale;

    public SystemMonitorViewModel(SystemMonitorSettingsViewModel settings)
    {
        _settings = settings;
        _settings.SettingsApplied += OnSettingsApplied;
        _settings.ScaleChanged += OnScaleChanged;
        _timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
        _timer.Tick += OnTimerTick;
        Update();
        _timer.Start();
    }

    public void Update()
    {
        try
        {
            var snapshot = _metrics.Sample();
            CpuPercent = snapshot.CpuPercent;
            MemoryPercent = snapshot.MemoryPercent;
            DiskMegabytesPerSecond = snapshot.DiskMegabytesPerSecond;
            DiskReadMegabytesPerSecond = snapshot.DiskReadMegabytesPerSecond;
            DiskWriteMegabytesPerSecond = snapshot.DiskWriteMegabytesPerSecond;
            NetworkMegabitsPerSecond = snapshot.NetworkMegabitsPerSecond;
            DiskDetail = snapshot.DiskDetail;
            NetworkDetail = snapshot.NetworkDetail;
            StatusText = "Live · updates every second";
            OnPropertyChanged(nameof(DiskDialPercent));
            OnPropertyChanged(nameof(DiskReadDialPercent));
            OnPropertyChanged(nameof(DiskWriteDialPercent));
            OnPropertyChanged(nameof(NetworkDialPercent));
            OnPropertyChanged(nameof(CpuText));
            OnPropertyChanged(nameof(MemoryText));
            OnPropertyChanged(nameof(DiskText));
            OnPropertyChanged(nameof(DiskReadText));
            OnPropertyChanged(nameof(DiskWriteText));
            OnPropertyChanged(nameof(NetworkText));
        }
        catch (Exception ex)
        {
            StatusText = "Monitor unavailable · " + ex.Message;
        }
    }

    public void Dispose()
    {
        _settings.SettingsApplied -= OnSettingsApplied;
        _settings.ScaleChanged -= OnScaleChanged;
        _timer.Stop();
        _timer.Tick -= OnTimerTick;
        _metrics.Dispose();
    }

    private void OnTimerTick(object? sender, EventArgs e) => Update();

    private void OnSettingsApplied(object? sender, EventArgs e)
    {
        OnScaleChanged(sender, e);
    }

    private void OnScaleChanged(object? sender, EventArgs e)
    {
        OnPropertyChanged(nameof(UiScale));
        OnPropertyChanged(nameof(WidgetWidth));
        OnPropertyChanged(nameof(WidgetHeight));
    }

    private static double ToDialPercent(double value, double fullScale)
    {
        return Math.Clamp(value / fullScale * 100, 0, 100);
    }
}
