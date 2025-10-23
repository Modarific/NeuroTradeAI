// NeuroTradeAI Dashboard JavaScript
let ws = null;
let isConnected = false;

function connectWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        return;
    }

    ws = new WebSocket('ws://localhost:8000/stream');
    
    ws.onopen = function() {
        isConnected = true;
        updateStatus('connected');
        console.log('WebSocket connected');
    };

    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    ws.onclose = function() {
        isConnected = false;
        updateStatus('disconnected');
        console.log('WebSocket disconnected');
    };

    ws.onerror = function(error) {
        console.error('WebSocket error:', error);
        updateStatus('disconnected');
    };
}

function disconnectWebSocket() {
    if (ws) {
        ws.close();
    }
}

function subscribeToData() {
    if (!isConnected) {
        console.log('WebSocket not connected, cannot subscribe');
        return;
    }

    console.log('Subscribing to data streams...');

    // Subscribe to OHLCV data
    ws.send(JSON.stringify({
        action: 'subscribe',
        data_type: 'ohlcv'
    }));

    // Subscribe to news data
    ws.send(JSON.stringify({
        action: 'subscribe',
        data_type: 'news'
    }));
    
    console.log('Subscribed to OHLCV and news data streams');
}

function updateStatus(status) {
    const statusElement = document.getElementById('ws-status');
    if (statusElement) {
        statusElement.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        statusElement.className = `status ${status}`;
    }
}

function handleWebSocketMessage(data) {
    console.log('Handling WebSocket message:', data.type);
    
    switch(data.type) {
        case 'ohlcv_update':
            console.log('Updating price for', data.symbol, ':', data.data);
            updatePriceData(data.symbol, data.data);
            break;
        case 'news_update':
            console.log('Adding news item:', data.data.headline);
            addNewsItem(data.data);
            break;
        case 'filing_update':
            console.log('Adding filing item:', data.data.filing_type);
            addFilingItem(data.data);
            break;
        case 'system_status':
            console.log('Updating metrics:', data.data);
            updateMetrics(data.data);
            break;
        default:
            console.log('Unknown message type:', data.type);
    }
}

function updatePriceData(symbol, data) {
    console.log('Updating price data for', symbol, ':', data);
    
    const priceGrid = document.getElementById('price-grid');
    if (!priceGrid) {
        console.error('Price grid element not found');
        return;
    }
    
    let priceItem = document.getElementById(`price-${symbol}`);
    
    if (!priceItem) {
        console.log('Creating new price item for', symbol);
        priceItem = document.createElement('div');
        priceItem.id = `price-${symbol}`;
        priceItem.className = 'price-item';
        priceGrid.appendChild(priceItem);
    }

    const change = data.close - data.open;
    const changePercent = (change / data.open) * 100;
    
    priceItem.innerHTML = `
        <strong>${symbol}</strong><br>
        $${data.close.toFixed(2)}<br>
        <span style="color: ${change >= 0 ? 'green' : 'red'}">
            ${change >= 0 ? '+' : ''}${change.toFixed(2)} (${changePercent.toFixed(2)}%)
        </span>
    `;
    
    priceItem.className = `price-item ${change >= 0 ? '' : 'negative'}`;
    
    // Add a subtle animation to show the update
    priceItem.style.transition = 'background-color 0.3s ease';
    priceItem.style.backgroundColor = '#e8f5e8';
    setTimeout(() => {
        priceItem.style.backgroundColor = '';
    }, 1000);
    
    console.log('Price updated for', symbol, 'to $' + data.close.toFixed(2));
}

