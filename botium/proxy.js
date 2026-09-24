const express = require('express');
const axios = require('axios');

const app = express();

// Middleware to parse all incoming request bodies as raw text first,
// preventing Express from stripping out unformatted data.
app.use(express.text({ type: '*/*' }));

app.post('/api/botium-webhook', async (req, res) => {
    try {
        console.log("---------------------------------------------------");
        console.log("[PROXY] Webhook received from Infobip/Ngrok");
        
        // Safely attempt to parse the incoming raw string into a JSON object
        let payload;
        try {
            payload = JSON.parse(req.body);
        } catch (e) {
            payload = req.body;
        }

        // CRITICAL FILTER: Ignore delivery receipts (ACKs) to prevent polluting Botium's queue
        // Infobip sends 'MESSAGE_ACCEPTED' when it receives our message, but this is NOT a bot reply.
        if (payload && payload.status === 'MESSAGE_ACCEPTED') {
            console.log("[PROXY] Delivery receipt ignored.");
            return res.status(200).send("OK");
        }

        console.log(`[PROXY] Forwarding payload to Botium. Message Type: ${payload?.message?.body?.type || 'UNKNOWN'}`);

        // Forward the actual bot message to Botium's internal listener (port 1234)
        // enforcing the correct Content-Type header
        await axios.post('http://127.0.0.1:1234/api/botium-webhook', payload, {
            headers: { 'Content-Type': 'application/json' }
        });
        
        console.log("[PROXY] Forwarding successfully completed!");
        console.log("---------------------------------------------------");
        
        // Acknowledge successful processing back to Infobip
        res.status(200).send("OK");

    } catch (err) {
        console.error("[PROXY] Error during payload processing:", err.message);
        res.status(500).send("Internal Server Error");
    }
});

// Start the Proxy Server
const PORT = 3000;
app.listen(PORT, () => {
    console.log(`[PROXY] Active and listening on port ${PORT}...`);
});