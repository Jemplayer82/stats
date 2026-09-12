using System.ComponentModel;
using System.Windows.Controls;
using System.Windows;
using System.Windows.Threading;
using StatsUsageWidget.Widgets.SystemMonitor.ViewModels;

namespace StatsUsageWidget.Widgets.SystemMonitor.Views;

public partial class MainUserControl : UserControl
{
    private const double HostWidthAllowance = 24;
    private const double HostHeightAllowance = 24;
    private SystemMonitorViewModel? _viewModel;

    public MainUserControl()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        SizeChanged += OnSizeChanged;
        DataContextChanged += OnDataContextChanged;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        AttachViewModel(DataContext as SystemMonitorViewModel);
        Dispatcher.BeginInvoke(ApplyHostWindowSize, DispatcherPriority.Loaded);
    }

    private void OnDataContextChanged(object sender, DependencyPropertyChangedEventArgs e)
    {
        AttachViewModel(e.NewValue as SystemMonitorViewModel);
    }

    private void OnSizeChanged(object sender, SizeChangedEventArgs e)
    {
        Dispatcher.BeginInvoke(ApplyHostWindowSize, DispatcherPriority.Loaded);
    }

    private void AttachViewModel(SystemMonitorViewModel? viewModel)
    {
        if (ReferenceEquals(_viewModel, viewModel)) return;
        if (_viewModel is not null) _viewModel.PropertyChanged -= OnViewModelPropertyChanged;
        _viewModel = viewModel;
        if (_viewModel is not null) _viewModel.PropertyChanged += OnViewModelPropertyChanged;
    }

    private void OnViewModelPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName is nameof(SystemMonitorViewModel.WidgetWidth) or
            nameof(SystemMonitorViewModel.WidgetHeight))
        {
            Dispatcher.BeginInvoke(ApplyHostWindowSize, DispatcherPriority.Loaded);
        }
    }

    private void ApplyHostWindowSize()
    {
        var hostWindow = Window.GetWindow(this);
        if (hostWindow is null)
            return;

        if (double.IsNaN(Width) || double.IsNaN(Height) ||
            Width <= 0 || Height <= 0 ||
            Width > 600 || Height > 600)
            return;

        try
        {
            hostWindow.Width = Width + HostWidthAllowance;
            hostWindow.Height = Height + HostHeightAllowance;
        }
        catch (InvalidOperationException)
        {
            // Some launcher hosts manage their own size and reject widget resizing.
        }
    }
}
