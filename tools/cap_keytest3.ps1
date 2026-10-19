Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win3 { [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h); [DllImport("user32.dll")] public static extern void keybd_event(byte v, byte s, uint f, UIntPtr e); }
"@
$job = Start-Job -ScriptBlock { Set-Location "C:\projets\kirby-gb2cpc"; & "C:\Program Files\Git\bin\sh.exe" tools/cpcshot.sh 12 build/demo/keytest_shot.png build/demo/keytest.dsk }
Start-Sleep 5
$p=Get-Process cap32 -ErrorAction SilentlyContinue | Select-Object -First 1
if($p){$p.Refresh(); if($p.MainWindowHandle -ne 0){[Win3]::SetForegroundWindow($p.MainWindowHandle)|Out-Null}; Start-Sleep -Milliseconds 300; [Win3]::keybd_event(0x50,0,0,[UIntPtr]::Zero); Start-Sleep 4; [Win3]::keybd_event(0x50,0,2,[UIntPtr]::Zero)} else {"no cap32"}
Wait-Job $job -Timeout 120 | Out-Null; Receive-Job $job
