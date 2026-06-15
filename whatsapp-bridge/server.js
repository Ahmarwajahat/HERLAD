const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');
const cors = require('cors');
const fs = require('fs');
const http = require('http');

const app = express();
app.use(express.json());
app.use(cors());

const HERALD_NUMBER = '923004085054';
const OWNER_NUMBER = '923430699325';
const OWNER = `${OWNER_NUMBER}@c.us`;
const TASKS_FILE = '../logs/pending_tasks.json';

let isConnected = false;
let pendingMessages = [];
let qrCodeString = null;

// WebSocket & Dashboard state integration
const WebSocket = require('ws');
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });
const net = require('net');

let currentTask = null;
let executedTools = [];
let sentMessages = [];

function checkMongoStatus() {
    return new Promise((resolve) => {
        const socket = new net.Socket();
        socket.setTimeout(200);
        socket.on('connect', () => {
            socket.destroy();
            resolve(true);
        });
        socket.on('timeout', () => {
            socket.destroy();
            resolve(false);
        });
        socket.on('error', () => {
            socket.destroy();
            resolve(false);
        });
        socket.connect(27017, '127.0.0.1');
    });
}

let lastMongoStatus = null;
setInterval(async () => {
    const isMongoOnline = await checkMongoStatus();
    if (isMongoOnline !== lastMongoStatus) {
        lastMongoStatus = isMongoOnline;
        wss.clients.forEach(client => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(JSON.stringify({
                    type: 'mongo_status',
                    data: { mongoConnected: isMongoOnline }
                }));
            }
        });
    }
}, 5000);

wss.on('connection', async ws => {
    console.log('[WS] Client connected');
    const isMongoOnline = await checkMongoStatus();
    lastMongoStatus = isMongoOnline;
    ws.send(JSON.stringify({
        type: 'init',
        data: {
            task: currentTask,
            tools: executedTools,
            status: currentTask ? (currentTask.status || 'running') : 'idle',
            whatsapp: sentMessages,
            mongoConnected: isMongoOnline,
            qr: qrCodeString,
            isConnected: isConnected
        }
    }));
    
    ws.on('close', () => {
        console.log('[WS] Client disconnected');
    });
});

function broadcastWhatsAppMessage(number, message) {
    const msgData = {
        number: number.replace('@c.us',''),
        message: message,
        timestamp: new Date().toISOString()
    };
    sentMessages.push(msgData);
    
    wss.clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(JSON.stringify({
                type: 'whatsapp_sent',
                data: msgData
            }));
        }
    });
}

async function checkUnreadMessages() {
    try {
        console.log('[Bridge] Checking for unread messages...');
        const chats = await client.getChats();
        const OWNER_NUMBERS = ['923430699325', '161843393859694'];
        
        console.log(`[Bridge] Total chats fetched: ${chats.length}`);
        for (const chat of chats) {
            if (chat.unreadCount > 0) {
                console.log(`[Bridge] Unread chat detected: "${chat.name}" (${chat.id._serialized}), count: ${chat.unreadCount}`);
                if (chat.id._serialized.endsWith('@g.us')) {
                    console.log(`[Bridge] Skipping group chat "${chat.name}"`);
                    continue;
                }
                
                const messages = await chat.fetchMessages({ limit: chat.unreadCount });
                console.log(`[Bridge] Fetched ${messages.length} unread messages from "${chat.name}"`);
                for (const msg of messages) {
                    if (msg.fromMe) continue;
                    
                    let sender = '';
                    try {
                        const contact = await msg.getContact();
                        sender = (contact.number || '').replace('+', '').trim();
                    } catch (e) {
                        console.log('[Bridge] Error getting contact in unread check:', e.message);
                    }
                    if (!sender) {
                        sender = msg.from.replace('@c.us','').replace('@lid','').replace('+','').split(':')[0].trim();
                    }
                    
                    console.log(`[Bridge] Message from "${chat.name}": "${msg.body}" (sender resolved: ${sender}, msg.from: ${msg.from})`);
                    
                    if (OWNER_NUMBERS.includes(sender) || msg.from.includes(OWNER_NUMBER)) {
                        console.log(`[Bridge] Found unread OWNER command from offline period: ${msg.body}`);
                        savePendingTask(msg.body, msg.from);
                        forwardToPython(msg.body, msg.from, 10);
                        
                        try {
                            await chat.sendSeen();
                        } catch (se) {}
                    } else {
                        console.log(`[Bridge] Ignored offline command - not owner (${sender})`);
                    }
                }
            }
        }
    } catch (e) {
        console.error('[Bridge] Error checking unread messages:', e.message);
    }
}

