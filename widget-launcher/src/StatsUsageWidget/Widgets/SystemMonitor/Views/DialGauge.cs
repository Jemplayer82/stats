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
        var center = new Point(ActualWidth / 2, ActualHeight / 2);
        var radius = Math.Max(1, Math.Min(ActualWidth, ActualHeight) / 2 - 11);
        const double startAngle = -90;
        const double totalSweep = 360;

        var faceBrush = new SolidColorBrush(Color.FromArgb(255, 18, 29, 43));
        drawingContext.DrawEllipse(faceBrush, null, center, radius + 6, radius + 6);

        var outerPen = new Pen(new SolidColorBrush(Color.FromArgb(255, 51, 70, 95)), 2);
        drawingContext.DrawEllipse(null, outerPen, center, radius + 5, radius + 5);

        DrawTicks(drawingContext, center, radius, startAngle);

        var backgroundPen = new Pen(new SolidColorBrush(Color.FromArgb(255, 38, 50, 68)), 7)
        {
            StartLineCap = PenLineCap.Round,
            EndLineCap = PenLineCap.Round
        };
        drawingContext.DrawEllipse(null, backgroundPen, center, radius - 3, radius - 3);

        var progress = Math.Clamp(Progress, 0, 100);
        if (progress > 0)
        {
            var accentPen = new Pen(Accent ?? Brushes.CornflowerBlue, 7)
            {
                StartLineCap = PenLineCap.Round,
                EndLineCap = PenLineCap.Round
            };
            if (progress >= 99.9)
            {
                drawingContext.DrawEllipse(null, accentPen, center, radius - 3, radius - 3);
            }
            else
            {
                drawingContext.DrawGeometry(
                    null,
                    accentPen,
                    CreateArc(center, radius - 3, startAngle, totalSweep * progress / 100));
            }
        }

        var needleAngle = startAngle + (totalSweep * progress / 100);
        var needleEnd = PointOnCircle(center, radius - 14, needleAngle);
        var needlePen = new Pen(Accent ?? Brushes.CornflowerBlue, 2.5)
        {
            StartLineCap = PenLineCap.Round,
            EndLineCap = PenLineCap.Round
        };
        drawingContext.DrawLine(needlePen, center, needleEnd);
        drawingContext.DrawEllipse(Accent ?? Brushes.CornflowerBlue, null, center, 5, 5);
        drawingContext.DrawEllipse(Brushes.White, null, center, 2, 2);
    }

    private static void DrawTicks(
        DrawingContext drawingContext,
        Point center,
        double radius,
        double startAngle)
    {
        for (var index = 0; index < 40; index++)
        {
            var major = index % 5 == 0;
            var angle = startAngle + (index * 9);
            var outer = PointOnCircle(center, radius + 1, angle);
            var inner = PointOnCircle(center, radius - (major ? 9 : 6), angle);
            var pen = new Pen(
                new SolidColorBrush(major
                    ? Color.FromArgb(255, 215, 224, 236)
                    : Color.FromArgb(170, 148, 163, 184)),
                major ? 1.5 : 1);
            drawingContext.DrawLine(pen, inner, outer);
        }
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