function addNewsItem(news) {
    console.log('Adding news item:', news.headline);
    
    const newsList = document.getElementById('news');
    if (!newsList) {
        console.error('News list element not found');
        return;
    }
    
    const newsItem = document.createElement('div');
    newsItem.className = 'news-item';
    
    // Format sentiment score
    const sentiment = news.sentiment_score || 0;
    const sentimentClass = sentiment > 0.1 ? 'positive' : sentiment < -0.1 ? 'negative' : 'neutral';
    const sentimentText = sentiment > 0.1 ? 'Positive' : sentiment < -0.1 ? 'Negative' : 'Neutral';
    
    newsItem.innerHTML = `
        <h4>${news.headline || 'No headline'}</h4>
        <p>${news.summary || 'No summary available'}</p>
        <div class="news-meta">
            <span class="source">${news.source || 'Unknown'}</span>
            <span class="timestamp">${new Date(news.timestamp_utc).toLocaleString()}</span>
            <span class="sentiment ${sentimentClass}">${sentimentText} (${sentiment.toFixed(2)})</span>
        </div>
        ${news.tickers && news.tickers.length > 0 ? 
            `<div class="tickers">Tickers: ${news.tickers.join(', ')}</div>` : ''}
    `;
    
    newsList.insertBefore(newsItem, newsList.firstChild);
    
    // Keep only last 10 news items
    while (newsList.children.length > 10) {
        newsList.removeChild(newsList.lastChild);
    }
    
    console.log('News item added:', news.headline);
}

function addFilingItem(filing) {
    console.log('Adding filing item:', filing.filing_type);
    
    const filingsList = document.getElementById('filings');
    if (!filingsList) {
        console.error('Filings list element not found');
        return;
    }
    
    const filingItem = document.createElement('div');
    filingItem.className = 'filing-item';
    
    // Format filing type with color coding
    const filingType = filing.filing_type || 'Unknown';
    const typeClass = filingType.includes('10-K') ? 'annual' : 
                     filingType.includes('10-Q') ? 'quarterly' : 
                     filingType.includes('8-K') ? 'current' : 'other';
    
    filingItem.innerHTML = `
        <h4>${filing.symbol || 'Unknown'} - ${filingType}</h4>
        <p>${filing.entity_name || 'No entity name'}</p>
        <div class="filing-meta">
            <span class="filing-date">${new Date(filing.filing_date).toLocaleDateString()}</span>
            <span class="filing-type ${typeClass}">${filingType}</span>
        </div>
        ${filing.url ? `<div class="filing-url"><a href="${filing.url}" target="_blank">View Filing</a></div>` : ''}
    `;
    
    filingsList.insertBefore(filingItem, filingsList.firstChild);
    
    // Keep only last 10 filing items
    while (filingsList.children.length > 10) {
        filingsList.removeChild(filingsList.lastChild);
    }
    
    console.log('Filing item added:', filing.filing_type);
}

