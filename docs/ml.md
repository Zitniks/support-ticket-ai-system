# ML: классификация тикетов

Необходимо выделить, к какому из следующих классов принадлежит тикет:

- Проблемы с оплатой
- Недоступность сервиса
- Недоступность внешних интеграций
- Другие (выделим отдельный класс под те запросы, которые не попадают в первые 4 класса)

Массовый сбой может быть по любому из этих типов классов, его выделим в отдельную плоскость и будем искать как кол-во похожих тикетов, пришедших в промежуток времени T (настраиваемый параметр), если кол-во > Q (настраиваемый параметр) -> массовый сбой.

Тк нам нужно выдерживать определенный баланс между скоростью и стоимостью решения, то сделаем следующий вариант из нескольких уровней определения класса:

| Уровень | Модель | Когда используем | Описание | Стоимость |
|---|---|---|---|---|
| L0 | Rule Matcher | 40% тикетов, confidence 0.98+ | Ищем категорию по подстрокам | Низкая |
| L1 | Модель классификации + отдаем модельный confidence | 50% тикетов, classification | Модель классификации тикетов по эмбедингам. + модельный confidence, который будет определять на какие вопросы может ответить LLM (где модельный confidence выше 60% - можно варьировать процент), и на какие человек | Средняя |
| L2 | Sentence-BERT + FAISS | 5% тикетов, semantic template match | Поиск похожих тикетов в уже определенных классах из уровня L1 | Средняя |
| L3 | LLM API / Human | | Поиск ответа в базе знаний / Ответ человека | Высокая |

На этапе L1 и L2 нужны эмбединги, есть 3 варианта:

**1 — самый качественный, но будет дольше работать и займет больше ресурсов:**
Взять отдельные модели для L1 и для L2. Для L1 можно взять специальные модели для классификации текста, например, DistilBERT. И для L2 можно взять Sentence-BERT. Эти модели заточены специально под свои задачи, что потенциально может улучшить итоговое качество обеих задач, но займет больше ресурсов, тк эмбеднги будут считаться дважды.

**2 — менее качественный, но будет работать быстрее и займет меньше ресурсов:**
Делаем эмбединги 1 моделью (например Е5-large), кладем их в базу данных FAISS. Далее для L1 — строим отдельную модель классификации на этих эмбедингах, например в baseline формате catboost. И для L2 также берем эти эмбединги и ищем похожие например по косинусом расстоянию. Из-за того, что модель эмбедингов 1 и она изначально не заточена на классификацию или поиск семантически похожих предложений, то качество может быть снижено. Но за счет того, что мы не делаем дважды этап создания эмбедингов, мы экономим ресурсы. + на этапе L1 будем выдавать поле confidence модели, по которому можно будет определить уверенность модели, в этом случае можно взять выше трешхолд для определения, куда дальше пойдет тикет в LLM или человеку.

**3 — Shared Encoder (одна модель — два выхода) — нужно провести эксперимент и замерить качество:**
В shared encoder мы берём одну модель — ту же DistilBERT — и вместо того чтобы выбрасывать всё, кроме классификации, используем её внутренние состояния дважды. С одной стороны, берём специальный служебный токен, который модель выучила для задач классификации, и по нему предсказываем категорию, срочность и уровень автоматизации. С другой стороны, усредняем внутренние представления всех слов тикета, проецируем их в компактное пространство и нормализуем — получаем семантический вектор, который сразу отправляется в поисковый индекс FAISS.

Для baseline решения — лучше остановиться на более простом решении — варианте 2. Дальше можно провести эксперименты, замерить качество и если оно существенно лучше baseline решения, то заменить его.

---

## Этап L0 — поиск по подстрокам

