module.exports = ({ botMsg, botMsgRoot }) => {
    try {
        // Safety check: if there is no payload, skip processing
        if (!botMsgRoot) return;
        
        // Secondary safety check: ignore delivery receipts just in case they bypass the Proxy
        if (botMsgRoot.status === 'MESSAGE_ACCEPTED') return;

        let textToAssign = "EMPTY_OR_UNKNOWN_MESSAGE";

        // Deep extraction: navigate Infobip's proprietary JSON structure
        if (botMsgRoot.message && botMsgRoot.message.body) {
            const body = botMsgRoot.message.body;
            
            // 1. Standard text message extraction
            if (body.type === 'TEXT' && body.text) {
                textToAssign = body.text;
            } 
            // 2. Interactive JSON payload extraction (e.g., Buttons, Carousels)
            else if (body.type === 'JSON' && body.json) {
                textToAssign = JSON.stringify(body.json);
            } 
            // 3. Fallback for other media types (images, locations)
            else {
                textToAssign = JSON.stringify(body);
            }
        } else {
            // Ultimate fallback if Infobip alters its API schema unexpectedly
            textToAssign = JSON.stringify(botMsgRoot);
        }

        // Assign the extracted string to Botium's internal message text property
        botMsg.messageText = textToAssign;
        console.log(`[HOOK] Extracted message: ${botMsg.messageText}`);

    } catch (err) {
        console.log(`[HOOK FATAL ERROR]: ${err.message}`);
        // Ensure the test doesn't crash completely, but registers a verifiable failure
        botMsg.messageText = "HOOK_CRASHED_BUT_TEST_CONTINUES";
    }
};