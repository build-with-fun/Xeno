$desktop = [Environment]::GetFolderPath("Desktop")
$folderName = "NewFolder"
$folderPath = Join-Path $desktop $folderName
if (Test-Path $folderPath) {
    Write-Output "Folder already exists: $folderPath"
} else {
    New-Item -ItemType Directory -Path $folderPath -Force | Out-Null
    Write-Output "Created folder: $folderPath"
}
