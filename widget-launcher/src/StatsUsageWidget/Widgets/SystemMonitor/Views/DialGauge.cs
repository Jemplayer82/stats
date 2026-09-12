using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace StatsUsageWidget.Widgets.SystemMonitor.Views;

public sealed class DialGauge : FrameworkElement
{
    public static readonly DependencyProperty ProgressProperty =
        DependencyProperty.Register(
            nameof(Progress),
            typeof(double),
            typeof(DialGauge),
            new FrameworkPropertyMetadata(0d, FrameworkPropertyMetadataOptions.AffectsRender));

    public static readonly DependencyProperty AccentProperty =
        DependencyProperty.Register(
            nameof(Accent),
            typeof(Brush),
            typeof(DialGauge),
            new FrameworkPropertyMetadata(Brushes.CornflowerBlue, FrameworkPropertyMetadataOptions.AffectsRender));

    public double Progress
    {
        get => (double)GetValue(ProgressProperty);
        set => SetValue(ProgressProperty, value);
    }

    public Brush Accent
    {
        get => (Brush)GetValue(AccentProperty);
        set => SetValue(AccentProperty, value);
    }

    protected override void OnRender(DrawingContext drawingContext)
    {
        base.OnRender(drawingContext);
        var center = new Point(ActualWidth / 2, ActualHeight / 2 + 2);
        var radius = Math.Max(1, Math.Min(ActualWidth, ActualHeight) / 2 - 9);
        const double startAngle = 135;
        const double totalSweep = 270;

        var backgroundPen = new Pen(new SolidColorBrush(Color.FromArgb(255, 38, 50, 68)), 8)
        {
            StartLineCap = PenLineCap.Round,
            EndLineCap = PenLineCap.Round
        };
        drawingContext.DrawGeometry(null, backgroundPen, CreateArc(center, radius, startAngle, totalSweep));

        var progress = Math.Clamp(Progress, 0, 100);
        if (progress <= 0) return;

        var accentPen = new Pen(Accent ?? Brushes.CornflowerBlue, 8)
        {
            StartLineCap = PenLineCap.Round,
            EndLineCap = PenLineCap.Round
        };
        drawingContext.DrawGeometry(
            null,
            accentPen,
            CreateArc(center, radius, startAngle, totalSweep * progress / 100));
    }

    private static StreamGeometry CreateArc(Point center, double radius, double startAngle, double sweep)
    {
        var start = PointOnCircle(center, radius, startAngle);
        var end = PointOnCircle(center, radius, startAngle + sweep);
        var geometry = new StreamGeometry();
        using (var context = geometry.Open())
        {
            context.BeginFigure(start, false, false);
            context.ArcTo(
                end,
                new Size(radius, radius),
                0,
                sweep > 180,
                SweepDirection.Clockwise,
                true,
                false);
        }
        geometry.Freeze();
        return geometry;
    }

    private static Point PointOnCircle(Point center, double radius, double angle)
    {
        var radians = angle * Math.PI / 180;
        return new Point(
            center.X + radius * Math.Cos(radians),
            center.Y + radius * Math.Sin(radians));
    }
}
