import asyncio
import logging
import datetime
import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
from pydantic import BaseModel
import config
from services.okx_service import OKXService
from services.gemini_service import GeminiService

# Cấu hình logging
logger = logging.getLogger("trading_bot")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Stream handler cho console
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

# Hàng đợi log lưu trong bộ nhớ để cung cấp cho Web Console
log_history: List[Dict[str, Any]] = []
active_websockets: List[WebSocket] = []

class MemoryLogHandler(logging.Handler):
    def emit(self, record):
        log_entry = {
            "timestamp": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime("%H:%M:%S"),            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name
        }
        log_history.append(log_entry)
        if len(log_history) > 200:
            log_history.pop(0)
        
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(broadcast_log(log_entry))
        except RuntimeError:
            pass

mem_handler = MemoryLogHandler()
mem_handler.setFormatter(formatter)
logger.addHandler(mem_handler)

# Hàm broadcast log qua WebSocket
async def broadcast_log(log_entry: Dict[str, Any]):
    disconnected = []
    for ws in active_websockets:
        try:
            await ws.send_json({"type": "LOG", "data": log_entry})
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in active_websockets:
            active_websockets.remove(ws)

app = FastAPI(title="Gemini Trading Bot Console")

# Cấu hình CORS để cho phép kết nối từ client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khởi tạo các services
okx_service = OKXService()
gemini_service = GeminiService()

# Trạng thái toàn cục của Bot (Chuyển sang chế độ phân tích thủ công mặc định)
bot_state = {
    "is_running": False,
    "last_analysis_time": "Chưa phân tích",
    "next_analysis_in_seconds": config.ANALYSIS_INTERVAL_MINUTES * 60,
    "last_recommendation": {
        "recommendation": "HOLD",
        "confidence": 0,
        "take_profit": None,
        "stop_loss": None,
        "indicators_summary": "Nhấn nút 'Phân tích ngay' để kích hoạt phân tích AI.",
        "rationale": "Trợ lý đang chờ lệnh phân tích kỹ thuật từ bạn.",
        "estimated_timeframe": "N/A",
        "risk_percentage": 0
    },    "trade_symbol": config.TRADE_SYMBOL,
    "timeframe": config.TIMEFRAME,
    "interval_minutes": config.ANALYSIS_INTERVAL_MINUTES,
    "paper_mode": not okx_service.has_keys,
    "okx_demo": config.OKX_USE_DEMO
}

# Biến khóa đồng bộ hóa để tránh chạy song song nhiều tiến trình phân tích
analysis_lock = asyncio.Lock()

async def run_bot_analysis() -> Dict[str, Any]:
    """
    Tiến trình phân tích chính: Cào dữ liệu -> Gemini phân tích -> Cập nhật trạng thái.
    """
    async with analysis_lock:
        logger.info("=== Bắt đầu chu kỳ phân tích thị trường (Thủ công) ===")
        logger.info(f"Đang cào dữ liệu nến cho {config.TRADE_SYMBOL}...")
        ohlcv = await okx_service.get_market_data(limit=300)
        
        # Cào thêm nến 4h và Daily làm bối cảnh vĩ mô
        logger.info("Đang cào dữ liệu nến 4h và Daily...")
        ohlcv_4h = await okx_service.get_market_data(limit=100, timeframe='4h')
        ohlcv_1d = await okx_service.get_market_data(limit=100, timeframe='1d')
        
        logger.info("Đang gửi dữ liệu phân tích kỹ thuật đa khung thời gian sang Gemini...")
        analysis = await gemini_service.analyze_market(ohlcv, ohlcv_4h, ohlcv_1d)
        
        bot_state["last_analysis_time"] = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S")
        bot_state["last_recommendation"] = analysis
        
        logger.info(f"Gemini khuyến nghị: {analysis['recommendation']} (Độ tin cậy: {analysis['confidence']}%)")
        logger.info(f"Lý do: {analysis['rationale']}")
        logger.info("=== Kết thúc chu kỳ phân tích thị trường ===")
        
        await broadcast_state()
        return analysis

async def broadcast_state():
    """Gửi trạng thái bot hiện tại tới tất cả client qua WebSocket"""
    disconnected = []
    for ws in active_websockets:
        try:
            await ws.send_json({"type": "STATE", "data": bot_state})
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in active_websockets:
            active_websockets.remove(ws)

# Loop chạy background định kỳ của bot (Chỉ duy trì countdown để hiển thị UI)
async def bot_background_task():
    logger.info("Background task của trading bot đã bắt đầu.")
    while True:
        try:
            while bot_state["next_analysis_in_seconds"] > 0:
                if not bot_state["is_running"]:
                    await asyncio.sleep(1)
                    continue
                    
                await asyncio.sleep(1)
                bot_state["next_analysis_in_seconds"] -= 1
                
                if bot_state["next_analysis_in_seconds"] % 10 == 0:
                    await broadcast_state()
                    
                if bot_state["next_analysis_in_seconds"] <= 0:
                    break
            
            bot_state["next_analysis_in_seconds"] = bot_state["interval_minutes"] * 60
            logger.info("Đã đạt mốc thời gian chu kỳ mới. (Hệ thống chạy chế độ thủ công On-Demand, bỏ qua tự phân tích).")
            await broadcast_state()
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Lỗi trong vòng lặp background của bot: {e}")
            await asyncio.sleep(10)

