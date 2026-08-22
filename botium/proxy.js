const express = require('express');
const axios = require('axios');

const app = express();

// middleware per parsare il body come testo
app.use(express.text({ type: '*/*' }));

app.post('/api/botium-webhook', async (req, res) => {
    try {
        console.log("---------------------------------------------------");
        console.log("[PROXY] Ricevuto webhook da Infobip/Ngrok!");
        
        // Prendiamo la stringa ricevuta e la convertiamo in JSON
        let payload;
        try {
            payload = JSON.parse(req.body);
        } catch (e) {
            payload = req.body;
        }

        // Ignoriamo le ricevute di ritorno vuote per non intasare Botium
        if (payload && payload.status === 'MESSAGE_ACCEPTED') {
            return res.status(200).send("OK");
        }

        console.log(`[PROXY] Inoltro a Botium del pacchetto: ${payload?.message?.body?.type || 'UNKNOWN'}`);

        // Inoltriamo il pacchetto a Botium (porta 1234) forzando l'header corretto
        await axios.post('http://127.0.0.1:1234/api/botium-webhook', payload, {
            headers: { 'Content-Type': 'application/json' }
        });
        
        console.log("[PROXY] Inoltro completato con successo!");
        console.log("---------------------------------------------------");
        
        // Rispondiamo a Infobip che è tutto ok
        res.status(200).send("OK");

    } catch (err) {
        console.error("[PROXY] Errore durante l'elaborazione:", err.message);
        res.status(500).send("Errore Interno");
    }
});

// Accendiamo il Proxy sulla porta 3000
const PORT = 3000;
app.listen(PORT, () => {
    console.log(`[PROXY] Attivo e in ascolto sulla porta ${PORT}...`);
});