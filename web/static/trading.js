/**
 * Trading dashboard JavaScript functionality.
 * Handles trading controls, real-time updates, and backtesting interface.
 */

// Trading state
let tradingStatus = null;
let positions = [];
let orders = [];
let performance = null;
let tradingWebSocket = null;

// Initialize trading dashboard
document.addEventListener('DOMContentLoaded', function() {
    initializeTradingDashboard();
    setupTradingWebSocket();
    loadTradingData();
});

/**
 * Initialize trading dashboard
 */
function initializeTradingDashboard() {
    // Set default dates for backtesting
    const today = new Date();
    const oneMonthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
    
    document.getElementById('backtest-start-date').value = oneMonthAgo.toISOString().split('T')[0];
    document.getElementById('backtest-end-date').value = today.toISOString().split('T')[0];
    
    // Load initial trading data
    loadTradingStatus();
    loadPositions();
    loadOrders();
    loadPerformance();
}

/**
 * Setup trading WebSocket connection
 */
function setupTradingWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/v1/trading/ws`;
    
    tradingWebSocket = new WebSocket(wsUrl);
    
    tradingWebSocket.onopen = function() {
        console.log('Trading WebSocket connected');
    };
    
    tradingWebSocket.onmessage = function(event) {
        const message = JSON.parse(event.data);
        handleTradingUpdate(message);
    };
    
    tradingWebSocket.onclose = function() {
        console.log('Trading WebSocket disconnected');
        // Reconnect after 5 seconds
        setTimeout(setupTradingWebSocket, 5000);
    };
    
    tradingWebSocket.onerror = function(error) {
        console.error('Trading WebSocket error:', error);
    };
}

/**
 * Handle trading WebSocket updates
 */
function handleTradingUpdate(message) {
    switch(message.type) {
        case 'status_update':
            updateTradingStatus(message.data);
            break;
        case 'position_update':
            updatePositions(message.data);
            break;
        case 'order_update':
            updateOrders(message.data);
            break;
        case 'pnl_update':
            updatePerformance(message.data);
            break;
        case 'risk_alert':
            showRiskAlert(message.data);
            break;
        case 'trade_signal':
            showTradeSignal(message.data);
            break;
    }
}

/**
 * Load trading status
 */
async function loadTradingStatus() {
    try {
        const response = await fetch('/api/v1/trading/status');
        const status = await response.json();
        updateTradingStatus(status);
    } catch (error) {
        console.error('Error loading trading status:', error);
    }
}

/**
 * Update trading status display
 */
function updateTradingStatus(status) {
    tradingStatus = status;
    
    const statusDiv = document.getElementById('trading-status');
    if (statusDiv) {
        statusDiv.innerHTML = `
            <div class="status-item">
                <span class="label">Status:</span>
                <span class="value ${status.is_running ? 'running' : 'stopped'}">
                    ${status.is_running ? 'Running' : 'Stopped'}
                </span>
            </div>
            <div class="status-item">
                <span class="label">Mode:</span>
                <span class="value">${status.mode}</span>
            </div>
            <div class="status-item">
                <span class="label">Broker:</span>
                <span class="value">${status.broker}</span>
            </div>
            <div class="status-item">
                <span class="label">Strategy:</span>
                <span class="value">${status.strategy || 'None'}</span>
            </div>
            <div class="status-item">
                <span class="label">Armed:</span>
                <span class="value ${status.is_armed ? 'armed' : 'disarmed'}">
                    ${status.is_armed ? 'Yes' : 'No'}
                </span>
            </div>
            <div class="status-item">
                <span class="label">Positions:</span>
                <span class="value">${status.positions_count}</span>
            </div>
            <div class="status-item">
                <span class="label">Total P&L:</span>
                <span class="value ${status.total_pnl >= 0 ? 'positive' : 'negative'}">
                    $${status.total_pnl.toFixed(2)} (${status.total_pnl_pct.toFixed(2)}%)
                </span>
            </div>
            <div class="status-item">
                <span class="label">Risk Status:</span>
                <span class="value risk-${status.risk_status}">${status.risk_status}</span>
            </div>
        `;
    }
}

/**
 * Load positions
 */
async function loadPositions() {
    try {
        const response = await fetch('/api/v1/trading/positions');
        const positionsData = await response.json();
        updatePositions(positionsData);
    } catch (error) {
        console.error('Error loading positions:', error);
    }
}

/**
 * Update positions display
 */
function updatePositions(positionsData) {
    positions = positionsData;
    
    const positionsDiv = document.getElementById('positions');
    if (positionsDiv) {
        if (positions.length === 0) {
            positionsDiv.innerHTML = '<p>No open positions</p>';
        } else {
            positionsDiv.innerHTML = `
                <table class="positions-table">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Side</th>
                            <th>Quantity</th>
                            <th>Entry Price</th>
                            <th>Current Price</th>
                            <th>P&L</th>
                            <th>P&L %</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${positions.map(pos => `
                            <tr>
                                <td>${pos.symbol}</td>
                                <td class="side-${pos.side}">${pos.side.toUpperCase()}</td>
                                <td>${pos.quantity}</td>
                                <td>$${pos.entry_price.toFixed(2)}</td>
                                <td>$${pos.current_price.toFixed(2)}</td>
                                <td class="${pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}">
                                    $${pos.unrealized_pnl.toFixed(2)}
                                </td>
                                <td class="${pos.unrealized_pnl_pct >= 0 ? 'positive' : 'negative'}">
                                    ${pos.unrealized_pnl_pct.toFixed(2)}%
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
    }
}

/**
 * Load orders
 */
async function loadOrders() {
    try {
        const response = await fetch('/api/v1/trading/orders?limit=20');
        const ordersData = await response.json();
        updateOrders(ordersData);
    } catch (error) {
        console.error('Error loading orders:', error);
    }
}

/**
 * Update orders display
 */
function updateOrders(ordersData) {
    orders = ordersData;
    
    const ordersDiv = document.getElementById('orders');
    if (ordersDiv) {
        if (orders.length === 0) {
            ordersDiv.innerHTML = '<p>No recent orders</p>';
        } else {
            ordersDiv.innerHTML = `
                <table class="orders-table">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Side</th>
                            <th>Quantity</th>
                            <th>Type</th>
                            <th>Status</th>
                            <th>Price</th>
                            <th>Time</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${orders.map(order => `
                            <tr>
                                <td>${order.symbol}</td>
                                <td class="side-${order.side}">${order.side.toUpperCase()}</td>
                                <td>${order.quantity}</td>
                                <td>${order.order_type}</td>
                                <td class="status-${order.status}">${order.status}</td>
                                <td>$${order.filled_price || order.limit_price || 'N/A'}</td>
                                <td>${new Date(order.submission_time).toLocaleString()}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
    }
}

/**
 * Load performance metrics
 */
async function loadPerformance() {
    try {
        const response = await fetch('/api/v1/trading/performance');
        const performanceData = await response.json();
        updatePerformance(performanceData);
    } catch (error) {
        console.error('Error loading performance:', error);
    }
}

/**
 * Update performance display
 */
function updatePerformance(performanceData) {
    performance = performanceData;
    
    const performanceDiv = document.getElementById('performance');
    if (performanceDiv) {
        performanceDiv.innerHTML = `
            <div class="performance-metrics">
                <div class="metric">
                    <span class="label">Total Return:</span>
                    <span class="value ${performance.total_return >= 0 ? 'positive' : 'negative'}">
                        $${performance.total_return.toFixed(2)} (${performance.total_return_pct.toFixed(2)}%)
                    </span>
                </div>
                <div class="metric">
                    <span class="label">Win Rate:</span>
                    <span class="value">${(performance.win_rate * 100).toFixed(1)}%</span>
                </div>
                <div class="metric">
                    <span class="label">Total Trades:</span>
                    <span class="value">${performance.total_trades}</span>
                </div>
                <div class="metric">
                    <span class="label">Sharpe Ratio:</span>
                    <span class="value">${performance.sharpe_ratio.toFixed(2)}</span>
                </div>
                <div class="metric">
                    <span class="label">Max Drawdown:</span>
                    <span class="value negative">${performance.max_drawdown.toFixed(2)}%</span>
                </div>
            </div>
        `;
    }
}

/**
 * Trading control functions
 */
function showTradingPanel() {
    document.getElementById('tradingModal').style.display = 'block';
    loadTradingStatus();
}

function hideTradingPanel() {
    document.getElementById('tradingModal').style.display = 'none';
}

function showBacktesting() {
    document.getElementById('backtestModal').style.display = 'block';
}

function hideBacktesting() {
    document.getElementById('backtestModal').style.display = 'none';
}

function showRiskMonitor() {
    document.getElementById('riskModal').style.display = 'block';
    loadRiskStatus();
}

function hideRiskMonitor() {
    document.getElementById('riskModal').style.display = 'none';
}

/**
 * Trading control actions
 */
async function startTrading() {
    try {
        const response = await fetch('/api/v1/trading/start', { method: 'POST' });
        const result = await response.json();
        showNotification(result.message, 'success');
        loadTradingStatus();
    } catch (error) {
        console.error('Error starting trading:', error);
        showNotification('Error starting trading', 'error');
    }
}

async function stopTrading() {
    try {
        const response = await fetch('/api/v1/trading/stop', { method: 'POST' });
        const result = await response.json();
        showNotification(result.message, 'success');
        loadTradingStatus();
    } catch (error) {
        console.error('Error stopping trading:', error);
        showNotification('Error stopping trading', 'error');
    }
}

async function emergencyStop() {
    if (confirm('Are you sure you want to execute emergency stop? This will close all positions immediately.')) {
        try {
            const response = await fetch('/api/v1/trading/emergency_stop', { method: 'POST' });
            const result = await response.json();
            showNotification(result.message, 'warning');
            loadTradingStatus();
        } catch (error) {
            console.error('Error executing emergency stop:', error);
            showNotification('Error executing emergency stop', 'error');
        }
    }
}

async function changeStrategy() {
    const strategy = document.getElementById('strategy-select').value;
    try {
        const response = await fetch('/api/v1/trading/strategy/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ strategy_name: strategy })
        });
        const result = await response.json();
        showNotification(result.message, 'success');
        loadTradingStatus();
    } catch (error) {
        console.error('Error changing strategy:', error);
        showNotification('Error changing strategy', 'error');
    }
}

async function armLiveTrading() {
    const key = document.getElementById('arming-key').value;
    if (!key) {
        showNotification('Please enter arming key', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/v1/trading/arm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'arm', confirmation_key: key })
        });
        const result = await response.json();
        showNotification(result.message, 'success');
        loadTradingStatus();
    } catch (error) {
        console.error('Error arming live trading:', error);
        showNotification('Error arming live trading', 'error');
    }
}

async function disarmLiveTrading() {
    try {
        const response = await fetch('/api/v1/trading/arm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'disarm', confirmation_key: '' })
        });
        const result = await response.json();
        showNotification(result.message, 'success');
        loadTradingStatus();
    } catch (error) {
        console.error('Error disarming live trading:', error);
        showNotification('Error disarming live trading', 'error');
    }
}

/**
 * Backtesting functions
 */
async function runBacktest() {
    const strategy = document.getElementById('backtest-strategy').value;
    const symbols = document.getElementById('backtest-symbols').value.split(',').map(s => s.trim());
    const startDate = document.getElementById('backtest-start-date').value;
    const endDate = document.getElementById('backtest-end-date').value;
    const initialBalance = parseFloat(document.getElementById('backtest-initial-balance').value);
    
    try {
        const response = await fetch('/api/v1/backtest/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                strategy_name: strategy,
                symbols: symbols,
                start_date: startDate + 'T00:00:00Z',
                end_date: endDate + 'T23:59:59Z',
                initial_balance: initialBalance,
                engine_type: 'vectorized'
            })
        });
        const result = await response.json();
        showNotification('Backtest started', 'success');
        monitorBacktest(result.backtest_id);
    } catch (error) {
        console.error('Error running backtest:', error);
        showNotification('Error running backtest', 'error');
    }
}

async function monitorBacktest(backtestId) {
    const resultsDiv = document.getElementById('backtest-results');
    resultsDiv.innerHTML = '<p>Running backtest...</p>';
    
    const checkStatus = async () => {
        try {
            const response = await fetch(`/api/v1/backtest/status/${backtestId}`);
            const status = await response.json();
            
            if (status.status === 'completed') {
                const resultsResponse = await fetch(`/api/v1/backtest/results/${backtestId}`);
                const results = await resultsResponse.json();
                displayBacktestResults(results);
            } else if (status.status === 'failed') {
                resultsDiv.innerHTML = `<p>Backtest failed: ${status.message}</p>`;
            } else {
                setTimeout(checkStatus, 2000);
            }
        } catch (error) {
            console.error('Error monitoring backtest:', error);
            resultsDiv.innerHTML = '<p>Error monitoring backtest</p>';
        }
    };
    
    checkStatus();
}

function displayBacktestResults(results) {
    const resultsDiv = document.getElementById('backtest-results');
    
    if (results.combined_metrics) {
        const metrics = results.combined_metrics;
        resultsDiv.innerHTML = `
            <div class="backtest-results">
                <h4>Backtest Results</h4>
                <div class="metrics-grid">
                    <div class="metric">
                        <span class="label">Total Return:</span>
                        <span class="value">${metrics.total_return_pct.toFixed(2)}%</span>
                    </div>
                    <div class="metric">
                        <span class="label">Total Trades:</span>
                        <span class="value">${metrics.total_trades}</span>
                    </div>
                    <div class="metric">
                        <span class="label">Win Rate:</span>
                        <span class="value">${(metrics.win_rate * 100).toFixed(1)}%</span>
                    </div>
                    <div class="metric">
                        <span class="label">Sharpe Ratio:</span>
                        <span class="value">${metrics.sharpe_ratio.toFixed(2)}</span>
                    </div>
                    <div class="metric">
                        <span class="label">Max Drawdown:</span>
                        <span class="value">${metrics.max_drawdown.toFixed(2)}%</span>
                    </div>
                </div>
            </div>
        `;
    } else {
        resultsDiv.innerHTML = '<p>No results available</p>';
    }
}

/**
 * Risk monitoring functions
 */
async function loadRiskStatus() {
    try {
        const response = await fetch('/api/v1/trading/risk/status');
        const riskStatus = await response.json();
        updateRiskStatus(riskStatus);
    } catch (error) {
        console.error('Error loading risk status:', error);
    }
}

function updateRiskStatus(riskStatus) {
    const riskDiv = document.getElementById('risk-status');
    if (riskDiv) {
        riskDiv.innerHTML = `
            <div class="risk-metrics">
                <div class="metric">
                    <span class="label">Status:</span>
                    <span class="value risk-${riskStatus.status}">${riskStatus.status}</span>
                </div>
                <div class="metric">
                    <span class="label">Warnings:</span>
                    <span class="value">${riskStatus.warnings ? riskStatus.warnings.length : 0}</span>
                </div>
            </div>
        `;
    }
}

/**
 * Utility functions
 */
function showNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        document.body.removeChild(notification);
    }, 3000);
}

function showRiskAlert(alert) {
    showNotification(`Risk Alert: ${alert.message}`, 'warning');
}

function showTradeSignal(signal) {
    showNotification(`Trade Signal: ${signal.action} ${signal.symbol}`, 'info');
}

/**
 * Load all trading data
 */
async function loadTradingData() {
    await Promise.all([
        loadTradingStatus(),
        loadPositions(),
        loadOrders(),
        loadPerformance()
    ]);
}

// Auto-refresh trading data every 30 seconds
setInterval(loadTradingData, 30000);
