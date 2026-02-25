<div align="center">

![Zotero PDF2zh](./favicon@0.5x.svg)

<h2 id="title">Zotero PDF2zh</h2>

[![zotero target version](https://img.shields.io/badge/Zotero-8-blue?style=flat-square&logo=zotero&logoColor=CC2936)](https://www.zotero.org/download/)
[![Using Zotero Plugin Template](https://img.shields.io/badge/Using-Zotero%20Plugin%20Template-blue?style=flat-square&logo=github)](https://github.com/windingwind/zotero-plugin-template)
![Downloads release](https://img.shields.io/github/downloads/guaguastandup/zotero-pdf2zh/total?color=yellow)
[![License](https://img.shields.io/github/license/guaguastandup/zotero-pdf2zh)](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/LICENSE)

Zotero에서[PDF2zh](https://github.com/Byaidu/PDFMathTranslate)와[PDF2zh_next](https://github.com/PDFMathTranslate/PDFMathTranslate-next)를 사용하여 PDF 번역 수행

버전 v3.0.36 | [이전 버전 v2.4.3](./2.4.3%20version/README.md)

**📝 사용 가능한 언어:** [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Italiano](README.it.md) | [Français](README.fr.md)

> **참고:** 이 번역은 AI로 생성되었으며 부정확한 정보가 포함될 수 있습니다. 가장 정확한 정보는 [원본 중국어 버전](README.md)을 참조하십시오.

</div>


# 플러그인 사용 방법

이 가이드에서는 Zotero PDF2zh 플러그인의 설치 및 구성에 대해 설명합니다.

❓ 도움이 필요하신가요?

- FAQ로 이동: [자주 묻는 질문](#frequently-asked-questions-faq)
- 기본 질문(Python 설치 방법 등)은 AI에게 질문하세요
- GitHub Issues에서 질문하기
- QQ 그룹 가입: 5군 1064435415（입장 답: github）

# 설치 가이드

## 0단계: Python과 Zotero 설치

- [Python 다운로드 링크](https://www.python.org/downloads/) - 버전 3.12.0 권장

- 플러그인은[Zotero 8](https://www.zotero.org/download/)을 지원합니다

- 터미널/cmd 열기（Windows 사용자는 cmd.exe를**관리자 권한**으로 실행）

## 1단계: uv/conda 설치

**uv 설치（권장）**

1. uv 설치
```shell
# macOS/Linux
wget -qO- https://astral.sh/uv/install.sh | sh
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 또는 pip 사용
pip install uv
```

2. uv 설치 확인
```shell
# uv 버전이 표시되면 설치 완료
uv --version
```

**conda 설치**

1. conda 설치: https://www.anaconda.com/docs/getting-started/miniconda/install#windows-command-prompt

2. conda 설치 확인
```shell
conda --version
```

## 2단계: 프로젝트 파일 다운로드

```shell
# 1. zotero-pdf2zh 폴더 생성 및 이동
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# 2. server 폴더 다운로드 및 압축 해제
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
unzip server.zip

# 3. server 폴더로 이동
cd server
```

## 3단계: 환경 준비 및 실행

1. **종속성 설치**
```shell
pip install -r requirements.txt
```

2. **conda 사용 시**
```shell
python server.py --env_tool=conda
```

3. **uv 사용 시（기본값）**
```shell
python server.py
```

번역 중에는 스크립트를 계속 실행해주세요. 기본 옵션:
- 가상 환경 관리 활성화
- 가상 환경 도구로 uv 사용
- 자동 업데이트 확인 활성화
- 기본 포트: **8890**

## 4단계: 플러그인 다운로드 및 설치

v3.0.37 [다운로드](https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v3.0.37/zotero-pdf-2-zh.xpi)

Zotero에서「도구→플러그인」을 열고 xpi 파일을 드래그하여 설치합니다. 필요한 경우 Zotero를 다시 시작하세요.

## 5단계: Zotero 플러그인 설정

**구성 옵션**

- `pdf2zh`/`pdf2zh_next` 번역 엔진 전환
- 서비스 제공자에 따라**qps**와**poolsize** 설정
- pdf2zh 엔진의 사용자 정의 폰트

**번역 서비스**

| 서비스 유형 | 서비스 이름 | 설명 |
|--------------|--------------|-------------|
| 무료·설정 불필요 | siliconflowfree | SiliconFlow의 GLM4-9B 모델(pdf2zh_next만 해당) |
| 무료·설정 불필요 | bing/google | 공식 기계 번역 |
| 할인 혜택 | openaliked | 화산 엔진 협업 계획 - 50만 토큰/일 |
| 할인 혜택 | silicon | 초대 리워드 있음 |
| 고품질 | deepseek | 번역 품질 좋음, 캐시 메커니즘 있음 |
| 고품질 | aliyunDashScope | 좋은 결과, 신규 사용자 보너스 |

## 6단계: 번역 옵션

Zotero에서 항목/PDF를 마우스 오른쪽 버튼으로 클릭하고 PDF2zh 번역 옵션을 선택합니다.

옵션:
- **PDF 번역**: 번역된 PDF 생성
- **PDF 자르기**: 모바일 보기를 위해 자르고 결합
- **PDF 비교**: 원본 텍스트와 번역을 나란히 표시
- **자르기 비교**: 이중 열 PDF용

## 7단계: 패키지 업데이트（새 기능）

플러그인과 서버는 자동 업데이트를 지원합니다. 수동 업데이트의 경우:

1. 가상 환경 진입
2. 실행: `pip install --upgrade pdf2zh_next babeldoc` (conda) 또는 `uv pip install --upgrade pdf2zh_next babeldoc` (uv)

# 자주 묻는 질문(FAQ)

### 가상 환경에 대해

**Q: uv/conda 설치에 실패했습니다. 가상 환경을 건너뛸 수 있나요?**

A: 하나의 엔진만 사용하고 전역 Python이 3.12.0인 경우 가상 환경 관리를 비활성화할 수 있습니다:
```shell
python server.py --enable_venv=False
```

### 네트워크에 대해

**Q: 리소스 가져오기 시 네트워크 오류가 발생했습니다?**

A:
- 플러그인이 버전 3.0.x인지 확인
- server.py를 실행한 상태로 유지
- 포트 8890이 점유되어 있는지 확인
- 포트 전환 시도
- 방화벽 및 백신 확인

**Q: 번역이 특정 위치에서 멈춥니다?**

A: pdf2zh_next는 첫 실행 시 에셋을 다운로드합니다. 시간이 오래 걸립니다. exe 패키지를 다운로드하여 한 번 실행하면 에셋을 캐시할 수 있습니다.

### 환경에 대해

**Q: DLL 초기화 루틴이 실패했습니다?**

A:
- 가상 환경에서 onnx 패키지를 버전`1.16.1`로 다운그레이드
- vs_redist.x86.exe 설치 시도
- macOS 이전 버전의 경우 Python 3.11 사용

### 원격 서비스에 대해

**Q: API 구성 없이 사용할 수 있나요?**

A: siliconflowfree 또는 bing/google과 같은 무료 서비스만 API 없이 작동합니다.

**Q: 토큰 소모가 너무 많습니다?**

A: 10페이지 논문은 일반적으로 7~10만 토큰을 소모합니다. pdf2zh_next 설정에서 용어 추출을 비활성화해 보세요.

### 플러그인 기능에 대해

**Q: 스캔된 PDF가 감지되었습니다, 번역에 실패했습니다?**

A: 플러그인은 OCR을 제공하지 않습니다. 스캔된 PDF는 다른 도구로 OCR 처리를 먼저 하세요.

### 질문에 대해

**Q: 효과적으로 문제 해결을 하려면?**

A:
- 가이드를 주의 깊게 읽기
- 터미널 출력을 txt로 복사
- Zotero 설정 스크린샷
- 이 3가지를 QQ 그룹에서 공유: 확인한 내용, 시도한 방법, 본 튜토리얼

# 감사의 말씀

- @Byaidu [PDF2zh](https://github.com/Byaidu/PDFMathTranslate)
- @awwaawwa [PDF2zh_next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next)
- @windingwind [zotero-plugin-template](https://github.com/windingwind/zotero-plugin-template)
- [Immersive Translate](https://immersivetranslate.com) Pro 회원권 제공

# 기여자

모든 기여자분들께 감사드립니다!

<a href="https://github.com/guaguastandup/zotero-pdf2zh/graphs/contributors"> <img src="https://contrib.rocks/image?repo=guaguastandup/zotero-pdf2zh" /></a>

# 지원 방법

💐 무료 오픈소스 플러그인, 여러분의 지원이 개발의 원동력입니다!

- ☕️ [Buy me a coffee (WeChat/Alipay)](https://github.com/guaguastandup/guaguastandup)
- 🐳 [AiDian](https://afdian.com/a/guaguastandup)
- 🤖 [SiliconFlow 초대 링크](https://cloud.siliconflow.cn/i/WLYnNanQ)

# Star History

[![Star History Chart](https://api.star-history.com/svg?repos=guaguastandup/zotero-pdf2zh&type=Date)](https://www.star-history.com/#guaguastandup/zotero-pdf2zh&Date)
