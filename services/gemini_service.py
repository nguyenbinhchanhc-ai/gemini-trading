import json
import logging
import pandas as pd
import ta
from openai import AsyncOpenAI
import config
from typing import Dict, Any, List

logger = logging.getLogger("trading_bot.gemini")

class GeminiService:
    def __init__(self):
        # Tự động phát hiện cấu hình API Key chính thức (được khuyên dùng cho tính ổn định cao)
        if config.GEMINI_OFFICIAL_API_KEY:
            self.client = AsyncOpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=config.GEMINI_OFFICIAL_API_KEY
            )
            self.model = config.GEMINI_OFFICIAL_MODEL
            logger.info(f"Gemini Service initialized using OFFICIAL Google AI Studio API key. Model: {self.model}")
        else:
            # Khởi tạo AsyncOpenAI client trỏ vào local go proxy (Cookies Web)
            self.client = AsyncOpenAI(
                base_url=config.GEMINI_BASE_URL,
                api_key=config.GEMINI_API_KEY
            )
            self.model = config.GEMINI_MODEL
            logger.info(f"Gemini Service initialized using local Web-to-API Cookies Proxy. Endpoint: {config.GEMINI_BASE_URL}, Model: {self.model}")
    def prepare_indicators(self, ohlcv_data: List[List[float]]) -> pd.DataFrame:
        """
        Chuyển dữ liệu nến thành DataFrame và tính toán các chỉ báo kỹ thuật cơ bản
        """
        df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['datetime'] = df['datetime'].dt.tz_localize('UTC').dt.tz_convert('Asia/Ho_Chi_Minh')        
        # Chuyển kiểu dữ liệu sang float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
            
        # Tính EMA
        df['ema_9'] = ta.trend.ema_indicator(df['close'], window=9)
        df['ema_21'] = ta.trend.ema_indicator(df['close'], window=21)
        df['ema_50'] = ta.trend.ema_indicator(df['close'], window=50)
        df['ema_200'] = ta.trend.ema_indicator(df['close'], window=200)
        
        # Tính RSI
        df['rsi'] = ta.momentum.rsi(df['close'], window=14)
        
        # Tính ATR
        df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
        
        # Tính Stochastic
        stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'], window=14, smooth_window=3)
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()
        
        # Tính MACD
        macd_indicator = ta.trend.MACD(df['close'])
        df['macd'] = macd_indicator.macd()
        df['macd_signal'] = macd_indicator.macd_signal()
        df['macd_diff'] = macd_indicator.macd_diff()
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df['close'])
        df['bb_high'] = bb.bollinger_hband()
        df['bb_low'] = bb.bollinger_lband()
        df['bb_mid'] = bb.bollinger_mavg()
        
        # Tính ADX, CMF và OBV
        df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=14)
        df['cmf'] = ta.volume.chaikin_money_flow(df['high'], df['low'], df['close'], df['volume'], window=20)
        df['obv'] = ta.volume.on_balance_volume(df['close'], df['volume'])
        
        return df

    async def analyze_market(self, ohlcv_data: List[List[float]], ohlcv_4h: List[List[float]] = None, ohlcv_1d: List[List[float]] = None, orderbook_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Gửi dữ liệu thị trường và các chỉ báo kỹ thuật đến Gemini qua OpenAI compatible API,
        yêu cầu phân tích và đưa ra quyết định mua/bán/giữ.
        """
        try:
            # Chuẩn bị dữ liệu chỉ báo kỹ thuật khung 1h
            df = self.prepare_indicators(ohlcv_data)
            
            # Lấy 30 hàng cuối cùng để gửi cho Gemini (tránh làm tràn ngữ cảnh và tiết kiệm token)
            df_slice = df.tail(30).copy()
            
            # Định dạng dữ liệu giá để gửi
            market_data_str = ""
            for idx, row in df_slice.iterrows():
                rsi_val = 0.0 if pd.isna(row['rsi']) else row['rsi']
                ema9_val = 0.0 if pd.isna(row['ema_9']) else row['ema_9']
                ema21_val = 0.0 if pd.isna(row['ema_21']) else row['ema_21']
                ema50_val = 0.0 if pd.isna(row['ema_50']) else row['ema_50']
                ema200_val = 0.0 if pd.isna(row['ema_200']) else row['ema_200']
                atr_val = 0.0 if pd.isna(row['atr']) else row['atr']
                stoch_k = 0.0 if pd.isna(row['stoch_k']) else row['stoch_k']
                stoch_d = 0.0 if pd.isna(row['stoch_d']) else row['stoch_d']
                
                market_data_str += (
                    f"Time: {row['datetime'].strftime('%Y-%m-%d %H:%M')}, "
                    f"O: {row['open']:.2f}, H: {row['high']:.2f}, L: {row['low']:.2f}, C: {row['close']:.2f}, V: {row['volume']:.2f}, "
                    f"RSI: {rsi_val:.1f}, EMA9: {ema9_val:.2f}, EMA21: {ema21_val:.2f}, "
                    f"EMA50: {ema50_val:.2f}, EMA200: {ema200_val:.2f}, ATR: {atr_val:.2f}, "
                    f"Stoch%K: {stoch_k:.1f}, Stoch%D: {stoch_d:.1f}\n"
                )
            
            current_row = df.iloc[-1]
            coin = config.TRADE_SYMBOL.split('/')[0]
            
            # Phân tích Khung 4h (Vĩ mô trung hạn)
            context_4h = ""
            if ohlcv_4h:
                df_4h = self.prepare_indicators(ohlcv_4h)
                row_4h = df_4h.iloc[-1]
                rsi_4h = "N/A" if pd.isna(row_4h['rsi']) else f"{row_4h['rsi']:.1f}"
                adx_4h = "N/A" if pd.isna(row_4h['adx']) else f"{row_4h['adx']:.1f}"
                cmf_4h = "N/A" if pd.isna(row_4h['cmf']) else f"{row_4h['cmf']:.2f}"
                ema50_4h = "N/A" if pd.isna(row_4h['ema_50']) else f"{row_4h['ema_50']:.2f}"
                ema200_4h = "N/A" if pd.isna(row_4h['ema_200']) else f"{row_4h['ema_200']:.2f}"
                context_4h = (
                    f"- Giá đóng cửa 4h: {row_4h['close']:.2f}\n"
                    f"- Volume nến 4h: {row_4h['volume']:.2f} BTC\n"
                    f"- RSI (14) 4h: {rsi_4h}\n"
                    f"- ADX (14) 4h: {adx_4h} (Sức mạnh xu hướng 4h)\n"
                    f"- CMF (20) 4h: {cmf_4h} (Dòng tiền 4h)\n"
                    f"- EMA 50 4h: {ema50_4h} | EMA 200 4h: {ema200_4h}\n"
                )
            else:
                context_4h = "- Không có dữ liệu cấu hình khung 4h\n"

            # Phân tích Khung 1d (Daily - Vĩ mô dài hạn)
            context_1d = ""
            if ohlcv_1d:
                df_1d = self.prepare_indicators(ohlcv_1d)
                row_1d = df_1d.iloc[-1]
                rsi_1d = "N/A" if pd.isna(row_1d['rsi']) else f"{row_1d['rsi']:.1f}"
                adx_1d = "N/A" if pd.isna(row_1d['adx']) else f"{row_1d['adx']:.1f}"
                cmf_1d = "N/A" if pd.isna(row_1d['cmf']) else f"{row_1d['cmf']:.2f}"
                ema50_1d = "N/A" if pd.isna(row_1d['ema_50']) else f"{row_1d['ema_50']:.2f}"
                ema200_1d = "N/A" if pd.isna(row_1d['ema_200']) else f"{row_1d['ema_200']:.2f}"
                context_1d = (
                    f"- Giá đóng cửa Daily: {row_1d['close']:.2f}\n"
                    f"- Volume nến Daily: {row_1d['volume']:.2f} BTC\n"
                    f"- RSI (14) Daily: {rsi_1d}\n"
                    f"- ADX (14) Daily: {adx_1d} (Sức mạnh xu hướng Daily)\n"
                    f"- CMF (20) Daily: {cmf_1d} (Dòng tiền Daily)\n"
                    f"- EMA 50 Daily: {ema50_1d} | EMA 200 Daily: {ema200_1d}\n"
                )
            else:
                context_1d = "- Không có dữ liệu cấu hình khung Daily\n"

            # Phân tích dữ liệu Sổ lệnh (Orderbook) & Tâm lý
            orderbook_context = ""
            if orderbook_data:
                orderbook_context = (
                    f"THÔNG TIN SỔ LỆNH (ORDERBOOK - CHIỀU SÂU 20 LEVELS):\n"
                    f"- Tỷ lệ đặt lệnh Mua (Bid) vs Bán (Ask): B {orderbook_data['bid_percentage']}% | {orderbook_data['ask_percentage']}% S\n"
                    f"- Tường Mua (Support Wall) mạnh nhất: Giá {orderbook_data['strongest_bid_price']:.2f} (Khối lượng: {orderbook_data['strongest_bid_vol']:.2f} {coin})\n"
                    f"- Tường Bán (Resistance Wall) mạnh nhất: Giá {orderbook_data['strongest_ask_price']:.2f} (Khối lượng: {orderbook_data['strongest_ask_vol']:.2f} {coin})\n"
                )
            else:
                orderbook_context = "THÔNG TIN SỔ LỆNH: Không có dữ liệu\n"



            # Tính toán mốc TP/SL toán học gợi ý dựa trên biến động ATR hiện tại
            atr_val = current_row['atr']
            close_price = current_row['close']
            if not pd.isna(atr_val) and atr_val > 0:
                tp_buy_s = close_price + 3 * atr_val
                sl_buy_s = close_price - 2 * atr_val
               # Xây dựng System Prompt định hướng cho Gemini
            system_prompt = (
                "Bạn là một chuyên gia phân tích kỹ thuật Price Action cấp cao chuyên nghiệp (Senior Price Action Technical Analyst). "
                "Nhiệm vụ của bạn là nghiên cứu cấu trúc thị trường, phân tích hành động giá qua các cản kháng cự/hỗ trợ, xu hướng đa khung thời gian, sổ lệnh depth và các chỉ báo động lượng. "
                "Hãy tự do phân tích, suy luận và đưa ra quyết định giao dịch khách quan theo cách nghĩ riêng của bạn. "
                "Hãy tự đánh giá tỷ lệ rủi ro (risk_percentage) và độ tin cậy (confidence) một cách linh hoạt, sát với thực tế thị trường. "
                "Trả về kết quả ở định dạng JSON nghiêm ngặt với cấu trúc được định nghĩa sẵn, không kèm giải thích ngoài JSON."
            )
            
            rsi_text = "N/A" if pd.isna(current_row['rsi']) else f"{current_row['rsi']:.1f}"
            macd_text = "N/A" if pd.isna(current_row['macd']) else f"{current_row['macd']:.2f}"
            macd_sig_text = "N/A" if pd.isna(current_row['macd_signal']) else f"{current_row['macd_signal']:.2f}"
            bb_high_text = "N/A" if pd.isna(current_row['bb_high']) else f"{current_row['bb_high']:.2f}"
            bb_low_text = "N/A" if pd.isna(current_row['bb_low']) else f"{current_row['bb_low']:.2f}"
            ema9_text = "N/A" if pd.isna(current_row['ema_9']) else f"{current_row['ema_9']:.2f}"
            ema21_text = "N/A" if pd.isna(current_row['ema_21']) else f"{current_row['ema_21']:.2f}"
            ema50_text = "N/A" if pd.isna(current_row['ema_50']) else f"{current_row['ema_50']:.2f}"
            ema200_text = "N/A" if pd.isna(current_row['ema_200']) else f"{current_row['ema_200']:.2f}"
            atr_text = "N/A" if pd.isna(current_row['atr']) else f"{current_row['atr']:.2f}"
            stoch_k_text = "N/A" if pd.isna(current_row['stoch_k']) else f"{current_row['stoch_k']:.1f}"
            stoch_d_text = "N/A" if pd.isna(current_row['stoch_d']) else f"{current_row['stoch_d']:.1f}"
            adx_text = "N/A" if pd.isna(current_row['adx']) else f"{current_row['adx']:.1f}"
            cmf_text = "N/A" if pd.isna(current_row['cmf']) else f"{current_row['cmf']:.2f}"
            obv_text = "N/A" if pd.isna(current_row['obv']) else f"{current_row['obv']:.0f}"
            
            # Xây dựng User Prompt
            user_prompt = f"""
Hãy phân tích dữ liệu kỹ thuật của cặp {config.TRADE_SYMBOL} sau đây:

THÔNG TIN KHUNG NGẮN HẠN {config.TIMEFRAME} (HIỆN TẠI):
- Giá đóng cửa gần nhất: {current_row['close']:.2f}
- Khối lượng giao dịch (Volume nến hiện tại): {current_row['volume']:.2f} BTC
- RSI (14): {rsi_text}
- MACD Line: {macd_text} | MACD Signal: {macd_sig_text}
- Bollinger Band High: {bb_high_text} | Bollinger Band Low: {bb_low_text}
- EMA 9: {ema9_text} | EMA 21: {ema21_text} | EMA 50: {ema50_text} | EMA 200: {ema200_text}
- ATR (14): {atr_text}
- Stochastic %K: {stoch_k_text} | Stochastic %D: {stoch_d_text}
- ADX (14) (Độ mạnh xu hướng): {adx_text}
- CMF (20) (Dòng tiền Chaikin): {cmf_text}
- OBV (Khối lượng lũy tích): {obv_text}

THÔNG TIN KHUNG TRUNG HẠN 4H:
{context_4h}

THÔNG TIN KHUNG DÀI HẠN DAILY (1 NGÀY):
{context_1d}

{orderbook_context}

MỐC TP/SL TOÁN HỌC GỢI Ý DỰA TRÊN ATR (Để tham khảo):
- Nếu khuyên MUA (BUY): TP = {tp_buy_s:.2f} (Độ rộng 3*ATR) | SL = {sl_buy_s:.2f} (Độ rộng 2*ATR)
- Nếu khuyên BÁN (SELL): TP = {tp_sell_s:.2f} (Độ rộng 3*ATR) | SL = {sl_sell_s:.2f} (Độ rộng 2*ATR)

Dữ liệu nến và chỉ báo 1h (30 chu kỳ gần nhất):
{market_data_str}

Nhiệm vụ:
Đánh giá xu hướng ngắn hạn và tự phản biện rủi ro để trả về quyết định giao dịch dưới dạng JSON với các trường sau:
1. "recommendation": Chuỗi chữ in hoa, chỉ được chọn một trong các giá trị: "BUY", "SELL", "HOLD". Bạn tự do quyết định hành động này dựa trên phân tích kỹ thuật Price Action của mình.
2. "confidence": Số nguyên từ 0 đến 100 đại diện cho độ tự tin (xác suất thắng thực tế sau khi đã trừ đi các yếu tố rủi ro phản biện). Hãy đánh giá tự do theo suy nghĩ của bạn, không bị ràng buộc bởi ngưỡng cố định.
3. "take_profit": Giá chốt lời đề xuất (kiểu số float hoặc null nếu khuyên HOLD). Bạn nên ưu tiên điều chỉnh mốc TP toán học dựa trên các cản hỗ trợ/kháng cự thực tế của đa khung thời gian.
4. "stop_loss": Giá dừng lỗ đề xuất (kiểu số float hoặc null nếu khuyên HOLD). Bạn nên ưu tiên điều chỉnh mốc SL toán học dựa trên các cản hỗ trợ/kháng cự thực tế của đa khung thời gian.
5. "indicators_summary": Tóm tắt ngắn gọn tình trạng chỉ báo (ví dụ: "ADX báo xu hướng yếu, CMF dòng tiền phân phối").
6. "rationale": Giải thích chi tiết bằng tiếng Việt theo định dạng bắt buộc gồm 2 phần rõ rệt:
   - [LUẬN ĐIỂM]: Luận điểm cốt lõi ủng hộ quyết định giao dịch này (kết hợp phân tích đa khung thời gian, cấu trúc Price Action và dòng tiền).
   - [PHẢN BIỆN RỦI RO]: Tự phản biện tìm ra các nhược điểm, bẫy giá tiềm ẩn (bulltrap/beartrap), phân kỳ giả hoặc rủi ro vĩ mô của khung thời gian Daily/4h để cảnh báo người dùng.
7. "estimated_timeframe": Chuỗi ước tính thời gian chốt lời (ví dụ: "6-12h", "1-2 ngày", "3-5 ngày" hoặc null nếu khuyên HOLD).
8. "risk_percentage": Số nguyên từ 0 đến 100 đại diện cho tỷ lệ rủi ro thực tế của lệnh (tính dựa trên khoảng cách cắt lỗ, lực đè của cản kháng cự/hỗ trợ và độ biến động ATR). Hãy đánh giá tự do theo suy nghĩ riêng của bạn.
"""

            logger.info("Sending market analysis request to local Gemini proxy...")
            
            # Gọi chat completions API bất đồng bộ
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2, # Nhiệt độ thấp để phân tích mang tính nhất quang và logic hơn
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.info(f"Raw response received from Gemini proxy: {response_text[:300]}...")

            # Clean response text phòng trường hợp AI vẫn bọc trong markdown codeblock
            if response_text.startswith("```"):
                # Cắt bỏ dòng ```json và ``` ở cuối
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                response_text = "\n".join(lines).strip()
            
            # Parse JSON
            analysis_result = json.loads(response_text)
            
            # Xác thực các trường bắt buộc
            required_fields = [
                "recommendation", "confidence", "take_profit", "stop_loss", 
                "indicators_summary", "rationale", "estimated_timeframe", "risk_percentage"
            ]
            for field in required_fields:
                if field not in analysis_result:
                    analysis_result[field] = None
                    
            # Chuẩn hóa recommendation
            rec = str(analysis_result.get("recommendation", "HOLD")).upper()
            if rec not in ["BUY", "SELL", "HOLD"]:
                analysis_result["recommendation"] = "HOLD"
            else:
                analysis_result["recommendation"] = rec

            # ==========================================
            # BỘ LỌC TÍN HIỆU CHẤT LƯỢNG CAO (CONFIDENCE >= 60%)
            # ==========================================
            conf = analysis_result.get("confidence", 0)
            try:
                conf = int(float(conf))
                analysis_result["confidence"] = conf
            except Exception:
                conf = 0
                analysis_result["confidence"] = conf

            if analysis_result["recommendation"] in ["BUY", "SELL"] and conf < 60:
                logger.info(f"Downgrading recommendation {analysis_result['recommendation']} to HOLD because confidence ({conf}%) is below threshold (60%)")
                analysis_result["recommendation"] = "HOLD"
                analysis_result["take_profit"] = None
                analysis_result["stop_loss"] = None
                analysis_result["estimated_timeframe"] = None
                analysis_result["rationale"] = (
                    f"[BỘ LỌC CHẤT LƯỢNG]: Tín hiệu {rec} bị tự động hạ cấp xuống HOLD do độ tin cậy chỉ đạt {conf}% "
                    "(dưới ngưỡng tối thiểu 60% để vào lệnh). Hệ thống ưu tiên sự an toàn, bảo toàn vốn "
                    "và chỉ chấp nhận các tín hiệu giao dịch có chất lượng cao.\n\n"
                    + str(analysis_result.get("rationale", ""))
                )
                
            return analysis_result
        except Exception as e:
            logger.error(f"Error in Gemini market analysis: {e}")
            # Trả về fallback kết quả HOLD mặc định nếu có lỗi xảy ra
            return {
                "recommendation": "HOLD",
                "confidence": 0,
                "take_profit": None,
                "stop_loss": None,
                "indicators_summary": "Lỗi phân tích hoặc phản hồi không đúng định dạng.",
                "rationale": f"Hệ thống gặp lỗi khi liên kết với AI: {str(e)}",
                "estimated_timeframe": "N/A",
                "risk_percentage": 0
            }
    async def chat_response(self, user_message: str, ohlcv_data: List[List[float]]) -> str:
        """
        Trả lời câu hỏi của người dùng dựa trên ngữ cảnh dữ liệu thị trường hiện tại.
        """
        try:
            df = self.prepare_indicators(ohlcv_data)
            df_slice = df.tail(15).copy() # Lấy 15 nến làm bối cảnh nhanh
            
            market_data_str = ""
            for idx, row in df_slice.iterrows():
                rsi_val = 0.0 if pd.isna(row['rsi']) else row['rsi']
                market_data_str += (
                    f"Time: {row['datetime'].strftime('%m-%d %H:%M')}, "
                    f"Close: {row['close']:.2f}, RSI: {rsi_val:.1f}\n"
                )
                
            current_row = df.iloc[-1]
            rsi_text = "N/A" if pd.isna(current_row['rsi']) else f"{current_row['rsi']:.1f}"
            
            system_prompt = (
                "Bạn là một trợ lý AI phân tích kỹ thuật tài chính và chuyên gia về thị trường Crypto. "
                "Bạn được tích hợp ngay sát bên biểu đồ của nhà đầu tư. Hãy trả lời câu hỏi của họ một cách trực tiếp, "
                "ngắn gọn (khoảng 3-4 câu, đi thẳng vào vấn đề), thông minh và thực tế dựa trên dữ liệu kỹ thuật hiện tại được cung cấp. "
                "Hãy trả lời bằng tiếng Việt thân thiện, khách quan, phân tích hai mặt và không khuyên bảo đầu tư mang tính rủi ro."
            )
            
            user_prompt = f"""
Dữ liệu thị trường hiện tại của {config.TRADE_SYMBOL}:
- Giá đóng cửa gần nhất: {current_row['close']:.2f}
- RSI (14) hiện tại: {rsi_text}

Dữ liệu nến gần đây (15 chu kỳ):
{market_data_str}

Câu hỏi của người dùng: "{user_message}"

Hãy trả lời câu hỏi trên dựa trên các dữ liệu kỹ thuật và bối cảnh thị trường này.
"""
            
            logger.info("Sending chat query to local Gemini proxy...")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7, # Nhiệt độ trung bình để câu trả lời tự nhiên hơn
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error in Gemini chat completion: {e}")
            return f"Xin lỗi, tôi gặp lỗi khi lấy phản hồi từ Gemini AI: {str(e)}"
