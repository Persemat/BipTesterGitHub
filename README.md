# BipTester 🤖🧪
**Automated Model-Based E2E Testing Framework for Infobip Chatbots.**

BipTester è un framework automatizzato che traduce la logica visiva dei chatbot creati sulla piattaforma **Infobip Answers** (esportati in formato JSON) in suite di test E2E eseguibili meccanicamente tramite **Botium**. 

Attraverso la modellazione del bot in un grafo matematico, il tool garantisce la copertura dei percorsi conversazionali, validando a runtime gli stati del bot su canali asincroni live (Open Channel / Webhooks).

---

## 🚀 Funzionalità Chiave

* **Analisi e Inlining (Parser):** Appiattisce i JSON nativi in un MultiDiGraph (`NetworkX`), risolvendo dinamicamente le dipendenze e unendo i "Componenti" Infobip annidati in un unico flusso continuo.
* **Smart Routing & PathFinding:** Esplora il grafo tramite algoritmo DFS per dedurre i percorsi conversazionali unici (happy paths, fallback, timeout), estraendo i vincoli logici matematici (*Path Constraints*) necessari per attraversarli.
* **Session Tracking:** Simula la "memoria a breve termine" del bot durante il collaudo, registrando gli input generati per formattare coerentemente le variabili e le risposte testuali successive.
* **Mock Data Injection:** Interroga un registro interno per iniettare dati fittizi ma sintatticamente validi per superare i blocchi di validazione di Infobip (es. email, CAP numerici, stringhe).
* **Tolleranza Dinamica (Wildcards):** Scherma gli ID di sessione e i calcoli generati in tempo reale dal server convertendo le variabili non tracciabili in wildcard (`*`) per il motore di Botium.

---

## 🛠️ Prerequisiti

Prima di iniziare, assicurati di avere installato sulla tua macchina:
- **Python 3.8+** (per il motore di parsing e generazione BipTester)
- **Node.js 16+** (per eseguire l'ambiente Botium CLI e il reverse proxy)
- Accesso a un bot Infobip configurato con **Open Channel** 
- Account ngrok 

---

## 📂 Struttura del Progetto

```text
BipTester/
├── chatbots/                 # 📥 Inserire qui l'export JSON del bot
│   └── components/           # Sottomoduli/Componenti JSON collegati
├── botium/                   # ⚙️ Ambiente di esecuzione Node.js
│   ├── botium.json           # File di configurazione del connettore (Webhook URL)
│   └── botiumwork/           # Risultati e logs temporanei di Botium
├── output/                   # 📤 Destinazione dei file .convo.txt generati
├── parsing/                  # Modulo Parser (Estrazione e modellazione a grafo)
├── test_generation/          # Modulo Translator & PathFinder
├── rendering/                # Modulo di supporto per la generazione visiva del grafo
├── mock_registry.json        # Registro dei dati fittizi per l'injection
└── main.py                   # Script principale di orchestrazione
--- 

## Installazione

- Clona repository in locale: 
    git clone git@gitlab.com:securitychatbot/infobip-persico.git

    cd infobip-persico
- Crea l'ambiente virtuale:
    python -m venv .venv
- Attiva l'ambiente e installa le dipendenze necessarie:
    .venv\Scripts\activate  (Windows)
    source .venv/bin/activate   (macOS/linux)

    pip install -r requirements.txt
- Installa Botium CLI:
    npm install -g botium-cli

## Esecuzione test E2E (momentanea)

- Apri terminale:
    ngrok http 3000

- Copia l'url pubblico generato e incollalo nel campo response webhook del file botium.json:
        "responseWebhook": {
          "url": " inserisci qua l'url "
        }

- Apri un secondo terminale, entra nella cartella "botium" del progetto e fai partire il proxy:
    npm run start-proxy

- Apri un'altro terminale, vai nella cartella botium e esegui:
    npm run test-e2e



