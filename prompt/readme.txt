https://gemini.google.com/share/2fc2fa49817b


🏛️ 投行級量化交易系統 (Alpha-Prime) 構建 Prompt
角色設定：

你是一位在頂級對沖基金（如 Citadel 或 Two Sigma）工作的資深量化架構師。你現在需要指導我從零構建一個企業級的美股 Swing Trade 系統。該系統必須具備高並發處理能力、多因子風險控制和個股獨立建模能力。

任務目標：

請為我設計並分模塊編寫 Alpha-Prime 系統的核心框架。系統需接入 Alpaca API，並結合深度學習與金融工程。

模塊一：數據完整性與清洗引擎 (Data Integrity Engine)
具體要求：

校準邏輯： 編寫一個 DataSanitizer 類。在訓練前自動檢測數據缺失、異常毛刺（Outliers）以及因拆股導致的價格跳空。

時序對齊： 確保所有個股數據與標普 500 ($SPY) 的交易日曆嚴格對齊，處理非交易日數據。

多維特徵： 除了 OHLCV，需集成 Volatility（波動率）、Turnover Rate（換手率）和 Intraday Range（日內振幅）。

模塊二：基於 FinBERT 的時事感應器 (Event Sentiment Pipeline)
具體要求：

NLP 接入： 調用 Alpaca News API 或同類源。

情緒量化： 使用預訓練的 ProsusAI/finbert 對新聞進行分類（正面、負面、中性）。

板塊映射： 建立 Ticker-to-Sector 映射。當發生特定宏觀事件（如戰爭、聯準會決議）時，自動計算該事件對特定板塊的 Impact Score，並作為特徵輸入給 LSTM。

模塊三：個股分佈式模型工廠 (Distributed Model Factory)
具體要求：

架構： 採用 PyTorch Lightning 或類似框架，支持 GPU 加速。

模型規範： LSTM 後端需加入 Attention Mechanism (注意力機制)，讓模型學會辨識哪些歷史日期對未來更有參考價值。

自動化 Pipeline： Pipeline = (Data Scaling -> Sequence Creation -> Training -> Model Checkpointing -> Performance Logging)。

模塊四：組合優化與風控引擎 (Portfolio & Risk Engine) —— 投行核心
具體要求：

板塊中性化 (Sector Neutrality)： 算法在選股時，必須限制單一板塊的權重不得超過總倉位的 30%。

相關性過濾： 計算入選股票間的 Pearson Correlation。如果兩隻股票相關性 > 0.8，則只取預測信心值最高的一隻。

動態倉位 (Kelly Criterion)： 根據模型輸出的「信心評分」與歷史「勝率」，利用凱利公式自動分配每隻股票的買入股數。

模塊五：生產級執行與監控 (Production Executor)
具體要求：

訂單管理： 實現 Bracket Orders。買入的同時自動掛上 Trailing Stop（移動止損）和 Profit Taker。

虛擬回測回調： 實現一個 Paper Trading 與 Live Trading 的一鍵切換開關，且兩者共享同一套日誌邏輯。

🛠️ 專業工程建議（針對你現在的進度）：
作為工程師，我建議你不要先寫 LSTM 訓練代碼。專業的流程應該是：

第一步：定義 Data Schema。 確保你的數據庫能同時存下「價格數據」、「技術指標」和「新聞情緒分數」。

第二步：寫回測系統 (Backtester)。 在你寫出預測模型之前，你必須先有一個能準確計算「滑點」和「稅費」的模擬環境。否則你的 AI 預測得再準，你也沒法驗證它是否真的能賺錢。

你想讓我先幫你生成哪一個模塊的具體代碼？

A. 數據完整性引擎（確保數據沒問題是量化的第一步）。

B. 時事感應器模塊（整合 NLP 情緒與板塊影響）。

C. 帶有 Attention 機制的 LSTM 個股模型架構。