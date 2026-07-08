import ccxt.async_support as ccxt
import logging
import time
import aiohttp
from typing import Dict, Any, List
import config

logger = logging.getLogger("trading_bot.okx")

class OKXService:
    def __init__(self):
        self.symbol = config.TRADE_SYMBOL
        
        # Kiểm tra cấu hình API
        self.has_keys = bool(config.OKX_API_KEY and config.OKX_API_SECRET)
        
        # Khởi tạo client OKX bằng CCXT Async Support
        exchange_options = {}
        if self.has_keys:
            exchange_options.update({
                'apiKey': config.OKX_API_KEY,
                'secret': config.OKX_API_SECRET,
                'password': config.OKX_API_PASSWORD,
            })
        
        self.client = ccxt.okx(exchange_options)
        
        if self.has_keys and config.OKX_USE_DEMO:
            self.client.set_sandbox_mode(True)
            logger.info("OKX client initialized in SANDBOX (Demo) mode.")
        elif self.has_keys:
            logger.info("OKX client initialized in REAL trading mode. WARNING: Real funds will be used.")
        else:
            logger.info("OKX API keys not configured. Bot will run in local PAPER TRADING mode.")

        # Khởi tạo dữ liệu Paper Trading trong bộ nhớ
        self.paper_balance = {
            'USDT': config.INITIAL_PAPER_BALANCE,
            self.symbol.split('/')[0]: 0.0
        }
        self.paper_trades = []

    async def close(self):
        """Đóng kết nối client CCXT để giải phóng tài nguyên"""
        await self.client.close()

    async def get_market_data(self, limit: int = 100, timeframe: str = None) -> List[List[float]]:
        """
        Lấy dữ liệu nến (OHLCV) từ OKX bất đồng bộ cho một timeframe cụ thể.
        Nếu gặp lỗi (ví dụ bị chặn IP), tự động trả về dữ liệu nến giả lập để giữ Web UI hoạt động.
        """
        tf = timeframe or config.TIMEFRAME
        try:
            ohlcv = await self.client.fetch_ohlcv(self.symbol, tf, limit=limit)
            return ohlcv
        except Exception as e:
            logger.error(f"Error fetching OHLCV ({tf}) from OKX (Using fallback dummy data): {e}")
            
            # Tạo dữ liệu nến giả lập (dummy ohlcv) để biểu đồ TradingView vẫn hiển thị
            dummy_ohlcv = []
            # Ước lượng khoảng thời gian lùi lại (ví dụ 1h = 3600s)
            seconds_per_candle = 3600
            if tf == '1m': seconds_per_candle = 60
            elif tf == '5m': seconds_per_candle = 300
            elif tf == '15m': seconds_per_candle = 900
            elif tf == '4h': seconds_per_candle = 14400
            elif tf == '1d': seconds_per_candle = 86400
            
            base_time = int(time.time() * 1000) - (limit * seconds_per_candle * 1000)
            
            # Tạo chuỗi giá giả lập dao động quanh vùng 60,000 USD
            start_price = 60000.0
            for i in range(limit):
                change = (i % 7 - 3) * 15.0 # Dao động nhỏ
                open_p = start_price + change
                open_p = start_price + change
                close_p = open_p + (i % 5 - 2) * 12.0
                high_p = max(open_p, close_p) + 25.0
                low_p = min(open_p, close_p) - 25.0
                
                dummy_ohlcv.append([
                    base_time + (i * seconds_per_candle * 1000), # timestamp
                    open_p,
                    high_p,
                    low_p,
                    close_p,
                    150.0 # volume
                ])
                start_price = close_p
                
            return dummy_ohlcv
    async def get_ticker_price(self) -> float:
        """
        Lấy giá hiện tại (ticker price) bất đồng bộ.
        """
        try:
            ticker = await self.client.fetch_ticker(self.symbol)
            return float(ticker['last'])
        except Exception as e:
            logger.error(f"Error fetching ticker from OKX (Using fallback price): {e}")
            # Trả về giá đóng cửa của nến giả lập cuối cùng
            ohlcv = await self.get_market_data(limit=1)
            return ohlcv[-1][4]

    async def get_balance(self) -> Dict[str, float]:
        """
        Lấy số dư tài khoản bất đồng bộ.
        """
        if self.has_keys:
            try:
                balance_data = await self.client.fetch_balance()
                coin = self.symbol.split('/')[0]
                return {
                    'USDT': float(balance_data.get('USDT', {}).get('free', 0.0)),
                    coin: float(balance_data.get(coin, {}).get('free', 0.0))
                }
            except Exception as e:
                logger.error(f"Error fetching balance from OKX: {e}. Falling back to paper balance.")
        
        return self.paper_balance.copy()

    async def execute_trade(self, side: str, amount_pct: float = 100.0) -> Dict[str, Any]:
        """
        Thực hiện giao dịch Market Order bất đồng bộ.
        """
        side = side.upper()
        if side not in ['BUY', 'SELL']:
            raise ValueError("Giao dịch chỉ hỗ trợ 'BUY' hoặc 'SELL'")

        coin = self.symbol.split('/')[0]
        try:
            current_price = await self.get_ticker_price()
            balances = await self.get_balance()

            if side == 'BUY':
                usdt_balance = balances['USDT']
                usdt_to_use = usdt_balance * (amount_pct / 100.0)
                usdt_to_use_clean = usdt_to_use * 0.999
                
                if usdt_to_use_clean < 1.0:
                    return {"status": "FAILED", "reason": "Số dư USDT không đủ tối thiểu 1 USDT."}
                
                amount_to_buy = usdt_to_use_clean / current_price

                if self.has_keys:
                    order = await self.client.create_market_buy_order(self.symbol, amount_to_buy)
                    logger.info(f"OKX BUY Order Executed: {order}")
                    return {
                        "status": "SUCCESS",
                        "side": "BUY",
                        "price": float(order.get('price', current_price)),
                        "amount": float(order.get('amount', amount_to_buy)),
                        "cost": float(order.get('cost', usdt_to_use_clean)),
                        "id": order.get('id')
                    }
                else:
                    self.paper_balance['USDT'] -= usdt_to_use
                    self.paper_balance[coin] += amount_to_buy
                    trade_info = {
                        "status": "SUCCESS",
                        "side": "BUY",
                        "price": current_price,
                        "amount": amount_to_buy,
                        "cost": usdt_to_use,
                        "id": f"paper_{len(self.paper_trades) + 1}",
                        "timestamp": int(time.time() * 1000)
                    }
                    self.paper_trades.append(trade_info)
                    logger.info(f"Simulated BUY Executed: {trade_info}")
                    return trade_info

            elif side == 'SELL':
                coin_balance = balances[coin]
                amount_to_sell = coin_balance * (amount_pct / 100.0)
                
                if amount_to_sell <= 0.0:
                    return {"status": "FAILED", "reason": f"Không có {coin} để bán."}

                if self.has_keys:
                    order = await self.client.create_market_sell_order(self.symbol, amount_to_sell)
                    logger.info(f"OKX SELL Order Executed: {order}")
                    return {
                        "status": "SUCCESS",
                        "side": "SELL",
                        "price": float(order.get('price', current_price)),
                        "amount": float(order.get('amount', amount_to_sell)),
                        "cost": float(order.get('cost', amount_to_sell * current_price)),
                        "id": order.get('id')
                    }
                else:
                    usdt_received = amount_to_sell * current_price
                    self.paper_balance[coin] -= amount_to_sell
                    self.paper_balance['USDT'] += usdt_received
                    trade_info = {
                        "status": "SUCCESS",
                        "side": "SELL",
                        "price": current_price,
                        "amount": amount_to_sell,
                        "cost": usdt_received,
                        "id": f"paper_{len(self.paper_trades) + 1}",
                        "timestamp": int(time.time() * 1000)
                    }
                    self.paper_trades.append(trade_info)
                    logger.info(f"Simulated SELL Executed: {trade_info}")
                    return trade_info

        except Exception as e:
            logger.error(f"Error executing {side} order: {e}")
            return {"status": "FAILED", "reason": str(e)}

    async def get_trade_history(self) -> List[Dict[str, Any]]:
        """
        Lấy lịch sử giao dịch bất đồng bộ.
        """
        if self.has_keys:
            try:
                raw_trades = await self.client.fetch_my_trades(self.symbol)
                formatted_trades = []
                for t in raw_trades:
                    formatted_trades.append({
                        "id": t.get('id'),
                        "timestamp": t.get('timestamp'),
                        "side": t.get('side').upper(),
                        "price": float(t.get('price')),
                        "amount": float(t.get('amount')),
                        "cost": float(t.get('cost')),
                        "status": "SUCCESS"
                    })
                return formatted_trades
            except Exception as e:
                logger.error(f"Error fetching trades from OKX: {e}")
        
        return self.paper_trades

    async def get_ticker_24h(self) -> Dict[str, Any]:
        """
        Lấy thông tin Ticker 24h từ OKX công khai.
        """
        try:
            ticker = await self.client.fetch_ticker(self.symbol)
            return {
                "current_price": float(ticker.get('last', 0.0)),
                "high_24h": float(ticker.get('high', 0.0)),
                "low_24h": float(ticker.get('low', 0.0)),
                "volume_24h": float(ticker.get('baseVolume', 0.0)),
                "change_percentage_24h": float(ticker.get('percentage', 0.0))
            }
        except Exception as e:
            logger.error(f"Error fetching ticker 24h from OKX: {e}")
            # Fallback mock ticker data
            return {
                "current_price": 62500.0,
                "high_24h": 63000.0,
                "low_24h": 62000.0,
                "volume_24h": 12500.0,
                "change_percentage_24h": -0.5
            }

    async def get_order_book(self, limit: int = 20) -> Dict[str, Any]:
        """
        Lấy dữ liệu Sổ lệnh (Orderbook) từ OKX và tính toán áp lực mua/bán + tường giá.
        """
        try:
            order_book = await self.client.fetch_order_book(self.symbol, limit=limit)
            bids = order_book.get('bids', [])
            asks = order_book.get('asks', [])
            
            # Tính tổng volume
            bid_vol_total = sum(float(b[1]) for b in bids)
            ask_vol_total = sum(float(a[1]) for a in asks)
            
            # Tính tỷ lệ đặt lệnh mua/bán (%)
            total_vol = bid_vol_total + ask_vol_total
            bid_percentage = (bid_vol_total / total_vol * 100.0) if total_vol > 0 else 50.0
            ask_percentage = 100.0 - bid_percentage
            
            # Tìm tường mua/bán mạnh nhất (mức giá có volume lớn nhất)
            strongest_bid = max(bids, key=lambda x: float(x[1])) if bids else [0.0, 0.0]
            strongest_ask = max(asks, key=lambda x: float(x[1])) if asks else [0.0, 0.0]
            
            return {
                "bid_percentage": round(bid_percentage, 2),
                "ask_percentage": round(ask_percentage, 2),
                "strongest_bid_price": float(strongest_bid[0]),
                "strongest_bid_vol": float(strongest_bid[1]),
                "strongest_ask_price": float(strongest_ask[0]),
                "strongest_ask_vol": float(strongest_ask[1])
            }
        except Exception as e:
            logger.error(f"Error fetching order book from OKX: {e}")
            # Fallback mock orderbook
            return {
                "bid_percentage": 50.0,
                "ask_percentage": 50.0,
                "strongest_bid_price": 0.0,
                "strongest_bid_vol": 0.0,
                "strongest_ask_price": 0.0,
                "strongest_ask_vol": 0.0
            }

    async def get_rubik_sentiment(self) -> Dict[str, Any]:
        """
        Lấy thông tin Tỷ lệ Long/Short và Taker Volume từ OKX Rubik public API.
        """
        coin = self.symbol.split('/')[0]
        # Sử dụng aiohttp để gọi trực tiếp các API public Rubik với period=1H và instType=SPOT
        url_ls = f"https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy={coin}&period=1H"
        url_taker = f"https://www.okx.com/api/v5/rubik/stat/taker-volume?ccy={coin}&instType=SPOT&period=1H"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        sentiment_data = {
            "long_short_ratio": 1.0,
            "taker_buy_vol": 0.0,
            "taker_sell_vol": 0.0,
            "taker_buy_sell_ratio": 1.0
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                # 1. Gọi Long/Short Ratio
                async with session.get(url_ls, headers=headers, timeout=5) as resp:
                    if resp.status == 200:
                        res_json = await resp.json()
                        data_list = res_json.get('data', [])
                        if data_list:
                            # Phần tử đầu tiên (index 0) là mới nhất: [timestamp, ratio]
                            latest = data_list[0]
                            sentiment_data["long_short_ratio"] = float(latest[1])
                
                # 2. Gọi Taker Volume
                async with session.get(url_taker, headers=headers, timeout=5) as resp:
                    if resp.status == 200:
                        res_json = await resp.json()
                        data_list = res_json.get('data', [])
                        if data_list:
                            # Phần tử đầu tiên (index 0) là mới nhất: [timestamp, buyVol, sellVol]
                            latest = data_list[0]
                            buy_vol = float(latest[1])
                            sell_vol = float(latest[2])
                            
                            sentiment_data["taker_buy_vol"] = buy_vol
                            sentiment_data["taker_sell_vol"] = sell_vol
                            if sell_vol > 0:
                                sentiment_data["taker_buy_sell_ratio"] = round(buy_vol / sell_vol, 4)
                            else:
                                sentiment_data["taker_buy_sell_ratio"] = 1.0
                                
            return sentiment_data
        except Exception as e:
            logger.error(f"Error fetching Rubik sentiment from OKX: {e}")
            # Fallback mock sentiment
            return sentiment_data

