using System.Windows;

namespace StatsUsageWidget;

public partial class SampleMainWindow : Window
{
    public SampleMainWindow()
    {
        InitializeComponent();
    }

    private void Window_Loaded(object sender, RoutedEventArgs e)
    {
        WidgetContainer.Child = App.PrimaryWidget.GetWidgetControl();
        SettingsContainer.Child = App.PrimaryWidget.GetSettingsControl();
    }
}
