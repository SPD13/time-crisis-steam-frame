# Steam Frame: turn on Developer Mode and start "Lepton Development" from the library first.
param([string]$FrameHost='frame.local', [string]$Apk, [string]$Serial)
$ErrorActionPreference='Stop'
if(!$Apk){$Apk=Join-Path $PSScriptRoot 'artifacts\frame\TimeCrisisVR-frame-debug.apk'}
if(!(Test-Path -LiteralPath $Apk)){throw 'APK missing. Run Build-Frame.ps1 first.'}
$adb=if(Get-Command adb -ErrorAction SilentlyContinue){(Get-Command adb).Source}else{'C:\platform-tools\adb.exe'}
if(!$Serial){& $adb connect $FrameHost | Out-Host;$Serial=if($FrameHost -match ':'){$FrameHost}else{"${FrameHost}:5555"}}
$targetArgs=@('-s',$Serial)
& $adb @targetArgs get-state
if($LASTEXITCODE -ne 0){throw 'Steam Frame not reachable: enable Developer Mode, start Lepton Development, then retry (or pass -Serial).'}
& $adb @targetArgs install -r $Apk
if($LASTEXITCODE -ne 0){throw 'APK installation failed.'}
$activity=(& $adb @targetArgs shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p org.timecrisis.frame | Select-Object -Last 1).Trim()
if($LASTEXITCODE -ne 0 -or $activity -notmatch '^org\.timecrisis\.frame/org\.timecrisis\.quest\.(MainActivity|LauncherActivity)$'){throw 'Cannot resolve the app launcher.'}
& $adb @targetArgs shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n $activity
if($LASTEXITCODE -ne 0){throw 'APK launch failed.'}
