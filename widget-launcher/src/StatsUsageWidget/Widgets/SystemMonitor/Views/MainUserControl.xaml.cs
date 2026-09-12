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
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        Dispatcher.BeginInvoke(ApplyHostWindowSize, DispatcherPriority.Loaded);
    }

    private void ApplyHostWindowSize()
    {
        var hostWindow = Window.GetWindow(this);
        if (hostWindow is null ||
            string.Equals(hostWindow.Title, "Widget Launcher", StringComparison.OrdinalIgnoreCase))
            return;

        hostWindow.Width = Width + 104;
        hostWindow.Height = Height + 24;
    }
}
