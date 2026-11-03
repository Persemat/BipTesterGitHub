<img src="https://www.infobip.com/developers/wp-content/uploads/2023/03/Infobip_logo_favicon.png" alt="Testo alternativo" width="30">  

# Automated Model-Based E2E Testing Framework for Infobip Chatbots 

Questo progetto consiste in un framework automatizzato che traduce la logica visiva dei chatbot creati sulla piattaforma **Infobip Answers** (esportati in formato JSON) in suite di test E2E eseguibili meccanicamente tramite **Botium**. 

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
- **Python 3.8+** (per il motore di parsing e generazione test)
- **Node.js 16+** (per eseguire l'ambiente Botium CLI e il reverse proxy)
- Accesso a un bot Infobip configurato con **Open Channel** 
- Account ngrok 

---

## 📂 Struttura del Progetto

```text
FrameworkTestInfobip/
├── chatbots/                 # Inserire qui l'export JSON del bot
│   └── components/           # Sottomoduli/Componenti JSON collegati
├── botium/                   # ⚙️ Ambiente di esecuzione Node.js
│   ├── botium.json           # File di configurazione del connettore (Webhook URL)
├── spec/
│   ├── generatedTests/       # Destinazione dei file .convo.txt generati
        └── utterances/        # Destinazione file di Utterances        
├── parsing/                  # Modulo Parser (Estrazione e modellazione a grafo)
├── test_generation/          # Modulo Translator & PathFinder
├── rendering/                # Modulo di supporto per la generazione visiva del grafo
├── mock_registry.json        # Registro dei dati fittizi per l'injection
└── main.py                   # Script principale di orchestrazione
 ```
## Installazione

- **Clona la repository in locale e accedi alla cartella:** 
  ```bash
  git clone git@gitlab.com:securitychatbot/infobip-persico.git
  cd infobip-persico
  ```
- **Crea l'ambiente virtuale:**

  ```Bash
  python -m venv .venv
  ```

  - **Attiva l'ambiente:**

    - **Su Windows:**

    ```Bash
    .venv\Scripts\activate
    ```
    - **Su macOS / Linux:**

    ```Bash
    source .venv/bin/activate
    ```
  - **Installa le dipendenze Python necessarie e Botium CLI :**

  ```Bash
  pip install -r requirements.txt
  
  npm install -g botium-cli
  ```
  - **Configurazione e Setup credenziali**
    
    Per ragioni di sicurezza, credenziali sensibili e l'url ngrok non sono tracciate da Git; 
    di conseguenza configura il tuo ambiente locale in questo modo: 
    1. Naviga alla cartella 'botium/' e crea il tuo file locale dal template botium.example.json:

    ```bash
    cp botium/botium.example.json botium/botium.json
    ```

    2. Sostituisci i placeholders con i tuoi dati relativi a API key, URL Ngrok e Destinazione configurata per il chatbot che testi.

    - **Testing chatbot personale**

    Inserisci l'export del chatbot che vuoi testare nella cartella chatbots. Dopodichè modifica il file main.py sostituendo con il nome del file di export che hai inserito. 

- **Esecuzione test E2E (momentanea)**

  - **Avvia il tunnel di rete: Apri un terminale ed esegui:**

  ```Bash
  ngrok http 3000
  ```

    - **Configura l'endpoint:** 

      Copia l'URL pubblico generato da ngrok (es. [https://xyz.ngrok.app](https://xyz.ngrok.app)) e incollalo nel campo responseWebhook all'interno del file botium/botium.json:

      ```JSON
      "responseWebhook": {
      "url": "inserisci_qui_l_url_di_ngrok"
      }
      ```

  - **Avvia il Proxy locale:** 

    Apri un secondo terminale, assicurati di entrare nella cartella botium del progetto e fai partire il proxy per intercettare le risposte di Infobip:

    ```Bash
    cd botium
    npm run start-proxy
    ```
  - **Esegui la suite di test:** 

    Apri un terzo terminale, vai sempre nella cartella botium ed esegui il collaudo E2E:

    ```Bash
    cd botium
    npm run test-e2e
    ```