<div align="center">

![Zotero PDF2zh](./favicon@0.5x.svg)

<h2 id="title">Zotero PDF2zh</h2>

[![zotero target version](https://img.shields.io/badge/Zotero-8-blue?style=flat-square&logo=zotero&logoColor=CC2936)](https://www.zotero.org/download/)
[![Using Zotero Plugin Template](https://img.shields.io/badge/Using-Zotero%20Plugin%20Template-blue?style=flat-square&logo=github)](https://github.com/windingwind/zotero-plugin-template)
![Downloads release](https://img.shields.io/github/downloads/guaguastandup/zotero-pdf2zh/total?color=yellow)
[![License](https://img.shields.io/github/license/guaguastandup/zotero-pdf2zh)](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/LICENSE)

Utilisez [PDF2zh](https://github.com/Byaidu/PDFMathTranslate) et [PDF2zh_next](https://github.com/PDFMathTranslate/PDFMathTranslate-next) dans Zotero pour la traduction de PDF

Version v4.0.0 | [Ancienne version v2.4.3](./2.4.3%20version/README.md)

**📝 Langues disponibles:** [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Italiano](README.it.md) | [Français](README.fr.md)

> **Note:** Cette traduction a été générée par l'IA et peut contenir des imprécisions. Pour les informations les plus précises, veuillez vous référer à la [version chinoise originale](README.md).

</div>


# Comment Utiliser Ce Plugin

Ce guide vous accompagnera dans l'installation et la configuration du plugin Zotero PDF2zh.

❓ Besoin d'aide ?

- Allez aux FAQ : [Questions Fréquentes](#frequently-asked-questions-faq)
- Posez des questions de base (comme installer Python, conda, etc.) à l'IA
- Posez des questions dans les GitHub Issues
- Rejoignez le groupe QQ : Groupe 5 : 1064435415（Réponse : github）

# Guide d'Installation

## Étape 0 : Installer Python et Zotero

- [Lien de téléchargement Python](https://www.python.org/downloads/) - Version 3.12.0 recommandée

- Le plugin prend en charge [Zotero 8](https://www.zotero.org/download/)

- Ouvrez un terminal/cmd (les utilisateurs Windows doivent utiliser cmd.exe en mode **Administrateur**)

## Étape 1 : Installer uv/conda

**Installation uv (Recommandée)**

1. Installez uv
```shell
# Méthode 1 : Installation par script (recommandé)
# macOS/Linux
wget -qO- https://astral.sh/uv/install.sh | sh
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Méthode 2 : installation pip
pip install uv
```

2. Vérifiez l'installation d'uv
```shell
# Si la version d'uv s'affiche, l'installation est complète
uv --version
```

**Installation conda**

1. Installez conda en suivant : https://www.anaconda.com/docs/getting-started/miniconda/install#windows-command-prompt

2. Vérifiez l'installation de conda
```shell
conda --version
```

## Étape 2 : Télécharger les Fichiers du Projet

```shell
# 1. Créez et entrez dans le dossier zotero-pdf2zh
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# 2. Téléchargez et extrayez le dossier server
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
unzip server.zip

# 3. Entrez dans le dossier server
cd server
```

## Étape 3 : Préparer l'Environnement et Exécuter

Ce script Python peut démarrer des environnements virtuels pendant l'exécution, installer les paquets nécessaires, et implémenter le basculement entre les environnements virtuels pour les deux moteurs pdf2zh et pdf2zh_next.

Vous devez seulement choisir un outil d'environnement virtuel : `uv` ou `conda`

**1. Si vous choisissez uv (recommandé)**

```shell
# uv run créera automatiquement l'environnement virtuel et installera les dépendances nécessaires
uv run --with flask --with toml --with pypdf --with pymupdf --with packaging server.py
```

**2. Si vous choisissez conda**

Suivez ces étapes (exécutez **dans l'ordre**, ne sautez pas les étapes) :

**Étape 1 : Créer l'environnement virtuel principal** (exécutez une seule fois)

```shell
# Créer un environnement conda nommé zotero-pdf2zh-server
conda create -n zotero-pdf2zh-server python=3.12 -y
```

**Étape 2 : Activer l'environnement**

```shell
conda activate zotero-pdf2zh-server
```

**Étape 3 : Installer les dépendances**

```shell
pip install -r requirements.txt
```

**Étape 4 : Démarrer le service**

```shell
python server.py --env_tool=conda
```

::: danger Important
La fonction de traduction dépend de ce script Python, **vous devez garder le script en cours d'exécution**. Tant que vous avez besoin d'utiliser la fonction de traduction, **ne fermez pas cette fenêtre de script Python**. Fermer le script désactivera la fonction de traduction.
:::

### Configuration Par Défaut

**Options par défaut lors du démarrage avec `python server.py` :**
- Gestion de l'environnement virtuel : Activée
- Outil d'environnement : Auto-détection (uv/conda)
- Version Python : 3.12
- Installation automatique des dépendances : Activée
- Vérification automatique des mises à jour : Activée
- Source de mise à jour : gitee
- Port : 8890
- Source mirror : USTC

### Paramètres de Ligne de Commande Courants

| Paramètre | Description | Utilisation |
|-----------|-------------|----------|
| Démarrage de base | Configuration par défaut | `python server.py` |
| `--port` | Changer le numéro de port | `python server.py --port=9999` |
| `--check_update` | Vérification auto des mises à jour | `python server.py --check_update=False` |
| `--update_source` | Sélection de la source de mise à jour | `python server.py --update_source="github"` |
| `--enable_mirror` | Accélération miroir | `python server.py --enable_mirror=False` |
| `--mirror_source` | Source miroir personnalisée | `python server.py --mirror_source="URL"` |
| `--enable_winexe` | Mode Windows exe | `python server.py --enable_winexe=True --winexe_path='PATH'` |

::: tip Note
- update_source options : `github` / `gitee` (par défaut)
- mirror_source par défaut : miroir USTC
:::

### Remarques

- Si vous utilisez la méthode uv, après l'installation ne déplacez pas le dossier server et ne le renommez pas (cela affecte le chemin de l'environnement virtuel).
- Si vous utilisez la méthode conda, l'environnement virtuel est stocké dans le dossier envs de conda, le dossier server peut être déplacé en toute sécurité.
- Si la vérification des mises à jour échoue au démarrage, vous pouvez changer la source de mise à jour en fonction du réseau : `python server.py --update_source="gitee"` ou `python server.py --update_source="github"`

## Étape 4 : Télécharger et Installer le Plugin

Téléchargez v4.0.0 [ici](https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v4.0.0/zotero-pdf-2-zh.xpi)

Dans Zotero, ouvrez "Outils → Plugins", faites glisser le fichier xpi pour installer. Redémarrez Zotero si nécessaire.

## Étape 5 : Paramètres du Plugin Zotero

**Options de Configuration**

- Basculez entre les moteurs de traduction `pdf2zh`/`pdf2zh_next`

**Comparaison des Moteurs de Traduction**

| Caractéristique | PDF2ZH (Ancien) | PDF2ZH Next (Nouveau) |
|----------------|----------------|-----------------------|
| **Statut Maintenance** | ❌ Plus activement maintenu | ✅ Mises à jour continues |
| **Vitesse Traduction** | ⚡ Plus rapide | Légèrement plus lent |
| **Polices Personnalisées** | ✅ Supporte les polices personnalisées | ❌ Non supporté |
| **Fichier Config** | `config.json` | `config.toml` |
| **Modes Layout Double** | Uniquement layout double basique | Supporte modes Gauche&Droite / Haut&Bas |
| **Fonction Glossaire** | ❌ Non supporté | ✅ Extrait et utilise automatiquement le glossaire |
| **Traduction Tableaux** | ❌ Non supporté | ✅ Supporte la traduction du contenu des tableaux |
| **Compatibilité OCR** | ❌ Non supporté | ✅ Supporte mode compatibilité OCR et auto-OCR |
| **Suppression Watermark** | ❌ Non supporté | ✅ Supporte mode sans watermark |
| **Services Supportés** | Relativement moins | Supporte plus de services (inclus siliconflowfree gratuit) |
| **Projet Amont** | [Byaidu/PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate) | [PDFMathTranslate-next](https://github.com/PDFMathTranslate/PDFMathTranslate-next) |

::: tip Recommandation
Sauf si vous avez besoin de polices personnalisées ou exigez une vitesse maximale, nous recommandons d'utiliser le moteur **PDF2ZH Next**.
:::

- Configurez **qps** et **poolsize** selon votre fournisseur de services
- Polices personnalisées pour le moteur pdf2zh

**Services de Traduction**

| Type de Service | Nom du Service | Description |
|--------------|--------------|-------------|
| Gratuit & Pas de Config | siliconflowfree | Basé sur le modèle GLM4-9B de SiliconFlow (pdf2zh_next uniquement) |
| Gratuit & Pas de Config | bing/google | Traduction automatique officielle |
| Réduit | openaliked | Plan de collaboration Volcano Engine - 500k tokens/jour |
| Réduit | silicon | Récompenses d'invitation disponibles |
| Haute Qualité | deepseek | Bonne traduction, mécanisme de cache |
| Haute Qualité | aliyunDashScope | Bons résultats, bonus nouveaux utilisateurs |

## Étape 6 : Options de Traduction

Dans Zotero, faites un clic droit sur l'entrée/PDF, sélectionnez l'option de traduction PDF2zh.

Options :
- **Traduire PDF** : Génère un PDF traduit
- **Rogner PDF** : Rogne et assemble pour la lecture mobile
- **Comparer PDF** : Original et traduction côte à côte
- **Rogner-Comparer** : Pour les PDF à double colonne

## Étape 7 : Mise à Jour des Paquets (Nouveau)

Le plugin et le server prennent en charge la mise à jour automatique. Pour les mises à jour manuelles :

1. Entrez dans l'environnement virtuel
2. Exécutez : `pip install --upgrade pdf2zh_next babeldoc`

### Script de Lancement en Un Clic

Vous pouvez configurer un lancement en un clic pour plus de commodité :

**Utilisateurs Windows - Créer un Script de Raccourci sur le Bureau :**

1. Créez un nouveau fichier texte sur le bureau, avec :
```bat
@echo off
cd /d D:\zotero-pdf2zh\server
python server.py
pause
```

2. Renommez en `start-pdf2zh.bat` (l'extension doit être `.bat`)

3. Double-cliquez pour lancer

**Utilisateurs macOS / Linux - Configurer un Alias :**

1. Modifiez le fichier de configuration shell :
```shell
# Si vous utilisez zsh (macOS par défaut)
nano ~/.zshrc
# Si vous utilisez bash
nano ~/.bashrc
```

2. Ajoutez un alias à la fin (modifiez le chemin si nécessaire) :
```shell
alias pdf2zh-start='cd /path/to/zotero-pdf2zh/server && python server.py'
```

3. Sauvegardez et exécutez :
```shell
source ~/.zshrc
# ou
source ~/.bashrc
```

4. Tapez `pdf2zh-start` dans le terminal pour lancer

# Questions Fréquentes (FAQ)

### À Propos de l'Environnement Virtuel

**Q : Installation uv/conda échouée, puis-je sauter l'environnement virtuel ?**

R : Si vous n'utilisez qu'un seul moteur et avez Python 3.12.0 globalement, vous pouvez désactiver la gestion de l'environnement virtuel :
```shell
python server.py --enable_venv=False
```

### À Propos du Réseau

**Q : NetworkError lors de la tentative de récupération de ressources ?**

R :
- Assurez-vous que le plugin est en version 3.0.x
- Gardez server.py en cours d'exécution
- Vérifiez si le port 8890 est occupé
- Essayez de changer de port
- Vérifiez le pare-feu et l'antivirus

**Q : La traduction est bloquée à un certain point ?**

R : pdf2zh_next télécharge les assets lors de la première exécution. C'est lent. Vous pouvez télécharger le paquet exe et l'exécuter une fois pour mettre en cache les assets.

### À Propos de l'Environnement

**Q : Routine d'initialisation DLL échouée ?**

R :
- Downgradez le paquet onnx à la version `1.16.1` dans l'environnement virtuel
- Essayez d'installer vs_redist.x86.exe au lieu de x64
- Pour macOS anciennes versions, utilisez Python 3.11

### À Propos des Services Distants

**Q : Puis-je utiliser sans configuration API ?**

R : Seuls les services gratuits comme siliconflowfree ou bing/google fonctionnent sans API.

**Q : Trop de tokens consommés ?**

R : Un document de 10 pages consomme typiquement 70-100k tokens. Essayez de désactiver l'extraction de terminologie dans les paramètres pdf2zh_next.

### À Propos des Fonctions du Plugin

**Q : PDF scanné détecté, traduction échouée ?**

R : Le plugin ne fournit pas d'OCR. Utilisez d'autres outils pour faire d'abord l'OCR de vos PDF scannés.

### À Propos des Questions

**Q : Comment résoudre les problèmes efficacement ?**

R :
- Lisez le guide attentivement
- Copiez la sortie du terminal dans un txt
- Capture d'écran des paramètres Zotero
- Partagez les trois dans le groupe QQ avec : ce que vous avez vérifié, méthodes essayées, tutoriels regardés

# Remerciements

- @Byaidu [PDF2zh](https://github.com/Byaidu/PDFMathTranslate)
- @awwaawwa [PDF2zh_next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next)
- @windingwind [zotero-plugin-template](https://github.com/windingwind/zotero-plugin-template)
- [Immersive Translate](https://immersivetranslate.com) pour sponsoriser les memberships Pro

# Contributeurs

Merci à tous les contributeurs !

<a href="https://github.com/guaguastandup/zotero-pdf2zh/graphs/contributors"> <img src="https://contrib.rocks/image?repo=guaguastandup/zotero-pdf2zh" /></a>

# Comment Me Soutenir

💐 Plugin gratuit et open-source, votre soutien me maintient en activité !

- ☕️ [Buy me a coffee (WeChat/Alipay)](https://github.com/guaguastandup/guaguastandup)
- 🐳 [AiDian](https://afdian.com/a/guaguastandup)
- 🤖 [Invitation SiliconFlow](https://cloud.siliconflow.cn/i/WLYnNanQ)

# Star History

[![Star History Chart](https://api.star-history.com/svg?repos=guaguastandup/zotero-pdf2zh&type=Date)](https://www.star-history.com/#guaguastandup/zotero-pdf2zh&Date)
