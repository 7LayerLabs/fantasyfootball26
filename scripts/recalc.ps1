# Recalculate the workbook with real Excel, save, and dump the QA tab.
$path = "C:\Users\derek\Downloads\Documents\2026_Fantasy_Football_Draft_Engine_100_PERCENT_FIXED.xlsx"
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
    $wb = $xl.Workbooks.Open($path)
    $xl.CalculateFullRebuild()
    while ($xl.CalculationState -ne 0) { Start-Sleep -Milliseconds 200 }  # 0 = xlDone
    $qa = $wb.Worksheets.Item("QA Checks")
    Write-Output "=== QA CHECKS ==="
    for ($r = 4; $r -le 40; $r++) {
        $name = $qa.Cells.Item($r, 1).Value2
        $exp = $qa.Cells.Item($r, 2).Value2
        $act = $qa.Cells.Item($r, 3).Text
        $st = $qa.Cells.Item($r, 4).Text
        if ($name -or $st) { Write-Output ("{0,-48} exp={1,-6} actual={2,-8} {3}" -f $name, $exp, $act, $st) }
    }
    $wb.Save()
    $wb.Close($false)
} finally {
    $xl.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}
Write-Output "RECALC DONE"