let client = null;

function initializeClient() {
    console.log('[Bridge] Creating new WhatsApp client instance...');
    
    // Clean auth folders first just to be perfectly safe
    try {
        const path = require('path');
        const lockPath1 = path.join(__dirname, '.wwebjs_auth/session/.lock');
        const lockPath2 = path.join(__dirname, '.wwebjs_auth/session/SingletonLock');
        if (fs.existsSync(lockPath1)) fs.rmSync(lockPath1, { force: true });
        if (fs.existsSync(lockPath2)) fs.rmSync(lockPath2, { force: true });
    } catch(e) {}

    client = new Client({
        authStrategy: new LocalAuth(),
        authTimeoutMs: 180000,
        webVersionCache: {
            type: 'remote',
            remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.3000.1041450038-alpha.html',
            strict: false
        },
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        puppeteer: {
            headless: true,
            protocolTimeout: 240000,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
                '--no-first-run',
                '--no-zygote',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        }
    });

    client.on('loading_screen', (percent, message) => {
        console.log(`[HERALD Bridge] Loading Screen: ${percent}% - ${message}`);
    });

    client.on('authenticated', () => {
        console.log('[HERALD Bridge] Session Authenticated');
    });

    client.on('auth_failure', (msg) => {
        console.error('[HERALD Bridge] Session Auth Failure:', msg);
    });

    client.on('qr', qr => {
        console.log('\n[HERALD Bridge] Scan QR:\n');
        qrcode.generate(qr, { small: true });
        qrCodeString = qr;
        try {
            fs.writeFileSync('../logs/latest_qr.txt', qr);
        } catch (e) {
            console.error('Failed to write QR to file:', e.message);
        }
        // Broadcast QR to WS clients
        wss.clients.forEach(c => {
            if (c.readyState === WebSocket.OPEN) {
                c.send(JSON.stringify({
                    type: 'qr_code',
                    data: { qr }
                }));
            }
        });
    });

    client.on('ready', () => {
        isConnected = true;
        qrCodeString = null;
        try {
            if (fs.existsSync('../logs/latest_qr.txt')) {
                fs.unlinkSync('../logs/latest_qr.txt');
            }
        } catch (e) {}
        console.log('[HERALD Bridge] WhatsApp Connected!');
        checkUnreadMessages();
        // Broadcast ready status
        wss.clients.forEach(c => {
            if (c.readyState === WebSocket.OPEN) {
                c.send(JSON.stringify({
                    type: 'ready_status',
                    data: { isConnected: true }
                }));
            }
        });
    });

    client.on('disconnected', () => {
        isConnected = false;
        qrCodeString = null;
        // Broadcast ready status
        wss.clients.forEach(c => {
            if (c.readyState === WebSocket.OPEN) {
                c.send(JSON.stringify({
                    type: 'ready_status',
                    data: { isConnected: false }
                }));
            }
        });
    });

    client.on('message', async msg => {
        if (msg.fromMe) return;
        
        let sender = '';
        try {
            const contact = await msg.getContact();
            sender = (contact.number || '').replace('+', '').trim();
        } catch (e) {
            console.log('[Bridge] Failed to resolve contact:', e.message);
        }
        if (!sender) {
            sender = (msg.from || '').replace('@c.us', '').replace('+', '').trim();
        }
        
        const OWNER_NUMBERS = ['923430699325', '161843393859694'];
        // Owner verification
        if (!OWNER_NUMBERS.includes(sender)) {
            console.log(`[Bridge] Ignored incoming command from non-owner: ${sender}`);
            return;
        }
        
        console.log(`[Bridge] ✅ OWNER command: ${msg.body}`);
        
        // Auto reply with expected timing
        try {
            let expectedTime = '~15-30 seconds';
            const bodyLower = (msg.body || '').toLowerCase();
            if (bodyLower.includes('solve') || bodyLower.includes('generate') || bodyLower.includes('lab') || bodyLower.includes('report') || bodyLower.includes('create')) {
                expectedTime = '~60-90 seconds';
            }
            const replyMsg = `⚡ HERALD received! Working on it...\n⏳ Expected completion time: ${expectedTime}.\nI will notify you step-by-step.`;
            await msg.reply(replyMsg);
            broadcastWhatsAppMessage(msg.from, replyMsg);
        } catch(e) {
            console.log('[Bridge] Could not send reply:', e.message);
        }
        
        // Save task immediately with sender info
        savePendingTask(msg.body, msg.from);
        
        // Forward to Python with retry
        forwardToPython(msg.body, msg.from, 10);
    });

    client.initialize().catch(e => {
        console.error('[Bridge] Error during client initialize:', e.message);
    });
}

