# M8-C Design — Weekly Report + Deploy M8

## Overview

Add a weekly performance report (Sunday 20:00 CEST) and `/weekly` command, then deploy M8-A + M8-C to VPS.

## Module — Weekly Report

File: `src/polybot/components/weekly_report.py`

Separate from `report.py` (daily). The weekly report has a distinct structure: week number, cumulative stats, orchestrateur section, coûts section.

### API

```python
def generate_weekly_report(db_path: str, weeks: int = 1) -> str:
    """Generate a weekly performance report. Returns formatted HTML string."""
```

### Sections (in order)

#### 1. Header

```
📊 Weekly Report — Sem {week_number} ({date_start}-{date_end})
```

Week number from `datetime.isocalendar()`. Date range: `{start_day}-{end_day} {month} {year}`.

#### 2. Alertes émises (window = N weeks)

```sql
SELECT
    component,
    COUNT(*) as cnt,
    AVG(score) FILTER (WHERE component = 'C2') as avg_c2_score
FROM alerts
WHERE emitted_at >= CURRENT_DATE - INTERVAL '{7 * weeks} DAY'
GROUP BY component
```

For C1, also show side breakdown:
```sql
SELECT side, COUNT(*) FROM alerts
WHERE component = 'C1'
  AND emitted_at >= CURRENT_DATE - INTERVAL '{7 * weeks} DAY'
GROUP BY side
```

#### 3. Performance shadow (window = N weeks)

```sql
SELECT
    COUNT(*) FILTER (WHERE ao.resolution_outcome NOT IN ('PENDING')) as resolved,
    COUNT(*) FILTER (WHERE ao.was_direction_correct = TRUE) as correct,
    SUM(ao.shadow_pnl_simulated) FILTER (WHERE ao.resolution_outcome NOT IN ('PENDING')) as pnl
FROM alerts a
JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
WHERE a.emitted_at >= CURRENT_DATE - INTERVAL '{7 * weeks} DAY'
```

#### 4. Performance cumulée (all time)

Same query without date filter. Show warning if sample < 30.

#### 5. Wallets Tier A

```sql
-- Active wallets with trades this week
SELECT COUNT(DISTINCT t.proxy_wallet)
FROM trades t
JOIN tracked_wallets tw ON t.proxy_wallet = tw.address
WHERE tw.tier = 'A' AND tw.active = TRUE
  AND t.timestamp_ts >= CURRENT_DATE - INTERVAL '{7 * weeks} DAY'

-- Total tier A
SELECT COUNT(*) FROM tracked_wallets WHERE tier = 'A' AND active = TRUE

-- Silent wallets (names)
SELECT tw.address, tw.notes
FROM tracked_wallets tw
WHERE tw.tier = 'A' AND tw.active = TRUE
AND NOT EXISTS (
    SELECT 1 FROM trades t
    WHERE t.proxy_wallet = tw.address
    AND t.timestamp_ts >= CURRENT_DATE - INTERVAL '{7 * weeks} DAY'
)

-- Total trades this week
SELECT COUNT(*) FROM trades
WHERE timestamp_ts >= CURRENT_DATE - INTERVAL '{7 * weeks} DAY'
```

#### 6. Alignment C2 (window)

```sql
SELECT alignment_score, COUNT(*)
FROM alerts
WHERE component = 'C2'
  AND alignment_score IS NOT NULL
  AND emitted_at >= CURRENT_DATE - INTERVAL '{7 * weeks} DAY'
GROUP BY alignment_score
```

#### 7. Orchestrateur (window)

```sql
-- Kill switches activated
SELECT COUNT(*) FROM audit_log
WHERE event_type = 'kill_switch' AND action = 'on'
  AND created_at >= CURRENT_DATE - INTERVAL '{7 * weeks} DAY'

-- Rate limits hit
SELECT COUNT(*) FROM audit_log
WHERE event_type = 'rate_limit' AND action = 'exceeded'
  AND created_at >= CURRENT_DATE - INTERVAL '{7 * weeks} DAY'

-- Circuit breakers
SELECT COUNT(*) FROM audit_log
WHERE event_type = 'circuit_breaker'
  AND created_at >= CURRENT_DATE - INTERVAL '{7 * weeks} DAY'

-- Indexer errors
SELECT COUNT(*) FROM indexer_state WHERE last_run_status = 'failed'
```

