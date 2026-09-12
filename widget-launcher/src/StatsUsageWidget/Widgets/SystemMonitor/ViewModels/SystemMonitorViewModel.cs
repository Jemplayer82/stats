using System.Windows.Threading;
using CommunityToolkit.Mvvm.ComponentModel;
using StatsUsageWidget.Widgets.SystemMonitor.Services;

namespace StatsUsageWidget.Widgets.SystemMonitor.ViewModels;

public partial class SystemMonitorViewModel : ObservableObject, IDisposable
{
    private readonly SystemMetricsService _metrics = new();
    private readonly DispatcherTimer _timer;

    [ObservableProperty]
    private double _cpuPercent;

    [ObservableProperty]
    private double _memoryPercent;

    [ObservableProperty]
    private double _diskMegabytesPerSecond;

    [ObservableProperty]
    private double _networkMegabitsPerSecond;

    [ObservableProperty]
    private string _diskDetail = "R 0.0 · W 0.0 MB/s";

    [ObservableProperty]
    private string _networkDetail = "↓ 0.0 · ↑ 0.0 Mb/s";

    [ObservableProperty]
    private string _statusText = "Starting monitor…";

    public double DiskDialPercent => ToDialPercent(DiskMegabytesPerSecond, 100);
    public double NetworkDialPercent => ToDialPercent(NetworkMegabitsPerSecond, 1000);
    public string CpuText => $"{Math.Round(CpuPercent):0}%";
    public string MemoryText => $"{Math.Round(MemoryPercent):0}%";
    public string DiskText => $"{DiskMegabytesPerSecond:0.0} MB/s";
    public string NetworkText => $"{NetworkMegabitsPerSecond:0.0} Mb/s";

    public SystemMonitorViewModel()
    {
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
            NetworkMegabitsPerSecond = snapshot.NetworkMegabitsPerSecond;
            DiskDetail = snapshot.DiskDetail;
            NetworkDetail = snapshot.NetworkDetail;
            StatusText = "Live · updates every second";
            OnPropertyChanged(nameof(DiskDialPercent));
            OnPropertyChanged(nameof(NetworkDialPercent));
            OnPropertyChanged(nameof(CpuText));
            OnPropertyChanged(nameof(MemoryText));
            OnPropertyChanged(nameof(DiskText));
            OnPropertyChanged(nameof(NetworkText));
        }
        catch (Exception ex)
        {
            StatusText = "Monitor unavailable · " + ex.Message;
        }
    }

    public void Dispose()
    {
        _timer.Stop();
        _timer.Tick -= OnTimerTick;
        _metrics.Dispose();
    }

    private void OnTimerTick(object? sender, EventArgs e) => Update();

    private static double ToDialPercent(double value, double fullScale)
    {
        return Math.Clamp(value / fullScale * 100, 0, 100);
    }
}
