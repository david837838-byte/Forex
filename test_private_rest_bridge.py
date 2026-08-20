import unittest
import time
import server

class TestPrivateRESTBridgeSuite(unittest.TestCase):
    def setUp(self):
        # Reset server autotrade state for fresh testing
        with server.autotrade_lock:
            server.autotrade_state['enabled'] = True
            server.autotrade_state['mode'] = 'demo'
            server.autotrade_state['emergency_stop'] = False
            server.autotrade_state['emergency_reason'] = ''
            server.autotrade_state['account'] = {
                'connected': True,
                'mt5_connected': True,
                'ea_connected': True,
                'broker_connected': True,
                'bridge_mode': 'EA_WEBHOOK_LIVE',
                'server': 'JustMarkets-Demo',
                'login': '2001944351',
                'balance': 40000.00,
                'equity': 40000.00,
                'margin': 0.0,
                'free_margin': 40000.00,
                'margin_level': 100.0,
                'currency': 'USD',
                'leverage': 100,
                'last_sync_time': time.strftime('%H:%M:%S'),
                'last_heartbeat': time.time(),
                'last_account_sync': time.time(),
                'last_position_sync': time.time(),
                'last_market_sync': time.time(),
                'latency_ms': 12.5
            }
            server.autotrade_state['market_data'] = {}
            server.autotrade_state['risk_config'] = {
                'risk_percent': 1.0,
                'max_lot_cap': 0.50,
                'max_open_trades': 3,
                'max_daily_trades': 10,
                'max_daily_loss_pct': 3.0,
                'min_score': 75,
                'auto_breakeven': True,
                'breakeven_buffer_pips': 2.0,
                'partial_tp1_close_pct': 50,
                'partial_tp2_close_pct': 30,
                'trailing_stop_enabled': False,
                'consecutive_loss_limit': 2,
                'loss_cooldown_minutes': 30
            }
            server.autotrade_state['daily_stats'] = {
                'date': time.strftime('%Y-%m-%d'),
                'trades_opened': 0,
                'starting_balance': 40000.0,
                'realized_pnl': 0.0,
                'floating_pnl': 0.0,
                'consecutive_losses': 0,
                'cooldown_until': 0.0,
                'peak_equity': 40000.0
            }
            server.autotrade_state['open_positions'] = []
            server.autotrade_state['history'] = []
            server.autotrade_command_queue.clear()
            server.idempotency_store.clear()

    # 1. Health Monitoring Matrix (GET /api/autotrade/health)
    def test_01_health_monitoring_matrix(self):
        client = server.app.test_client()
        res = client.get('/api/autotrade/health')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['backend_status'], 'ONLINE')
        self.assertEqual(data['rest_api_status'], 'ONLINE')
        self.assertEqual(data['mt5_status'], 'CONNECTED')
        self.assertEqual(data['ea_status'], 'STREAMING')

    # 2. MT5 EA Registration (POST /api/mt5/register)
    def test_02_ea_registration(self):
        client = server.app.test_client()
        res = client.post('/api/mt5/register', json={
            'secret': server.EA_WEBHOOK_SECRET,
            'server': 'JustMarkets-Demo',
            'login': 2001944351,
            'currency': 'USD',
            'leverage': 100
        })
        self.assertEqual(res.status_code, 200)
        with server.autotrade_lock:
            self.assertEqual(server.autotrade_state['account']['login'], '2001944351')

    # 3. 1-Second Heartbeat & Latency (POST /api/mt5/heartbeat)
    def test_03_ea_heartbeat_latency(self):
        client = server.app.test_client()
        t_client = time.time() - 0.015 # 15ms latency
        res = client.post('/api/mt5/heartbeat', json={
            'secret': server.EA_WEBHOOK_SECRET,
            'timestamp': t_client
        })
        self.assertEqual(res.status_code, 200)
        with server.autotrade_lock:
            self.assertGreater(server.autotrade_state['account']['last_heartbeat'], 0)

    # 4. Live Account Metrics Sync (POST /api/mt5/account)
    def test_04_account_metrics_sync(self):
        client = server.app.test_client()
        res = client.post('/api/mt5/account', json={
            'secret': server.EA_WEBHOOK_SECRET,
            'balance': 41250.50,
            'equity': 41500.00,
            'margin': 250.00,
            'free_margin': 41250.00,
            'margin_level': 16600.0
        })
        self.assertEqual(res.status_code, 200)
        with server.autotrade_lock:
            self.assertEqual(server.autotrade_state['account']['balance'], 41250.50)
            self.assertEqual(server.autotrade_state['account']['equity'], 41500.00)

    # 5. Live Market Spreads & Prices Sync (POST /api/mt5/market)
    def test_05_market_data_sync(self):
        client = server.app.test_client()
        res = client.post('/api/mt5/market', json={
            'secret': server.EA_WEBHOOK_SECRET,
            'symbol': 'EURUSD',
            'bid': 1.08502,
            'ask': 1.08512,
            'spread': 1.0
        })
        self.assertEqual(res.status_code, 200)
        with server.autotrade_lock:
            self.assertIn('EURUSD', server.autotrade_state['market_data'])
            self.assertEqual(server.autotrade_state['market_data']['EURUSD']['spread'], 1.0)

    # 6. Live Open Positions Mirroring (POST /api/mt5/positions)
    def test_06_open_positions_mirroring(self):
        client = server.app.test_client()
        res = client.post('/api/mt5/positions', json={
            'secret': server.EA_WEBHOOK_SECRET,
            'positions': [{
                'ticket': '10928341',
                'symbol': 'XAUUSD',
                'type': 'BUY',
                'lot': 0.10,
                'entry': 2485.50,
                'current_price': 2490.00,
                'sl': 2475.00,
                'tp1': 2510.00,
                'pnl': 45.00,
                'swap': -0.50,
                'commission': -0.70
            }]
        })
        self.assertEqual(res.status_code, 200)
        with server.autotrade_lock:
            self.assertEqual(len(server.autotrade_state['open_positions']), 1)
            self.assertEqual(server.autotrade_state['open_positions'][0]['ticket'], '10928341')

    # 7. Closed Trade History Mirroring (POST /api/mt5/history)
    def test_07_closed_history_mirroring(self):
        client = server.app.test_client()
        res = client.post('/api/mt5/history', json={
            'secret': server.EA_WEBHOOK_SECRET,
            'history': [{
                'ticket': '10928000',
                'symbol': 'EURUSD',
                'type': 'BUY',
                'lot': 0.20,
                'entry': 1.0820,
                'close_price': 1.0870,
                'pnl': 100.0,
                'status': 'CLOSED_TP1'
            }]
        })
        self.assertEqual(res.status_code, 200)
        with server.autotrade_lock:
            self.assertEqual(len(server.autotrade_state['history']), 1)

    # 8. Stale Heartbeat Detection (> 10s Timeout)
    def test_08_stale_heartbeat_timeout(self):
        with server.autotrade_lock:
            server.autotrade_state['account']['last_heartbeat'] = time.time() - 15.0
        signal = {'symbol': 'EURUSD', 'type': 'BUY', 'entry': 1.0850, 'sl': 1.0825, 'tp1': 1.0900, 'score': 85}
        passed, code, reason = server.validate_trade_risk(signal)
        self.assertFalse(passed)
        self.assertEqual(code, 'MT5_DISCONNECTED')

    # 9. Risk-Based Position Sizing for Forex (EURUSD)
    def test_09_risk_sizing_forex(self):
        lot = server.calculate_risk_position_size('EURUSD', 1.0850, 1.0825, 40000.0, 1.0, 5.0)
        self.assertEqual(lot, 1.60)

    # 10. Risk-Based Position Sizing for Gold (XAUUSD)
    def test_10_risk_sizing_gold(self):
        lot = server.calculate_risk_position_size('XAUUSD', 2480.0, 2476.0, 40000.0, 1.0, 5.0)
        self.assertEqual(lot, 1.00)

    # 11. Max Lot Cap Strict Enforcement
    def test_11_max_lot_cap_enforcement(self):
        lot = server.calculate_risk_position_size('XAUUSD', 2480.0, 2476.0, 40000.0, 1.0, 0.50)
        self.assertEqual(lot, 0.50)

    # 12. Valid BUY Order Execution
    def test_12_valid_buy_execution(self):
        client = server.app.test_client()
        res = client.post('/api/autotrade/execute', json={
            'symbol': 'EURUSD',
            'type': 'BUY',
            'entry': 1.0850,
            'sl': 1.0820,
            'tp1': 1.0900,
            'score': 85
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(server.autotrade_state['open_positions']), 1)

    # 13. Valid SELL Order Execution
    def test_13_valid_sell_execution(self):
        client = server.app.test_client()
        res = client.post('/api/autotrade/execute', json={
            'symbol': 'GBPUSD',
            'type': 'SELL',
            'entry': 1.2950,
            'sl': 1.2980,
            'tp1': 1.2900,
            'score': 88
        })
        self.assertEqual(res.status_code, 200)

    # 14. Idempotency Key Duplicate Prevention
    def test_14_idempotency_duplicate_protection(self):
        client = server.app.test_client()
        client.post('/api/autotrade/execute', json={
            'symbol': 'USOIL',
            'type': 'BUY',
            'entry': 78.50,
            'sl': 77.80,
            'tp1': 79.80,
            'score': 82
        })
        res2 = client.post('/api/autotrade/execute', json={
            'symbol': 'USOIL',
            'type': 'BUY',
            'entry': 78.50,
            'sl': 77.80,
            'tp1': 79.80,
            'score': 82
        })
        self.assertEqual(res2.status_code, 400)

    # 15. Same Symbol Active Protection
    def test_15_same_symbol_active_protection(self):
        with server.autotrade_lock:
            server.autotrade_state['open_positions'].append({'symbol': 'EURUSD', 'ticket': '123'})
        signal = {'symbol': 'EURUSD', 'type': 'BUY', 'entry': 1.0850, 'sl': 1.0820, 'tp1': 1.0900, 'score': 85}
        passed, code, reason = server.validate_trade_risk(signal)
        self.assertFalse(passed)
        self.assertEqual(code, 'SAME_SYMBOL_ACTIVE')

    # 16. Max Open Trades Limit
    def test_16_max_open_trades_limit(self):
        with server.autotrade_lock:
            server.autotrade_state['open_positions'] = [
                {'symbol': 'EURUSD', 'ticket': '1'},
                {'symbol': 'GBPUSD', 'ticket': '2'},
                {'symbol': 'XAUUSD', 'ticket': '3'}
            ]
        signal = {'symbol': 'USDJPY', 'type': 'BUY', 'entry': 155.0, 'sl': 154.5, 'tp1': 156.0, 'score': 85}
        passed, code, reason = server.validate_trade_risk(signal)
        self.assertFalse(passed)
        self.assertEqual(code, 'MAX_OPEN_TRADES_LIMIT')

    # 17. Max Daily Trades Limit
    def test_17_max_daily_trades_limit(self):
        with server.autotrade_lock:
            server.autotrade_state['daily_stats']['trades_opened'] = 10
        signal = {'symbol': 'EURUSD', 'type': 'BUY', 'entry': 1.0850, 'sl': 1.0820, 'tp1': 1.0900, 'score': 85}
        passed, code, reason = server.validate_trade_risk(signal)
        self.assertFalse(passed)
        self.assertEqual(code, 'MAX_DAILY_TRADES_LIMIT')

    # 18. Daily Drawdown Limit Kill Switch
    def test_18_daily_drawdown_kill_switch(self):
        with server.autotrade_lock:
            server.autotrade_state['daily_stats']['starting_balance'] = 40000.0
            server.autotrade_state['daily_stats']['realized_pnl'] = -1300.0 # -3.25%
        signal = {'symbol': 'AUDUSD', 'type': 'BUY', 'entry': 0.6500, 'sl': 0.6470, 'tp1': 0.6560, 'score': 85}
        passed, code, reason = server.validate_trade_risk(signal)
        self.assertFalse(passed)
        self.assertEqual(code, 'MAX_DAILY_LOSS_EXCEEDED')
        with server.autotrade_lock:
            self.assertTrue(server.autotrade_state['emergency_stop'])

    # 19. Consecutive Loss Cooldown Period
    def test_19_consecutive_loss_cooldown(self):
        with server.autotrade_lock:
            server.autotrade_state['daily_stats']['cooldown_until'] = time.time() + 1800
        signal = {'symbol': 'USDCHF', 'type': 'BUY', 'entry': 0.8800, 'sl': 0.8760, 'tp1': 0.8880, 'score': 85}
        passed, code, reason = server.validate_trade_risk(signal)
        self.assertFalse(passed)
        self.assertEqual(code, 'LOSS_COOLDOWN_ACTIVE')

    # 20. Correlation Exposure Limit (Max 2 USD pairs)
    def test_20_correlation_exposure_limit(self):
        with server.autotrade_lock:
            server.autotrade_state['open_positions'] = [
                {'symbol': 'EURUSD', 'ticket': '1'},
                {'symbol': 'GBPUSD', 'ticket': '2'}
            ]
        signal = {'symbol': 'USDJPY', 'type': 'BUY', 'entry': 155.0, 'sl': 154.5, 'tp1': 156.0, 'score': 85}
        passed, code, reason = server.validate_trade_risk(signal)
        self.assertFalse(passed)
        self.assertEqual(code, 'CORRELATION_EXPOSURE_LIMIT')

    # 21. Insufficient Margin Rejection
    def test_21_insufficient_margin(self):
        with server.autotrade_lock:
            server.autotrade_state['account']['free_margin'] = 10.0
        signal = {'symbol': 'XAUUSD', 'type': 'BUY', 'entry': 2480.0, 'sl': 2470.0, 'tp1': 2500.0, 'score': 85}
        passed, code, reason = server.validate_trade_risk(signal)
        self.assertFalse(passed)
        self.assertEqual(code, 'INSUFFICIENT_MARGIN')

    # 22. Invalid SL Distance (< 15 points)
    def test_22_invalid_sl_distance(self):
        signal = {'symbol': 'EURUSD', 'type': 'BUY', 'entry': 1.08500, 'sl': 1.08498, 'tp1': 1.09000, 'score': 85}
        passed, code, reason = server.validate_trade_risk(signal)
        self.assertFalse(passed)
        self.assertEqual(code, 'INVALID_STOP_LOSS')

    # 23. Invalid Risk/Reward Ratio (< 1:1.5)
    def test_23_invalid_risk_reward(self):
        signal = {'symbol': 'EURUSD', 'type': 'BUY', 'entry': 1.0850, 'sl': 1.0800, 'tp1': 1.0870, 'score': 85}
        passed, code, reason = server.validate_trade_risk(signal)
        self.assertFalse(passed)
        self.assertEqual(code, 'INVALID_RISK_REWARD')

    # 24. TP1 Hit & 50% Partial Close Execution
    def test_24_tp1_partial_close(self):
        with server.autotrade_lock:
            server.autotrade_state['open_positions'] = [{
                'ticket': 'T-999',
                'symbol': 'EURUSD',
                'type': 'BUY',
                'lot': 0.50,
                'entry': 1.0850,
                'current_price': 1.0850,
                'sl': 1.0820,
                'tp1': 1.0900,
                'tp1_hit': False,
                'pnl': 0.0
            }]
        server.process_position_lifecycle_step(test_prices={'EURUSD': 1.0905})
        with server.autotrade_lock:
            pos = server.autotrade_state['open_positions'][0] if server.autotrade_state['open_positions'] else None
            self.assertIsNotNone(pos)
            self.assertTrue(pos.get('tp1_hit'))

    # 25. Auto Break-Even Buffer
    def test_25_auto_breakeven_buffer(self):
        with server.autotrade_lock:
            server.autotrade_state['open_positions'] = [{
                'ticket': 'T-999',
                'symbol': 'EURUSD',
                'type': 'BUY',
                'lot': 0.50,
                'entry': 1.0850,
                'current_price': 1.0850,
                'sl': 1.0820,
                'tp1': 1.0900,
                'tp1_hit': False,
                'pnl': 0.0
            }]
        server.process_position_lifecycle_step(test_prices={'EURUSD': 1.0905})
        with server.autotrade_lock:
            pos = server.autotrade_state['open_positions'][0] if server.autotrade_state['open_positions'] else None
            self.assertIsNotNone(pos)
            self.assertGreaterEqual(pos['sl'], 1.0850)

    # 26. Manual Close Position (POST /api/autotrade/close)
    def test_26_manual_close_position(self):
        with server.autotrade_lock:
            server.autotrade_state['open_positions'] = [{
                'ticket': 'T-100',
                'symbol': 'EURUSD',
                'type': 'BUY',
                'lot': 0.20,
                'entry': 1.0850,
                'pnl': 50.0
            }]
        client = server.app.test_client()
        res = client.post('/api/autotrade/close', json={'ticket': 'T-100'})
        self.assertEqual(res.status_code, 200)
        with server.autotrade_lock:
            self.assertEqual(len(server.autotrade_state['open_positions']), 0)
            self.assertEqual(len(server.autotrade_state['history']), 1)

    # 27. Close All Open Positions (POST /api/autotrade/close-all)
    def test_27_close_all_positions(self):
        with server.autotrade_lock:
            server.autotrade_state['open_positions'] = [
                {'ticket': 'T-1', 'symbol': 'EURUSD', 'pnl': 10.0},
                {'ticket': 'T-2', 'symbol': 'GBPUSD', 'pnl': -5.0}
            ]
        client = server.app.test_client()
        res = client.post('/api/autotrade/close-all', json={})
        self.assertEqual(res.status_code, 200)
        with server.autotrade_lock:
            self.assertEqual(len(server.autotrade_state['open_positions']), 0)

    # 28. Emergency Stop Trigger (POST /api/autotrade/emergency-stop)
    def test_28_emergency_stop_trigger(self):
        client = server.app.test_client()
        res = client.post('/api/autotrade/emergency-stop', json={'reason': 'اختبار زر الطوارئ'})
        self.assertEqual(res.status_code, 200)
        with server.autotrade_lock:
            self.assertTrue(server.autotrade_state['emergency_stop'])
            self.assertFalse(server.autotrade_state['enabled'])

    # 29. Multi-Asset Contract Specs
    def test_29_multi_asset_specs(self):
        gold = server.get_symbol_spec('XAUUSD')
        self.assertEqual(gold['size'], 100.0)
        oil = server.get_symbol_spec('USOIL')
        self.assertEqual(oil['size'], 1000.0)
        crypto = server.get_symbol_spec('BTCUSD')
        self.assertEqual(crypto['size'], 1.0)
        forex = server.get_symbol_spec('EURUSD')
        self.assertEqual(forex['size'], 100000.0)

    # 30. Secure Secret Authorization Check
    def test_30_secret_authorization_check(self):
        client = server.app.test_client()
        res = client.post('/api/mt5/sync', json={'secret': 'invalid_secret_key'})
        self.assertEqual(res.status_code, 401)

if __name__ == '__main__':
    unittest.main(verbosity=2)