#### 8. Coûts (window)

```sql
-- LLM calls this week
SELECT COUNT(*) FROM resolution_risk_cache
WHERE computed_at >= CURRENT_DATE - INTERVAL '{7 * weeks} DAY'
```

Estimated cost: `count * $0.001`. Alchemy CU and VPS are hardcoded strings.

### Output Format

```
📊 Weekly Report — Sem 17 (21-27 avril 2026)

🎯 Alertes émises
  C1 : {c1_cnt} alertes ({side_breakdown})
  C2 : {c2_cnt} alertes (score moyen {avg_score:.1f}/7)
  Total : {total}

⚖️ Performance shadow ({weeks * 7} jours)
  Résolues : {resolved}
  Direction correcte : {correct}/{resolved} ({pct}%)
  Shadow P&L : {sign}${pnl}

📈 Performance cumulée
  Total alertes : {cumul_total}
  Résolues : {cumul_resolved}
  Direction correcte : {cumul_correct}/{cumul_resolved} ({cumul_pct}%)
  Shadow P&L cumulé : {sign}${cumul_pnl}
  {warning if < 30}

👛 Wallets Tier A
  Actifs : {active}/{total_a}
  Silencieux > {weeks}sem : {silent_count} ({names})
  Trades : {trades_total}

🧭 Alignment C2
  📈 Suit mouvement : {suivre}
  📉 Contrariant : {contrariant}
  ➡️ Neutre : {neutre}

⚙️ Orchestrateur
  Kill switches activés : {ks_count}
  Rate limits atteints : {rl_count}
  Circuit breakers : {cb_count}
  Erreurs indexers : {idx_errors}

💰 Coûts
  LLM Haiku : ~${llm_cost:.2f} ({llm_calls} calls)
  Alchemy : usage estimé
  VPS : $4/mois
```

If 0 alerts in the window: short message "Aucune alerte cette semaine."

## Daemon Integration

### Scheduler

```python
async def schedule_weekly_report(bot: PolyBot, db_path: str) -> None:
    """Send weekly report every Sunday at 20:00 CEST."""
    while True:
        now = datetime.now(CEST)
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0 and now.hour >= 20:
            days_until_sunday = 7
        target = datetime.combine(
            now.date() + timedelta(days=days_until_sunday),
            time(20, 0), CEST
        )
        wait = (target - now).total_seconds()
        logger.info("weekly_report_scheduled", next_at=target.isoformat(), wait_s=int(wait))
        await asyncio.sleep(wait)
        try:
            report = generate_weekly_report(db_path)
            await bot.send_alert("ops", report)
            logger.info("weekly_report_sent")
        except Exception:
            logger.exception("weekly_report_failed")
```

Added to `asyncio.gather()` alongside existing coroutines.

## Bot Command

### `/weekly [N]`

```
/weekly     → report last 1 week
/weekly 2   → report last 2 weeks
```

Max N = 4. Added to `_register_handlers` and `set_my_commands`.

## Deploy M8 (A + C)

1. Commit + push
2. `ssh polybot "cd /root/polybot && git pull origin main && uv sync"`
3. Migration: `ssh polybot "cd /root/polybot && uv run python scripts/init_db.py"`
4. Restart: `ssh polybot "systemctl restart polybot-bot.service"`
5. Verify logs, test commands, check tables

## Tests (4)

1. **Weekly report format**: mock DB with C1+C2 alerts + outcomes → verify all 8 sections present
2. **Weekly report empty**: 0 alerts → "Aucune alerte cette semaine"
3. **`/weekly` command**: mock Telegram → response contains report
4. **Coûts LLM section**: 50 cache entries → "$0.05" in output

## What NOT to do

- Do not modify `report.py` (daily report stays unchanged)
- Do not implement Streamlit dashboard (M8-B)
- Do not modify C1/C2/C3 internal logic