initializeClient();

function savePendingTask(task, fromNumber) {
    let tasks = [];
    try {
        if (fs.existsSync(TASKS_FILE)) {
            tasks = JSON.parse(fs.readFileSync(TASKS_FILE));
        }
    } catch(e) {}
    
    tasks.push({
        task: task,
        timestamp: new Date().toISOString(),
        status: 'pending',
        from: fromNumber || OWNER
    });
    
    fs.mkdirSync('../logs', { recursive: true });
    fs.writeFileSync(TASKS_FILE, JSON.stringify(tasks, null, 2));
}

function checkPendingTasks() {
    try {
        if (!fs.existsSync(TASKS_FILE)) return;
        const tasks = JSON.parse(fs.readFileSync(TASKS_FILE));
        const pending = tasks.filter(t => t.status === 'pending');
        
        if (pending.length > 0) {
            console.log(`[HERALD] Found ${pending.length} pending tasks!`);
            pending.forEach(t => {
                console.log(`[HERALD] Executing missed task: ${t.task}`);
                forwardToPython(t.task, OWNER, 10);
            });
        }
    } catch(e) {}
}

function forwardToPython(task, from_number, retries=10) {
    const data = JSON.stringify({ task, from: from_number });
    
    const options = {
        hostname: 'localhost',
        port: 5000,
        path: '/task',
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(data)
        }
    };
    
    const req = http.request(options, res => {
        console.log(`[Bridge] ✅ Task forwarded to Python`);
    });
    
    req.setTimeout(5000);
    
    req.on('error', () => {
        if (retries > 0) {
            console.log(`[Bridge] Python not ready, retry in 4s (${retries} left)`);
            setTimeout(() => 
                forwardToPython(task, from_number, retries-1), 4000);
        } else {
            console.log('[Bridge] ❌ Failed to forward task to Python after retries; remaining in pending status.');
        }
    });
    
    req.write(data);
    req.end();
}

// WhatsApp Connection and Logout endpoints
app.post('/api/whatsapp/logout', async (req, res) => {
    console.log('[Bridge] Logout request received');
    try {
        if (client) {
            // Log out from the session (clears local auth cache)
            await client.logout();
            isConnected = false;
            qrCodeString = null;
            console.log('[Bridge] Successfully logged out');
            res.json({ success: true, message: 'Logged out successfully' });
        } else {
            res.status(400).json({ error: 'Client not initialized' });
        }
    } catch (err) {
        console.error('[Bridge] Error during client.logout(), executing fallback auth purge:', err.message);
        try {
            await client.destroy().catch(() => {});
            const path = require('path');
            const authPath = path.join(__dirname, '.wwebjs_auth');
            if (fs.existsSync(authPath)) {
                fs.rmSync(authPath, { recursive: true, force: true });
                console.log('[Bridge] Purged .wwebjs_auth directory');
            }
            isConnected = false;
            qrCodeString = null;
            
            // Reinitialize client to get a fresh QR code
            setTimeout(() => {
                initializeClient();
            }, 1000);
            
            res.json({ success: true, message: 'Cleaned session and reinitializing' });
        } catch (fallbackErr) {
            res.status(500).json({ error: 'Failed to force log out: ' + fallbackErr.message });
        }
    }
});

