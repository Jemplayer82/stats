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

    public ObservableCollection<ServiceUsageGroup> Services { get; } = [];

    [ObservableProperty]
    private string _statusText = "Connecting to Stats…";

    [ObservableProperty]
    private string _lastUpdated = string.Empty;

    [ObservableProperty]
    private bool _isLoading;

    [ObservableProperty]
    private double _transparencyPercent;

    public double BackgroundOpacity => Math.Clamp(1 - (TransparencyPercent / 100), 0.1, 1);

    public MainViewModel(SettingsViewModel settings)
    {
        _settings = settings;
        _settings.SettingsApplied += SettingsApplied;
        TransparencyPercent = _settings.TransparencyPercent;
        _ = RefreshAsync();
    }

    partial void OnTransparencyPercentChanged(double value) =>
        OnPropertyChanged(nameof(BackgroundOpacity));

    [RelayCommand]
    public async Task RefreshAsync()
    {
        if (!await _refreshGate.WaitAsync(0)) return;
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
            });
        }
        finally
        {
            IsLoading = false;
            _refreshGate.Release();
        }
    }

    private void SettingsApplied(object? sender, EventArgs e)
    {
        TransparencyPercent = _settings.TransparencyPercent;
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
