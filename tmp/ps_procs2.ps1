Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
  $_.CommandLine -match 'solar_system_collector|sero_space_weather|sero_autonomous_expansion'
} | ForEach-Object {
  $c = $_.CommandLine
  $t = if ($c -match 'solar_system_collector') {'SOLAR'} elseif ($c -match 'sero_space_weather') {'SW'} else {'AUTO'}
  "{0} {1} parent={2} born={3}" -f $t, $_.ProcessId, $_.ParentProcessId, $_.CreationDate
}
"parents:"
Get-CimInstance Win32_Process -Filter "ProcessId=5368 or ProcessId=19540 or ProcessId=12564 or ProcessId=14856" | ForEach-Object {
  "{0}: {1}" -f $_.ProcessId, $_.CommandLine.Substring(0,[Math]::Min(90,$_.CommandLine.Length))
}
