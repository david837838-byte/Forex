import unittest
import time
import os
import json
import server

class TestInstitutionalRobustnessSuite(unittest.TestCase):
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
            with server.command_lock:
                server.commands_store.clear()
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

    # 3. 1-Second Heartbeat & Latency (POST /api/mt5/heartbeat)
    def test_03_ea_heartbeat_latency(self):
        client = server.app.test_client()
        res = client.post('/api/mt5/heartbeat', json={
            'secret': server.EA_WEBHOOK_SECRET,
            'timestamp': time.time() - 0.012
        })
        self.assertEqual(res.status_code, 200)

    # 4. Live Account Metrics Sync (POST /api/mt5/account)
    def test_04_account_metrics_sync(self):
        client = server.app.test_client()
        res = client.post('/api/mt5/account', json={
            'secret': server.EA_WEBHOOK_SECRET,
            'balance': 41500.00,
            'equity': 41800.00
        })
        self.assertEqual(res.status_code, 200)
        with server.autotrade_lock:
            self.assertEqual(server.autotrade_state['account']['balance'], 41500.00)

    # 5. Live Market Spreads Sync (POST /api/mt5/market)
    def test_05_market_data_sync(self):
        client = server.app.test_client()
        res = client.post('/api/mt5/market', json={
            'secret': server.EA_WEBHOOK_SECRET,
            'symbol': 'EURUSD',
            'bid': 1.0850,
            'ask': 1.0851,
            'spread': 1.0
        })
        self.assertEqual(res.status_code, 200)

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
                'pnl': 45.00
            }]
        })
        self.assertEqual(res.status_code, 200)
        with server.autotrade_lock:
            self.assertEqual(len(server.autotrade_state['open_positions']), 1)

    # 7. Closed History Mirroring (POST /api/mt5/history)
    def test_07_closed_history_mirroring(self):
        client = server.app.test_client()
        res = client.post('/api/mt5/history', json={
            'secret': server.EA_WEBHOOK_SECRET,
            'history': [{
                'ticket': '10928000',
                'symbol': 'EURUSD',
                'pnl': 120.0
            }]
        })
        self.assertEqual(res.status_code, 200)

    # 8. Stale Heartbeat Detection (> 10s Timeout)
    def test_08_stale_heartbeat_timeout(self):
        with server.autotrade_lock:
            server.autotrade_state['account']['last_heartbeat'] = time.time() - 15.0
        signal = {'symbol': 'EURUSD', 'type': 'BUY', 'entry': 1.0850, 'sl': 1.0825, 'tp1': 1.0900, 'score': 85}
        passed, code, reason = server.validate_trade_risk(signal)
        self.assertFalse(passed)
        self.assertEqual(code, 'MT5_DISCONNECTED')

    # 9. Risk-Based Position Sizing for Forex
    def test_09_risk_sizing_forex(self):
        lot = server.calculate_risk_position_size('EURUSD', 1.0850, 1.0825, 40000.0, 1.0, 5.0)
        self.assertEqual(lot, 1.60)

    # 10. Risk-Based Position Sizing for Gold
    def test_10_risk_sizing_gold(self):
        lot = server.calculate_risk_position_size('XAUUSD', 2480.0, 2476.0, 40000.0, 1.0, 5.0)
        self.assertEqual(lot, 1.00)

    # 11. Max Lot Cap Enforcement
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

    # 19. Consecutive Loss Cooldown Period
    def test_19_consecutive_loss_cooldown(self):
        with server.autotrade_lock:
            server.autotrade_state['daily_stats']['cooldown_until'] = time.time() + 1800
        signal = {'symbol': 'USDCHF', 'type': 'BUY', 'entry': 0.8800, 'sl': 0.8760, 'tp1': 0.8880, 'score': 85}
        passed, code, reason = server.validate_trade_risk(signal)
        self.assertFalse(passed)
        self.assertEqual(code, 'LOSS_COOLDOWN_ACTIVE')

    # 20. Correlation Exposure Limit
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

    # 28. Two-Tier Emergency Stop: Pause Only (POST /api/autotrade/pause)
    def test_28_emergency_pause_keeps_positions(self):
        with server.autotrade_lock:
            server.autotrade_state['open_positions'] = [{'ticket': 'T-1', 'symbol': 'EURUSD', 'pnl': 10.0}]
        client = server.app.test_client()
        res = client.post('/api/autotrade/pause', json={})
        self.assertEqual(res.status_code, 200)
        with server.autotrade_lock:
            self.assertFalse(server.autotrade_state['enabled'])
            self.assertEqual(len(server.autotrade_state['open_positions']), 1)

    # 29. Multi-Asset Contract Specs
    def test_29_multi_asset_specs(self):
        gold = server.get_symbol_spec('XAUUSD')
        self.assertEqual(gold['size'], 100.0)
        forex = server.get_symbol_spec('EURUSD')
        self.assertEqual(forex['size'], 100000.0)

    # 30. Secure Secret Authorization Check
    def test_30_secret_authorization_check(self):
        client = server.app.test_client()
        res = client.post('/api/mt5/sync', json={'secret': 'invalid_secret_key'})
        self.assertEqual(res.status_code, 401)

    # ======================================================================
    # NEW EXPANDED TESTS (31 - 40): FAILURES, RESTARTS & RECONCILIATION
    # ======================================================================

    # 31. MT5 Disconnected During BUY Dispatch -> NO TRADE / Rejected
    def test_31_mt5_disconnected_during_buy_rejection(self):
        with server.autotrade_lock:
            server.autotrade_state['account']['connected'] = False
            server.autotrade_state['account']['last_heartbeat'] = 0.0
        client = server.app.test_client()
        res = client.post('/api/autotrade/execute', json={
            'symbol': 'EURUSD',
            'type': 'BUY',
            'entry': 1.0850,
            'sl': 1.0820,
            'tp1': 1.0900,
            'score': 85
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data['code'], 'MT5_DISCONNECTED')

    # 32. Stale Command TTL Expiry (Command Expired After 60s)
    def test_32_command_ttl_expiration(self):
        cmd = server.queue_trade_command('BUY', 'EURUSD', lot=0.10, entry=1.0850, sl=1.0820, tp1=1.0900)
        # Force command expiry
        with server.command_lock:
            cmd['expires_at'] = time.time() - 10.0 # expired 10s ago
        client = server.app.test_client()
        res = client.get(f'/api/mt5/commands?secret={server.EA_WEBHOOK_SECRET}')
        data = res.get_json()
        # Expired command must NOT be returned for execution
        self.assertEqual(len(data['commands']), 0)

    # 33. EA Restarts -> Recovers State & Commands Without Duplicate Order
    def test_33_ea_restart_recovery(self):
        cmd = server.queue_trade_command('BUY', 'GBPUSD', lot=0.20, entry=1.2950, sl=1.2920, tp1=1.3000)
        client = server.app.test_client()
        # 1st fetch
        res1 = client.get(f'/api/mt5/commands?secret={server.EA_WEBHOOK_SECRET}')
        cmds1 = res1.get_json()['commands']
        self.assertEqual(len(cmds1), 1)
        self.assertEqual(cmds1[0]['command_id'], cmd['command_id'])
        # EA crashed and restarts -> fetches again
        res2 = client.get(f'/api/mt5/commands?secret={server.EA_WEBHOOK_SECRET}')
        cmds2 = res2.get_json()['commands']
        # State machine marked it SENT_TO_EA, so it won't duplicate!
        self.assertEqual(len(cmds2), 0)

    # 34. Backend Restarts -> Restores State from Disk Storage
    def test_34_backend_restart_state_restoration(self):
        with server.autotrade_lock:
            server.autotrade_state['open_positions'] = [{
                'ticket': 'T-PERSIST-123',
                'symbol': 'XAUUSD',
                'type': 'BUY',
                'lot': 0.30,
                'entry': 2480.0,
                'sl': 2470.0,
                'tp1': 2500.0
            }]
            server.save_persisted_state()
        
        # Simulate clean restart by loading persisted state from file
        loaded = server.load_persisted_state()
        self.assertEqual(len(loaded['open_positions']), 1)
        self.assertEqual(loaded['open_positions'][0]['ticket'], 'T-PERSIST-123')

    # 35. Network Timeout During Execution -> Reconciliation Confirms Fill in MT5
    def test_35_reconciliation_verifies_fill_on_network_timeout(self):
        # Backend sent command with temp ticket
        with server.autotrade_lock:
            server.autotrade_state['open_positions'] = [{
                'ticket': 'T-TEMP-777',
                'symbol': 'EURUSD',
                'type': 'BUY',
                'lot': 0.10,
                'entry': 1.0850,
                'sl': 1.0820,
                'tp1': 1.0900,
                'status': 'PENDING_BROKER'
            }]
        
        # MT5 reports that broker successfully filled with broker ticket 99887766
        client = server.app.test_client()
        res = client.post('/api/mt5/command-result', json={
            'secret': server.EA_WEBHOOK_SECRET,
            'command_id': 'CMD-TEST',
            'ticket': '99887766',
            'retcode': 10009, # TRADE_RETCODE_DONE
            'error_message': 'Request executed successfully'
        })
        self.assertEqual(res.status_code, 200)
        with server.autotrade_lock:
            self.assertEqual(server.autotrade_state['open_positions'][0]['ticket'], '99887766')
            self.assertEqual(server.autotrade_state['open_positions'][0]['status'], 'FILLED')

    # 36. Broker Accepts Order but Acknowledgment Lost -> Reconciled via MT5 Positions
    def test_36_reconciliation_lost_ack_reconnection(self):
        # MT5 streams its active positions list containing real ticket #55443322
        mt5_stream = [{
            'ticket': '55443322',
            'symbol': 'USOIL',
            'type': 'BUY',
            'lot': 0.50,
            'entry': 78.50,
            'current_price': 79.00,
            'sl': 77.50,
            'tp1': 80.00,
            'pnl': 250.00
        }]
        server.reconcile_positions_with_mt5(mt5_stream)
        with server.autotrade_lock:
            self.assertEqual(len(server.autotrade_state['open_positions']), 1)
            self.assertEqual(server.autotrade_state['open_positions'][0]['ticket'], '55443322')

    # 37. Manual Trade Opened in MT5 -> Reconciled into UI Without Tampering
    def test_37_manual_trade_discovered_and_preserved(self):
        mt5_manual_stream = [{
            'ticket': 'MANUAL-999',
            'symbol': 'BTCUSD',
            'type': 'SELL',
            'lot': 0.05,
            'entry': 64000.0,
            'current_price': 63500.0,
            'sl': 65000.0,
            'tp1': 62000.0,
            'pnl': 25.00
        }]
        server.reconcile_positions_with_mt5(mt5_manual_stream)
        with server.autotrade_lock:
            self.assertEqual(len(server.autotrade_state['open_positions']), 1)
            pos = server.autotrade_state['open_positions'][0]
            self.assertEqual(pos['ticket'], 'MANUAL-999')
            self.assertEqual(pos['status'], 'OPEN_MANUAL')

    # 38. Manual Modification of SL/TP in MT5 -> Synchronized to Backend
    def test_38_manual_sl_tp_modification_sync(self):
        # Initial position in DB
        with server.autotrade_lock:
            server.autotrade_state['open_positions'] = [{
                'ticket': 'T-SYNC-1',
                'symbol': 'EURUSD',
                'type': 'BUY',
                'lot': 0.10,
                'entry': 1.0850,
                'sl': 1.0820,
                'tp1': 1.0900
            }]
        
        # User manually moves SL to 1.0840 and TP to 1.0950 in MT5
        mt5_modified_stream = [{
            'ticket': 'T-SYNC-1',
            'symbol': 'EURUSD',
            'type': 'BUY',
            'lot': 0.10,
            'entry': 1.0850,
            'sl': 1.0840,
            'tp1': 1.0950,
            'current_price': 1.0860,
            'pnl': 10.0
        }]
        server.reconcile_positions_with_mt5(mt5_modified_stream)
        with server.autotrade_lock:
            pos = server.autotrade_state['open_positions'][0]
            self.assertEqual(pos['sl'], 1.0840)
            self.assertEqual(pos['tp1'], 1.0950)

    # 39. Real Broker Rejection Return Codes Handled & Logged
    def test_39_broker_rejection_codes_mapped(self):
        cmd = server.queue_trade_command('BUY', 'EURUSD', lot=100.0) # oversized lot
        client = server.app.test_client()
        res = client.post('/api/mt5/command-result', json={
            'secret': server.EA_WEBHOOK_SECRET,
            'command_id': cmd['command_id'],
            'ticket': '0',
            'retcode': 10014, # TRADE_RETCODE_INVALID_VOLUME
            'error_message': 'Invalid trade volume'
        })
        self.assertEqual(res.status_code, 200)
        with server.command_lock:
            self.assertEqual(server.commands_store[cmd['command_id']]['status'], 'REJECTED')
            self.assertEqual(server.commands_store[cmd['command_id']]['retcode'], 10014)

    # 40. Full System Restart (Server + MT5 + EA) -> Complete Bidirectional Sync
    def test_40_full_system_restart_sync(self):
        # 1. State in MT5 after restart
        mt5_stream_after_restart = [{
            'ticket': 'RESTART-101',
            'symbol': 'XAUUSD',
            'type': 'BUY',
            'lot': 0.20,
            'entry': 2482.0,
            'current_price': 2486.0,
            'sl': 2475.0,
            'tp1': 2500.0,
            'pnl': 80.0
        }]
        
        # 2. EA calls unified sync
        client = server.app.test_client()
        res = client.post('/api/mt5/sync', json={
            'secret': server.EA_WEBHOOK_SECRET,
            'login': 2001944351,
            'server': 'JustMarkets-Demo',
            'currency': 'USD',
            'balance': 40080.0,
            'equity': 40160.0,
            'margin': 50.0,
            'free_margin': 40110.0,
            'positions': mt5_stream_after_restart
        })
        self.assertEqual(res.status_code, 200)
        
        # 3. Verify website / backend state is 100% reconciled
        with server.autotrade_lock:
            self.assertTrue(server.autotrade_state['account']['connected'])
            self.assertEqual(server.autotrade_state['account']['balance'], 40080.0)
            self.assertEqual(len(server.autotrade_state['open_positions']), 1)
            self.assertEqual(server.autotrade_state['open_positions'][0]['ticket'], 'RESTART-101')

if __name__ == '__main__':
    unittest.main(verbosity=2)
