Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
}
"@
$cap = "$env:LOCALAPPDATA\Caprice32\cap32-win64\cap32.exe"
$dsk = (Resolve-Path "build/kirby-demo2.dsk").Path
$out = (Join-Path (Get-Location) "build/demo/key_hold.png")
$tmp = "$env:TEMP\cpckey"; if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }; New-Item -ItemType Directory $tmp | Out-Null
$d = "\(CAP32_DELAY)"
$cmd = 'run"game' + "`n" + ($d * 3) + ($d * 3) + ($d * 3) + "\(CAP32_SCRNSHOT)\(CAP32_EXIT)"
$p = Start-Process -FilePath $cap -WorkingDirectory (Split-Path $cap) -ArgumentList @('-O','system.model=1','-O',"file.sdump_dir=$tmp",'-a',$cmd,$dsk) -PassThru
Start-Sleep -Seconds 4
$p.Refresh()
if ($p.MainWindowHandle -ne 0) { [Win]::SetForegroundWindow($p.MainWindowHandle) | Out-Null }
Start-Sleep -Milliseconds 300
[Win]::keybd_event(0x50,0,0,[UIntPtr]::Zero)
Start-Sleep -Seconds 3
[Win]::keybd_event(0x50,0,2,[UIntPtr]::Zero)
$p.WaitForExit(30000) | Out-Null
$shot = Get-ChildItem $tmp -Filter screenshot_*.png | Select-Object -Last 1
if ($shot) { Copy-Item $shot.FullName $out -Force; Write-Output "shot $out" } else { Write-Output "no shot" }
