Option Explicit
Dim shell, fso, folder, bat, logFolder, logFile, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

folder = fso.GetParentFolderName(WScript.ScriptFullName)
bat = fso.BuildPath(folder, "INICIAR-SEXTA-FEIRA.bat")
logFolder = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Sexta-Feira"
logFile = logFolder & "\launcher.log"

If Not fso.FileExists(bat) Then
  MsgBox "Nao encontrei o arquivo INICIAR-SEXTA-FEIRA.bat nesta pasta:" & vbCrLf & folder & vbCrLf & vbCrLf & "Deixe os dois arquivos na mesma pasta.", vbExclamation, "Sexta-Feira"
  WScript.Quit 1
End If

If Not fso.FolderExists(logFolder) Then
  fso.CreateFolder logFolder
End If

' Executa o inicializador oculto, mas registra erros para diagnostico.
command = "cmd.exe /d /c """"" & bat & """ >> """ & logFile & """ 2>&1"""
shell.CurrentDirectory = folder
shell.Run command, 0, False
