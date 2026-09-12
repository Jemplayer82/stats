using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Threading;
using StatsUsageWidget.Widgets.Usage.ViewModels;

namespace StatsUsageWidget.Widgets.Usage.Views;

public partial class MainUserControl : UserControl
{
    private const double HostWidthAllowance = 104;
    private const double HostHeightAllowance = 24;
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
        if (e.PropertyName is nameof(MainViewModel.UiScale) or nameof(MainViewModel.WidgetBaseHeight))
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
        var newWidth = (_viewModel.WidgetBaseWidth * scale) + HostWidthAllowance;
        var newHeight = (_viewModel.WidgetBaseHeight * scale) + HostHeightAllowance;
        var centerX = hostWindow.Left + (hostWindow.Width / 2);
        var centerY = hostWindow.Top + (hostWindow.Height / 2);
        var workArea = GetMonitorWorkArea(hostWindow);

        hostWindow.Width = newWidth;
        hostWindow.Height = newHeight;
        hostWindow.Left = Math.Clamp(
            centerX - (newWidth / 2),
            workArea.Left,
            Math.Max(workArea.Left, workArea.Right - newWidth));
        hostWindow.Top = Math.Clamp(
            centerY - (newHeight / 2),
            workArea.Top,
            Math.Max(workArea.Top, workArea.Bottom - newHeight));
    }

    private static Rect GetMonitorWorkArea(Window window)
    {
        var handle = new WindowInteropHelper(window).Handle;
        var monitor = MonitorFromWindow(handle, 2);
        var info = new MonitorInfo { Size = Marshal.SizeOf<MonitorInfo>() };
        if (monitor == IntPtr.Zero || !GetMonitorInfo(monitor, ref info))
            return SystemParameters.WorkArea;

        var screenOrigin = window.PointToScreen(new Point(0, 0));
        var fromDevice = PresentationSource.FromVisual(window)?.CompositionTarget?.TransformFromDevice
            ?? System.Windows.Media.Matrix.Identity;
        var topLeft = fromDevice.Transform(new Point(
            info.WorkArea.Left - screenOrigin.X,
            info.WorkArea.Top - screenOrigin.Y));
        var bottomRight = fromDevice.Transform(new Point(
            info.WorkArea.Right - screenOrigin.X,
            info.WorkArea.Bottom - screenOrigin.Y));
        return new Rect(
            window.Left + topLeft.X,
            window.Top + topLeft.Y,
            bottomRight.X - topLeft.X,
            bottomRight.Y - topLeft.Y);
    }

    [DllImport("user32.dll")]
    private static extern IntPtr MonitorFromWindow(IntPtr windowHandle, uint flags);

    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetMonitorInfo(IntPtr monitorHandle, ref MonitorInfo monitorInfo);

    [StructLayout(LayoutKind.Sequential)]
    private struct NativeRect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    private struct MonitorInfo
    {
        public int Size;
        public NativeRect Monitor;
        public NativeRect WorkArea;
        public uint Flags;
    }
}
