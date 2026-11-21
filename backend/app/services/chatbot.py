"""The PC-building assistant (chatbot).

Two modes:

* "ai"      - Claude (Anthropic API) answers, using TOOLS that query OUR database:
              search_parts, recommend_build, check_compatibility, get_product, search_marketplace.
              The model never invents prices: every product/price it mentions comes from a tool.
              The tool loop is written out by hand (see run_ai) so it is easy to follow and explain.
* "offline" - no API key (or the API is unreachable): a rule-based assistant that understands
              budget / use case / resolution in English or Arabic and calls the same recommender.
"""
from __future__ import annotations

import json
import logging
import re
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.constants import CATEGORIES, CATEGORY_SLUGS, LISTING_CATEGORIES
from app.models import Listing, Offer, Product
from app.schemas import ChatMessage, ChatOut, ProductSummaryOut, RecommendIn, RecommendOut
from app.services.catalog import apply_sort, build_product_query, with_store
from app.services.compatibility import build_report
from app.services.recommender import USE_CASE_LABEL, recommend

log = logging.getLogger(__name__)
PRODUCT_REF = re.compile(r"\[\[product:(\d+)\]\]")

SYSTEM_PROMPT = f"""You are the PC-building assistant of {settings.app_name}, a website that compares \
PC-part prices across three stores in Jordan (iGeek Megastore, CompuJordan and Oriental Store). \
All prices are in Jordanian Dinar (JOD). Users can also buy used parts from each other in the site's marketplace.

How to help:
- Understand the user's needs: budget in JOD, main use (gaming, streaming, video editing / 3D, \
programming / office, AI / workstation), target resolution and the games or apps they care about, \
and parts they already own. If the budget or main use is missing, ask one short question - but when the \
user wants a quick answer, make sensible assumptions and say what you assumed.
- Never invent products, specs or prices. Use the tools: recommend_build for complete builds, \
search_parts to look up parts or alternatives, check_compatibility for parts the user picked, \
get_product for details and per-store prices, search_marketplace for used items from other users.
- Prefer in-stock parts and point out when one store is clearly cheaper.
- Whenever you mention a catalog product, put its id right after its name as [[product:ID]], e.g. \
"Ryzen 5 7600 [[product:12]]". The website turns it into a link that already shows the current best price, \
so don't repeat that price next to it. Only use ids returned by the tools.
- Keep replies short and easy to scan: a one-line summary, then a compact list, then the key trade-offs \
in plain words (where the money goes and what to upgrade later). Don't repeat every spec.
- Reply in the user's language (Arabic or English).
- Prices change often; remind users to confirm price and stock on the store page before buying.
- Only help with PC hardware, PC builds and shopping on this site; politely decline unrelated requests."""