| Класс | RU-паттерны (regex) | EN-паттерны (regex) | Negative (не ловим) |
|---|---|---|---|
| 1. Проблемы с оплатой | `(не прошла\|не проходит\|ошибка) (оплата\|плат[её]ж\|оплатить)`<br>`(сняли\|списали) (деньги\|средства)`<br>`(карта\|картой) (не принимается\|отклонена\|declined)`<br>`(двойное\|повторное) списание`<br>`(верните\|возврат) (деньги\|средства\|оплату)`<br>`двойн(ая\|ое) (оплата\|списание)`<br>не могу оплатить | `(payment\|charge) (failed\|declined\|error)`<br>`(money\|funds) (deducted\|withdrawn\|charged)`<br>`(card\|credit card) (declined\|not working)`<br>`(double\|duplicate) charge`<br>`(refund\|money back)`<br>can't pay | отдел (оплаты\|billing)<br>способ (оплаты\|payment)<br>история (оплаты\|payments)<br>оплата прошла успешно<br>работа в (оплате\|billing) |
| 2. Недоступность сервиса | `(сайт\|приложение\|сервис\|платформа) (не работает\|недоступен\|лежит\|down\|упал)`<br>`(ошибка\|код) (500\|503\|502\|504)`<br>`не (открывается\|грузится) (сайт\|приложение\|страница)`<br>`(полный\|массовый) сбой (сервиса\|сайта)`<br>висит (на\|при) загрузке | `(site\|app\|service\|platform) (is down\|not working\|unavailable\|crashed)`<br>`(error\|code) (500\|503\|502\|504)`<br>`(can't access\|unable to reach)`<br>`(complete\|total) outage`<br>stuck on loading | сайт работает<br>приложение работает<br>не работает (кнопка\|фильтр\|поиск) |
| 3. Недоступность внешних интеграций | `(интеграция\|внешний сервис\|сторонний сервис\|api\|вебхук\|webhook) (не работает\|недоступен\|ошибка\|не отвечает\|не синхронизируется\|упал)`<br>`(не подключается\|ошибка соединения\|connection error) (интеграция\|api\|внешний)`<br>не приходят (данные\|запросы) из (внешнего\|стороннего) | `(integration\|external service\|third.party\|webhook\|api) (is down\|not working\|error\|failed\|not responding\|not syncing)`<br>`(connection error\|failed to connect) (integration\|api)`<br>not receiving (data\|requests) from (external\|third.party) | интеграция успешно (завершена\|настроена)<br>подключить интеграцию<br>новая интеграция<br>он сейчас в проде |

### Реализация L0 (`rule_matcher.ipynb`)

