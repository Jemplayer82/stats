using System.Collections.ObjectModel;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using StatsUsageWidget.Widgets.Usage.Models;
using StatsUsageWidget.Widgets.Usage.Services;

namespace StatsUsageWidget.Widgets.Usage.ViewModels;

public partial class MainViewModel : ObservableObject, IDisposable
{
    private readonly SettingsViewModel _settings;
    private readonly StatsUsageClient _client = new();
    private readonly SemaphoreSlim _refreshGate = new(1, 1);
    private readonly CancellationTokenSource _shutdown = new();
    private int _refreshQueued;

    public ObservableCollection<ServiceUsageGroup> Services { get; } = [];

    [ObservableProperty]
    private string _statusText = "Connecting to Stats…";

    [ObservableProperty]
    private string _lastUpdated = string.Empty;

    [ObservableProperty]
    private bool _isLoading;

    [ObservableProperty]
    private double _transparencyPercent;

    [ObservableProperty]
    private double _scalePercent;

    public double BackgroundOpacity => Math.Clamp(1 - (TransparencyPercent / 100), 0.1, 1);
    public double UiScale => ScalePercent / 100;
    public bool HasStatusText => !string.IsNullOrWhiteSpace(StatusText);
    public double WidgetBaseWidth => 720;
    public double WidgetBaseHeight => Math.Clamp(
        12 + (Math.Max(Services.Count, 1) * 76) +
        (HasStatusText ? 18 : 0),
        110,
        334);

    public MainViewModel(SettingsViewModel settings)
    {
        _settings = settings;
        _settings.SettingsApplied += SettingsApplied;
        TransparencyPercent = _settings.TransparencyPercent;
        ScalePercent = _settings.ScalePercent;
        _ = RefreshAsync();
    }

    partial void OnTransparencyPercentChanged(double value) =>
        OnPropertyChanged(nameof(BackgroundOpacity));

    partial void OnScalePercentChanged(double value) =>
        OnPropertyChanged(nameof(UiScale));

    partial void OnStatusTextChanged(string value)
    {
        OnPropertyChanged(nameof(HasStatusText));
        OnPropertyChanged(nameof(WidgetBaseHeight));
    }

    [RelayCommand]
    public async Task RefreshAsync()
    {
        if (!await _refreshGate.WaitAsync(0))
        {
            Interlocked.Exchange(ref _refreshQueued, 1);
            return;
        }
        IsLoading = true;
        StatusText = "Refreshing…";

        try
        {
            var response = await _client.GetUsageAsync(_settings.ToSettings(), _shutdown.Token);
            var groups = StatsUsageClient.ToDisplayGroups(response);
            await RunOnUiThreadAsync(() =>
            {
                Services.Clear();
                foreach (var group in groups) Services.Add(group);
                StatusText = groups.Count == 0 ? "No services selected" : string.Empty;
                LastUpdated = "Updated " + DateTime.Now.ToString("h:mm tt");
                OnPropertyChanged(nameof(WidgetBaseHeight));
            });
        }
        catch (OperationCanceledException) when (_shutdown.IsCancellationRequested)
        {
        }
        catch (Exception ex)
        {
            await RunOnUiThreadAsync(() =>
            {
                Services.Clear();
                StatusText = "Stats is unavailable · " + ex.Message;
                LastUpdated = "Check the address in widget settings";
                OnPropertyChanged(nameof(WidgetBaseHeight));
            });
        }
        finally
        {
            IsLoading = false;
            _refreshGate.Release();
            if (Interlocked.Exchange(ref _refreshQueued, 0) == 1 && !_shutdown.IsCancellationRequested)
                _ = RefreshAsync();
        }
    }

    private void SettingsApplied(object? sender, EventArgs e)
    {
        TransparencyPercent = _settings.TransparencyPercent;
        ScalePercent = _settings.ScalePercent;
        _ = RefreshAsync();
    }

    private static async Task RunOnUiThreadAsync(Action action)
    {
        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher is null || dispatcher.CheckAccess())
        {
            action();
            return;
        }
        await dispatcher.InvokeAsync(action);
    }

    public void Dispose()
    {
        _settings.SettingsApplied -= SettingsApplied;
        _shutdown.Cancel();
        _shutdown.Dispose();
        _refreshGate.Dispose();
    }
}