app.post('/api/whatsapp/connect', async (req, res) => {
    console.log('[Bridge] Connect request received');
    if (isConnected) {
        return res.json({ success: true, message: 'Already connected' });
    }
    
    try {
        console.log('[Bridge] Reinitializing client to force QR generation');
        if (client) {
            await client.destroy().catch(() => {});
        }
        isConnected = false;
        qrCodeString = null;
        
        setTimeout(() => {
            initializeClient();
        }, 1000);
        
        res.json({ success: true, message: 'Initializing connection and generating QR' });
    } catch (err) {
        res.status(500).json({ error: 'Failed to initiate connection: ' + err.message });
    }
});

// HTTP endpoints
app.get('/status', async (req, res) => {
    let internalState = 'unknown';
    try {
        if (client && client.pupPage) {
            internalState = await client.getState();
        }
    } catch (e) {
        internalState = 'error: ' + e.message;
    }
    res.json({
        status: isConnected ? 'connected' : 'disconnected',
        state: internalState,
        qr: qrCodeString,
        info: client ? {
            pushname: client.info ? client.info.pushname : null,
            wid: client.info ? client.info.wid : null
        } : null
    });
});

app.get('/screenshot', async (req, res) => {
    try {
        if (client && client.pupPage) {
            await client.pupPage.screenshot({ path: '../logs/whatsapp_debug.png' });
            res.send("Screenshot saved to logs/whatsapp_debug.png");
        } else {
            res.status(400).send("No puppet page available");
        }
    } catch (e) {
        res.status(500).send("Error taking screenshot: " + e.message);
    }
});

app.post('/api/manual-task', (req, res) => {
    const { task } = req.body;
    if (!task) {
        return res.status(400).json({ error: 'No task provided' });
    }
    console.log(`[Bridge] Manual task submitted via dashboard: ${task}`);
    
    // Save task
    savePendingTask(task, 'Dashboard');
    
    // Forward to Python
    forwardToPython(task, 'Dashboard', 10);
    
    res.json({ success: true });
});

app.post('/api/event', (req, res) => {
    const event = req.body;
    
    if (event.type === 'task_started') {
        currentTask = event.data;
        executedTools = [];
    } else if (event.type === 'plan_generated') {
        if (currentTask) {
            currentTask.goal = event.data.goal;
            currentTask.plan = event.data.plan;
            currentTask.current_step = event.data.current_step;
        }
    } else if (event.type === 'tool_call') {
        executedTools.push(event.data);
    } else if (event.type === 'task_completed') {
        if (currentTask) {
            currentTask.status = 'completed';
            currentTask.model = event.data.model;
        }
    }
    
    // Broadcast event to all WS clients
    wss.clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(JSON.stringify(event));
        }
    });
    
    res.json({ success: true });
});

app.post('/send', async (req, res) => {
    let { number, message } = req.body;
    number = number.replace(/[+\-\s]/g, '');
    if (!number.includes('@c.us') && !number.includes('@lid')) number = `${number}@c.us`;
    console.log(`[Bridge] Sending message to ${number}: ${message}`);
    try {
        await client.sendMessage(number, message);
        broadcastWhatsAppMessage(number, message);
        res.json({ success: true });
    } catch (err) {
        console.error(`[Bridge] Error sending message: ${err.message}`);
        res.json({ success: false, error: err.message });
    }
});