# Vòng lặp hợp nhất: Cào Ticker và tính Indicators liên tục 2 giây/lần để đẩy qua WebSocket
async def realtime_data_task():
    logger.info("Realtime Data task (2s) đã bắt đầu.")
    while True:
        try:
            if active_websockets:
                # 1. Cào Ticker 24h từ OKX
                ticker_data = await okx_service.get_ticker_24h()
                
                # 2. Cào 300 nến và tính toán Chỉ báo kỹ thuật
                ohlcv = await okx_service.get_market_data(limit=300)
                df = gemini_service.prepare_indicators(ohlcv)
                current_row = df.iloc[-1]
                
                indicators_data = {
                    "close": float(current_row['close']),
                    "rsi": float(current_row['rsi']) if not pd.isna(current_row['rsi']) else None,
                    "macd": float(current_row['macd']) if not pd.isna(current_row['macd']) else None,
                    "macd_signal": float(current_row['macd_signal']) if not pd.isna(current_row['macd_signal']) else None,
                    "macd_diff": float(current_row['macd_diff']) if not pd.isna(current_row['macd_diff']) else None,
                    "ema_9": float(current_row['ema_9']) if not pd.isna(current_row['ema_9']) else None,
                    "ema_21": float(current_row['ema_21']) if not pd.isna(current_row['ema_21']) else None,
                    "ema_50": float(current_row['ema_50']) if not pd.isna(current_row['ema_50']) else None,
                    "ema_200": float(current_row['ema_200']) if not pd.isna(current_row['ema_200']) else None,
                    "bb_high": float(current_row['bb_high']) if not pd.isna(current_row['bb_high']) else None,
                    "bb_low": float(current_row['bb_low']) if not pd.isna(current_row['bb_low']) else None,
                    "bb_mid": float(current_row['bb_mid']) if not pd.isna(current_row['bb_mid']) else None,
                    "atr": float(current_row['atr']) if not pd.isna(current_row['atr']) else None,
                    "stoch_k": float(current_row['stoch_k']) if not pd.isna(current_row['stoch_k']) else None,
                    "stoch_d": float(current_row['stoch_d']) if not pd.isna(current_row['stoch_d']) else None,
                    "adx": float(current_row['adx']) if not pd.isna(current_row['adx']) else None,
                    "cmf": float(current_row['cmf']) if not pd.isna(current_row['cmf']) else None,
                    "obv": float(current_row['obv']) if not pd.isna(current_row['obv']) else None
                }                
                # 3. Phát đồng thời qua WebSocket
                disconnected = []
                for ws in active_websockets:
                    try:
                        # Gửi ticker
                        await ws.send_json({"type": "TICKER", "data": ticker_data})
                        # Gửi indicators
                        await ws.send_json({
                            "type": "INDICATORS", 
                            "data": {
                                "symbol": config.TRADE_SYMBOL,
                                "timeframe": config.TIMEFRAME,
                                "indicators": indicators_data
                            }
                        })
                    except Exception:
                        disconnected.append(ws)
                for ws in disconnected:
                    if ws in active_websockets:
                        active_websockets.remove(ws)
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Lỗi trong vòng lặp realtime data 2s: {e}")
            await asyncio.sleep(5)

# Start background tasks khi ứng dụng khởi chạy
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(bot_background_task())
    asyncio.create_task(realtime_data_task())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Đang đóng các kết nối dịch vụ...")
    await okx_service.close()

