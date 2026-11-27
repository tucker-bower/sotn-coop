# Registers the nightly maintenance run (scripts/nightly.py, D236) in Windows Task Scheduler:
# every night at 03:00, waking the PC if it sleeps, and catching up after a missed night. It runs
# with no window (conhost --headless), so nothing appears on the desktop.
#
#   powershell.exe -ExecutionPolicy Bypass -File scripts\nightly_schedule.ps1 [-Remove] [-At 03:00]
#
# Waking needs Windows' "Allow wake timers" (Power Options) on. To pause without removing the task,
# create local/nightly.stop, or open a GitHub issue labelled pause-nightly.
param([switch]$Remove, [string]$At = "03:00", [string]$Distro = "Ubuntu",
      [string]$Worktree = "/home/tucker/sotn-coop-work")
$name = "SOTN Co-op nightly"
if ($Remove) { Unregister-ScheduledTask -TaskName $name -Confirm:$false; return }
$cmd = "--headless wsl.exe -d $Distro -- bash -lc 'cd $Worktree && python3 scripts/nightly.py'"
$action = New-ScheduledTaskAction -Execute "conhost.exe" -Argument $cmd
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 6) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force |
    Select-Object TaskName, State
