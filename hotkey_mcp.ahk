#Requires AutoHotkey v2.0
#SingleInstance Force

; ================================
; 配置区
; ================================

PythonExe := "C:\Users\wangh\.conda\envs\doubao-mcp-bridge\python.exe"
BridgeScript := "D:\code\doubao-mcp-bridge\bridge.py"

Tip(msg, time := 1000) {
    TrayTip("MCP Bridge", msg, time)
}

; ================================
; F9
; 调用 bridge.py prompt
; 自动生成 MCP prompt
; 写入剪贴板并粘贴到当前输入框
; ================================

F9:: {

    global PythonExe, BridgeScript

    Tip("正在获取可用工具...")

    A_Clipboard := ""
    
    ;cmd := Format(
    ;    'cmd /c ""{1}" "{2}" prompt & pause"',
    ;    PythonExe,
    ;    BridgeScript
    ;)
    ; RunWait(cmd, , "Visible")

    cmd := Format(
        'cmd /c ""{1}" "{2}" prompt"',
        PythonExe,
        BridgeScript
    )
    RunWait(cmd, , "Hide")

    if Trim(A_Clipboard) = "" {
        Tip("Prompt 生成失败：剪贴板为空")
        return
    }

    Send("^v")
    Sleep(100)
    Send("{Enter}")
    Tip("Prompt 生成并粘贴成功")
}

; ================================
; F10
; 假设：
; 1. 你已经复制了 <MCP_CALL>...</MCP_CALL>
; 2. 当前光标位于豆包输入框
;
; 功能：
; - 调用 bridge.py call
; - Python 从剪贴板读取 MCP_CALL
; - Python 执行 MCP
; - Python 将 MCP_RESULT 写回剪贴板
; - AHK 自动粘贴并发送
; ================================

F10:: {

    global PythonExe, BridgeScript

    if Trim(A_Clipboard) = "" {
        Tip("剪贴板为空")
        return
    }

    if !InStr(A_Clipboard, "MCP_CALL_JSON") {
        Tip("剪贴板中未检测到 MCP_CALL_JSON")
        return
    }

    cmd := Format(
        'cmd /c ""{1}" "{2}" call"',
        PythonExe,
        BridgeScript
    )
    RunWait(cmd, , "Hide")

    if Trim(A_Clipboard) = "" {
        Tip("MCP 调用失败：剪贴板为空")
        return
    }

    if !InStr(A_Clipboard, "MCP_RESULT_JSON") {
        Tip("未检测到 MCP_RESULT_JSON")
        return
    }

    Send("^v")
    Sleep(100)
    Send("{Enter}")
}