# --- REST APIS ENDPOINTS ---

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat_with_gemini(req: ChatRequest):
    """
    Kênh trò chuyện trực tiếp với Gemini dựa trên bối cảnh thị trường thực tế
    """
    try:
        ohlcv = await okx_service.get_market_data(limit=30)
        response_text = await gemini_service.chat_response(req.message, ohlcv)
        return {"status": "SUCCESS", "response": response_text}
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/indicators")
async def get_indicators():
    """
    Cào dữ liệu OKX (limit=300 nến) và tính toán các chỉ báo kỹ thuật thời gian thực trả về cho UI
    """
    try:
        ohlcv = await okx_service.get_market_data(limit=300)
        df = gemini_service.prepare_indicators(ohlcv)
        current_row = df.iloc[-1]
        ticker_24h = await okx_service.get_ticker_24h()
        
        return {
            "status": "SUCCESS",
            "symbol": config.TRADE_SYMBOL,
            "timeframe": config.TIMEFRAME,
            "datetime": current_row['datetime'].strftime("%Y-%m-%d %H:%M:%S"),
            "ticker": ticker_24h,
            "indicators": {
                "close": float(current_row['close']),
                "rsi": float(current_row['rsi']) if not pd.isna(current_row['rsi']) else None,
                "macd": float(current_row['macd']) if not pd.isna(current_row['macd']) else None,
                "macd_signal": float(current_row['macd_signal']) if not pd.isna(current_row['macd_signal']) else None,
                "macd_diff": float(current_row['macd_diff']) if not pd.isna(current_row['macd_diff']) else None,
                "ema_9": float(current_row['ema_9']) if not pd.isna(current_row['ema_9']) else None,
                "ema_21": float(current_row['ema_21']) if not pd.isna(current_row['ema_21']) else None,
                "ema_50": float(current_row['ema_50']) if not pd.isna(current_row['ema_50']) else None,
                "ema_200": float(current_row['ema_200']) if not pd.isna(current_row['ema_200']) else None,
                "bb_high": float(current_row['bb_high']) if not pd.isna(current_row['bb_high']) else None,
                "bb_low": float(current_row['bb_low']) if not pd.isna(current_row['bb_low']) else None,
                "bb_mid": float(current_row['bb_mid']) if not pd.isna(current_row['bb_mid']) else None,
                "atr": float(current_row['atr']) if not pd.isna(current_row['atr']) else None,
                "stoch_k": float(current_row['stoch_k']) if not pd.isna(current_row['stoch_k']) else None,
                "stoch_d": float(current_row['stoch_d']) if not pd.isna(current_row['stoch_d']) else None,
                "adx": float(current_row['adx']) if not pd.isna(current_row['adx']) else None,
                "cmf": float(current_row['cmf']) if not pd.isna(current_row['cmf']) else None,
                "obv": float(current_row['obv']) if not pd.isna(current_row['obv']) else None
            }
        }
    except Exception as e:
        logger.error(f"Error compiling technical indicators: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def get_status():
    """Lấy trạng thái cấu hình của Bot"""
    return {
        "bot_state": bot_state,
        "current_price": await okx_service.get_ticker_price()
    }

@app.get("/api/market-data")
async def get_market_data():
    """Lấy dữ liệu nến thô"""
    try:
        ohlcv = await okx_service.get_market_data(limit=300)
        return {"ohlcv": ohlcv}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trades")
async def get_trades():
    return {"trades": []}

@app.get("/api/logs")
async def get_logs():
    """Lấy lịch sử logs hệ thống"""
    return {"logs": log_history}

@app.post("/api/analyze-now")
async def analyze_now():
    """Kích hoạt phân tích tức thì và trả về trực tiếp kết quả JSON cho UI"""
    if analysis_lock.locked():
        raise HTTPException(status_code=400, detail="Hệ thống đang chạy phân tích, vui lòng đợi.")
    
    try:
        analysis = await run_bot_analysis()
        return {
            "status": "SUCCESS", 
            "analysis": analysis,
            "last_analysis_time": bot_state["last_analysis_time"]
        }
    except Exception as e:
        logger.error(f"Manual analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/toggle-bot")
async def toggle_bot():
    """Bật / Tắt trạng thái hoạt động của Bot"""
    bot_state["is_running"] = not bot_state["is_running"]
    status_str = "chạy" if bot_state["is_running"] else "tạm dừng"
    logger.info(f"Người dùng đã chuyển trạng thái bot sang: {status_str}")
    await broadcast_state()
    return {"status": "SUCCESS", "is_running": bot_state["is_running"]}

@app.post("/api/config-update")
async def config_update(symbol: str, timeframe: str, interval: int):
    """Cập nhật cấu hình bot động"""
    if interval <= 0:
        raise HTTPException(status_code=400, detail="Tần suất phân tích phải lớn hơn 0")
        
    config.TRADE_SYMBOL = symbol
    config.TIMEFRAME = timeframe
    config.ANALYSIS_INTERVAL_MINUTES = interval
    
    okx_service.symbol = symbol
    bot_state["trade_symbol"] = symbol
    bot_state["timeframe"] = timeframe
    bot_state["interval_minutes"] = interval
    bot_state["next_analysis_in_seconds"] = interval * 60
    
    logger.info(f"Đã cập nhật cấu hình: Cặp coin={symbol}, Khung={timeframe}, Chu kỳ={interval} phút")
    await broadcast_state()
    return {"status": "SUCCESS"}

# --- WEBSOCKET FOR REALTIME STREAMING ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    logger.info(f"Kết nối Web Console mới thiết lập. Tổng số kết nối: {len(active_websockets)}")
    
    try:
        await websocket.send_json({"type": "STATE", "data": bot_state})
        for log in log_history:
            await websocket.send_json({"type": "LOG", "data": log})
    except Exception as e:
        logger.error(f"Lỗi khi gửi dữ liệu khởi tạo qua WebSocket: {e}")
        
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "PONG"})
    except WebSocketDisconnect:
        logger.info("Kết nối Web Console đã ngắt.")
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)

# Phục vụ Web UI (Static Files)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
