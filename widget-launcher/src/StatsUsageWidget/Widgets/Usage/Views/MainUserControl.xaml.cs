using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using StatsUsageWidget.Widgets.Usage.ViewModels;

namespace StatsUsageWidget.Widgets.Usage.Views;

public partial class MainUserControl : UserControl
{
    private const double BaseWindowWidth = 720;
    private const double BaseWindowHeight = 300;
    private MainViewModel? _viewModel;

    public MainUserControl()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
        DataContextChanged += OnDataContextChanged;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        AttachViewModel(DataContext as MainViewModel);
        Dispatcher.BeginInvoke(ApplyHostWindowSize, DispatcherPriority.Loaded);
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        AttachViewModel(null);
    }

    private void OnDataContextChanged(object sender, DependencyPropertyChangedEventArgs e)
    {
        AttachViewModel(e.NewValue as MainViewModel);
        if (IsLoaded) Dispatcher.BeginInvoke(ApplyHostWindowSize, DispatcherPriority.Loaded);
    }

    private void AttachViewModel(MainViewModel? viewModel)
    {
        if (ReferenceEquals(_viewModel, viewModel)) return;
        if (_viewModel is not null) _viewModel.PropertyChanged -= OnViewModelPropertyChanged;
        _viewModel = viewModel;
        if (_viewModel is not null) _viewModel.PropertyChanged += OnViewModelPropertyChanged;
    }

    private void OnViewModelPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(MainViewModel.UiScale))
            Dispatcher.BeginInvoke(ApplyHostWindowSize, DispatcherPriority.Loaded);
    }

    private void ApplyHostWindowSize()
    {
        if (_viewModel is null) return;

        var hostWindow = Window.GetWindow(this);
        if (hostWindow is null ||
            string.Equals(hostWindow.Title, "Widget Launcher", StringComparison.OrdinalIgnoreCase))
            return;

        var scale = Math.Clamp(_viewModel.UiScale, 0.75, 1.5);
        var newWidth = BaseWindowWidth * scale;
        var newHeight = BaseWindowHeight * scale;
        var centerX = hostWindow.Left + (hostWindow.Width / 2);
        var centerY = hostWindow.Top + (hostWindow.Height / 2);

        hostWindow.Width = newWidth;
        hostWindow.Height = newHeight;
        hostWindow.Left = centerX - (newWidth / 2);
        hostWindow.Top = centerY - (newHeight / 2);
    }
}
