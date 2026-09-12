using System.Windows.Controls;
using System.Windows;
using System.Windows.Threading;

namespace StatsUsageWidget.Widgets.SystemMonitor.Views;

public partial class MainUserControl : UserControl
{
    public MainUserControl()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        SizeChanged += OnSizeChanged;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        Dispatcher.BeginInvoke(ApplyHostWindowSize, DispatcherPriority.Loaded);
    }

    private void OnSizeChanged(object sender, SizeChangedEventArgs e)
    {
        Dispatcher.BeginInvoke(ApplyHostWindowSize, DispatcherPriority.Loaded);
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
            hostWindow.Width = Width + 104;
            hostWindow.Height = Height + 24;
        }
        catch (InvalidOperationException)
        {
            // Some launcher hosts manage their own size and reject widget resizing.
        }
    }
}
