Option Explicit

Dim shell, powershellExe, launcher, batchName, workspacePath, pythonExePath
Dim command, exitCode

If WScript.Arguments.Count <> 5 Then
    WScript.Quit 2
End If

powershellExe = WScript.Arguments(0)
launcher = WScript.Arguments(1)
batchName = WScript.Arguments(2)
workspacePath = WScript.Arguments(3)
pythonExePath = WScript.Arguments(4)

command = QuoteArgument(powershellExe) _
    & " -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File " & QuoteArgument(launcher) _
    & " -BatchName " & QuoteArgument(batchName) _
    & " -WorkspacePath " & QuoteArgument(workspacePath) _
    & " -PythonExePath " & QuoteArgument(pythonExePath)

Set shell = CreateObject("WScript.Shell")
exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode

Function QuoteArgument(ByVal value)
    QuoteArgument = Chr(34) & Replace(CStr(value), Chr(34), Chr(34) & Chr(34)) & Chr(34)
End Function