app.post('/send-file', async (req, res) => {
    let { number, filepath, caption } = req.body;
    
    if (!filepath) {
        return res.json({ success: false, error: 'No filepath given' });
    }
    
    if (!number) number = process.env.OWNER || OWNER_NUMBER;
    number = number.replace(/[+\-\s]/g, '');
    if (!number.includes('@c.us') && !number.includes('@lid')) number = `${number}@c.us`;
    
    const fs = require('fs');
    if (!fs.existsSync(filepath)) {
        return res.json({ 
            success: false, 
            error: `File not found: ${filepath}` 
        });
    }
    
    if (!isConnected) {
        return res.json({ 
            success: false, 
            error: 'WhatsApp not connected' 
        });
    }
    
    console.log(`[Bridge] Sending file ${filepath} to ${number} with caption: ${caption}`);
    try {
        const { MessageMedia } = require('whatsapp-web.js');
        const media = MessageMedia.fromFilePath(filepath);
        await client.sendMessage(number, media, { 
            caption: caption || 'File from HERALD' 
        });
        broadcastWhatsAppMessage(number, caption || `Sent file: ${filepath}`);
        return res.json({ success: true, 
                         message: 'File sent successfully' });
    } catch (err) {
        console.error(`[Bridge] Error sending file: ${err.message}`);
        return res.json({ success: false, error: err.message });
    }
});

app.get('/messages', (req, res) => {
    res.json({
        messages: pendingMessages.filter(m => !m.read),
        count: pendingMessages.filter(m => !m.read).length
    });
});

app.get('/api/workspace-files', (req, res) => {
    const path = require('path');
    const files = [];
    try {
        const reportsDir = path.join(__dirname, '../reports');
        if (fs.existsSync(reportsDir)) {
            fs.readdirSync(reportsDir).forEach(file => {
                if (file.endsWith('.docx') || file.endsWith('.pdf') || file.endsWith('.txt')) {
                    const stats = fs.statSync(path.join(reportsDir, file));
                    files.push({
                        name: file,
                        path: `reports/${file}`,
                        size: stats.size,
                        mtime: stats.mtime
                    });
                }
            });
        }
        const screenshotsDir = '/mnt/AhmarData/screenshots';
        if (fs.existsSync(screenshotsDir)) {
            fs.readdirSync(screenshotsDir).forEach(file => {
                if (file.endsWith('.png') || file.endsWith('.webp')) {
                    const stats = fs.statSync(path.join(screenshotsDir, file));
                    files.push({
                        name: file,
                        path: `screenshots/${file}`,
                        size: stats.size,
                        mtime: stats.mtime
                    });
                }
            });
        }
    } catch (e) {
        console.error(e);
    }
    res.json({ files });
});

app.get('/api/download-file', (req, res) => {
    const { filepath } = req.query;
    if (!filepath) return res.status(400).send('No filepath');
    const path = require('path');
    let absolutePath;
    if (filepath.startsWith('screenshots/')) {
        absolutePath = path.join('/mnt/AhmarData/screenshots', filepath.replace('screenshots/', ''));
    } else {
        absolutePath = path.join(__dirname, '..', filepath);
    }
    if (fs.existsSync(absolutePath)) {
        res.download(absolutePath);
    } else {
        res.status(404).send('File not found');
    }
});

app.get('/api/view-file', (req, res) => {
    const { filepath } = req.query;
    if (!filepath) return res.status(400).send('No filepath');
    const path = require('path');
    let absolutePath;
    if (filepath.startsWith('screenshots/')) {
        absolutePath = path.join('/mnt/AhmarData/screenshots', filepath.replace('screenshots/', ''));
    } else {
        absolutePath = path.join(__dirname, '..', filepath);
    }
    if (fs.existsSync(absolutePath)) {
        res.sendFile(absolutePath);
    } else {
        res.status(404).send('File not found');
    }
});

const PORT = 3001;
server.listen(PORT, () => {
    console.log(`[HERALD Bridge] Running on port ${PORT}`);
}).on('error', err => {
    if (err.code === 'EADDRINUSE') {
        console.log(`Port ${PORT} busy! Run:`);
        console.log(`sudo kill -9 $(sudo lsof -t -i:${PORT})`);
        process.exit(1);
    }
});

