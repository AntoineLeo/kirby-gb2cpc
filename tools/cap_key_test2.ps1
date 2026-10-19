Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win2 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
}
"@
$job = Start-Job -ScriptBlock {
  Set-Location "C:\projets\kirby-gb2cpc"
  & "C:\Program Files\Git\bin\sh.exe" tools/cpcshot.sh 14 build/demo/key_hold2.png build/kirby-demo2.dsk
}
Start-Sleep -Seconds 5
$p = Get-Process cap32 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($p) {
  $p.Refresh()
  if ($p.MainWindowHandle -ne 0) { [Win2]::SetForegroundWindow($p.MainWindowHandle) | Out-Null }
  Start-Sleep -Milliseconds 300
  [Win2]::keybd_event(0x50,0,0,[UIntPtr]::Zero)
  Start-Sleep -Seconds 4
  [Win2]::keybd_event(0x50,0,2,[UIntPtr]::Zero)
} else { Write-Output "cap32 not found" }
Wait-Job $job -Timeout 120 | Out-Null
Receive-Job $job