```python
import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class RuleResult:
    category: Optional[str] = None      # "billing", "outage", "integration", None
    is_mass_incident: bool = False
    confidence: float = 0.0
    matched_pattern: str = ""

class L0RuleMatcher:
    # Класс 1: Проблемы с оплатой
    BILLING_RU = re.compile(
        r"(не прошла|не проходит|ошибка)\s+(оплата|плат[ёе]ж|оплатить)|"
        r"(сняли|списали)\s+(деньги|средства)|"
        r"(карта|картой)\s+(не принимается|отклонена|declined)|"
        r"(двойное|повторное)\s+списание|"
        r"(верните|возврат)\s+(деньги|средства|оплату)|"
        r"двойн(ая|ое)\s+(оплата|списание)|"
        r"не могу\s+оплатить",
        re.IGNORECASE
    )
    
    BILLING_EN = re.compile(
        r"(payment|charge)\s+(failed|declined|error)|"
        r"(money|funds)\s+(deducted|withdrawn|charged)|"
        r"(card|credit card)\s+(declined|not working)|"
        r"(double|duplicate)\s+charge|"
        r"(refund|money back)|"
        r"can't\s+pay",
        re.IGNORECASE
    )
    
    # Класс 2: Недоступность сервиса
    OUTAGE_RU = re.compile(
        r"(сайт|приложение|сервис|платформа)\s+(не работает|недоступен|лежит|down|упал)|"
        r"(ошибка|код)\s+(500|503|502|504)|"
        r"не (открывается|грузится)\s+(сайт|приложение|страница)|"
        r"(полный|массовый)\s+сбой\s+(сервиса|сайта)|"
        r"висит\s+(на|при)\s+загрузке",
        re.IGNORECASE
    )
    
    OUTAGE_EN = re.compile(
        r"(site|app|service|platform)\s+(is down|not working|unavailable|crashed)|"
        r"(error|code)\s+(500|503|502|504)|"
        r"(can't access|unable to reach)|"
        r"(complete|total)\s+outage|"
        r"stuck\s+on\s+loading",
        re.IGNORECASE
    )
    
    # Класс 3: Недоступность внешних интеграций
    INTEGRATION_RU = re.compile(
        r"(интеграция|внешний сервис|сторонний сервис|api|вебхук|webhook)\s+"
        r"(не работает|недоступен|ошибка|не отвечает|не синхронизируется|упал)|"
        r"(не подключается|ошибка соединения|connection error)\s+"
        r"(интеграция|api|внешний)|"
        r"не приходят\s+(данные|запросы)\s+из\s+(внешнего|стороннего)",
        re.IGNORECASE
    )
    
    INTEGRATION_EN = re.compile(
        r"(integration|external service|third.party|webhook|api)\s+"
        r"(is down|not working|error|failed|not responding|not syncing)|"
        r"(connection error|failed to connect)\s+(integration|api)|"
        r"not receiving\s+(data|requests)\s+from\s+(external|third.party)",
        re.IGNORECASE
    )
    
    # Индикаторы массового сбоя (модификаторы)
    MASS_RU = re.compile(
        r"(у всех|всем|массово|весь|полностью|никто не может|все пользователи|везде|повсеместно)",
        re.IGNORECASE
    )
    MASS_EN = re.compile(
        r"(everyone|all users|widespread|completely|nobody can|all over|everywhere)",
        re.IGNORECASE
    )
    
    # Negative patterns (исключаем false positives)
    NEGATIVE_BILLING = re.compile(
        r"(отдел\s+(оплаты|billing)|способ\s+(оплаты|payment)|"
        r"история\s+(оплаты|payments)|работа\s+в\s+(оплате|billing)|"
        r"оплата\s+прошла\s+успешно)",
        re.IGNORECASE
    )
    
    NEGATIVE_OUTAGE = re.compile(
        r"(сайт\s+работает|приложение\s+работает|"
        r"не\s+работает\s+(кнопка|фильтр|поиск|функция))",
        re.IGNORECASE
    )
    
    NEGATIVE_INTEGRATION = re.compile(
        r"(интеграция\s+успешно\s+(завершена|настроена)|"
        r"подключить\s+интеграцию|новая\s+интеграция)",
        re.IGNORECASE
    )

    def match(self, text: str) -> RuleResult:
        text_lower = text.lower()
        
        # Сначала проверяем массовость (модификатор)
        is_mass = bool(self.MASS_RU.search(text_lower) or self.MASS_EN.search(text_lower))
        
        # Класс 1: Billing
        if not self.NEGATIVE_BILLING.search(text_lower):
            if self.BILLING_RU.search(text_lower) or self.BILLING_EN.search(text_lower):
                return RuleResult(
                    category="billing",
                    is_mass_incident=is_mass,
                    confidence=0.98,
                    matched_pattern="billing_strict"
                )
        
        # Класс 2: Outage
        if not self.NEGATIVE_OUTAGE.search(text_lower):
            if self.OUTAGE_RU.search(text_lower) or self.OUTAGE_EN.search(text_lower):
                return RuleResult(
                    category="outage",
                    is_mass_incident=is_mass,
                    confidence=0.98,
                    matched_pattern="outage_strict"
                )
        
        # Класс 3: Integration
        if not self.NEGATIVE_INTEGRATION.search(text_lower):
            if self.INTEGRATION_RU.search(text_lower) or self.INTEGRATION_EN.search(text_lower):
                return RuleResult(
                    category="integration",
                    is_mass_incident=is_mass,
                    confidence=0.98,
                    matched_pattern="integration_strict"
                )
        
        # ABSTAIN → идём в L1 (BERT)
        return RuleResult(
            category=None,
            is_mass_incident=is_mass,  # даже если класс не определён, массовость может быть сигналом
            confidence=0.0,
            matched_pattern="abstain"
        )


# ==================== ПРИМЕРЫ ====================

matcher = L0RuleMatcher()


test_cases = [
    ("Не прошла оплата картой, уже три раза пробовал", "billing", False),
    ("У всех не работает сайт, ошибка 500", "outage", True),
    ("Webhook не отвечает, данные не синхронизируются", "integration", False),
    ("Как подключить интеграцию с вашим API?", None, False),  # ABSTAIN: setup, не проблема
    ("Работа в отделе оплаты, есть вакансии?", None, False),  # ABSTAIN: false positive
    ("Сайт работает, но кнопка 'Купить' не работает", None, False),  # ABSTAIN: partial outage = tech
    ("Верните деньги за прошлый месяц", "billing", False),
    ("У всех пользователей упал внешний сервис интеграции", "integration", True),
    ("Can't pay with my Visa card, keeps declining", "billing", False),
    ("The app is completely down for everyone", "outage", True),
]

print("=" * 70)
print("L0 RULE MATCHER: ТЕСТЫ")
print("=" * 70)


for text, expected_cat, expected_mass in test_cases:
    result = matcher.match(text)
    status = "✅" if (result.category == expected_cat and result.is_mass_incident == expected_mass) else "❌"
    print(f"{status} Класс: {str(result.category):12s} | Масс: {str(result.is_mass_incident):5s} | {text[:50]}...")
```

