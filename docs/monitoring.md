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
