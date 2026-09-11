# Stats Usage Widget for Widget Launcher

This is a native [Widget Launcher](https://github.com/chanallenk/widgetlauncher.extension) extension for the Stats `/api/widget/usage` endpoint. It displays Codex, Claude, Ollama, and Gemini usage in a desktop widget.

## Install locally

Requirements:

- Windows 11 x64
- Widget Launcher 6.x
- .NET 10 SDK

Open PowerShell in this directory and run:

```powershell
winget install Microsoft.DotNet.SDK.10
Set-ExecutionPolicy -Scope Process Bypass
.\Install-Local.ps1
```

The installer prompts for Windows administrator approval so it can trust the local test certificate and install the MSIX package. After it finishes:

1. Open Widget Launcher.
2. Open its settings and enable **Developer Mode**.
3. Refresh extensions, then add **Stats AI Usage**.
4. Open the widget settings and enter the complete address you use to open Stats, such as `http://192.168.1.10` or `https://stats.example.com`.
5. Select the services to display, choose a refresh interval, and use **Test connection**.
6. Save the widget settings.

The built installer is written to `artifacts/StatsUsageWidget.msix`.

## Development preview

Build and run the WPF project to preview the widget and settings without installing the MSIX:

```powershell
dotnet run --project .\src\StatsUsageWidget\StatsUsageWidget.csproj -c Release -p:Platform=x64
```

The extension targets `net10.0-windows`, x64, and Widget Launcher extension API 6.0.1.
