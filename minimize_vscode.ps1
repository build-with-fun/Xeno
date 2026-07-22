Add-Type @"
using System;
using System.Runtime.InteropServices;
public class W {
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@

$vscode = Get-Process -Name "Code" -ErrorAction SilentlyContinue
if ($vscode) {
    foreach ($p in $vscode) {
        if ($p.MainWindowHandle -ne 0) {
            [W]::ShowWindow($p.MainWindowHandle, 6) | Out-Null
            Write-Output "Minimized VS Code PID $($p.Id)"
        }
    }
} else {
    Write-Output "VS Code not running"
}
