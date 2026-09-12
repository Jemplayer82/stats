using System.Windows;
using CSS.WidgetExtension.Core;
using CSS.WidgetExtension.Core.Interfaces;
using StatsUsageWidget.Widgets.SystemMonitor.ViewModels;
using StatsUsageWidget.Widgets.SystemMonitor.Views;

namespace StatsUsageWidget.Widgets.SystemMonitor;

public sealed class SystemMonitorExtension : IWidgetExtension, IExiting, IRefreshing, ILog
{
    private readonly SystemMonitorViewModel _viewModel = new();

    public int RefreshInterval => 1;
    public bool RefreshOnBackground => true;
    public bool AllowUserManualRefresh => false;
    public Action<string, string>? Logger { get; set; }

    public FrameworkElement GetWidgetControl()
    {
        return new MainUserControl { DataContext = _viewModel };
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
