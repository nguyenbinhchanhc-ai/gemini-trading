// ==========================================================================
// GEMINI QUANTUM TRADING CONSOLE - APP LOGIC (VANILLA JAVASCRIPT)
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const connectionBadge = document.getElementById('connection-status');
    const connectionText = connectionBadge.querySelector('.status-text');
    const btnAnalyzeNow = document.getElementById('btn-analyze-now');
    const btnSettingsToggle = document.getElementById('btn-settings-toggle');
    
    // Sleek Market Ribbon Elements
    const stripSymbol = document.getElementById('strip-symbol');
    const stripPrice = document.getElementById('strip-price');
    const stripChange = document.getElementById('strip-change');
    const stripVolume = document.getElementById('strip-volume');
    const stripHigh = document.getElementById('strip-high');
    const stripLow = document.getElementById('strip-low');
    const stripLastAnalysis = document.getElementById('strip-last-analysis');
    
    // Indicators DOM Elements (Values)
    const indEma9 = document.getElementById('ind-ema9');
    const indEma21 = document.getElementById('ind-ema21');
    const indEma50 = document.getElementById('ind-ema50');
    const indEma200 = document.getElementById('ind-ema200');
    const indRsi = document.getElementById('ind-rsi');
    const indStochk = document.getElementById('ind-stochk');
    const indStochd = document.getElementById('ind-stochd');
    const indAtr = document.getElementById('ind-atr');
    const indMacd = document.getElementById('ind-macd');
    const indMacdsig = document.getElementById('ind-macdsig');
    const indBbhigh = document.getElementById('ind-bbhigh');
    const indBblow = document.getElementById('ind-bblow');
    const indAdx = document.getElementById('ind-adx');
    const indCmf = document.getElementById('ind-cmf');
    const indObv = document.getElementById('ind-obv');
    
    // Indicators Status Column DOM Elements
    const statusEma9 = document.getElementById('status-ema9');
    const statusEma21 = document.getElementById('status-ema21');
    const statusEma50 = document.getElementById('status-ema50');
    const statusEma200 = document.getElementById('status-ema200');
    const statusRsi = document.getElementById('status-rsi');
    const statusStoch = document.getElementById('status-stoch');
    const statusStochd = document.getElementById('status-stochd');
    const statusAtr = document.getElementById('status-atr');
    const statusMacd = document.getElementById('status-macd');
    const statusMacdsig = document.getElementById('status-macdsig');
    const statusBbhigh = document.getElementById('status-bbhigh');
    const statusBblow = document.getElementById('status-bblow');
    const statusAdx = document.getElementById('status-adx');
    const statusCmf = document.getElementById('status-cmf');
    const statusObv = document.getElementById('status-obv');
    
    // AI Panel elements
    const aiSignal = document.getElementById('ai-signal');
    const aiConfidence = document.getElementById('ai-confidence');
    const aiConfidenceBar = document.getElementById('ai-confidence-bar');
    const aiTp = document.getElementById('ai-tp');
    const aiSl = document.getElementById('ai-sl');
    const aiTimeframe = document.getElementById('ai-timeframe');
    const aiRisk = document.getElementById('ai-risk');
    const aiIndicatorsText = document.getElementById('ai-indicators-text');
    const aiRationaleText = document.getElementById('ai-rationale-text');    
    
    // Sentiment & Orderbook DOM Elements
    const sentBidBar = document.getElementById('sentiment-bid-bar');
    const sentBidPct = document.getElementById('sentiment-bid-percentage');
    const sentAskBar = document.getElementById('sentiment-ask-bar');
    const sentAskPct = document.getElementById('sentiment-ask-percentage');
    const sentBidWall = document.getElementById('sent-bid-wall');
    const sentBidWallVol = document.getElementById('sent-bid-wall-vol');
    const sentAskWall = document.getElementById('sent-ask-wall');
    const sentAskWallVol = document.getElementById('sent-ask-wall-vol');


    // Tabs
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const terminalLogs = document.getElementById('terminal-logs');
    const analysisHistoryList = document.getElementById('analysis-history-list');
    
    // Modal
    const settingsModal = document.getElementById('settings-modal');
    const closeModalElements = document.querySelectorAll('.close-modal, .close-modal-btn');
    const settingsForm = document.getElementById('settings-form');
    const inputSymbol = document.getElementById('input-symbol');
    const selectTimeframe = document.getElementById('select-timeframe');
    const inputInterval = document.getElementById('input-interval');

    // Global State
    let socket = null;
    let currentSymbol = 'BTC/USDT';
    let analysisHistory = [];

    // --- Tab Switching Logic ---
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-tab');
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });

    // --- Settings Modal Logic ---
    btnSettingsToggle.addEventListener('click', () => {
        inputSymbol.value = currentSymbol;
        settingsModal.style.display = 'block';
    });

    closeModalElements.forEach(el => {
        el.addEventListener('click', () => {
            settingsModal.style.display = 'none';
        });
    });

    window.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            settingsModal.style.display = 'none';
        }
    });

    // --- State Update Function ---
    function updateBotState(state) {
        currentSymbol = state.trade_symbol;
        stripSymbol.innerText = currentSymbol;
        stripLastAnalysis.innerText = state.last_analysis_time;
        updateAiDecisionUI(state.last_recommendation);
    }

    function updateAiDecisionUI(recData) {
        const rec = recData.recommendation || 'HOLD';
        aiSignal.innerText = rec;
        
        aiSignal.className = 'signal-value';
        if (rec === 'BUY') {
            aiSignal.classList.add('signal-buy');
        } else if (rec === 'SELL') {
            aiSignal.classList.add('signal-sell');
        } else {
            aiSignal.classList.add('signal-hold');
        }

        const conf = recData.confidence || 0;
        aiConfidence.innerText = `${conf}%`;
        aiConfidenceBar.style.width = `${conf}%`;

        if (rec === 'BUY') {
            aiConfidenceBar.style.backgroundColor = 'var(--color-green)';
        } else if (rec === 'SELL') {
            aiConfidenceBar.style.backgroundColor = 'var(--color-red)';
        } else {
            aiConfidenceBar.style.backgroundColor = 'var(--color-yellow)';
        }

        aiTp.innerText = recData.take_profit ? `$${parseFloat(recData.take_profit).toLocaleString()}` : '--';
        aiSl.innerText = recData.stop_loss ? `$${parseFloat(recData.stop_loss).toLocaleString()}` : '--';
        aiTimeframe.innerText = recData.estimated_timeframe || '--';
        
        const risk = recData.risk_percentage || 0;
        aiRisk.innerText = recData.risk_percentage ? `${risk}%` : '--';
        
        if (risk > 50) {
            aiRisk.style.color = 'var(--color-red)';
            aiRisk.style.textShadow = '0 0 8px rgba(255, 23, 68, 0.3)';
        } else if (risk > 25) {
            aiRisk.style.color = 'var(--color-yellow)';
            aiRisk.style.textShadow = '0 0 8px rgba(255, 235, 59, 0.3)';
        } else {
            aiRisk.style.color = 'var(--color-green)';
            aiRisk.style.textShadow = '0 0 8px rgba(0, 230, 118, 0.3)';
        }

        aiIndicatorsText.innerText = recData.indicators_summary || 'N/A';
        aiRationaleText.innerText = recData.rationale || 'N/A';    }

    // --- WebSocket Realtime UI Updates ---

    function updateTickerUI(ticker) {
        const changePct = ticker.change_percentage_24h || 0;
        stripChange.innerText = `${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%`;
        stripChange.className = `val ${changePct >= 0 ? 'text-success' : 'text-danger'}`;
        
        stripPrice.innerText = `$${ticker.current_price.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
        stripVolume.innerText = `${ticker.volume_24h.toLocaleString(undefined, {maximumFractionDigits: 0})} BTC`;
        stripHigh.innerText = `$${ticker.high_24h.toLocaleString()}`;
        stripLow.innerText = `$${ticker.low_24h.toLocaleString()}`;
    }

    function setStatusCell(element, text, stateClass) {
        element.innerText = text;
        element.className = `text-right status-col ${stateClass}`;
    }

    function updateIndicatorsUI(data) {
        const ind = data.indicators;
        const price = ind.close;
        
        // EMA values
        indEma9.innerText = ind.ema_9 ? `$${ind.ema_9.toLocaleString(undefined, {minimumFractionDigits: 2})}` : '--';
        indEma21.innerText = ind.ema_21 ? `$${ind.ema_21.toLocaleString(undefined, {minimumFractionDigits: 2})}` : '--';
        indEma50.innerText = ind.ema_50 ? `$${ind.ema_50.toLocaleString(undefined, {minimumFractionDigits: 2})}` : '--';
        indEma200.innerText = ind.ema_200 ? `$${ind.ema_200.toLocaleString(undefined, {minimumFractionDigits: 2})}` : '--';
        
        // EMA status
        if (ind.ema_9 && ind.ema_21) {
            if (ind.ema_9 > ind.ema_21) {
                setStatusCell(statusEma9, "Tăng trưởng ngắn", "status-up");
                setStatusCell(statusEma21, "Hỗ trợ tăng", "status-up");
            } else {
                setStatusCell(statusEma9, "Suy thoái ngắn", "status-down");
                setStatusCell(statusEma21, "Kháng cự giảm", "status-down");
            }
        }
        
        if (ind.ema_50 && price) {
            setStatusCell(statusEma50, price >= ind.ema_50 ? "Trên EMA50 (Tốt)" : "Dưới EMA50 (Xấu)", price >= ind.ema_50 ? "status-up" : "status-down");
        }
        if (ind.ema_200 && price) {
            setStatusCell(statusEma200, price >= ind.ema_200 ? "Uptrend dài hạn" : "Downtrend dài hạn", price >= ind.ema_200 ? "status-up" : "status-down");
        }

        // RSI
        if (ind.rsi) {
            indRsi.innerText = ind.rsi.toFixed(2);
            if (ind.rsi >= 70) {
                indRsi.className = 'mono text-right val-col text-danger';
                setStatusCell(statusRsi, "Quá Mua (Cản)", "status-down");
            } else if (ind.rsi <= 30) {
                indRsi.className = 'mono text-right val-col text-success';
                setStatusCell(statusRsi, "Quá Bán (Hỗ trợ)", "status-up");
            } else {
                indRsi.className = 'mono text-right val-col text-white';
                setStatusCell(statusRsi, "Trung tính", "status-neutral");
            }
        } else {
            indRsi.innerText = '--';
            setStatusCell(statusRsi, "--", "status-neutral");
        }
        
        // Stochastic
        indStochk.innerText = ind.stoch_k ? ind.stoch_k.toFixed(2) : '--';
        indStochd.innerText = ind.stoch_d ? ind.stoch_d.toFixed(2) : '--';
        if (ind.stoch_k && ind.stoch_d) {
            if (ind.stoch_k >= 80) {
                setStatusCell(statusStoch, "Quá mua động lượng", "status-down");
            } else if (ind.stoch_k <= 20) {
                setStatusCell(statusStoch, "Quá bán động lượng", "status-up");
            } else {
                setStatusCell(statusStoch, ind.stoch_k >= ind.stoch_d ? "Động lượng tăng" : "Động lượng giảm", ind.stoch_k >= ind.stoch_d ? "status-up" : "status-down");
            }
            setStatusCell(statusStochd, "Đường tín hiệu", "status-neutral");
        }

        // ATR
        indAtr.innerText = ind.atr ? `$${ind.atr.toLocaleString(undefined, {minimumFractionDigits: 2})}` : '--';
        setStatusCell(statusAtr, "Biến động trung bình", "status-neutral");

        // MACD
        indMacd.innerText = ind.macd ? ind.macd.toFixed(2) : '--';
        indMacdsig.innerText = ind.macd_signal ? ind.macd_signal.toFixed(2) : '--';
        if (ind.macd && ind.macd_signal) {
            const macdClass = ind.macd >= ind.macd_signal ? "status-up" : "status-down";
            setStatusCell(statusMacd, ind.macd >= ind.macd_signal ? "MACD cắt lên (Mua)" : "MACD cắt xuống (Bán)", macdClass);
            setStatusCell(statusMacdsig, "Đường tín hiệu", "status-neutral");
        }
        
        // Bollinger Bands
        indBbhigh.innerText = ind.bb_high ? `$${ind.bb_high.toLocaleString(undefined, {minimumFractionDigits: 2})}` : '--';
        indBblow.innerText = ind.bb_low ? `$${ind.bb_low.toLocaleString(undefined, {minimumFractionDigits: 2})}` : '--';
        if (ind.bb_high && ind.bb_low && price) {
            const bandWidth = ind.bb_high - ind.bb_low;
            const pct = (price - ind.bb_low) / bandWidth;
            if (pct >= 0.9) {
                setStatusCell(statusBbhigh, "Tiệm cận biên trên (Quá mua)", "status-down");
            } else if (pct <= 0.1) {
                setStatusCell(statusBblow, "Tiệm cận biên dưới (Quá bán)", "status-up");
            } else {
                setStatusCell(statusBbhigh, "Dao động trong kênh", "status-neutral");
                setStatusCell(statusBblow, "Dao động trong kênh", "status-neutral");
            }
        }

        // ADX - Trend strength
        if (ind.adx) {
            indAdx.innerText = ind.adx.toFixed(2);
            if (ind.adx >= 25) {
                setStatusCell(statusAdx, "Xu hướng mạnh", "status-up");
            } else if (ind.adx < 20) {
                setStatusCell(statusAdx, "Sideway / Không xu hướng", "status-neutral");
            } else {
                setStatusCell(statusAdx, "Xu hướng yếu", "status-neutral");
            }
        } else {
            indAdx.innerText = '--';
            setStatusCell(statusAdx, "--", "status-neutral");
        }

        // CMF - Money Flow
        if (ind.cmf) {
            indCmf.innerText = ind.cmf.toFixed(4);
            if (ind.cmf > 0.05) {
                setStatusCell(statusCmf, "Cá mập gom hàng (Mua)", "status-up");
            } else if (ind.cmf < -0.05) {
                setStatusCell(statusCmf, "Cá mập xả hàng (Bán)", "status-down");
            } else {
                setStatusCell(statusCmf, "Dòng tiền cân bằng", "status-neutral");
            }
        } else {
            indCmf.innerText = '--';
            setStatusCell(statusCmf, "--", "status-neutral");
        }

        // OBV - On-balance volume
        if (ind.obv) {
            indObv.innerText = ind.obv.toLocaleString(undefined, {maximumFractionDigits: 0});
            setStatusCell(statusObv, "Thanh khoản tích lũy", "status-neutral");
        } else {
            indObv.innerText = '--';
            setStatusCell(statusObv, "--", "status-neutral");
        }
    }

    function updateSentimentUI(orderbook) {
        // 1. Cập nhật Orderbook Pressure Bar
        if (orderbook && orderbook.bid_percentage !== undefined) {
            const bidPct = orderbook.bid_percentage;
            const askPct = orderbook.ask_percentage;
            
            sentBidBar.style.width = `${bidPct}%`;
            sentAskBar.style.width = `${askPct}%`;
            
            sentBidPct.innerText = `BUY ${bidPct}%`;
            sentAskPct.innerText = `SELL ${askPct}%`;
            
            // Tường mua/bán
            sentBidWall.innerText = `$${orderbook.strongest_bid_price.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
            sentBidWallVol.innerText = `Khối lượng: ${orderbook.strongest_bid_vol.toFixed(4)} BTC`;
            
            sentAskWall.innerText = `$${orderbook.strongest_ask_price.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
            sentAskWallVol.innerText = `Khối lượng: ${orderbook.strongest_ask_vol.toFixed(4)} BTC`;
        } else {
            sentBidBar.style.width = `50%`;
            sentAskBar.style.width = `50%`;
            sentBidPct.innerText = `BUY --`;
            sentAskPct.innerText = `SELL --`;
            sentBidWall.innerText = '--';
            sentBidWallVol.innerText = 'Khối lượng: --';
            sentAskWall.innerText = '--';
            sentAskWallVol.innerText = 'Khối lượng: --';
        }
    }

    // --- Pull Indicators HTTP fallback ---
    async function fetchIndicators() {
        try {
            const response = await fetch('/api/indicators');
            const data = await response.json();
            if (data.status === 'SUCCESS') {
                updateTickerUI(data.ticker);
                updateIndicatorsUI(data);
                updateSentimentUI(data.orderbook);
            }
        } catch (error) {
            console.error("Error fetching indicators:", error);
        }
    }

    // --- WebSocket Connection ---
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            connectionBadge.className = 'status-badge connected';
            connectionText.innerText = 'Đã kết nối';
            addTerminalLog("INFO", "SYSTEM", "WebSocket kết nối thành công.");
        };

        socket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            
            if (message.type === 'STATE') {
                updateBotState(message.data);
            } else if (message.type === 'LOG') {
                appendLogLine(message.data);
            } else if (message.type === 'TICKER') {
                updateTickerUI(message.data);
            } else if (message.type === 'INDICATORS') {
                updateIndicatorsUI(message.data);
                updateSentimentUI(message.data.orderbook);
            }
        };

        socket.onclose = () => {
            connectionBadge.className = 'status-badge disconnected';
            connectionText.innerText = 'Mất kết nối';
            addTerminalLog("WARNING", "SYSTEM", "Mất kết nối WebSocket. Đang thử kết nối lại sau 5 giây...");
            setTimeout(connectWebSocket, 5000);
        };
    }

    // --- Fetch Initial HTTP Data ---
    async function fetchInitialData() {
        await fetchIndicators();

        try {
            const statusRes = await fetch('/api/status');
            const statusData = await statusRes.json();
            if (statusData.bot_state) {
                updateBotState(statusData.bot_state);
            }
        } catch (error) {
            console.error("Error loading initial configuration:", error);
        }

        try {
            const logsRes = await fetch('/api/logs');
            const logsData = await logsRes.json();
            if (logsData.logs) {
                terminalLogs.innerHTML = '';
                logsData.logs.forEach(appendLogLine);
            }
        } catch (error) {
            console.error("Error loading initial logs:", error);
        }
    }

    // --- Logs rendering ---
    function appendLogLine(log) {
        const logLine = document.createElement('div');
        logLine.className = `log-line ${log.level.toLowerCase()}`;
        
        const timeSpan = document.createElement('span');
        timeSpan.className = 'log-time';
        timeSpan.innerText = `[${log.timestamp}]`;
        
        const tagSpan = document.createElement('span');
        tagSpan.className = 'log-tag';
        tagSpan.innerText = `[${log.name.split('.').pop().toUpperCase()}]`;
        
        const textSpan = document.createElement('span');
        textSpan.className = 'log-text';
        textSpan.innerText = log.message;
        
        logLine.appendChild(timeSpan);
        logLine.appendChild(tagSpan);
        logLine.appendChild(textSpan);
        
        terminalLogs.appendChild(logLine);
        terminalLogs.scrollTop = terminalLogs.scrollHeight;
    }

    function addTerminalLog(level, sender, message) {
        const timestamp = new Date().toLocaleTimeString();
        appendLogLine({
            timestamp: timestamp,
            level: level,
            name: sender,
            message: message
        });
    }

    // --- AI Analysis History render ---
    function renderAnalysisHistory() {
        if (analysisHistory.length === 0) {
            analysisHistoryList.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-muted">Chưa có dữ liệu phân tích nào được lưu. Hãy bấm 'Phân tích ngay'.</td>
                </tr>
            `;
            return;
        }

        analysisHistoryList.innerHTML = '';
        analysisHistory.forEach(item => {
            const tr = document.createElement('tr');
            const recClass = item.recommendation === 'BUY' ? 'text-success' : (item.recommendation === 'SELL' ? 'text-danger' : '');
            
            tr.innerHTML = `
                <td>${item.timestamp}</td>
                <td>${item.symbol}</td>
                <td>${item.timeframe}</td>
                <td class="${recClass} font-weight-bold">${item.recommendation}</td>
                <td>${item.confidence}%</td>
                <td class="text-muted small">${item.indicators_summary}</td>
            `;
            analysisHistoryList.appendChild(tr);
        });
    }

    // --- Action Handlers ---

    settingsForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const symbolVal = inputSymbol.value.trim().toUpperCase();
        const timeframeVal = selectTimeframe.value;
        const intervalVal = parseInt(inputInterval.value);

        addTerminalLog("INFO", "USER", `Yêu cầu cập nhật cấu hình: Cặp=${symbolVal}, Khung=${timeframeVal}, Chu kỳ=${intervalVal}m`);
        
        try {
            const response = await fetch(`/api/config-update?symbol=${encodeURIComponent(symbolVal)}&timeframe=${timeframeVal}&interval=${intervalVal}`, {
                method: 'POST'
            });
            const result = await response.json();
            
            if (result.status === 'SUCCESS') {
                addTerminalLog("INFO", "SYSTEM", "Cập nhật cấu hình thành công!");
                settingsModal.style.display = 'none';
                await fetchIndicators();
            } else {
                addTerminalLog("WARNING", "SYSTEM", `Cập nhật cấu hình thất bại: ${result.reason}`);
            }
        } catch (error) {
            console.error("Config update error:", error);
            addTerminalLog("ERROR", "SYSTEM", "Lỗi mạng khi cập nhật cấu hình.");
        }
    });

    btnAnalyzeNow.addEventListener('click', async () => {
        const icon = btnAnalyzeNow.querySelector('i');
        icon.className = 'fa-solid fa-spinner fa-spin';
        btnAnalyzeNow.disabled = true;
        
        addTerminalLog("INFO", "USER", "Kích hoạt chu kỳ phân tích AI thủ công.");
        
        try {
            await fetchIndicators();

            const response = await fetch('/api/analyze-now', { method: 'POST' });
            const result = await response.json();
            
            if (result.status === 'SUCCESS') {
                addTerminalLog("INFO", "SYSTEM", "Phân tích AI hoàn tất!");
                
                updateAiDecisionUI(result.analysis);
                stripLastAnalysis.innerText = result.last_analysis_time;
                
                analysisHistory.unshift({
                    timestamp: result.last_analysis_time,
                    symbol: currentSymbol,
                    timeframe: selectTimeframe.value,
                    recommendation: result.analysis.recommendation,
                    confidence: result.analysis.confidence,
                    indicators_summary: result.analysis.indicators_summary
                });
                
                renderAnalysisHistory();
            } else {
                addTerminalLog("WARNING", "SYSTEM", `Phân tích thất bại: ${result.reason}`);
            }
        } catch (error) {
            console.error("Manual analysis trigger error:", error);
            addTerminalLog("ERROR", "SYSTEM", "Lỗi kết nối hoặc AI gặp sự cố khi phân tích.");
        } finally {
            icon.className = 'fa-solid fa-wand-magic-sparkles';
            btnAnalyzeNow.disabled = false;
        }
    });

    // --- Sidebar Tabs (Tín hiệu AI / Trò chuyện AI) ---
    const sidebarTabBtns = document.querySelectorAll('.sidebar-tab-btn');
    const sidebarTabContents = document.querySelectorAll('.sidebar-tab-content');

    sidebarTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-stab');
            
            sidebarTabBtns.forEach(b => b.classList.remove('active'));
            sidebarTabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            const targetContent = document.getElementById(tabId);
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });

    // --- Direct chat with Gemini AI ---
    const chatMessages = document.getElementById('chat-messages');
    const chatInputText = document.getElementById('chat-input-text');
    const btnSendChat = document.getElementById('btn-send-chat');

    function appendChatMessage(sender, text, isAi = false) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-msg ${isAi ? 'ai' : 'user'}`;
        
        const senderDiv = document.createElement('div');
        senderDiv.className = 'msg-sender';
        senderDiv.innerHTML = isAi ? '<i class="fa-solid fa-robot"></i> Gemini Assistant' : '<i class="fa-solid fa-user"></i> Bạn';
        
        const textDiv = document.createElement('div');
        textDiv.className = 'msg-text';
        textDiv.innerText = text;
        
        msgDiv.appendChild(senderDiv);
        msgDiv.appendChild(textDiv);
        chatMessages.appendChild(msgDiv);
        
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return msgDiv;
    }

    async function handleSendChatMessage() {
        const message = chatInputText.value.trim();
        if (!message) return;
        
        appendChatMessage('user', message, false);
        chatInputText.value = '';
        
        const thinkingMsg = appendChatMessage('ai', 'Đang phân tích dữ liệu chỉ báo kỹ thuật và soạn câu trả lời...', true);
        
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: message })
            });
            const data = await response.json();
            
            if (data.status === 'SUCCESS') {
                thinkingMsg.querySelector('.msg-text').innerText = data.response;
            } else {
                thinkingMsg.querySelector('.msg-text').innerText = `Lỗi hệ thống: ${data.reason || 'Không rõ lỗi'}`;
            }
        } catch (error) {
            console.error("Chat API error:", error);
            thinkingMsg.querySelector('.msg-text').innerText = "Không thể kết nối với server. Vui lòng kiểm tra lại.";
        } finally {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    btnSendChat.addEventListener('click', handleSendChatMessage);
    chatInputText.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleSendChatMessage();
        }
    });

    // --- App Initializations ---
    fetchInitialData();
    connectWebSocket();
});
