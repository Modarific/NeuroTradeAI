/**
 * NeuroTradeAI - Professional Trading Dashboard
 * Advanced JavaScript for real-time trading system
 */

// Global state management
const AppState = {
    isConnected: false,
    isTrading: false,
    isArmed: false,
    currentStrategy: 'mean_reversion',
    autoRefresh: true,
    refreshInterval: null,
    websocket: null,
    marketData: {},
    positions: [],
    orders: [],
    performance: {}
};

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupEventListeners();
    connectWebSocket();
    startAutoRefresh();
});

// Initialize application components
function initializeApp() {
    console.log('🚀 Initializing NeuroTradeAI Dashboard...');
    
    // Set up navigation
    setupNavigation();
    
    // Initialize date inputs
    initializeDateInputs();
    
    // Load initial data
    loadInitialData();
    
    // Update UI state
    updateConnectionStatus(false);
    updateTradingStatus();
    
    console.log('✅ Dashboard initialized successfully');
}

// Set up navigation between sections
function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.content-section');
    
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Remove active class from all items and sections
            navItems.forEach(nav => nav.classList.remove('active'));
            sections.forEach(section => section.classList.remove('active'));
            
            // Add active class to clicked item
            item.classList.add('active');
            
            // Show corresponding section
            const sectionId = item.dataset.section;
            const targetSection = document.getElementById(sectionId);
            if (targetSection) {
                targetSection.classList.add('active');
            }
        });
    });
}

// Set up event listeners
function setupEventListeners() {
    // Tab switching for trading data
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            
            // Remove active class from all tabs and panes
            tabBtns.forEach(t => t.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));
            
            // Add active class to clicked tab and corresponding pane
            btn.classList.add('active');
            const targetPane = document.getElementById(`${tabName}-tab`);
            if (targetPane) {
                targetPane.classList.add('active');
            }
        });
    });
    
    // Modal close handlers
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal')) {
            closeAllModals();
        }
    });
    
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeAllModals();
        }
    });
}

// Initialize date inputs with default values
function initializeDateInputs() {
    const today = new Date();
    const threeMonthsAgo = new Date(today.getFullYear(), today.getMonth() - 3, today.getDate());
    
    const startDateInput = document.getElementById('backtest-start');
    const endDateInput = document.getElementById('backtest-end');
    
    if (startDateInput) {
        startDateInput.value = threeMonthsAgo.toISOString().split('T')[0];
    }
    
    if (endDateInput) {
        endDateInput.value = today.toISOString().split('T')[0];
    }
}

// Load initial data
async function loadInitialData() {
    try {
        await Promise.all([
            updateMarketData(),
            updateTradingStatus(),
            updatePositions(),
            updateOrders()
        ]);
    } catch (error) {
        console.error('Error loading initial data:', error);
        showNotification('Failed to load initial data', 'error');
    }
}

