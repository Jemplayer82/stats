using System;
using System.Diagnostics;
using Windows.ApplicationModel;
using Windows.Data.Xml.Dom;
using Windows.UI.Notifications;
using Microsoft.UI.Xaml;

namespace StatsUsageWidget.WinUI;

public partial class App : Application
{
    public App()
    {
        InitializeComponent();
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        try
        {
            var packageName = Package.Current.Id.FamilyName;
            Process.Start(new ProcessStartInfo
            {
                FileName = $"css.widgetlauncher:?package={packageName}",
                UseShellExecute = true
            });
        }
        catch
        {
        }

        var document = new XmlDocument();
        document.LoadXml("""
            <toast>
              <visual>
                <binding template='ToastGeneric'>
                  <image src='Images/App/WidgetLauncherWatermark.png' />
                  <text>Opening Widget Launcher…</text>
                  <text>The Stats Usage widget is ready to add.</text>
                </binding>
              </visual>
            </toast>
            """);
        ToastNotificationManager.CreateToastNotifier().Show(new ToastNotification(document));
        Environment.Exit(0);
    }
}