---

# L1: Модель классификации тикетов на эмбеддингах

## 1. Общая концепция

L1 получает тикеты, которые **не поймал L0 Rule Matcher** (ABSTAIN).  
Задача — определить класс из 4 категорий и выдать **модельный confidence**, по которому принимается решение:

- `confidence >= 0.60` → L2 (semantic search) / L3 (LLM draft)
- `confidence < 0.60` → Operator Workbench (ручная обработка)

**Ключевое архитектурное решение (baseline):** один forward через **E5-large** → эмбеддинг используется и для L1 (CatBoost-классификация), и для L2 (FAISS-поиск). Не два энкодера — один.

---

## 2. Почему именно E5-large + CatBoost

| Компонент | Почему он | Альтернатива | Почему не она |
|-----------|-----------|--------------|---------------|
| **E5-large** | Обучена на задачах «text → embedding» с инструкциями. Лучше raw BERT для downstream-задач | DistilBERT raw | CLS-токен плохо рефлектит семантику |
| **CatBoost** | Работает с 1024-мерными векторами из коробки, быстро обучается (< 1 мин), вероятности калиброваны | Sklearn LogReg | Хуже на высокой размерности |
| | Не требует нормализации, устойчив к выбросам | PyTorch NN | Дольше обучать, нужен GPU |

---

## 3. Архитектура пайплайна L1

```
Тикет (текст)
    ↓
E5-large encode (1024 dim)          ← один forward для L1 и L2
    ↓
┌─────────────────┬─────────────────┐
│  L1: CatBoost   │  L2: FAISS      │
│  predict_proba  │  search top-k   │
│  (4 класса)     │  (похожие тикеты)│
└────────┬────────┴─────────────────┘
         ↓
    [class, confidence]
         ↓
    confidence >= 0.6?
         ↓ ДА                          ↓ НЕТ
    ┌─────────────┐              ┌─────────────┐
    │  L3: LLM    │              │  Operator   │
    │+ L2 semantic│              │  Workbench  │
    │   search    │              │             │
    └─────────────┘              └─────────────┘
```

---

## 4. Таблица выходных полей L1

| Поле | Описание | Пример |
|------|----------|--------|
| `class` | 1 из 4 категорий | `billing` |
| `confidence` | Вероятность топ-класса (0–1) | `0.87` |
| `all_probs` | Вероятности всех 4 классов | `[0.05, 0.87, 0.06, 0.02]` |
| `is_ambiguous` | True, если max_prob < threshold | `False` |
| `similar_tickets` | Топ-k похожих тикетов из FAISS | `[{text, label, score}]` |
| `embedding` | Вектор тикета (1024 dim) | `np.array([...])` |

---

## 5. Сбор датасета для L1

### 5.1. Источники данных

| Источник | Что собираем | Как получить | Качество |
|----------|-------------|--------------|----------|
| **Operator labels** | `category`, `resolution_action` | Оператор выбирает категорию при закрытии тикета | Высокое (ground truth) |
| **L0 Rule labels** | Категория от Rule Matcher | Автоматическая разметка L0 на исторических тикетах | Высокое (только уверенные случаи) |
| **LLM-as-a-Judge** | Псевдо-лейблы на неразмеченных тикетах | Few-shot промпт GPT-4o-mini на 100 примерах → разметка 10k | Среднее (требует валидации) |
| **Active Learning** | Тикеты с высокой uncertainty | Модель просит разметить 200 тикетов/день с entropy > 0.8 | Высокое (целевые сэмплы) |

### 5.2. Пайплайн сбора (ежедневный)