_CATEGORY_ENUM = list(CATEGORY_SLUGS)
TOOLS = [
    {
        "name": "search_parts",
        "description": (
            "Search the live catalog of PC parts sold by the three Jordanian stores, with the current lowest "
            "price in JOD, the store, stock status and key specs. Call this whenever the user asks about "
            "specific parts, prices, availability, cheaper or faster alternatives, or wants options in a category."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": _CATEGORY_ENUM, "description": "Part category."},
                "query": {"type": "string", "description": "Free text such as 'rtx 4060', 'ryzen 5' or 'ddr5 32gb'. Empty to browse."},
                "max_price": {"type": "number", "description": "Maximum price in JOD."},
                "min_price": {"type": "number", "description": "Minimum price in JOD."},
                "sort": {"type": "string", "enum": ["price_asc", "price_desc", "performance"],
                         "description": "performance = fastest first (CPUs/GPUs)."},
                "in_stock_only": {"type": "boolean", "description": "Default true."},
                "limit": {"type": "integer", "description": "1-10, default 6."},
            },
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "recommend_build",
        "description": (
            "Build a complete, compatible PC from in-stock parts for a budget, using RigRadar's recommender "
            "(budget split by use case, socket/RAM/PSU/case compatibility checks). Call this when the user wants "
            "a full build or asks what they can get for a budget. Returns the parts, prices, total and notes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "budget": {"type": "number", "description": "Total budget in JOD (150-20000)."},
                "use_case": {"type": "string", "enum": ["gaming", "streaming", "creator", "office", "workstation"],
                             "description": "creator = video editing/3D/design, workstation = AI/CAD/heavy multi-core."},
                "resolution": {"type": "string", "enum": ["1080p", "1440p", "4k"], "description": "Gaming resolution, if known."},
                "cpu_brand": {"type": "string", "enum": ["any", "amd", "intel"]},
                "gpu_brand": {"type": "string", "enum": ["any", "nvidia", "amd", "intel"]},
                "include": {"type": "array", "items": {"type": "string", "enum": _CATEGORY_ENUM},
                            "description": "Only these categories (e.g. when the user already owns a case). Omit for a full build."},
            },
            "required": ["budget", "use_case"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "check_compatibility",
        "description": "Check whether specific catalog parts work together (socket, RAM type, case size, PSU wattage, graphics output).",
        "input_schema": {
            "type": "object",
            "properties": {"product_ids": {"type": "array", "items": {"type": "integer"}, "description": "Catalog product ids."}},
            "required": ["product_ids"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "get_product",
        "description": "Get full specs and every store's current price and stock for one catalog product.",
        "input_schema": {
            "type": "object",
            "properties": {"product_id": {"type": "integer"}},
            "required": ["product_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "search_marketplace",
        "description": "Search used / second-hand items that users of this site are selling. Call when the user asks for used parts or has a very tight budget.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category": {"type": "string", "enum": list(LISTING_CATEGORIES)},
                "max_price": {"type": "number"},
            },
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


# --------------------------------------------------------------------------- tool implementations
class ToolState:
    """Remembers products/builds returned by tools so the API can send them to the frontend."""

    def __init__(self):
        self.products: dict[int, Product] = {}
        self.build: RecommendOut | None = None

    def remember(self, products):
        for p in products:
            self.products[p.id] = p


def _compact(p: Product) -> dict:
    keep = ("socket", "cores", "chip", "vram_gb", "score", "gaming_score", "multi_score", "chipset", "memory_type",
            "form_factor", "wifi", "capacity_gb", "speed_mhz", "storage_type", "wattage", "efficiency",
            "cooler_type", "radiator_mm", "igpu", "tdp_w")
    return {
        "id": p.id, "name": p.name, "category": p.category,
        "price_jod": float(p.best_price) if p.best_price is not None else None,
        "store": p.best_store.name if p.best_store else None,
        "in_stock": p.in_stock, "stores_selling": p.offer_count,
        "specs": {k: v for k, v in (p.specs or {}).items() if k in keep},
    }


def tool_search_parts(db: Session, state: ToolState, args: dict) -> dict:
    category = args.get("category")
    if category not in CATEGORY_SLUGS:
        category = None
    query = (args.get("query") or "").strip() or None
    if not category and not query:
        return {"error": "Give a category or a search query."}
    limit = min(max(int(args.get("limit") or 6), 1), 10)
    stmt = build_product_query(
        category=category, q=query, min_price=args.get("min_price"), max_price=args.get("max_price"),
        in_stock=args.get("in_stock_only", True),
    )
    rows = db.scalars(with_store(apply_sort(stmt, args.get("sort") or "price_asc", category)).limit(limit)).all()
    state.remember(rows)
    return {"results": [_compact(p) for p in rows], "count": len(rows)}


def tool_recommend_build(db: Session, state: ToolState, args: dict) -> dict:
    budget = min(max(float(args.get("budget") or 0), 150), 20000)
    req = RecommendIn(
        budget=Decimal(str(budget)), use_case=args.get("use_case") or "gaming", resolution=args.get("resolution"),
        cpu_brand=args.get("cpu_brand") or "any", gpu_brand=args.get("gpu_brand") or "any",
        include=args.get("include") or None,
    )
    rec = recommend(db, req)
    state.build = rec
    ids = [part.product.id for part in rec.parts]
    state.remember(db.scalars(select(Product).where(Product.id.in_(ids)).options(selectinload(Product.best_store))).all())
    return {
        "parts": [{"category": p.category, "id": p.product.id, "name": p.product.name, "price_jod": p.price,
                   "store": p.product.best_store.name if p.product.best_store else None, "why": p.reason}
                  for p in rec.parts],
        "total_jod": rec.total_price, "budget_jod": rec.budget, "leftover_jod": rec.leftover,
        "estimated_watts": rec.estimated_wattage, "compatible": rec.compatible,
        "issues": [i.message for i in rec.issues if i.level != "info"], "notes": rec.notes,
    }


def tool_check_compatibility(db: Session, state: ToolState, args: dict) -> dict:
    ids = [int(i) for i in (args.get("product_ids") or [])][:12]
    products = db.scalars(select(Product).where(Product.id.in_(ids)).options(selectinload(Product.best_store))).all()
    if not products:
        return {"error": "None of those product ids exist."}
    state.remember(products)
    parts = {p.category: p for p in products}
    report = build_report(parts)
    return {"compatible": report.compatible, "total_jod": report.total_price, "estimated_watts": report.estimated_wattage,
            "recommended_psu_watts": report.recommended_psu_w,
            "issues": [{"level": i.level, "message": i.message} for i in report.issues]}


def tool_get_product(db: Session, state: ToolState, args: dict) -> dict:
    product = db.scalar(select(Product).where(Product.id == int(args.get("product_id") or 0))
                        .options(selectinload(Product.offers).selectinload(Offer.store), selectinload(Product.best_store)))
    if product is None:
        return {"error": "Product not found."}
    state.remember([product])
    data = _compact(product)
    data["specs"] = {k: v for k, v in (product.specs or {}).items() if not k.startswith("_")}
    data["offers"] = [{"store": o.store.name, "price_jod": float(o.price) if o.price else None,
                       "in_stock": o.in_stock, "url": o.url} for o in product.offers if o.is_active]
    return data


def tool_search_marketplace(db: Session, state: ToolState, args: dict) -> dict:
    stmt = select(Listing).where(Listing.status == "active").options(selectinload(Listing.seller))
    if q := (args.get("query") or "").strip():
        for token in q.lower().split()[:6]:
            stmt = stmt.where(or_(func.lower(Listing.title).like(f"%{token}%"), func.lower(Listing.description).like(f"%{token}%")))
    if args.get("category") in LISTING_CATEGORIES:
        stmt = stmt.where(Listing.category == args["category"])
    if args.get("max_price"):
        stmt = stmt.where(Listing.price <= args["max_price"])
    rows = db.scalars(stmt.order_by(Listing.created_at.desc()).limit(8)).all()
    return {"listings": [{"title": r.title, "price_jod": float(r.price), "condition": r.condition, "city": r.city,
                          "seller": r.seller.username, "link": f"/marketplace/{r.id}"} for r in rows]}


TOOL_HANDLERS = {
    "search_parts": tool_search_parts,
    "recommend_build": tool_recommend_build,
    "check_compatibility": tool_check_compatibility,
    "get_product": tool_get_product,
    "search_marketplace": tool_search_marketplace,
}


def run_tool(db: Session, state: ToolState, name: str, args: dict) -> tuple[str, bool]:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool {name}"}), True
    try:
        result = handler(db, state, args if isinstance(args, dict) else {})
        return json.dumps(result, ensure_ascii=False, default=str), "error" in result
    except Exception as exc:  # noqa: BLE001 - report tool failures back to the model
        log.exception("tool %s failed", name)
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"}), True


# --------------------------------------------------------------------------- AI mode
def _echoable(blocks) -> list:
    """Content to send back as the assistant turn. After a refusal fallback, blocks produced
    before the last `fallback` marker must not be replayed (see the Anthropic docs on fallbacks)."""
    last_fallback = max((i for i, b in enumerate(blocks) if b.type == "fallback"), default=-1)
    drop_before = {"thinking", "redacted_thinking", "tool_use", "server_tool_use"}
    return [b for i, b in enumerate(blocks) if not (i < last_fallback and b.type in drop_before)]


def _finish(text: str, state: ToolState, mode: str = "ai") -> ChatOut:
    referenced = [int(i) for i in PRODUCT_REF.findall(text)]
    products = [state.products[i] for i in dict.fromkeys(referenced) if i in state.products]
    return ChatOut(reply=text.strip(), mode=mode,
                   products=[ProductSummaryOut.model_validate(p) for p in products], build=state.build)


def run_ai(db: Session, messages: list[ChatMessage]) -> ChatOut:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=2, timeout=90)
    convo: list[dict] = [{"role": m.role, "content": m.content} for m in messages]
    while convo and convo[0]["role"] != "user":
        convo.pop(0)  # the API wants the conversation to start with the user
    state = ToolState()
    extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if settings.chat_fallbacks else {}

    for round_ in range(settings.chat_max_tool_rounds + 1):
        last_round = round_ == settings.chat_max_tool_rounds
        response = client.beta.messages.create(
            model=settings.chat_model,
            max_tokens=settings.chat_max_tokens,
            # Static system prompt + tools are cached between requests (cheaper, faster).
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS,
            # On the last round, tools are switched off so the model must answer.
            tool_choice={"type": "none"} if last_round else {"type": "auto"},
            output_config={"effort": settings.chat_effort},
            messages=convo,
            **extra,
        )
        if response.stop_reason == "refusal":
            return ChatOut(reply="Sorry, I can't help with that. I can help you choose PC parts, "
                                 "compare prices and plan a build.", mode="ai")
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason == "max_tokens" and tool_uses:
            return ChatOut(reply="That answer got too long - could you narrow the question down a bit?", mode="ai")
        if response.stop_reason != "tool_use" or not tool_uses:
            text = "".join(b.text for b in response.content if b.type == "text")
            return _finish(text or "Sorry, I couldn't come up with an answer - please try rephrasing.", state)

        convo.append({"role": "assistant", "content": _echoable(response.content)})
        results = []
        for block in tool_uses:  # all results go back together in ONE user message
            content, is_error = run_tool(db, state, block.name, block.input)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error})
        convo.append({"role": "user", "content": results})
    return _finish("Sorry, that took too many steps - please try a simpler question.", state)


# --------------------------------------------------------------------------- offline mode
_ARABIC = re.compile(r"[؀-ۿ]")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
USE_CASE_WORDS = {
    "workstation": r"\bai\b|machine learning|deep learning|\bml\b|\bcad\b|autocad|solidworks|workstation|data science|ذكاء|محطة عمل",
    "creator": r"edit|premiere|davinci|after effects|render|blender|\b3d\b|design|photoshop|youtube video|مونتاج|تصميم|رندر",
    "streaming": r"stream|twitch|kick|بث|ستريم",
    "gaming": r"gam|fps|valorant|fortnite|\bcs2?\b|pubg|warzone|\bgta\b|call of duty|\bcod\b|minecraft|العاب|ألعاب|قيمنق|جيمنج|جيمنق|لعب",
    "office": r"office|study|school|universit|brows|programm|coding|excel|word|مكتب|دراس|برمجة|جامعة",
}
CATEGORY_WORDS = {
    "gpu": r"\bgpu\b|graphics|video card|\brtx\b|\bgtx\b|\brx\s?\d|radeon|geforce|كرت شاشة|كرت الشاشة|كرت",
    "cpu": r"\bcpu\b|processor|ryzen|core i\d|intel core|معالج|بروسيسور",
    "ram": r"\bram\b|memory|ddr[45]|رام|ذاكرة",
    "storage": r"\bssd\b|nvme|storage|hard ?drive|\bhdd\b|هارد|تخزين",
    "psu": r"\bpsu\b|power supply|باور",
    "motherboard": r"motherboard|mainboard|ماذربورد|مذربورد|لوحة ام|لوحة أم",
    "case": r"\bcase\b|chassis|كيس|كيسة",
    "cooler": r"cooler|cooling|\baio\b|مبرد|تبريد",
}


# Model numbers are not budgets: "RTX 5060", "i5-14400F", "Ryzen 7 7800X3D", "B650", "750W"...
_MODEL_NUMBER = re.compile(
    r"(?:rtx|gtx|gt|rx|arc|ryzen\s?\d|i[3579]|ultra\s?\d|[abhxz](?=\d{3}))[\s-]?\d{3,5}\w*"
    r"|\d{3,5}(?:x3d|xt|xtx|ti|kf|k|f|g|x|w|mhz|mt|gb|tb|hz|mm)\b"
)


def parse_budget(text: str) -> float | None:
    t = text.lower().translate(_AR_DIGITS).replace(",", "")
    t = _MODEL_NUMBER.sub(" ", t)
    if m := re.search(r"(\d+(?:\.\d+)?)\s*k\b", t):
        return float(m.group(1)) * 1000
    if m := re.search(r"(\d{3,5})\s*(?:jd|jod|dinar|dinars|دينار|د\.ا|ليرة)", t):
        return float(m.group(1))
    if m := re.search(r"(?:budget|under|around|about|up to|max|ميزانية|ميزانيتي|حدود|بحدود|تقريبا)\D{0,20}(\d{3,5})", t):
        return float(m.group(1))
    numbers = [float(n) for n in re.findall(r"(?<![\d.])(\d{3,5})(?![\d.])", t) if 150 <= float(n) <= 20000]
    return numbers[-1] if numbers else None


def detect_use_case(text: str) -> str | None:
    t = text.lower()
    for use_case, pattern in USE_CASE_WORDS.items():  # dict order = priority
        if re.search(pattern, t):
            return use_case
    return None


def detect_resolution(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\b4k\b|2160", t):
        return "4k"
    if re.search(r"1440|\b2k\b|qhd", t):
        return "1440p"
    if re.search(r"1080|full ?hd|\bfhd\b", t):
        return "1080p"
    return None


AR_USE_CASE = {"gaming": "الألعاب", "streaming": "الألعاب والبث", "creator": "المونتاج والتصميم",
               "workstation": "الأعمال الثقيلة والذكاء الاصطناعي", "office": "الدراسة والعمل المكتبي"}
AR_CATEGORY = {"cpu": "المعالج", "gpu": "كرت الشاشة", "motherboard": "اللوحة الأم", "ram": "الرام",
               "storage": "التخزين", "psu": "مزود الطاقة", "case": "الكيس", "cooler": "مبرد المعالج"}


def _fmt(price: float | None) -> str:
    return "-" if price is None else f"{price:,.2f}".rstrip("0").rstrip(".") + " JOD"


def run_offline(db: Session, messages: list[ChatMessage]) -> ChatOut:
    user_text = " ".join(m.content for m in messages if m.role == "user")
    latest = messages[-1].content
    arabic = bool(_ARABIC.search(latest))
    state = ToolState()
    budget = parse_budget(latest) or parse_budget(user_text)
    use_case = detect_use_case(latest) or detect_use_case(user_text)
    resolution = detect_resolution(user_text)
    t = user_text.lower()
    cpu_brand = "amd" if re.search(r"\bamd\b|ryzen", t) else ("intel" if "intel" in t else "any")
    gpu_brand = "nvidia" if re.search(r"nvidia|rtx|geforce", t) else ("amd" if re.search(r"radeon|\brx\b", t) else "any")

    wants_parts = [c for c, pat in CATEGORY_WORDS.items() if re.search(pat, latest.lower())]
    if wants_parts and not re.search(r"build|pc\b|تجميع|جهاز", latest.lower()):
        category = wants_parts[0]
        query = " ".join(re.findall(r"(?:rtx|gtx|rx|ryzen|core|i[3579])\s?-?\w*\s?\d{3,5}\w*(?:\s?(?:ti|super|xt|x3d))?", latest.lower())) or None
        result = tool_search_parts(db, state, {"category": category, "query": query, "max_price": budget, "limit": 5})
        if query and not result.get("results"):
            result = tool_search_parts(db, state, {"category": category, "max_price": budget, "limit": 5})
        items = result.get("results", [])
        if not items:
            reply = ("لم أجد قطعاً متوفرة بهذه المواصفات حالياً." if arabic
                     else "I couldn't find matching in-stock parts right now - try a higher budget or another model.")
            return _finish(reply, state, "offline")
        head = (f"أرخص الخيارات المتوفرة في فئة {CATEGORIES[category]['name']}:" if arabic
                else f"Cheapest in-stock {CATEGORIES[category]['name'].lower()}" + (f" under {_fmt(budget)}" if budget else "") + ":")
        lines = [f"- {i['name']} [[product:{i['id']}]] · {i['store']}" for i in items]
        return _finish("\n".join([head, *lines]), state, "offline")

    if not budget:
        reply = ("أهلاً! كم ميزانيتك بالدينار، وما الاستخدام الأساسي للجهاز (ألعاب، مونتاج، دراسة/مكتب، ذكاء اصطناعي)؟"
                 if arabic else
                 "Hi! What's your budget in JOD, and what will you mainly use the PC for "
                 "(gaming, streaming, video editing / 3D, study / office, AI / workstation)? "
                 "If it's for gaming, which resolution (1080p, 1440p or 4K)?")
        return _finish(reply, state, "offline")

    use_case = use_case or "gaming"
    tool_recommend_build(db, state, {"budget": budget, "use_case": use_case, "resolution": resolution,
                                     "cpu_brand": cpu_brand, "gpu_brand": gpu_brand})
    rec = state.build
    label = USE_CASE_LABEL[use_case]
    if arabic:
        lines = [f"هذا تجميع مقترح لـ{AR_USE_CASE[use_case]} بميزانية {_fmt(budget)} (المجموع {_fmt(rec.total_price)}):"]
    else:
        lines = [f"Here's a {label} build for a {_fmt(budget)} budget (total {_fmt(rec.total_price)}):"]
    for part in rec.parts:
        store = part.product.best_store.name if part.product.best_store else ""
        cat = AR_CATEGORY[part.category] if arabic else CATEGORIES[part.category]["singular"]
        lines.append(f"- {cat}: {part.product.name} [[product:{part.product.id}]] · {store}")
    problems = [i.message for i in rec.issues if i.level == "error"]
    if problems:
        lines.append(("⚠️ " if arabic else "Warning: ") + " ".join(problems))
    else:
        lines.append("✅ كل القطع متوافقة مع بعضها." if arabic else "All parts are compatible with each other.")
    if rec.total_price > budget:
        lines.append("المجموع أعلى من ميزانيتك - جرّب القطع المستعملة في السوق أو زِد الميزانية قليلاً." if arabic
                     else rec.notes[1] if len(rec.notes) > 1 else "")
    elif not arabic:
        lines.append(rec.notes[0])
    lines.append("يمكنك فتح التجميع في صفحة التجميع لتبديل القطع. الأسعار من آخر تحديث، تأكد منها في المتجر قبل الشراء." if arabic
                 else "Open it in the PC Builder to swap any part.")
    return _finish("\n".join(lines), state, "offline")


def chat(db: Session, messages: list[ChatMessage]) -> ChatOut:
    if not settings.anthropic_api_key:
        return run_offline(db, messages)
    import anthropic

    try:
        return run_ai(db, messages)
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        log.error("Anthropic API key rejected (%s) - using the offline assistant", exc)
    except anthropic.RateLimitError:
        log.warning("Anthropic rate limit - using the offline assistant")
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
        log.warning("Anthropic API unavailable (%s) - using the offline assistant", exc)
    out = run_offline(db, messages)
    out.reply += "\n\n(The AI assistant is temporarily unavailable, so this is an automatic suggestion.)"
    return out
