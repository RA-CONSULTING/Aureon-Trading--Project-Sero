Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
  $_.CommandLine -match 'solar_system_collector|sero_space_weather|sero_autonomous_expansion'
} | ForEach-Object {
  "{0} parent={1} born={2} cmd={3}" -f $_.ProcessId, $_.ParentProcessId,
    $_.CreationDate, $_.CommandLine.Substring(0,[Math]::Min(95,$_.CommandLine.Length))
}