// Enhanced Dashboard Functions
function toggleDataSource(source, enabled) {
    console.log(`Toggling ${source} data source: ${enabled ? 'enabled' : 'disabled'}`);
    
    // Update the UI immediately
    const toggle = document.getElementById(`${source}-toggle`);
    if (toggle) {
        toggle.checked = enabled;
    }
    
    // Send request to server to enable/disable source
    fetch(`/api/v1/sources/${source}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ enabled: enabled })
    })
    .then(response => response.json())
    .then(data => {
        console.log(`${source} source ${enabled ? 'enabled' : 'disabled'}:`, data);
        // Update source status display
        updateSourceStatus({});
    })
    .catch(error => {
        console.error(`Error toggling ${source} source:`, error);
        // Revert toggle on error
        if (toggle) {
            toggle.checked = !enabled;
        }
    });
}

function showSystemSettings() {
    document.getElementById('systemModal').style.display = 'block';
    loadSystemSettings();
}

function hideSystemSettings() {
    document.getElementById('systemModal').style.display = 'none';
}

function loadSystemSettings() {
    // Load current settings from server
    fetch('/api/v1/settings')
    .then(response => response.json())
    .then(settings => {
        document.getElementById('polling-interval').value = settings.polling_interval || 60;
        document.getElementById('max-symbols').value = settings.max_symbols || 50;
        document.getElementById('retention-days').value = settings.retention_days || 365;
        document.getElementById('auto-cleanup').checked = settings.auto_cleanup !== false;
        document.getElementById('error-alerts').checked = settings.error_alerts !== false;
        document.getElementById('rate-limit-alerts').checked = settings.rate_limit_alerts !== false;
    })
    .catch(error => {
        console.error('Error loading system settings:', error);
    });
}

function saveSystemSettings() {
    const settings = {
        polling_interval: parseInt(document.getElementById('polling-interval').value),
        max_symbols: parseInt(document.getElementById('max-symbols').value),
        retention_days: parseInt(document.getElementById('retention-days').value),
        auto_cleanup: document.getElementById('auto-cleanup').checked,
        error_alerts: document.getElementById('error-alerts').checked,
        rate_limit_alerts: document.getElementById('rate-limit-alerts').checked
    };
    
    fetch('/api/v1/settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Settings saved:', data);
        hideSystemSettings();
        // Show success message
        alert('Settings saved successfully!');
    })
    .catch(error => {
        console.error('Error saving settings:', error);
        alert('Error saving settings. Please try again.');
    });
}

function updateMetrics(metrics) {
    const metricsContainer = document.getElementById('metrics');
    if (!metricsContainer) return;
    
    metricsContainer.innerHTML = `
        <div class="metric-item">
            <h4>Storage</h4>
            <div class="value">${metrics.storage?.total_files || 0}</div>
            <div class="label">Files</div>
        </div>
        <div class="metric-item">
            <h4>Size</h4>
            <div class="value">${(metrics.storage?.total_size_mb || 0).toFixed(1)}</div>
            <div class="label">MB</div>
        </div>
        <div class="metric-item">
            <h4>Symbols</h4>
            <div class="value">${metrics.database?.symbols || 0}</div>
            <div class="label">Tracked</div>
        </div>
        <div class="metric-item">
            <h4>OHLCV</h4>
            <div class="value">${metrics.storage?.ohlcv_files || 0}</div>
            <div class="label">Files</div>
        </div>
        <div class="metric-item">
            <h4>News</h4>
            <div class="value">${metrics.storage?.news_files || 0}</div>
            <div class="label">Files</div>
        </div>
        <div class="metric-item">
            <h4>Filings</h4>
            <div class="value">${metrics.storage?.filings_files || 0}</div>
            <div class="label">Files</div>
        </div>
    `;
    
    // Update source status
    updateSourceStatus(metrics);
}

function updateSourceStatus(metrics) {
    const sourceStatusContainer = document.getElementById('source-status');
    if (!sourceStatusContainer) return;
    
    const sources = [
        { name: 'Finnhub Market Data', id: 'finnhub', status: 'active' },
        { name: 'News Feed', id: 'news', status: 'active' },
        { name: 'SEC Filings', id: 'edgar', status: 'active' }
    ];
    
    sourceStatusContainer.innerHTML = sources.map(source => `
        <div class="source-item ${source.status}">
            <h4>${source.name}</h4>
            <div class="status ${source.status}">${source.status.toUpperCase()}</div>
            <div class="details">Last update: ${new Date().toLocaleTimeString()}</div>
        </div>
    `).join('');
}

// Load initial data
async function loadInitialData() {
    try {
        // Load metrics
        const metricsResponse = await fetch('/api/v1/metrics');
        const metricsData = await metricsResponse.json();
        updateMetrics(metricsData);

        // Load recent news
        const newsResponse = await fetch('/api/v1/news?limit=10');
        const newsData = await newsResponse.json();
        if (newsData.news) {
            newsData.news.forEach(news => addNewsItem(news));
        }
        
        // Load recent filings
        const filingsResponse = await fetch('/api/v1/filings?limit=10');
        const filingsData = await filingsResponse.json();
        if (filingsData.filings) {
            filingsData.filings.forEach(filing => addFilingItem(filing));
        }

    } catch (error) {
        console.error('Error loading initial data:', error);
    }
}

// API Key Management Functions
function showKeyManagement() {
    document.getElementById('keyModal').style.display = 'block';
    loadKeyStatus();
}

function hideKeyManagement() {
    document.getElementById('keyModal').style.display = 'none';
}

async function loadKeyStatus() {
    try {
        const response = await fetch('/api/v1/keys/status');
        const data = await response.json();
        
        if (!data.vault_unlocked) {
            document.getElementById('keyStatus').innerHTML = 
                '<p style="color: red;">Vault not unlocked. Please restart the application.</p>';
            return;
        }
        
        let statusHtml = '<h3>API Key Status</h3>';
        let formsHtml = '<h3>Add/Update API Keys</h3>';
        
        for (const [service, info] of Object.entries(data.services)) {
            const statusClass = info.configured ? 'configured' : 'not-configured';
            const statusText = info.configured ? 'Configured' : 'Not Configured';
            
            statusHtml += `
                <div class="key-service">
                    <h4>${service.toUpperCase()} 
                        <span class="key-status ${statusClass}">${statusText}</span>
                        <button class="btn-test" onclick="testApiKey('${service}')">Test</button>
                    </h4>
                    <p>Last Updated: ${info.last_updated}</p>
                    ${info.description ? `<p>Description: ${info.description}</p>` : ''}
                </div>
            `;
            
            formsHtml += `
                <div class="key-service">
                    <h4>${service.toUpperCase()}</h4>
                    <div class="key-form">
                        <input type="password" id="key-${service}" placeholder="Enter API key for ${service}">
                        <button class="btn-add" onclick="addApiKey('${service}')">Add/Update</button>
                        <button class="btn-remove" onclick="removeApiKey('${service}')">Remove</button>
                    </div>
                </div>
            `;
        }
        
        document.getElementById('keyStatus').innerHTML = statusHtml;
        document.getElementById('keyForms').innerHTML = formsHtml;
        
    } catch (error) {
        console.error('Error loading key status:', error);
        document.getElementById('keyStatus').innerHTML = 
            '<p style="color: red;">Error loading key status. Please try again.</p>';
    }
}

async function addApiKey(service) {
    const keyInput = document.getElementById(`key-${service}`);
    const apiKey = keyInput.value.trim();
    
    if (!apiKey) {
        alert('Please enter an API key');
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('api_key', apiKey);
        formData.append('description', `Added via web interface`);
        
        const response = await fetch(`/api/v1/keys/${service}`, {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            alert(`API key for ${service} added successfully!`);
            keyInput.value = '';
            loadKeyStatus();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail}`);
        }
    } catch (error) {
        console.error('Error adding API key:', error);
        alert('Error adding API key. Please try again.');
    }
}

