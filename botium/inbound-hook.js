module.exports = ({ botMsg, botMsgRoot }) => {
    // botMsgRoot contiene il JSON sia della risposta immediata che del webhook
    const payload = botMsgRoot;

    // 1. Se è la ricevuta sincrona di Infobip, la ignoriamo silenziosamente
    if (payload && payload.status === 'MESSAGE_ACCEPTED') {
        return;
    }

    // 2. Se è il vero webhook di Infobip, estraiamo il testo
    if (payload && payload.message && payload.message.body) {
        const body = payload.message.body;
        
        if (body.type === 'TEXT' && body.text) {
            botMsg.messageText = body.text;
            console.log(`[HOOK] Testo estratto con successo: "${botMsg.messageText}"`);
        } 
        else if (body.type === 'JSON' && body.json) {
            let extractedText = body.json.content.text || "";
            if (body.json.content.options) {
                const buttonTitles = body.json.content.options.map(opt => opt.title).join(" | ");
                extractedText += " [" + buttonTitles + "]";
            }
            botMsg.messageText = extractedText;
            console.log(`[HOOK] Custom JSON estratto con successo: "${botMsg.messageText}"`);
        }
    }
};