```
02:00 UTC
    ↓
Extract: новые resolved тикеты за сутки из PostgreSQL
    ↓
Clean: PII redaction (Presidio), deduplication
    ↓
Label: merge operator_actions → automation labels
    ↓
Augment: добавляем L0-rule labels (где confidence > 0.95)
    ↓
Filter: убираем спам, тестовые тикеты, дубликаты
    ↓
Split: time-based (train: T-6m..T-1w, val: T-1w..T-now)
    ↓
Encode: E5-large → 1024-dim embeddings
    ↓
Train: CatBoost на embeddings
    ↓
Evaluate: F1-macro, per-class F1, calibration
    ↓
If F1-macro > prev + 2%: deploy to shadow mode
```

### 5.3. Требования к разметке

- **Минимум для старта:** 500 размеченных тикетов (по ~125 на класс).
- **Комфортный старт:** 2000 тикетов (по ~500 на класс).
- **Продакшен:** 10 000+ тикетов с еженедельным пополнением.

---

## 6. Холодный старт (нет размеченных данных)

### 6.1. Сценарий: Day 0, датасета нет

| Этап | Что делаем | Результат |
|------|-----------|-----------|
| **L0 работает всегда** | Regex на подстроки ловит 40–60% типовых тикетов | Мгновенная автоматизация без ML |
| **LLM Zero-Shot** | GPT-4o-mini с few-shot промптом классифицирует остальное | ~80% accuracy, но дорого ($0.003/тикет) |
| **Сбор лейблов** | Операторы размечают категорию при закрытии (2 клика в UI) | +200–500 тикетов/день |
| **Weak Supervision** | Snorkel: 10–15 regex + LLM-as-a-judge → псевдо-лейблы | +2000 тикетов за неделю |
| **Self-Training** | Обучаем CatBoost на псевдо-лейблах → предсказываем на неразмеченных → берём confident > 0.95 | +3000 тикетов |

### 6.2. Граница применимости при холодном старте
**ML-модель (L1) включается только после накопления 500+ размеченных тикетов.** До этого момента система работает на правилах + LLM.

### 6.3. Почему это приемлемо

- **Правила (L0)** закрывают все типовые сценарии: «не прошла оплата», «сайт не работает», «возврат».
- **LLM (L3)** покрывает сложные/неоднозначные случаи без риска: всё равно идёт через HITL.
- **Операторы** не замечают разницы: их UI не меняется, просто начинают собираться лейблы.
- **Через 2 недели** у вас 2000+ тикетов — можно обучить первую версию CatBoost и начать экономить на LLM.

---

## 7. Работа при готовых данных (есть разметка)

### 7.1. Ежедневный цикл

```
T-1 день (resolved тикеты)
    ↓
Извлекаем текст + operator_label
    ↓
E5-large encode
    ↓
Добавляем в обучающий пул
    ↓
Переобучаем CatBoost (1 эпоха, lr=2e-5, 30 сек)
    ↓
Валидируем на rolling window (T-7d..T-1d)
    ↓
Если F1-macro > текущей модели + 1%
    → Shadow mode (10% трафика)
    → Через 24ч без деградации → promote
```

### 7.2. Инференс в реальном времени

---

## 8. Метрики L1

| Метрика | Как считать | Порог | Зачем |
|---------|-------------|-------|-------|
| **F1-macro** | По 4 классам на time-based val | > 0.80 | Общее качество классификации |
| **F1 per class (outage)** | Редкий, но важный класс | > 0.85 | Не пропустить сбой |
| **Calibration (ECE)** | `|confidence - accuracy|` | < 0.05 | Confidence можно доверять для routing |
| **Coverage @ threshold 0.6** | Доля тикетов с conf ≥ 0.6 | > 70% | Достаточно данных для автоматизации |
| **False Auto Rate** | `other`, отправленный в LLM | < 5% | Не автоматизировать мусор |
| **Latency p99** | Время encode + predict | < 100 мс | Укладываемся в SLA 500 мс (вместе с L0) |

---

## 9. Roadmap: от baseline к продакшену

| Этап | Что меняем | Когда | Результат |
|------|-----------|-------|-----------|
| **Baseline** | E5-large + CatBoost CPU | Сейчас (4ч) | Работает, F1 ~0.75 на 500 сэмплах |
| **V1** | E5-large → E5-small (384 dim) | 1 неделя | В 2× быстрее, F1 ~0.72 |
| **V2** | CatBoost → Fine-tuned E5 head | 2 недели | End-to-end, F1 ~0.85, проще деплой |
| **V3** | Shared Encoder (DistilBERT + projection + triplet) | 1 месяц | Один forward, F1 ~0.88, но сложнее обучать |


