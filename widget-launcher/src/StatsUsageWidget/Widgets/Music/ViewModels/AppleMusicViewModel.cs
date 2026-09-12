using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using StatsUsageWidget.Widgets.Music;
using Windows.Media.Control;

namespace StatsUsageWidget.Widgets.Music.ViewModels;

public partial class AppleMusicViewModel : ObservableObject, IDisposable
{
    private readonly SemaphoreSlim _refreshGate = new(1, 1);
    private readonly CancellationTokenSource _shutdown = new();
    private GlobalSystemMediaTransportControlsSessionManager? _manager;
    private GlobalSystemMediaTransportControlsSession? _session;
    private Task? _pollingTask;

    public Action<string, string>? Logger { get; set; }

    [ObservableProperty]
    private string _songTitle = "Nothing playing";

    [ObservableProperty]
    private string _artist = "Open Apple Music to start listening";

    [ObservableProperty]
    private string _album = string.Empty;

    [ObservableProperty]
    private ImageSource? _albumArt;

    [ObservableProperty]
    private string _playPauseGlyph = "▶";

    [ObservableProperty]
    private string _playbackStatus = "APPLE MUSIC";

    [ObservableProperty]
    private bool _canControl;

    [ObservableProperty]
    private int _transparencyPercent = 5;

    [ObservableProperty]
    private double _temporaryTransparencyPercent = 5;

    [ObservableProperty]
    private Brush _widgetBackground = CreateBackgroundBrush(5);

    public AppleMusicWidgetSettings ToSettings()
    {
        return new AppleMusicWidgetSettings { TransparencyPercent = TransparencyPercent };
    }

    public void LoadSettings(AppleMusicWidgetSettings settings)
    {
        TransparencyPercent = Math.Clamp(settings.TransparencyPercent, 0, 100);
        TemporaryTransparencyPercent = TransparencyPercent;
        WidgetBackground = CreateBackgroundBrush(TransparencyPercent);
    }

    public void LoadTemporarySettings()
    {
        TemporaryTransparencyPercent = TransparencyPercent;
        WidgetBackground = CreateBackgroundBrush(TransparencyPercent);
    }

    public void ApplySettings()
    {
        TransparencyPercent = Math.Clamp((int)Math.Round(TemporaryTransparencyPercent), 0, 100);
        TemporaryTransparencyPercent = TransparencyPercent;
        WidgetBackground = CreateBackgroundBrush(TransparencyPercent);
    }

    public void DiscardSettings()
    {
        TemporaryTransparencyPercent = TransparencyPercent;
        WidgetBackground = CreateBackgroundBrush(TransparencyPercent);
    }

    partial void OnTemporaryTransparencyPercentChanged(double value)
    {
        WidgetBackground = CreateBackgroundBrush(value);
    }

    public void Start()
    {
        if (_pollingTask is not null) return;
        _pollingTask = PollAsync(_shutdown.Token);
    }

    public async Task RefreshAsync()
    {
        if (!await _refreshGate.WaitAsync(0)) return;
        try
        {
            _manager ??= await GlobalSystemMediaTransportControlsSessionManager.RequestAsync();
            _session = FindAppleMusicSession(_manager);

            if (_session is null)
            {
                await UpdateUiAsync(() =>
                {
                    SongTitle = "Nothing playing";
                    Artist = "Open Apple Music to start listening";
                    Album = string.Empty;
                    AlbumArt = null;
                    PlayPauseGlyph = "▶";
                    PlaybackStatus = "APPLE MUSIC";
                    CanControl = false;
                });
                return;
            }

            var media = await _session.TryGetMediaPropertiesAsync();
            var playback = _session.GetPlaybackInfo();
            var artwork = await ReadArtworkAsync(media.Thumbnail);
            var isPlaying = playback.PlaybackStatus ==
                            GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing;

            await UpdateUiAsync(() =>
            {
                SongTitle = string.IsNullOrWhiteSpace(media.Title) ? "Unknown song" : media.Title;
                Artist = string.IsNullOrWhiteSpace(media.Artist) ? "Apple Music" : media.Artist;
                Album = media.AlbumTitle ?? string.Empty;
                AlbumArt = artwork;
                PlayPauseGlyph = isPlaying ? "⏸" : "▶";
                PlaybackStatus = isPlaying ? "NOW PLAYING" : "PAUSED";
                CanControl = true;
            });
        }
        catch (OperationCanceledException) when (_shutdown.IsCancellationRequested)
        {
        }
        catch (Exception ex)
        {
            Logger?.Invoke("Apple Music", ex.Message);
            await UpdateUiAsync(() =>
            {
                PlaybackStatus = "APPLE MUSIC";
                SongTitle = "Apple Music is unavailable";
                Artist = "Click the artwork to open the app";
                Album = string.Empty;
                AlbumArt = null;
                CanControl = false;
            });
        }
        finally
        {
            _refreshGate.Release();
        }
    }

