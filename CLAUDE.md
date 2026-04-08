# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TWStockAnalysis-RealtimeJob is a Python project for real-time Taiwan stock market analysis.

## Language & Tooling

- Python (see .gitignore for standard Python project patterns)
- No build/test/lint configuration exists yet — update this file when tooling is added


## Git Commit

- Commit message 不要加 `Co-Authored-By` 或任何 AI 相關署名

## Workflow

- **所有涉及 coding、架構規劃、寫程式的任務，一律請先設計完架構並釐清所有實作細節，有疑問的地方提出討論，沒問題再開始實作。** 不可以未經討論就直接動手寫 code。
- **每次改動如果涉及使用者行為、交易行為、alpha pick/sell 行為的變更，必須同步更新 `README.md`，讓 `README.md` 保持最新狀態。** 包括但不限於：新增/修改 CLI 參數、新增/修改交易邏輯、新增/修改資料表、新增/修改選股或賣出條件。
- **如果程式碼有修改 data source（新增、刪除、變更 API 來源或 fetch function），必須同步更新 `docs/data_sources.md`。**
