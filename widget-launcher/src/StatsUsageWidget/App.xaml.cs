using System.Windows;
using StatsUsageWidget.Widgets.Usage;

namespace StatsUsageWidget;

public partial class App : Application
{
    public static StatsUsageExtension PrimaryWidget { get; private set; } = null!;

    private void Application_Startup(object sender, StartupEventArgs e)
    {
        PrimaryWidget = new StatsUsageExtension
        {
            Logger = (title, message) =>
                System.Diagnostics.Debug.WriteLine($"[Stats widget] {title}: {message}")
        };

        new SampleMainWindow().Show();
    }
}
