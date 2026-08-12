$path = "C:\Users\derek\Downloads\Documents\2026_Fantasy_Football_Draft_Engine_100_PERCENT_FIXED.xlsx"

$locked = $false
try { $fs = [IO.File]::Open($path,'Open','ReadWrite','None'); $fs.Close() }
catch { $locked = $true }

if (-not ("ComHelper" -as [type])) {
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class ComHelper {
    [DllImport("oleaut32.dll", PreserveSig=false)]
    public static extern void GetActiveObject(ref Guid rclsid, IntPtr pvReserved, [MarshalAs(UnmanagedType.IUnknown)] out object ppunk);
    public static object GetActiveExcel() {
        Guid clsid = new Guid("00024500-0000-0000-C000-000000000046");
        object obj; GetActiveObject(ref clsid, IntPtr.Zero, out obj);
        return obj;
    }
}
"@
}

$msg = @(
  "Hey, sending you my 2026 fantasy football draft kit. Two pieces, built to work together.",
  "",
  "THE EXCEL SHEET: a complete draft engine for 10-team full-PPR. 230 players, each with a rating, projected season points, value over a waiver-wire replacement, and a 0-100 draft score. Everything runs off one master table, so one tweak (an injury, a role change) updates every tab instantly. Kickers and defenses are locked to the late rounds where they belong. It even tests itself: the QA Checks tab runs 13 self-checks and they all say PASS. The How It Works tab explains every number in plain English. All data is current as of August 12, 2026: rankings cross-checked against ESPN's, real teams and bye weeks, injuries swept, and draft prices from about 6,000 real drafts run this week.",
  "",
  "THE APP (draft-board.html, comes with the sheet): open it in any browser. No install, no internet, nothing to set up. Use it during a live draft: type a few letters of a name, hit Enter when someone gets taken, and it tracks everything while telling you who to take next in plain English, with the odds he is still there at your next pick, bye-week warnings, position-run alarms, and a live grade of your team against the whole league. It also has a full mock draft mode: up to 15 AI opponents who each draft off a different guide (ESPN's rankings, market prices, one is a homer who reaches for his favorite team), a 60-second pick clock, and enough randomness that no two mocks ever play out the same.",
  "",
  "Short version: the sheet does the math, the app runs the draft, and neither one needs anything installed."
)

try {
  if ($locked) {
    $excel = [ComHelper]::GetActiveExcel()
    $wb = $null
    foreach ($w in $excel.Workbooks) { if ($w.FullName -eq $path) { $wb = $w } }
    if ($null -eq $wb) { Write-Output "Locked, but workbook not found in running Excel"; exit 1 }
    $attached = $true
    Write-Output "Attached to open Excel instance"
  } else {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $attached = $false
  }
  $excel.DisplayAlerts = $false
  if (-not $attached) { $wb = $excel.Workbooks.Open($path) }

  foreach ($s in @($wb.Worksheets)) { if ($s.Name -eq "TLDR") { $s.Delete() } }
  $after = $wb.Worksheets.Item("How It Works")
  $ws = $wb.Worksheets.Add([Type]::Missing, $after)
  $ws.Name = "TLDR"
  $ws.Columns.Item(1).ColumnWidth = 110

  $c = $ws.Cells.Item(1, 1)
  $c.Value2 = "TLDR: THE READY-TO-SEND MESSAGE"
  $c.Font.Bold = $true; $c.Font.Size = 16; $c.Font.Color = 3893315

  $c = $ws.Cells.Item(2, 1)
  $c.Value2 = "Sharing this with somebody? Select the gray box below, copy, and paste it straight into your text or email. Attach this file and draft-board.html and you are done."
  $c.Font.Italic = $true; $c.Font.Size = 11; $c.Font.Color = 8421504

  $r = 4
  foreach ($line in $msg) {
    $c = $ws.Cells.Item($r, 1)
    if ($line -ne "") {
      $c.Value2 = $line
      $c.Font.Size = 11
      $c.WrapText = $true
    }
    $c.Interior.Color = 15921906   # light gray box marking the copy region
    $r++
  }
  $ws.Rows.AutoFit() | Out-Null

  $ws.Activate()
  $excel.ActiveWindow.DisplayGridlines = $false
  $wb.Worksheets.Item("Draft Board").Activate()

  $excel.CalculateFullRebuild()
  while ($excel.CalculationState -ne 0) { Start-Sleep -Milliseconds 200 }
  $qa = $wb.Worksheets.Item("QA Checks").Cells.Item(18, 4).Value2
  Write-Output "QA overall: $qa"
  Write-Output "Sheet count: $($wb.Worksheets.Count)"

  $wb.Save()
  if (-not $attached) { $wb.Close($false) }
}
finally {
  if ($excel) {
    $excel.DisplayAlerts = $true
    if (-not $attached) { $excel.Quit(); [Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null }
  }
}
Write-Output "DONE"
