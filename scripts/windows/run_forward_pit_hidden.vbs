Option Explicit

Dim shell, powershellExe, launcher, batchName, workspacePath, pythonExePath, batchConfigPath
Dim command, exitCode

If WScript.Arguments.Count <> 5 And WScript.Arguments.Count <> 6 Then
    WScript.Quit 2
End If

powershellExe = WScript.Arguments(0)
launcher = WScript.Arguments(1)
batchName = WScript.Arguments(2)
workspacePath = WScript.Arguments(3)
pythonExePath = WScript.Arguments(4)
If WScript.Arguments.Count = 6 Then
    batchConfigPath = WScript.Arguments(5)
End If

command = QuoteArgument(powershellExe) _
    & " -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File " & QuoteArgument(launcher) _
    & " -BatchName " & QuoteArgument(batchName) _
    & " -WorkspacePath " & QuoteArgument(workspacePath) _
    & " -PythonExePath " & QuoteArgument(pythonExePath)
If WScript.Arguments.Count = 6 Then
    command = command & " -BatchConfigPath " & QuoteArgument(batchConfigPath)
End If

Set shell = CreateObject("WScript.Shell")
exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode

Function QuoteArgument(ByVal value)
    QuoteArgument = Chr(34) & Replace(CStr(value), Chr(34), Chr(34) & Chr(34)) & Chr(34)
End Function
