# Generates placeholder PWA icons (dark background, green up-trend arrow, "ETF" text)
Add-Type -AssemblyName System.Drawing

$outDir = Join-Path $PSScriptRoot "..\public\icons"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

foreach ($size in 192, 512) {
  $bmp = New-Object System.Drawing.Bitmap($size, $size)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias
  $g.Clear([System.Drawing.ColorTranslator]::FromHtml('#1a1a2e'))

  $green = [System.Drawing.ColorTranslator]::FromHtml('#34d399')
  $pen = New-Object System.Drawing.Pen($green, [float]($size * 0.045))
  $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
  $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
  $pen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
  $pts = @(
    (New-Object System.Drawing.PointF([float]($size * 0.15), [float]($size * 0.62))),
    (New-Object System.Drawing.PointF([float]($size * 0.38), [float]($size * 0.44))),
    (New-Object System.Drawing.PointF([float]($size * 0.52), [float]($size * 0.54))),
    (New-Object System.Drawing.PointF([float]($size * 0.80), [float]($size * 0.28)))
  )
  $g.DrawLines($pen, $pts)

  $brush = New-Object System.Drawing.SolidBrush($green)
  $head = @(
    (New-Object System.Drawing.PointF([float]($size * 0.84), [float]($size * 0.24))),
    (New-Object System.Drawing.PointF([float]($size * 0.84), [float]($size * 0.42))),
    (New-Object System.Drawing.PointF([float]($size * 0.66), [float]($size * 0.24)))
  )
  $g.FillPolygon($brush, $head)

  $font = New-Object System.Drawing.Font('Arial', [float]($size * 0.16), [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
  $white = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
  $sf = New-Object System.Drawing.StringFormat
  $sf.Alignment = [System.Drawing.StringAlignment]::Center
  $rect = New-Object System.Drawing.RectangleF(0, [float]($size * 0.66), [float]$size, [float]($size * 0.25))
  $g.DrawString('ETF', $font, $white, $rect, $sf)

  $path = Join-Path $outDir ("icon-{0}x{0}.png" -f $size)
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose()
  $bmp.Dispose()
  Write-Host "Saved $path"
}
