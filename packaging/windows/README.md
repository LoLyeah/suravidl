# Windows Packaging (Inno Setup)

## Compiler Command

To compile the per-user installer from the repository root (after building `dist\suravidl.exe` with PyInstaller):

```cmd
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=0.41.0 packaging\windows\suravidl.iss
```

The compiled installer is written to:
`packaging/windows/Output/suravidl-setup.exe`

## Runner Environment

GitHub's `windows-2022` runner has Inno Setup 6 preinstalled at:
`C:\Program Files (x86)\Inno Setup 6\ISCC.exe`

If Inno Setup is missing in a local environment or on a custom runner, install it via Chocolatey:

```powershell
choco install innosetup -y --no-progress
```

## What the Installer Does

- **Per-user install**: Installs into `{localappdata}\Programs\suravidl` (`%LOCALAPPDATA%\Programs\suravidl`) using `PrivilegesRequired=lowest` and `PrivilegesRequiredOverridesAllowed=none`. It requires no administrator rights and produces zero UAC prompts.
- **Start Menu shortcut**: Creates `{userprograms}\suravidl.lnk` in the user's Start Menu programs folder.
- **Desktop icon**: Includes an optional `desktopicon` task, unchecked by default to avoid cluttering the desktop.
- **Uninstaller in Windows Settings**: Registers uninstall metadata under `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{E8F67C29-7B1A-4D3E-9A52-3E6B20261004}_is1`, appearing in Windows Settings -> Installed Apps.
- **User data preservation**: On uninstall, `[UninstallDelete]` removes cached update installers in `{localappdata}\suravidl\updates`, but preserves the parent `{localappdata}\suravidl` directory (`jobs.db`, `settings.json`, cookies, and sessions).
- **Post-install launch**: Offers to launch `suravidl.exe` after an interactive install (`nowait postinstall skipifsilent`). Silent updates skip the auto-launch because the application engine handles its own restart.

## Silent Upgrade Invocation

The in-app updater invokes the installer during automatic updates with:

```cmd
suravidl-setup.exe /SILENT /SP- /NORESTART /CLOSEAPPLICATIONS
```

Flags explained:
- `/SILENT`: Runs unattended without wizard pages, showing only a small progress bar.
- `/SP-`: Skips the initial "This will install... Do you wish to continue?" prompt.
- `/NORESTART`: Prevents the installer from restarting the system.
- `/CLOSEAPPLICATIONS`: Uses Windows Restart Manager to close running `suravidl.exe` instances so executable files can be overwritten without rebooting.

## Assumptions to Verify on a Real Windows Box

1. **Preinstalled path**: Confirm `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` is present on the runner without needing Chocolatey.
2. **SmartScreen behavior**: Because the installer and portable binary are unsigned, SmartScreen displays an unrecognized application banner on first launch; users must click "More info" -> "Run anyway".
3. **Process locking on upgrade**: Ensure `suravidl.exe` exits cleanly before update application so the installer does not encounter `ERROR_SHARING_VIOLATION`.
4. **Data preservation across cycles**: Verify that updating or uninstalling never clears `{localappdata}\suravidl\jobs.db` or user configurations.
5. **Windows Settings registration**: Check that the app name, publisher, version, and icon display correctly in Windows Settings -> Apps / Installed Apps.

## Code signing (optional, not required)

The installer ships unsigned, so SmartScreen shows its standard warning until
the file has enough reputation. Free code-signing programs for open-source
projects exist (e.g. the SignPath Foundation); nothing in the build depends on
getting one.
