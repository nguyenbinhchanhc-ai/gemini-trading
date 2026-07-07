import unittest
import sys
import os
import pandas as pd
import time

# Thêm thư mục gốc vào python path để import được services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.okx_service import OKXService
from services.gemini_service import GeminiService

class TestTradingBotServices(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.okx = OKXService()
        self.gemini = GeminiService()

    async def asyncTearDown(self):
        # Đóng connection pool của CCXT sau mỗi test
        await self.okx.close()

    async def test_okx_market_data(self):
        """Kiểm tra cào dữ liệu nến từ OKX (API Public)"""
        print("\nTesting OKX OHLCV retrieval...")
        try:
            ohlcv = await self.okx.get_market_data(limit=10)
            self.assertIsNotNone(ohlcv)
            self.assertEqual(len(ohlcv), 10)
            self.assertEqual(len(ohlcv[0]), 6)
            print("OKX OHLCV retrieval: PASS")
        except Exception as e:
            self.fail(f"Failed to fetch market data from OKX: {e}")

    async def test_okx_ticker_price(self):
        """Kiểm tra lấy giá hiện tại của OKX"""
        print("\nTesting OKX ticker price...")
        try:
            price = await self.okx.get_ticker_price()
            self.assertIsInstance(price, float)
            self.assertGreater(price, 0)
            print(f"OKX Ticker price: {price} - PASS")
        except Exception as e:
            self.fail(f"Failed to fetch ticker price: {e}")

    async def test_paper_trading_logic(self):
        """Kiểm tra logic giao dịch giả lập (Paper Trading)"""
        print("\nTesting paper trading execution...")
        
        # Lấy số dư ban đầu
        initial_balance = await self.okx.get_balance()
        self.assertGreater(initial_balance['USDT'], 0)
        coin = self.okx.symbol.split('/')[0]
        self.assertEqual(initial_balance[coin], 0.0)

        # Chạy lệnh BUY giả lập
        buy_res = await self.okx.execute_trade('BUY', amount_pct=50.0)
        self.assertEqual(buy_res['status'], 'SUCCESS')
        self.assertEqual(buy_res['side'], 'BUY')
        self.assertGreater(buy_res['amount'], 0)

        # Kiểm tra số dư thay đổi
        mid_balance = await self.okx.get_balance()
        self.assertLess(mid_balance['USDT'], initial_balance['USDT'])
        self.assertGreater(mid_balance[coin], 0.0)

        # Chạy lệnh SELL giả lập 100% coin
        sell_res = await self.okx.execute_trade('SELL', amount_pct=100.0)
        self.assertEqual(sell_res['status'], 'SUCCESS')
        self.assertEqual(sell_res['side'], 'SELL')
        
        # Số dư coin sau khi bán hết phải về 0
        final_balance = await self.okx.get_balance()
        self.assertAlmostEqual(final_balance[coin], 0.0, places=5)
        self.assertGreater(final_balance['USDT'], mid_balance['USDT'])
        
        # Kiểm tra lịch sử giao dịch có 2 lệnh
        history = await self.okx.get_trade_history()
        self.assertEqual(len(history), 2)
        print("Paper trading logic: PASS")

    def test_technical_indicators(self):
        """Kiểm tra việc tính toán chỉ báo kỹ thuật của Gemini Service"""
        print("\nTesting technical indicators calculation...")
        dummy_ohlcv = []
        base_time = int(time.time() * 1000) - (100 * 3600 * 1000)
        
        # Tạo 100 nến giả lập
        for i in range(100):
            dummy_ohlcv.append([
                base_time + (i * 3600 * 1000), # timestamp
                100.0 + i,                     # open
                105.0 + i,                     # high
                98.0 + i,                      # low
                102.0 + i,                     # close
                1000.0                         # volume
            ])
            
        df = self.gemini.prepare_indicators(dummy_ohlcv)
        
        self.assertIn('rsi', df.columns)
        self.assertIn('ema_9', df.columns)
        self.assertIn('ema_21', df.columns)
        self.assertIn('macd', df.columns)
        self.assertIn('bb_high', df.columns)
        
        self.assertFalse(pd.isna(df.iloc[-1]['rsi']))
        self.assertFalse(pd.isna(df.iloc[-1]['ema_9']))
        print("Technical indicators calculation: PASS")

if __name__ == '__main__':
    unittest.main()