// WebSocket connection
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/stream`;
    
    try {
        AppState.websocket = new WebSocket(wsUrl);
        
        AppState.websocket.onopen = function() {
            console.log('🔗 WebSocket connected');
            AppState.isConnected = true;
            updateConnectionStatus(true);
        };
        
        AppState.websocket.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
        
        AppState.websocket.onclose = function() {
            console.log('🔌 WebSocket disconnected');
            AppState.isConnected = false;
            updateConnectionStatus(false);
            
            // Attempt to reconnect after 5 seconds
            setTimeout(connectWebSocket, 5000);
        };
        
        AppState.websocket.onerror = function(error) {
            console.error('WebSocket error:', error);
            AppState.isConnected = false;
            updateConnectionStatus(false);
        };
    } catch (error) {
        console.error('Failed to connect WebSocket:', error);
        AppState.isConnected = false;
        updateConnectionStatus(false);
    }
}

// Handle WebSocket messages
function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'market_data':
            updateMarketDataTable(data.data);
            break;
        case 'trading_status':
            updateTradingStatusDisplay(data.data);
            break;
        case 'position_update':
            updatePositionsTable(data.data);
            break;
        case 'order_update':
            updateOrdersTable(data.data);
            break;
        case 'performance_update':
            updatePerformanceMetrics(data.data);
            break;
        case 'alert':
            showNotification(data.message, data.level || 'info');
            break;
        default:
            console.log('Unknown WebSocket message type:', data.type);
    }
}

// Update connection status
function updateConnectionStatus(connected) {
    const statusIndicator = document.getElementById('connection-status');
    if (statusIndicator) {
        statusIndicator.className = `status-indicator ${connected ? 'connected' : 'disconnected'}`;
        statusIndicator.innerHTML = `
            <i class="fas fa-circle"></i>
            <span>${connected ? 'Connected' : 'Disconnected'}</span>
        `;
    }
}

// Auto refresh functionality
function startAutoRefresh() {
    if (AppState.autoRefresh) {
        AppState.refreshInterval = setInterval(async () => {
            if (AppState.isConnected) {
                await updateMarketData();
                await updateTradingStatus();
            }
        }, 5000); // Refresh every 5 seconds
    }
}

function toggleAutoRefresh() {
    AppState.autoRefresh = !AppState.autoRefresh;
    
    const icon = document.getElementById('auto-refresh-icon');
    const text = document.getElementById('auto-refresh-text');
    
    if (AppState.autoRefresh) {
        icon.className = 'fas fa-pause';
        text.textContent = 'Auto Refresh';
        startAutoRefresh();
    } else {
        icon.className = 'fas fa-play';
        text.textContent = 'Auto Refresh';
        if (AppState.refreshInterval) {
            clearInterval(AppState.refreshInterval);
            AppState.refreshInterval = null;
        }
    }
}

// Market data functions
async function updateMarketData() {
    try {
        // Try to fetch from trading data endpoint first
        const response = await fetch('/api/v1/trading/data/latest');
        if (response.ok) {
            const data = await response.json();
            AppState.marketData = data;
            updateMarketDataTable(data);
            updateMetrics(data);
            return;
        }
    } catch (error) {
        console.log('Trading data endpoint not available, using mock data');
    }
    
    // Fallback to mock data
    const mockData = generateMockMarketData();
    AppState.marketData = mockData;
    updateMarketDataTable(mockData);
    updateMetrics(mockData);
}

function generateMockMarketData() {
    const symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN', 'META', 'NVDA', 'NFLX'];
    const data = {};
    
    symbols.forEach(symbol => {
        const basePrice = Math.random() * 1000 + 50;
        const change = (Math.random() - 0.5) * 10;
        const changePercent = (change / basePrice) * 100;
        
        data[symbol] = {
            price: basePrice + change,
            open: basePrice,
            high: basePrice + Math.random() * 5,
            low: basePrice - Math.random() * 5,
            close: basePrice + change,
            volume: Math.floor(Math.random() * 10000000) + 1000000,
            change: change,
            change_percent: changePercent,
            timestamp: new Date().toISOString(),
            signal: ['BUY', 'SELL', 'HOLD'][Math.floor(Math.random() * 3)],
            rsi: Math.random() * 100,
            bb_position: Math.random()
        };
    });
    
    return data;
}

function updateMarketDataTable(data) {
    const tbody = document.getElementById('market-data');
    if (!tbody) return;
    
    if (!data || Object.keys(data).length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="loading">Loading market data...</td></tr>';
        return;
    }
    
    const rows = Object.entries(data).map(([symbol, info]) => {
        const change = info.change || 0;
        const changePercent = info.change_percent || 0;
        const changeClass = change >= 0 ? 'positive' : 'negative';
        const signal = info.signal || 'N/A';
        const signalClass = getSignalClass(signal);
        
        return `
            <tr>
                <td><strong>${symbol}</strong></td>
                <td>$${info.price?.toFixed(2) || 'N/A'}</td>
                <td class="${changeClass}">
                    ${change >= 0 ? '+' : ''}${change.toFixed(2)} (${changePercent.toFixed(2)}%)
                </td>
                <td>${info.volume?.toLocaleString() || 'N/A'}</td>
                <td>${info.rsi?.toFixed(2) || 'N/A'}</td>
                <td>${info.bb_position?.toFixed(3) || 'N/A'}</td>
                <td><span class="signal-badge ${signalClass}">${signal}</span></td>
                <td>${formatTime(info.timestamp)}</td>
            </tr>
        `;
    }).join('');
    
    tbody.innerHTML = rows;
}

function getSignalClass(signal) {
    switch (signal.toLowerCase()) {
        case 'buy': return 'signal-buy';
        case 'sell': return 'signal-sell';
        case 'hold': return 'signal-hold';
        default: return 'signal-neutral';
    }
}

// Trading functions
async function startTrading() {
    try {
        const response = await fetch('/api/v1/trading/start', {
            method: 'POST'
        });
        
        if (response.ok) {
            AppState.isTrading = true;
            updateTradingStatus();
            showNotification('Trading started successfully!', 'success');
        } else {
            const error = await response.json();
            showNotification('Failed to start trading: ' + error.detail, 'error');
        }
    } catch (error) {
        console.error('Error starting trading:', error);
        showNotification('Error starting trading: ' + error.message, 'error');
    }
}

async function stopTrading() {
    try {
        const response = await fetch('/api/v1/trading/stop', {
            method: 'POST'
        });
        
        if (response.ok) {
            AppState.isTrading = false;
            updateTradingStatus();
            showNotification('Trading stopped successfully!', 'success');
        } else {
            const error = await response.json();
            showNotification('Failed to stop trading: ' + error.detail, 'error');
        }
    } catch (error) {
        console.error('Error stopping trading:', error);
        showNotification('Error stopping trading: ' + error.message, 'error');
    }
}

async function emergencyStop() {
    if (confirm('Are you sure you want to emergency stop all trading?')) {
        try {
            const response = await fetch('/api/v1/trading/emergency-stop', {
                method: 'POST'
            });
            
            if (response.ok) {
                AppState.isTrading = false;
                AppState.isArmed = false;
                updateTradingStatus();
                showNotification('Emergency stop executed!', 'warning');
            } else {
                const error = await response.json();
                showNotification('Failed to emergency stop: ' + error.detail, 'error');
            }
        } catch (error) {
            console.error('Error emergency stopping:', error);
            showNotification('Error emergency stopping: ' + error.message, 'error');
        }
    }
}

async function updateTradingStatus() {
    try {
        const response = await fetch('/api/v1/trading/status');
        if (response.ok) {
            const status = await response.json();
            updateTradingStatusDisplay(status);
        }
    } catch (error) {
        console.error('Error fetching trading status:', error);
    }
}

function updateTradingStatusDisplay(status) {
    const statusElement = document.getElementById('trading-status');
    if (statusElement) {
        const statusClass = status.running ? 'running' : 'stopped';
        const statusIcon = status.running ? 'play-circle' : 'stop-circle';
        const statusText = status.running ? 'Running' : 'Stopped';
        
        statusElement.innerHTML = `
            <div class="status-badge ${statusClass}">
                <i class="fas fa-${statusIcon}"></i>
                <span>${statusText}</span>
            </div>
        `;
    }
    
    AppState.isTrading = status.running;
    AppState.isArmed = status.is_armed;
}

// Strategy functions
async function changeStrategy() {
    const strategy = document.getElementById('strategy-select').value;
    
    try {
        const response = await fetch('/api/v1/trading/strategy', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                strategy: strategy
            })
        });
        
        if (response.ok) {
            AppState.currentStrategy = strategy;
            showNotification(`Strategy changed to ${strategy}`, 'success');
        } else {
            const error = await response.json();
            showNotification('Failed to change strategy: ' + error.detail, 'error');
        }
    } catch (error) {
        console.error('Error changing strategy:', error);
        showNotification('Error changing strategy: ' + error.message, 'error');
    }
}

// Alpaca API Key Management
async function saveAlpacaKeys() {
    const apiKey = document.getElementById('alpaca-api-key').value;
    const secretKey = document.getElementById('alpaca-secret-key').value;
    const paperTrading = document.getElementById('alpaca-paper-trading').checked;
    
    if (!apiKey || !secretKey) {
        showNotification('Please enter both API Key and Secret Key', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/api/v1/trading/broker/configure', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                broker: 'alpaca',
                api_key: apiKey,
                secret_key: secretKey,
                paper_trading: paperTrading
            })
        });
        
        if (response.ok) {
            showNotification('Alpaca keys saved successfully!', 'success');
        } else {
            const error = await response.json();
            showNotification('Failed to save keys: ' + error.detail, 'error');
        }
    } catch (error) {
        console.error('Error saving Alpaca keys:', error);
        showNotification('Error saving keys: ' + error.message, 'error');
    }
}

async function testAlpacaConnection() {
    try {
        const response = await fetch('/api/v1/trading/broker/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                broker: 'alpaca'
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            showNotification('Connection test successful! Account: ' + result.account_id, 'success');
        } else {
            const error = await response.json();
            showNotification('Connection test failed: ' + error.detail, 'error');
        }
    } catch (error) {
        console.error('Error testing Alpaca connection:', error);
        showNotification('Error testing connection: ' + error.message, 'error');
    }
}

// Live trading security
function showArmDialog() {
    const modal = document.getElementById('arm-modal');
    if (modal) {
        modal.classList.add('active');
        document.getElementById('arming-key').focus();
    }
}

function closeArmDialog() {
    const modal = document.getElementById('arm-modal');
    if (modal) {
        modal.classList.remove('active');
        document.getElementById('arming-key').value = '';
    }
}

async function armLiveTrading() {
    const armingKey = document.getElementById('arming-key').value;
    
    if (!armingKey) {
        showNotification('Please enter the arming key', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/api/v1/trading/arm', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                arming_key: armingKey
            })
        });
        
        if (response.ok) {
            AppState.isArmed = true;
            updateTradingStatus();
            closeArmDialog();
            showNotification('Live trading armed successfully!', 'success');
        } else {
            const error = await response.json();
            showNotification('Failed to arm live trading: ' + error.detail, 'error');
        }
    } catch (error) {
        console.error('Error arming live trading:', error);
        showNotification('Error arming live trading: ' + error.message, 'error');
    }
}

async function disarmLiveTrading() {
    try {
        const response = await fetch('/api/v1/trading/disarm', {
            method: 'POST'
        });
        
        if (response.ok) {
            AppState.isArmed = false;
            updateTradingStatus();
            showNotification('Live trading disarmed successfully!', 'success');
        } else {
            const error = await response.json();
            showNotification('Failed to disarm live trading: ' + error.detail, 'error');
        }
    } catch (error) {
        console.error('Error disarming live trading:', error);
        showNotification('Error disarming live trading: ' + error.message, 'error');
    }
}

// Positions and Orders
async function updatePositions() {
    try {
        const response = await fetch('/api/v1/trading/positions');
        if (response.ok) {
            const positions = await response.json();
            AppState.positions = positions;
            updatePositionsTable(positions);
        }
    } catch (error) {
        console.error('Error fetching positions:', error);
    }
}

function updatePositionsTable(positions) {
    const tbody = document.getElementById('positions-table');
    if (!tbody) return;
    
    if (!positions || positions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="no-data">No positions</td></tr>';
        return;
    }
    
    const rows = positions.map(position => {
        const pnl = position.unrealized_pl || 0;
        const pnlPercent = position.unrealized_plpc || 0;
        const pnlClass = pnl >= 0 ? 'positive' : 'negative';
        
        return `
            <tr>
                <td><strong>${position.symbol}</strong></td>
                <td>${position.quantity}</td>
                <td>$${position.avg_entry_price?.toFixed(2) || 'N/A'}</td>
                <td>$${position.current_price?.toFixed(2) || 'N/A'}</td>
                <td class="${pnlClass}">$${pnl.toFixed(2)}</td>
                <td class="${pnlClass}">${pnlPercent.toFixed(2)}%</td>
                <td>
                    <button class="btn btn-sm btn-danger" onclick="closePosition('${position.symbol}')">
                        <i class="fas fa-times"></i> Close
                    </button>
                </td>
            </tr>
        `;
    }).join('');
    
    tbody.innerHTML = rows;
}

async function updateOrders() {
    try {
        const response = await fetch('/api/v1/trading/orders');
        if (response.ok) {
            const orders = await response.json();
            AppState.orders = orders;
            updateOrdersTable(orders);
        }
    } catch (error) {
        console.error('Error fetching orders:', error);
    }
}

function updateOrdersTable(orders) {
    const tbody = document.getElementById('orders-table');
    if (!tbody) return;
    
    if (!orders || orders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="no-data">No orders</td></tr>';
        return;
    }
    
    const rows = orders.map(order => {
        const statusClass = getOrderStatusClass(order.status);
        
        return `
            <tr>
                <td><code>${order.order_id}</code></td>
                <td><strong>${order.symbol}</strong></td>
                <td><span class="order-side ${order.side}">${order.side.toUpperCase()}</span></td>
                <td>${order.quantity}</td>
                <td>$${order.price?.toFixed(2) || 'Market'}</td>
                <td><span class="order-status ${statusClass}">${order.status.toUpperCase()}</span></td>
                <td>${formatTime(order.created_at)}</td>
            </tr>
        `;
    }).join('');
    
    tbody.innerHTML = rows;
}

function getOrderStatusClass(status) {
    switch (status.toLowerCase()) {
        case 'filled': return 'status-filled';
        case 'pending': return 'status-pending';
        case 'cancelled': return 'status-cancelled';
        case 'rejected': return 'status-rejected';
        default: return 'status-unknown';
    }
}

// Backtesting
function showBacktestModal() {
    const modal = document.getElementById('backtest-modal');
    if (modal) {
        modal.classList.add('active');
    }
}

function closeBacktestModal() {
    const modal = document.getElementById('backtest-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}

async function runBacktest() {
    const strategy = document.getElementById('backtest-strategy').value;
    const symbols = document.getElementById('backtest-symbols').value;
    const startDate = document.getElementById('backtest-start').value;
    const endDate = document.getElementById('backtest-end').value;
    
    if (!symbols || !startDate || !endDate) {
        showNotification('Please fill in all backtest fields', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/api/v1/backtest/run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                strategy: strategy,
                symbols: symbols.split(',').map(s => s.trim()),
                start_date: startDate,
                end_date: endDate
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            displayBacktestResults(result);
            closeBacktestModal();
            showNotification('Backtest completed successfully!', 'success');
        } else {
            const error = await response.json();
            showNotification('Backtest failed: ' + error.detail, 'error');
        }
    } catch (error) {
        console.error('Error running backtest:', error);
        showNotification('Error running backtest: ' + error.message, 'error');
    }
}

function displayBacktestResults(results) {
    const container = document.getElementById('backtest-results');
    if (!container) return;
    
    const totalReturn = results.total_return || 0;
    const sharpeRatio = results.sharpe_ratio || 0;
    const maxDrawdown = results.max_drawdown || 0;
    const winRate = results.win_rate || 0;
    
    container.innerHTML = `
        <div class="backtest-summary">
            <h3><i class="fas fa-chart-line"></i> Backtest Results</h3>
            <div class="results-grid">
                <div class="result-metric">
                    <span class="metric-label">Total Return</span>
                    <span class="metric-value ${totalReturn >= 0 ? 'positive' : 'negative'}">
                        ${totalReturn.toFixed(2)}%
                    </span>
                </div>
                <div class="result-metric">
                    <span class="metric-label">Sharpe Ratio</span>
                    <span class="metric-value">${sharpeRatio.toFixed(2)}</span>
                </div>
                <div class="result-metric">
                    <span class="metric-label">Max Drawdown</span>
                    <span class="metric-value negative">${maxDrawdown.toFixed(2)}%</span>
                </div>
                <div class="result-metric">
                    <span class="metric-label">Win Rate</span>
                    <span class="metric-value">${winRate.toFixed(2)}%</span>
                </div>
            </div>
        </div>
    `;
}

// Performance metrics
function updatePerformanceMetrics(data) {
    // Update performance metrics in the performance tab
    const totalReturn = document.getElementById('total-return');
    const sharpeRatio = document.getElementById('sharpe-ratio');
    const maxDrawdown = document.getElementById('max-drawdown');
    const winRate = document.getElementById('win-rate');
    
    if (totalReturn) totalReturn.textContent = `${(data.total_return || 0).toFixed(2)}%`;
    if (sharpeRatio) sharpeRatio.textContent = (data.sharpe_ratio || 0).toFixed(2);
    if (maxDrawdown) maxDrawdown.textContent = `${(data.max_drawdown || 0).toFixed(2)}%`;
    if (winRate) winRate.textContent = `${(data.win_rate || 0).toFixed(2)}%`;
}

function updateMetrics(data) {
    // Update main dashboard metrics
    const totalPnl = document.getElementById('total-pnl');
    const totalPnlChange = document.getElementById('total-pnl-change');
    const dailyPnl = document.getElementById('daily-pnl');
    const dailyPnlChange = document.getElementById('daily-pnl-change');
    const portfolioValue = document.getElementById('portfolio-value');
    const portfolioChange = document.getElementById('portfolio-change');
    const activeSignals = document.getElementById('active-signals');
    const lastSignal = document.getElementById('last-signal');
    
    // Calculate metrics from market data
    let totalPnlValue = 0;
    let totalPnlPercent = 0;
    let activeSignalsCount = 0;
    let lastSignalValue = 'None';
    
    if (data && typeof data === 'object') {
        const symbols = Object.keys(data);
        let totalValue = 0;
        let totalChange = 0;
        
        symbols.forEach(symbol => {
            const symbolData = data[symbol];
            if (symbolData) {
                totalValue += symbolData.price || 0;
                totalChange += symbolData.change || 0;
                
                if (symbolData.signal && symbolData.signal !== 'HOLD') {
                    activeSignalsCount++;
                    lastSignalValue = `${symbol}: ${symbolData.signal}`;
                }
            }
        });
        
        totalPnlValue = totalChange;
        totalPnlPercent = totalValue > 0 ? (totalChange / totalValue) * 100 : 0;
    }
    
    if (totalPnl) totalPnl.textContent = `$${totalPnlValue.toFixed(2)}`;
    if (totalPnlChange) {
        totalPnlChange.textContent = `${totalPnlPercent >= 0 ? '+' : ''}${totalPnlPercent.toFixed(2)}%`;
        totalPnlChange.className = `metric-change ${totalPnlPercent >= 0 ? 'positive' : 'negative'}`;
    }
    
    if (dailyPnl) dailyPnl.textContent = `$${(totalPnlValue * 0.3).toFixed(2)}`;
    if (dailyPnlChange) {
        const dailyChange = totalPnlPercent * 0.3;
        dailyPnlChange.textContent = `${dailyChange >= 0 ? '+' : ''}${dailyChange.toFixed(2)}%`;
        dailyPnlChange.className = `metric-change ${dailyChange >= 0 ? 'positive' : 'negative'}`;
    }
    
    if (portfolioValue) portfolioValue.textContent = `$${(100000 + totalPnlValue).toFixed(2)}`;
    if (portfolioChange) {
        portfolioChange.textContent = `${totalPnlPercent >= 0 ? '+' : ''}${totalPnlPercent.toFixed(2)}%`;
        portfolioChange.className = `metric-change ${totalPnlPercent >= 0 ? 'positive' : 'negative'}`;
    }
    
    if (activeSignals) activeSignals.textContent = activeSignalsCount;
    if (lastSignal) lastSignal.textContent = lastSignalValue;
}

// Utility functions
function formatTime(timestamp) {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    return date.toLocaleString();
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${getNotificationIcon(type)}"></i>
            <span>${message}</span>
        </div>
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Show notification
    setTimeout(() => notification.classList.add('show'), 100);
    
    // Remove after 5 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

function getNotificationIcon(type) {
    switch (type) {
        case 'success': return 'check-circle';
        case 'error': return 'exclamation-circle';
        case 'warning': return 'exclamation-triangle';
        default: return 'info-circle';
    }
}

function closeAllModals() {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => modal.classList.remove('active'));
}

function refreshData() {
    loadInitialData();
    showNotification('Data refreshed', 'success');
}

// Position management
async function closePosition(symbol) {
    if (confirm(`Are you sure you want to close position for ${symbol}?`)) {
        try {
            const response = await fetch(`/api/v1/trading/positions/${symbol}/close`, {
                method: 'POST'
            });
            
            if (response.ok) {
                showNotification(`Position for ${symbol} closed successfully`, 'success');
                updatePositions();
            } else {
                const error = await response.json();
                showNotification(`Failed to close position: ${error.detail}`, 'error');
            }
        } catch (error) {
            console.error('Error closing position:', error);
            showNotification('Error closing position: ' + error.message, 'error');
        }
    }
}

// Export functions for global access
window.startTrading = startTrading;
window.stopTrading = stopTrading;
window.emergencyStop = emergencyStop;
window.changeStrategy = changeStrategy;
window.saveAlpacaKeys = saveAlpacaKeys;
window.testAlpacaConnection = testAlpacaConnection;
window.showArmDialog = showArmDialog;
window.closeArmDialog = closeArmDialog;
window.armLiveTrading = armLiveTrading;
window.disarmLiveTrading = disarmLiveTrading;
window.showBacktestModal = showBacktestModal;
window.closeBacktestModal = closeBacktestModal;
window.runBacktest = runBacktest;
window.refreshData = refreshData;
window.toggleAutoRefresh = toggleAutoRefresh;
window.closePosition = closePosition;