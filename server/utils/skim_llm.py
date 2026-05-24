import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.skim_doc import (
    block_context,
    block_position_label,
    clamp_text,
    document_brief,
    is_reading_text_block,
    is_skippable_section,
    media_context,
    section_by_id,
    section_position,
)


class SkimLLMError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(self, base_url=None, api_key=None, model=None, timeout=None):
        self.base_url = (base_url or os.getenv("SKIM_LLM_BASE_URL", "")).strip()
        self.api_key = api_key or os.getenv("SKIM_LLM_API_KEY", "")
        self.model = model or os.getenv("SKIM_LLM_MODEL", "")
        self.timeout = int(timeout or os.getenv("SKIM_LLM_TIMEOUT", "120"))
        if self.base_url and not self.base_url.endswith("/chat/completions"):
            self.base_url = self.base_url.rstrip("/") + "/chat/completions"

    def assert_configured(self):
        missing = []
        if not self.base_url:
            missing.append("SKIM_LLM_BASE_URL")
        if not self.api_key:
            missing.append("SKIM_LLM_API_KEY")
        if not self.model:
            missing.append("SKIM_LLM_MODEL")
        if missing:
            raise SkimLLMError("Missing LLM configuration: " + ", ".join(missing))

    def chat(self, messages, max_tokens=1200, temperature=0.1, model=None):
        self.assert_configured()
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.base_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if resp.status < 200 or resp.status >= 300:
                    raise SkimLLMError(f"LLM HTTP {resp.status}: {body}")
                result = json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise SkimLLMError(f"LLM HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise SkimLLMError(f"LLM network error: {e}") from e
        except json.JSONDecodeError as e:
            raise SkimLLMError(f"Invalid JSON response from LLM: {e}") from e

        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise SkimLLMError(f"Unexpected LLM response shape: {result}") from e


def sanitize_error(message):
    text = str(message or "")
    for secret in [os.getenv("SKIM_LLM_API_KEY", ""), os.getenv("MINERU_TOKEN", "")]:
        if secret and len(secret) >= 6:
            text = text.replace(secret, "***")
    text = text.replace("\r", " ").replace("\n", " ")
    if len(text) > 800:
        text = text[:800] + "...[truncated]"
    return text


def generate_skim(doc_ir, max_workers=None, client=None):
    client = client or OpenAICompatibleClient()
    max_workers = int(max_workers or os.getenv("SKIM_LLM_MAX_WORKERS", "3"))
    max_workers = max(1, min(max_workers, 8))

    brief = document_brief(doc_ir)
    document_result = call_document_overview(client, brief)
    section_results = call_section_briefs(client, doc_ir, brief, document_result)
    items = call_block_tasks(client, doc_ir, brief, document_result, section_results, max_workers)

    return {
        "version": 1,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "title": doc_ir.get("title"),
        "documentBrief": document_result,
        "sectionBriefs": section_results,
        "items": items,
        "stats": {
            "pages": len(doc_ir.get("pages") or []),
            "blocks": len(doc_ir.get("blocks") or []),
            "items": len(items),
            "failedItems": sum(1 for item in items if item.get("error")),
        },
    }


def call_document_overview(client, brief):
    prompt = "\n".join([
        "请基于下面论文结构生成用于后续段落精简的全文上下文。",
        "要求忠于原文；只保留论文问题、方法、实验对象、主要结论和阅读路线。",
        "输出合法 JSON，不要 Markdown 代码围栏。",
        'JSON: {"overview":"3-6句全文概览","core_claims":["关键主张"],"reading_map":["阅读路径"],"terms":[{"source":"英文术语","target":"中文译名"}]}',
        "",
        brief,
    ])
    return parse_llm_json(client.chat(base_messages(prompt), max_tokens=1600))


def call_section_briefs(client, doc_ir, brief, document_result):
    results = {}
    by_id = {b["id"]: b for b in doc_ir["blocks"]}
    document_context = result_to_plain_text(document_result, env_limit("SKIM_DOCUMENT_CONTEXT_LIMIT", None))
    for section in doc_ir.get("sections") or []:
        if section["id"] == "sec_default" and not section.get("paragraphIds"):
            continue
        if is_skippable_section(doc_ir, section["id"]):
            continue
        paragraph_text = "\n\n".join(
            by_id[block_id]["text"]
            for block_id in section.get("blockIds", [])[:40]
            if block_id in by_id and is_reading_text_block(by_id[block_id])
        )
        if not paragraph_text:
            continue
        prompt = "\n".join([
            "请为后续段落精简生成当前章节上下文。",
            "要求：说明本章在全文中的位置、它解决什么子问题、关键对象和阅读重点；不要逐段复述。",
            "输出合法 JSON，不要 Markdown 代码围栏。",
            'JSON: {"title":"章节标题","summary":"章节上下文","key_points":["阅读重点"],"role_in_paper":"本章在全文中的作用"}',
            "",
            brief,
            f"已有全文上下文:\n{document_context}",
            section_position(doc_ir, section["id"]),
            f"章节内容:\n{limit_text(paragraph_text, env_limit('SKIM_SECTION_CONTEXT_LIMIT', None))}",
        ])
        try:
            results[section["id"]] = parse_llm_json(client.chat(base_messages(prompt), max_tokens=1200))
        except Exception as e:
            results[section["id"]] = {"error": sanitize_error(e), "summary": ""}
    return results


def call_block_tasks(client, doc_ir, brief, document_result, section_results, max_workers):
    blocks = [
        block for block in doc_ir.get("blocks") or []
        if block.get("skimEligible") and not is_skippable_section(doc_ir, block.get("sectionId"))
    ]
    if not blocks:
        return []

    items = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {
            pool.submit(skim_block, client, doc_ir, block, brief, document_result, section_results): block
            for block in blocks
        }
        for future in as_completed(future_map):
            block = future_map[future]
            try:
                item = future.result()
            except Exception as e:
                item = base_item(block)
                item["error"] = sanitize_error(e)
                item["skimText"] = fallback_skim_text(block)
            items.append(item)

    order = {block["id"]: index for index, block in enumerate(doc_ir.get("blocks") or [])}
    items.sort(key=lambda item: order.get(item["blockId"], 10**9))
    return items


def skim_block(client, doc_ir, block, brief, document_result, section_results):
    if block["type"] == "paragraph":
        return skim_paragraph(client, doc_ir, block, brief, document_result, section_results)
    return skim_media(client, doc_ir, block, brief, document_result, section_results)


def skim_paragraph(client, doc_ir, block, brief, document_result, section_results):
    section = section_by_id(doc_ir, block.get("sectionId"))
    section_context = result_to_plain_text(section_results.get(block.get("sectionId")), env_limit("SKIM_SECTION_RESULT_LIMIT", None))
    prompt = "\n".join([
        "请把下面论文段落改写成用于侧边伴读的中文精简句。",
        "这不是总结任务，而是忠实压缩原文：删除不影响主干理解的引用串、修饰、铺垫和重复表达。",
        "必须保留关键事实、数字、实验设置、条件、模型名、数据集名、变量、缩写、图表公式引用和结论。",
        "不要补充原文没有的信息，不要写“本段主要讲了”。",
        "默认输出 1-3 个短句，显著短于原文。",
        "输出合法 JSON，不要 Markdown 代码围栏。",
        'JSON: {"compression":"中文精简句","key_points":["保留的关键点"],"importance":"高/中/低及理由"}',
        "",
        brief,
        f"全文上下文:\n{result_to_plain_text(document_result, env_limit('SKIM_DOCUMENT_CONTEXT_LIMIT', None))}",
        f"章节上下文:\n{section_context}",
        section_position(doc_ir, section.get("id")),
        f"当前对象位置:\n{block_position_label(block)}",
        f"相邻上下文:\n{chr(10).join(block_context(doc_ir, block)) or '无'}",
        f"待精简段落:\n{block.get('text')}",
    ])
    result = parse_llm_json(client.chat(base_messages(prompt), max_tokens=900))
    item = base_item(block)
    item["sourceText"] = block.get("text", "")
    item["result"] = result
    item["skimText"] = clean_skim(result.get("compression") or result.get("summary") or result_to_plain_text(result, 500))
    return item


def skim_media(client, doc_ir, block, brief, document_result, section_results):
    section = section_by_id(doc_ir, block.get("sectionId"))
    section_context = result_to_plain_text(section_results.get(block.get("sectionId")), env_limit("SKIM_SECTION_RESULT_LIMIT", None))
    context_text = media_context(doc_ir, block)
    prompt = build_media_prompt(block, brief, document_result, section_context, section_position(doc_ir, section.get("id")), context_text)
    image_url = asset_to_data_url(block.get("assetPath"))
    result = None
    warning = ""

    if image_url:
        try:
            result = parse_llm_json(client.chat(vision_messages(prompt, image_url), max_tokens=1200))
        except Exception as e:
            warning = f"vision fallback: {sanitize_error(e)}"

    if result is None:
        result = parse_llm_json(client.chat(base_messages(prompt), max_tokens=1200))

    item = base_item(block)
    item["sourceText"] = "\n".join(filter(bool, [
        block.get("caption", ""),
        block.get("text", ""),
        block.get("tableBody", ""),
        block.get("latex", ""),
    ]))
    item["result"] = result
    item["skimText"] = clean_skim(
        result.get("skim")
        or result.get("explanation")
        or result.get("key_message")
        or result.get("table_summary")
        or result.get("equation_summary")
        or result.get("description")
        or result_to_plain_text(result, 900),
        limit=1800,
    )
    if warning:
        item["warning"] = warning
    return item


def build_media_prompt(block, brief, document_result, section_context, position, context_text):
    label = block.get("displayLabel") or {
        "figure": "图",
        "table": "表",
        "equation": "式",
    }.get(block.get("type"), "对象")
    common = [
        "请为论文中的图、表或公式生成侧边伴读解释。",
        "这不是普通段落精简。图、表、公式通常承载证据或方法结构，需要说明它想证明什么、对比什么、变量/模块/指标如何对应正文论点。",
        "你需要自行判断详细程度：架构图、流程图、benchmark/ablation 表、核心公式应给 2-5 个短句；普通样例图或装饰性示例只给 1-2 个短句。",
        "开头必须带对象编号或对象名，例如“Fig. 1：...”“Table 1：...”“Eq. 2：...”。如果没有明确编号，用给定对象标签开头。",
        "必须忠于原文和可见内容；如果需要推断，明确写“推断”。",
        "不要复写整张表或大段 caption；优先解释主结论、关键对比、重要数值、机制关系和正文引用目的。",
        "输出合法 JSON，不要 Markdown 代码围栏。",
        "",
        brief,
        f"全文上下文:\n{result_to_plain_text(document_result, env_limit('SKIM_DOCUMENT_CONTEXT_LIMIT', None))}",
        f"章节上下文:\n{section_context}",
        position,
        f"当前对象位置:\n{block_position_label(block)}",
        f"对象标签:\n{label}",
        f"caption:\n{block.get('caption') or '无'}",
        f"附近正文:\n{context_text or '无'}",
    ]
    if block["type"] == "figure":
        specific = [
            "对象类型: 图",
            "请说明图中的模块/流程/变量/对比/趋势/结论，以及正文为什么引用它。",
            "如果是系统架构图或方法流程图，重点解释信息流、组件关系和该图支撑的核心方法；如果只是样例展示，说明样例展示了什么能力和是否有关键差异。",
            'JSON: {"skim":"带图编号的2-5句伴读解释或1-2句简述","importance":"高/中/低及理由","visual_structure":"图中结构或可见内容","key_message":"核心信息","relation_to_text":"与正文关系"}',
        ]
    elif block["type"] == "table":
        specific = [
            "对象类型: 表",
            "请解释主要比较对象、指标、最重要数值、最强/最弱结果、实验设置，以及表格如何支撑论文主张。",
            f"表格文本:\n{limit_text(block.get('tableBody') or block.get('text') or '', env_limit('SKIM_TABLE_TEXT_LIMIT', None))}",
            'JSON: {"skim":"带表编号的2-5句伴读解释","importance":"高/中/低及理由","main_comparison":"主要比较","best_or_notable_results":["重要结果"],"supports_claim":"支撑的论点"}',
        ]
    else:
        specific = [
            "对象类型: 公式",
            "请解释变量含义、公式整体作用，以及它服务于哪一步方法、训练目标、推导或评价计算。",
            f"LaTeX/公式文本:\n{block.get('latex') or block.get('text') or ''}",
            'JSON: {"skim":"带公式编号的2-4句伴读解释","importance":"高/中/低及理由","equation_summary":"公式整体含义","symbol_notes":["变量解释"],"role_in_paper":"公式作用"}',
        ]
    return "\n".join(common + specific)


def base_messages(prompt):
    return [
        {
            "role": "system",
            "content": "\n".join([
                "你是严谨的学术论文阅读助手。",
                "你必须忠于原文，不编造原文没有的信息。",
                "输出中文，保留关键英文术语、公式变量、图表编号、缩写和专有名词。",
            ]),
        },
        {"role": "user", "content": prompt},
    ]


def vision_messages(prompt, image_url):
    return [
        {
            "role": "system",
            "content": "你是严谨的多模态论文阅读助手。区分图中直接可见信息和结合上下文的推断。",
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]


def asset_to_data_url(path):
    if not path or not os.path.exists(path) or not os.path.isfile(path):
        return ""
    mime = mimetypes.guess_type(path)[0] or "image/png"
    if not mime.startswith("image/"):
        return ""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{data}"


def parse_llm_json(text):
    original = str(text or "").strip()
    clean = original
    if clean.startswith("```"):
        clean = clean.strip("`")
        clean = clean[4:] if clean.lower().startswith("json") else clean
    try:
        return json.loads(clean)
    except Exception:
        start = clean.find("{")
        end = clean.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(clean[start:end + 1])
            except Exception:
                pass
    return {"raw": original}


def env_limit(name, default):
    value = os.getenv(name, "")
    if value == "":
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else None


def limit_text(text, limit=None):
    if limit is None:
        return str(text or "")
    return clamp_text(text, limit)


def result_to_plain_text(result, limit=None):
    if not result:
        return ""
    if isinstance(result, str):
        return limit_text(result, limit)
    if isinstance(result, dict):
        for key in ["compression", "overview", "summary", "skim", "raw"]:
            if result.get(key):
                return limit_text(str(result[key]), limit)
    try:
        return limit_text(json.dumps(result, ensure_ascii=False), limit)
    except Exception:
        return limit_text(str(result), limit)


def clean_skim(text, limit=1200):
    text = " ".join(str(text or "").split())
    return text[:limit]


def fallback_skim_text(block):
    if block["type"] == "paragraph":
        return clamp_text(block.get("text") or "", 240)
    return clamp_text(block.get("caption") or block.get("text") or block.get("latex") or "", 240)


def base_item(block):
    return {
        "blockId": block["id"],
        "type": block["type"],
        "page": block["page"],
        "column": block.get("column") or "single",
        "bbox": block.get("bbox"),
        "sectionId": block.get("sectionId"),
        "sectionTitle": block.get("sectionTitle") or "",
        "sectionPath": block.get("sectionPath") or [],
        "sectionPathText": block.get("sectionPathText") or "",
        "paragraphIndex": block.get("paragraphIndex"),
        "displayLabel": block.get("displayLabel") or "",
        "positionLabel": block_position_label(block),
        "skimText": "",
        "sourceText": "",
        "assetPath": block.get("assetPath") or "",
    }