async function removeApiKey(service) {
    if (!confirm(`Are you sure you want to remove the API key for ${service}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/v1/keys/${service}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            alert(`API key for ${service} removed successfully!`);
            loadKeyStatus();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail}`);
        }
    } catch (error) {
        console.error('Error removing API key:', error);
        alert('Error removing API key. Please try again.');
    }
}

async function testApiKey(service) {
    try {
        const response = await fetch(`/api/v1/keys/test/${service}`, {
            method: 'GET'
        });
        const result = await response.json();
        
        if (response.ok) {
            alert(`${service.toUpperCase()} API Key Test:\nStatus: ${result.status}\nMessage: ${result.message}`);
        } else {
            alert(`Error testing API key: ${result.detail}`);
        }
    } catch (error) {
        console.error('Error testing API key:', error);
        alert('Error testing API key. Please try again.');
    }
}

// Auto-connect on page load
window.addEventListener('load', function() {
    loadInitialData();
    connectWebSocket();
    
    // Refresh metrics every 30 seconds
    setInterval(async () => {
        try {
            const metricsResponse = await fetch('/api/v1/metrics');
            if (metricsResponse.ok) {
                const metrics = await metricsResponse.json();
                updateMetrics(metrics);
            }
        } catch (error) {
            console.error('Error refreshing metrics:', error);
        }
    }, 30000);
    
    // Refresh price data every 60 seconds as backup
    setInterval(async () => {
        try {
            const symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA'];
            for (const symbol of symbols) {
                const response = await fetch(`/api/v1/ohlcv/${symbol}?interval=1m&limit=1`);
                if (response.ok) {
                    const data = await response.json();
                    if (data.bars && data.bars.length > 0) {
                        updatePriceData(symbol, data.bars[0]);
                    }
                }
            }
        } catch (error) {
            console.error('Error refreshing price data:', error);
        }
    }, 60000);
});
