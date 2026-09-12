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
        if (hostWindow is null)
            return;

        var requiredWidth = Width + 104;
        var requiredHeight = Height + 24;

        hostWindow.MinWidth = Math.Max(hostWindow.MinWidth, requiredWidth);
        hostWindow.MinHeight = Math.Max(hostWindow.MinHeight, requiredHeight);

        if (hostWindow.Width < requiredWidth)
            hostWindow.Width = requiredWidth;

        if (hostWindow.Height < requiredHeight)
            hostWindow.Height = requiredHeight;
    }
}
