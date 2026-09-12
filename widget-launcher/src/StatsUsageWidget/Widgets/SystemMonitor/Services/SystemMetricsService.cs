using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;

namespace StatsUsageWidget.Widgets.SystemMonitor.Services;

public sealed class SystemMetricsService : IDisposable
{
    private PerformanceCounter? _diskRead;
    private PerformanceCounter? _diskWrite;
    private readonly List<PerformanceCounter> _networkReceive = [];
    private readonly List<PerformanceCounter> _networkSend = [];
    private CpuTimes? _lastCpuTimes;

    public SystemMetricsService()
    {
        InitializeDiskCounters();
        InitializeNetworkCounters();
        PrimeCounters();
    }

    public SystemMetricsSnapshot Sample()
    {
        var cpu = ReadCpuPercent();
        var memory = ReadMemoryPercent();
        var diskReadBytes = ReadCounter(_diskRead);
        var diskWriteBytes = ReadCounter(_diskWrite);
        var networkReceiveBytes = ReadCounters(_networkReceive);
        var networkSendBytes = ReadCounters(_networkSend);

        return new SystemMetricsSnapshot
        {
            CpuPercent = cpu,
            MemoryPercent = memory,
            DiskReadMegabytesPerSecond = diskReadBytes / 1_000_000d,
            DiskWriteMegabytesPerSecond = diskWriteBytes / 1_000_000d,
            NetworkReceiveMegabitsPerSecond = networkReceiveBytes * 8d / 1_000_000d,
            NetworkSendMegabitsPerSecond = networkSendBytes * 8d / 1_000_000d
        };
    }

    public void Dispose()
    {
        _diskRead?.Dispose();
        _diskWrite?.Dispose();
        foreach (var counter in _networkReceive) counter.Dispose();
        foreach (var counter in _networkSend) counter.Dispose();
    }

    private void InitializeDiskCounters()
    {
        try
        {
            _diskRead = new PerformanceCounter("PhysicalDisk", "Disk Read Bytes/sec", "_Total", true);
            _diskWrite = new PerformanceCounter("PhysicalDisk", "Disk Write Bytes/sec", "_Total", true);
        }
        catch
        {
            _diskRead?.Dispose();
            _diskWrite?.Dispose();
            _diskRead = null;
            _diskWrite = null;
        }
    }

    private void InitializeNetworkCounters()
    {
        try
        {
            var category = new PerformanceCounterCategory("Network Interface");
            foreach (var instance in category.GetInstanceNames())
            {
                if (instance.Contains("Loopback", StringComparison.OrdinalIgnoreCase) ||
                    instance.Contains("isatap", StringComparison.OrdinalIgnoreCase) ||
                    instance.Contains("Teredo", StringComparison.OrdinalIgnoreCase))
                    continue;

                _networkReceive.Add(new PerformanceCounter(
                    "Network Interface", "Bytes Received/sec", instance, true));
                _networkSend.Add(new PerformanceCounter(
                    "Network Interface", "Bytes Sent/sec", instance, true));
            }
        }
        catch
        {
            // The network category is optional on locked-down or very early Windows sessions.
        }
    }

    private void PrimeCounters()
    {
        _ = ReadCounter(_diskRead);
        _ = ReadCounter(_diskWrite);
        _ = ReadCounters(_networkReceive);
        _ = ReadCounters(_networkSend);
    }

    private static double ReadCounter(PerformanceCounter? counter)
    {
        if (counter is null) return 0;
        try
        {
            return Math.Max(0, counter.NextValue());
        }
        catch
        {
            return 0;
        }
    }

    private static double ReadCounters(IEnumerable<PerformanceCounter> counters)
    {
        return counters.Sum(ReadCounter);
    }

    private double ReadCpuPercent()
    {
        if (!GetSystemTimes(out var idle, out var kernel, out var user)) return 0;

        var current = new CpuTimes(
            FileTimeToUInt64(idle),
            FileTimeToUInt64(kernel),
            FileTimeToUInt64(user));
        var previous = _lastCpuTimes;
        _lastCpuTimes = current;
        if (previous is null) return 0;

        var totalDelta = (current.Kernel + current.User) - (previous.Value.Kernel + previous.Value.User);
        var idleDelta = current.Idle - previous.Value.Idle;
        if (totalDelta <= 0) return 0;

        return Math.Clamp((1 - (idleDelta / (double)totalDelta)) * 100, 0, 100);
    }

    private static double ReadMemoryPercent()
    {
        var status = new MemoryStatusEx { Length = (uint)Marshal.SizeOf<MemoryStatusEx>() };
        if (!GlobalMemoryStatusEx(ref status) || status.TotalPhysicalMemory == 0) return 0;

        var used = status.TotalPhysicalMemory - status.AvailablePhysicalMemory;
        return Math.Clamp(used * 100d / status.TotalPhysicalMemory, 0, 100);
    }

    private static ulong FileTimeToUInt64(System.Runtime.InteropServices.ComTypes.FILETIME value)
    {
        return ((ulong)(uint)value.dwHighDateTime << 32) | (uint)value.dwLowDateTime;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetSystemTimes(
        out System.Runtime.InteropServices.ComTypes.FILETIME idleTime,
        out System.Runtime.InteropServices.ComTypes.FILETIME kernelTime,
        out System.Runtime.InteropServices.ComTypes.FILETIME userTime);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GlobalMemoryStatusEx(ref MemoryStatusEx status);

    [StructLayout(LayoutKind.Sequential)]
    private struct MemoryStatusEx
    {
        public uint Length;
        public uint MemoryLoad;
        public ulong TotalPhysicalMemory;
        public ulong AvailablePhysicalMemory;
        public ulong TotalPageFile;
        public ulong AvailablePageFile;
        public ulong TotalVirtual;
        public ulong AvailableVirtual;
        public ulong AvailableExtendedVirtual;
    }

    private readonly record struct CpuTimes(ulong Idle, ulong Kernel, ulong User);
}

public sealed class SystemMetricsSnapshot
{
    public double CpuPercent { get; init; }
    public double MemoryPercent { get; init; }
    public double DiskReadMegabytesPerSecond { get; init; }
    public double DiskWriteMegabytesPerSecond { get; init; }
    public double NetworkReceiveMegabitsPerSecond { get; init; }
    public double NetworkSendMegabitsPerSecond { get; init; }

    public double DiskMegabytesPerSecond =>
        DiskReadMegabytesPerSecond + DiskWriteMegabytesPerSecond;

    public double NetworkMegabitsPerSecond =>
        NetworkReceiveMegabitsPerSecond + NetworkSendMegabitsPerSecond;

    public string DiskDetail => string.Create(
        CultureInfo.CurrentCulture,
        $"R {DiskReadMegabytesPerSecond:0.0} · W {DiskWriteMegabytesPerSecond:0.0} MB/s");

    public string NetworkDetail => string.Create(
        CultureInfo.CurrentCulture,
        $"↓ {NetworkReceiveMegabitsPerSecond:0.0} · ↑ {NetworkSendMegabitsPerSecond:0.0} Mb/s");
}
