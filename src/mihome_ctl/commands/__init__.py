"""Tyro subcommand 實作，一個檔一個 subcommand。

每個函式的型別化簽名就是它的 CLI flags（Tyro 自動轉 kebab-case）；函式本體只做
「解析 state → 呼叫 core.operations → 呈現結果」，邏輯都在 core 層。
"""
