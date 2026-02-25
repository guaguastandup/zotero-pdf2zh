<div align="center">

![Zotero PDF2zh](./favicon@0.5x.svg)

<h2 id="title">Zotero PDF2zh</h2>

[![zotero target version](https://img.shields.io/badge/Zotero-8-blue?style=flat-square&logo=zotero&logoColor=CC2936)](https://www.zotero.org/download/)
[![Using Zotero Plugin Template](https://img.shields.io/badge/Using-Zotero%20Plugin%20Template-blue?style=flat-square&logo=github)](https://github.com/windingwind/zotero-plugin-template)
![Downloads release](https://img.shields.io/github/downloads/guaguastandup/zotero-pdf2zh/total?color=yellow)
[![License](https://img.shields.io/github/license/guaguastandup/zotero-pdf2zh)](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/LICENSE)

Usa [PDF2zh](https://github.com/Byaidu/PDFMathTranslate) e [PDF2zh_next](https://github.com/PDFMathTranslate/PDFMathTranslate-next) in Zotero per la traduzione di PDF

Versione v3.0.36 | [Vecchia versione v2.4.3](./2.4.3%20version/README.md)

**📝 Lingue disponibili:** [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Italiano](README.it.md) | [Français](README.fr.md)

> **Nota:** Questa traduzione è stata generata dall'AI e potrebbe contenere imprecisioni. Per le informazioni più accurate, fare riferimento alla [versione cinese originale](README.md).

</div>


# Come Usare Questo Plugin

Questa guida ti guiderà attraverso l'installazione e la configurazione del plugin Zotero PDF2zh.

❓ Hai bisogno di aiuto?

- Vai alle FAQ: [Domande Frequenti](#frequently-asked-questions-faq)
- Chiedi domande base (come installare Python, conda, ecc.) all'AI
- Chiedi nei GitHub Issues
- Unisciti al gruppo QQ: Gruppo 5: 1064435415（Risposta: github）

# Guida all'Installazione

## Passo 0: Installa Python e Zotero

- [Link Download Python](https://www.python.org/downloads/) - Versione 3.12.0 raccomandata

- Il plugin supporta [Zotero 8](https://www.zotero.org/download/)

- Apri terminale/cmd (gli utenti Windows usa cmd.exe in modalità **Amministratore**)

## Passo 1: Installa uv/conda

**Installazione uv (Raccomandata)**

1. Installa uv
```shell
# Metodo 1: Installazione tramite script (raccomandato)
# macOS/Linux
wget -qO- https://astral.sh/uv/install.sh | sh
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Metodo 2: installazione pip
pip install uv
```

2. Verifica l'installazione di uv
```shell
# Se viene mostrata la versione di uv, l'installazione è completa
uv --version
```

**Installazione conda**

1. Installa conda seguendo: https://www.anaconda.com/docs/getting-started/miniconda/install#windows-command-prompt

2. Verifica l'installazione di conda
```shell
conda --version
```

## Passo 2: Scarica i File del Progetto

```shell
# 1. Crea e entra nella cartella zotero-pdf2zh
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# 2. Scarica ed estrai la cartella server
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
unzip server.zip

# 3. Entra nella cartella server
cd server
```

## Passo 3: Prepara l'Ambiente ed Esegui

1. **Installa le dipendenze**
```shell
pip install -r requirements.txt
```

2. **Se usi conda**
```shell
python server.py --env_tool=conda
```

3. **Se usi uv (predefinito)**
```shell
python server.py
```

Mantieni lo script in esecuzione durante la traduzione. Opzioni predefinite:
- Gestione ambiente virtuale abilitata
- uv come strumento ambiente virtuale
- Controllo automatico aggiornamenti
- Porta predefinita: **8890**

## Passo 4: Scarica e Installa il Plugin

Scarica v3.0.37 [qui](https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v3.0.37/zotero-pdf-2-zh.xpi)

In Zotero, apri "Strumenti → Plugin", trascina il file xpi per installare. Riavvia Zotero se necessario.

## Passo 5: Impostazioni Plugin Zotero

**Opzioni di Configurazione**

- Cambia tra motori di traduzione `pdf2zh`/`pdf2zh_next`
- Configura **qps** e **poolsize** in base al tuo fornitore di servizi
- Font personalizzati per motore pdf2zh

**Servizi di Traduzione**

| Tipo di Servizio | Nome Servizio | Descrizione |
|--------------|--------------|-------------|
| Gratis & No Config | siliconflowfree | Basato sul modello GLM4-9B di SiliconFlow (solo pdf2zh_next) |
| Gratis & No Config | bing/google | Traduzione automatica ufficiale |
| Scontato | openaliked | Piano di collaborazione Volcano Engine - 500k token/giorno |
| Scontato | silicon | Ricompense invito disponibili |
| Alta Qualità | deepseek | Buona traduzione, meccanismo cache |
| Alta Qualità | aliyunDashScope | Buoni risultati, bonus nuovi utenti |

## Passo 6: Opzioni di Traduzione

In Zotero, clicca con il tasto destro sulla voce/PDF, seleziona l'opzione di traduzione PDF2zh.

Opzioni:
- **Traduci PDF**: Genera PDF tradotto
- **Ritaglia PDF**: Ritaglia e unisci per lettura mobile
- **Confronta PDF**: Originale e traduzione affiancati
- **Ritaglia-Confronta**: Per PDF a doppia colonna

## Passo 7: Aggiornamento Pacchetto (Nuovo)

Sia plugin che server supportano auto-aggiornamento. Per aggiornamenti manuali:

1. Entra nell'ambiente virtuale
2. Esegui: `pip install --upgrade pdf2zh_next babeldoc` (conda) o `uv pip install --upgrade pdf2zh_next babeldoc` (uv)

# Domande Frequenti (FAQ)

### Sull'Ambiente Virtuale

**D: Installazione uv/conda fallita, posso saltare l'ambiente virtuale?**

A: Se usi solo un motore e hai Python 3.12.0 globalmente, puoi disabilitare la gestione dell'ambiente virtuale:
```shell
python server.py --enable_venv=False
```

### Sulla Rete

**D: NetworkError quando tento di recuperare risorse?**

A:
- Assicurati che il plugin sia versione 3.0.x
- Mantieni server.py in esecuzione
- Verifica se la porta 8890 è occupata
- Prova a cambiare porta
- Controlla firewall e antivirus

**D: La traduzione è bloccata in un certo punto?**

A: pdf2zh_next scarica gli asset alla prima esecuzione. Questo è lento. Puoi scaricare il pacchetto exe ed eseguirlo una volta per memorizzare nella cache gli asset.

### Sull'Ambiente

**D: Routine di inizializzazione DLL fallita?**

A:
- Downgrada il pacchetto onnx alla versione `1.16.1` nell'ambiente virtuale
- Prova a installare vs_redist.x86.exe invece di x64
- Per macOS vecchie versioni, usa Python 3.11

### Sui Servizi Remoti

**D: Posso usare senza configurazione API?**

A: Solo i servizi gratuiti come siliconflowfree o bing/google funzionano senza API.

**D: Troppi token consumati?**

A: Un documento di 10 pagina consuma tipicamente 70-100k token. Prova a disabilitare l'estrazione di terminologia nelle impostazioni pdf2zh_next.

### Sulle Funzioni del Plugin

**D: PDF scansionato rilevato, traduzione fallita?**

A: Il plugin non fornisce OCR. Usa altri strumenti per fare prima l'OCR dei tuoi PDF scansionati.

### Sulle Domande

**D: Come risolvere i problemi efficacemente?**

A:
- Leggi la guida attentamente
- Copia l'output del terminale in txt
- Screenshot delle impostazioni Zotero
- Condividi tutti e tre nel gruppo QQ con: cosa hai controllato, metodi provati, tutorial guardati

# Ringraziamenti

- @Byaidu [PDF2zh](https://github.com/Byaidu/PDFMathTranslate)
- @awwaawwa [PDF2zh_next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next)
- @windingwind [zotero-plugin-template](https://github.com/windingwind/zotero-plugin-template)
- [Immersive Translate](https://immersivetranslate.com) per sponsorizzare le membership Pro

# Contributori

Grazie a tutti i contributori!

<a href="https://github.com/guaguastandup/zotero-pdf2zh/graphs/contributors"> <img src="https://contrib.rocks/image?repo=guaguastandup/zotero-pdf2zh" /></a>

# Come Supportarmi

💐 Plugin gratuito e open-source, il tuo supporto mi mantiene in attività!

- ☕️ [Buy me a coffee (WeChat/Alipay)](https://github.com/guaguastandup/guaguastandup)
- 🐳 [AiDian](https://afdian.com/a/guaguastandup)
- 🤖 [Invito SiliconFlow](https://cloud.siliconflow.cn/i/WLYnNanQ)

# Star History

[![Star History Chart](https://api.star-history.com/svg?repos=guaguastandup/zotero-pdf2zh&type=Date)](https://www.star-history.com/#guaguastandup/zotero-pdf2zh&Date)
