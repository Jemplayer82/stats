using System.Globalization;
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

    public static readonly DependencyProperty LabelProperty =
        DependencyProperty.Register(
            nameof(Label),
            typeof(string),
            typeof(DialGauge),
            new FrameworkPropertyMetadata(string.Empty, FrameworkPropertyMetadataOptions.AffectsRender));

    public static readonly DependencyProperty ValueTextProperty =
        DependencyProperty.Register(
            nameof(ValueText),
            typeof(string),
            typeof(DialGauge),
            new FrameworkPropertyMetadata(string.Empty, FrameworkPropertyMetadataOptions.AffectsRender));

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

    public string Label
    {
        get => (string)GetValue(LabelProperty);
        set => SetValue(LabelProperty, value);
    }

    public string ValueText
    {
        get => (string)GetValue(ValueTextProperty);
        set => SetValue(ValueTextProperty, value);
    }

    protected override void OnRender(DrawingContext drawingContext)
    {
        base.OnRender(drawingContext);
        var center = new Point(ActualWidth / 2, ActualHeight / 2);
        var radius = Math.Max(1, Math.Min(ActualWidth, ActualHeight) / 2 - 11);
        const double startAngle = 180;
        const double totalSweep = 270;

        var faceBrush = new SolidColorBrush(Color.FromArgb(255, 9, 13, 18));
        drawingContext.DrawEllipse(faceBrush, null, center, radius + 6, radius + 6);

        var outerPen = new Pen(new SolidColorBrush(Color.FromArgb(255, 181, 191, 201)), 2);
        drawingContext.DrawEllipse(null, outerPen, center, radius + 5, radius + 5);

        var innerRimPen = new Pen(new SolidColorBrush(Color.FromArgb(255, 57, 68, 78)), 1);
        drawingContext.DrawEllipse(null, innerRimPen, center, radius + 2, radius + 2);

        DrawTicks(drawingContext, center, radius, startAngle, totalSweep);

        var backgroundPen = new Pen(new SolidColorBrush(Color.FromArgb(255, 43, 49, 54)), 7)
        {
            StartLineCap = PenLineCap.Round,
            EndLineCap = PenLineCap.Round
        };
        drawingContext.DrawGeometry(
            null,
            backgroundPen,
            CreateArc(center, radius - 3, startAngle, totalSweep));

        var progress = Math.Clamp(Progress, 0, 100);
        if (progress > 0)
        {
            var accentPen = new Pen(Accent ?? Brushes.CornflowerBlue, 7)
            {
                StartLineCap = PenLineCap.Round,
                EndLineCap = PenLineCap.Round
            };
            drawingContext.DrawGeometry(
                null,
                accentPen,
                CreateArc(center, radius - 3, startAngle, totalSweep * progress / 100));
        }

        var needleAngle = startAngle + (totalSweep * progress / 100);
        var needleEnd = PointOnCircle(center, radius - 14, needleAngle);
        var needlePen = new Pen(Brushes.White, ActualWidth >= 150 ? 3.2 : 2.2)
        {
            StartLineCap = PenLineCap.Round,
            EndLineCap = PenLineCap.Round
        };
        drawingContext.DrawLine(needlePen, center, needleEnd);
        drawingContext.DrawEllipse(Brushes.White, null, center, ActualWidth >= 150 ? 6 : 4, ActualWidth >= 150 ? 6 : 4);
        drawingContext.DrawEllipse(Brushes.Black, null, center, ActualWidth >= 150 ? 2.5 : 1.7, ActualWidth >= 150 ? 2.5 : 1.7);
        DrawCenterText(drawingContext, center);
    }

    private static void DrawTicks(
        DrawingContext drawingContext,
        Point center,
        double radius,
        double startAngle,
        double totalSweep)
    {
        const int tickCount = 60;
        for (var index = 0; index <= tickCount; index++)
        {
            var major = index % 10 == 0;
            var medium = index % 5 == 0;
            var angle = startAngle + (index * totalSweep / tickCount);
            var outer = PointOnCircle(center, radius + 1, angle);
            var inner = PointOnCircle(center, radius - (major ? 11 : medium ? 8 : 5), angle);
            var pen = new Pen(
                new SolidColorBrush(major
                    ? Color.FromArgb(255, 242, 244, 245)
                    : Color.FromArgb(190, 185, 193, 198)),
                major ? 1.8 : medium ? 1.2 : 0.8);
            drawingContext.DrawLine(pen, inner, outer);
        }

        var redlinePen = new Pen(new SolidColorBrush(Color.FromArgb(255, 220, 55, 55)), 3);
        drawingContext.DrawGeometry(
            null,
            redlinePen,
            CreateArc(center, radius - 3, startAngle + (totalSweep * 0.78), totalSweep * 0.22));
    }

    private void DrawCenterText(DrawingContext drawingContext, Point center)
    {
        var dpi = VisualTreeHelper.GetDpi(this).PixelsPerDip;
        var label = new FormattedText(
            Label,
            CultureInfo.CurrentCulture,
            FlowDirection.LeftToRight,
            new Typeface("Segoe UI Semibold"),
            ActualWidth >= 150 ? 13 : 9,
            Brushes.White,
            dpi);
        var value = new FormattedText(
            ValueText,
            CultureInfo.CurrentCulture,
            FlowDirection.LeftToRight,
            new Typeface("Segoe UI Semibold"),
            ActualWidth >= 150 ? 22 : 12,
            Brushes.White,
            dpi);

        drawingContext.DrawText(label, new Point(center.X - (label.Width / 2), center.Y - (ActualWidth >= 150 ? 20 : 16)));
        drawingContext.DrawText(value, new Point(center.X - (value.Width / 2), center.Y + (ActualWidth >= 150 ? 1 : 0)));
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
