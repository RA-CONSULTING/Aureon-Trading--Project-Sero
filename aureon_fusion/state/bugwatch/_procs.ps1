Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
  $c = $_.CommandLine
  if ($c -match 'master_launcher|unified_hub|organ_registry') {
    "{0} :: {1}" -f $_.ProcessId, $c.Substring(0, [Math]::Min(130, $c.Length))
  }
}