    [RelayCommand]
    private async Task PreviousAsync()
    {
        if (_session is null) return;
        await _session.TrySkipPreviousAsync();
        await Task.Delay(200);
        await RefreshAsync();
    }

    [RelayCommand]
    private async Task TogglePlayPauseAsync()
    {
        if (_session is null)
        {
            OpenAppleMusic();
            return;
        }
        await _session.TryTogglePlayPauseAsync();
        await Task.Delay(150);
        await RefreshAsync();
    }

    [RelayCommand]
    private async Task NextAsync()
    {
        if (_session is null) return;
        await _session.TrySkipNextAsync();
        await Task.Delay(200);
        await RefreshAsync();
    }

    [RelayCommand]
    private void OpenAppleMusic()
    {
        try
        {
            Process.Start(new ProcessStartInfo("music:") { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            Logger?.Invoke("Open Apple Music", ex.Message);
        }
    }

    private async Task PollAsync(CancellationToken cancellationToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(2));
        await RefreshAsync();
        try
        {
            while (await timer.WaitForNextTickAsync(cancellationToken))
            {
                await RefreshAsync();
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
        }
    }

    private static GlobalSystemMediaTransportControlsSession? FindAppleMusicSession(
        GlobalSystemMediaTransportControlsSessionManager manager)
    {
        return manager.GetSessions().FirstOrDefault(session =>
        {
            var source = session.SourceAppUserModelId ?? string.Empty;
            return source.Contains("AppleMusic", StringComparison.OrdinalIgnoreCase) ||
                   source.Contains("AppleInc", StringComparison.OrdinalIgnoreCase);
        });
    }

    private static async Task<ImageSource?> ReadArtworkAsync(
        Windows.Storage.Streams.IRandomAccessStreamReference? thumbnail)
    {
        if (thumbnail is null) return null;
        using var randomAccessStream = await thumbnail.OpenReadAsync();
        using var stream = randomAccessStream.AsStreamForRead();
        using var memory = new MemoryStream();
        await stream.CopyToAsync(memory);
        memory.Position = 0;

        var image = new BitmapImage();
        image.BeginInit();
        image.CacheOption = BitmapCacheOption.OnLoad;
        image.StreamSource = memory;
        image.EndInit();
        image.Freeze();
        return image;
    }

    private static Brush CreateBackgroundBrush(double transparencyPercent)
    {
        var opacity = 1 - (Math.Clamp(transparencyPercent, 0, 100) / 100d);
        var alpha = (byte)Math.Round(255 * opacity);
        var brush = new SolidColorBrush(Color.FromArgb(alpha, 12, 12, 16));
        brush.Freeze();
        return brush;
    }

    private static async Task UpdateUiAsync(Action action)
    {
        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher is null || dispatcher.CheckAccess())
        {
            action();
            return;
        }
        await dispatcher.InvokeAsync(action);
    }

    public void Dispose()
    {
        _shutdown.Cancel();
    }
}