---

## 10. Мониторинг через Grafana

### 10.1. Что мониторим

| Панель | Метрика | Источник | Алерт |
|--------|---------|----------|-------|
| **Throughput** | Тикетов/сек по уровням (L0/L1/L2/L3/Operator) | FastAPI Prometheus metrics | Падение throughput > 30% за 5 мин |
| **Latency p50/p95/p99** | Время обработки по этапам | Prometheus histogram | p99 > 500 мс |
| **Model Confidence** | Распределение confidence L1 | CatBoost predict_proba логи | Доля < 0.60 > 40% (деградация модели) |
| **F1-macro (rolling)** | F1 на последних 1000 тикетов | Label Studio / операторская разметка | Падение > 5% относительно недельного baseline |
| **Mass Incident** | Кол-во тикетов по классам за окно T | Redis counters | > Q (50) за 10 мин → P1 alert |
| **LLM Cost** | $/день, $/тикет | OpenAI API billing | > $500/день |
| **Cache Hit Rate** | FAISS / Template hit | Redis metrics | < 30% (индекс устарел) |
| **Data Drift** | KL-divergence эмбеддингов текущих vs обучающих | E5 encode + статистика | KL > 0.1 |

### 10.2. Архитектура сбора метрик

```
FastAPI App
    ↓
Prometheus Client (prometheus-fastapi-instrumentator)
    ↓
Prometheus Server (scraping каждые 15s)
    ↓
Grafana (dashboards + alerts)
    ↓
Alertmanager 
```


### 11.1 Grafana Dashboards

#### Dashboard 1: System Overview (Real-time)

| Row | Панели |
|-----|--------|
| **RPS & Latency** | `rate(tickets_processed_total[1m])` by level; `l1_latency_seconds` p50/p95/p99 |
| **Routing Decision** | Pie chart: L0 auto / L1 LLM / L1 operator / L3 / Fallback |
| **Confidence Heatmap** | Heatmap `l1_confidence_distribution` за последний час |
| **Queue Depth** | Kafka consumer lag по топикам (llm_drafts, operator_queue) |

#### Dashboard 2: Model Quality (Batch, обновляется раз в день)

| Row | Панели |
|-----|--------|
| **F1-macro Trend** | Rolling F1 на последних 1000/5000/10000 тикетов |
| **Per-Class F1** | F1 billing / outage / integration / other |
| **Calibration Plot** | ECE (Expected Calibration Error) за день |
| **Confusion Matrix** | Таблица predicted vs actual (из Label Studio) |

#### Dashboard 3: Business & Cost

| Row | Панели |
|-----|--------|
| **Automation Rate** | % auto_sent / draft / operator |
| **LLM Cost** | `llm_cost_usd_daily` + прогноз до конца месяца |
| **Operator Load** | Тикетов/час на оператора, среднее время HITL |
| **CSAT Correlation** | CSAT vs decision type (auto / draft / operator) |

### 11.2. Логи и трейсинг

| Система | Что логируем | Зачем |
|---------|-------------|-------|
| **Loki** | `ticket_id`, `text` (redacted), `l0_result`, `l1_probs`, `decision`, `latency_ms` | Отладка конкретного тикета |
| **Jaeger** | Спаны: `normalize → pii → l0 → encode → predict → faiss → decision` | Где тормозит hot path |
| **MLflow / W&B** | Model version, F1, dataset hash, hyperparameters | Версионирование моделей |


## 12. Итоговая архитектура мониторинга

```
┌─────────────────────────────────────────────────────────────┐
│                         Grafana                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  System     │  │  Model      │  │  Business   │         │
│  │  Overview   │  │  Quality    │  │  & Cost     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              ↑
                    Prometheus Server
                              ↑
    ┌─────────┬─────────┬─────────┬─────────┐
    │ FastAPI │  Redis  │  Kafka  │  LLM    │
    │ metrics │  stats  │  lag    │  cost   │
    └─────────┴─────────┴─────────┴─────────┘
                              ↑
                        Loki / Jaeger
                              ↑
                         FastAPI App
```
