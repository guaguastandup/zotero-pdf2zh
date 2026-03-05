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

1. **Installez les dépendances**
```shell
pip install -r requirements.txt
```

2. **Si vous utilisez conda**
```shell
python server.py --env_tool=conda
```

3. **Si vous utilisez uv (par défaut)**
```shell
python server.py
```

Gardez le script en cours d'exécution pendant la traduction. Options par défaut :
- Gestion de l'environnement virtuel activée
- uv comme outil d'environnement virtuel
- Vérification automatique des mises à jour
- Port par défaut : **8890**

## Étape 4 : Télécharger et Installer le Plugin

Téléchargez v4.0.0 [ici](https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v4.0.0/zotero-pdf-2-zh.xpi)

Dans Zotero, ouvrez "Outils → Plugins", faites glisser le fichier xpi pour installer. Redémarrez Zotero si nécessaire.

## Étape 5 : Paramètres du Plugin Zotero

**Options de Configuration**

- Basculez entre les moteurs de traduction `pdf2zh`/`pdf2zh_next`
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
2. Exécutez : `pip install --upgrade pdf2zh_next babeldoc` (conda) ou `uv pip install --upgrade pdf2zh_next babeldoc` (uv)

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
