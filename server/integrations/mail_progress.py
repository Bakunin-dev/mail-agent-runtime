"""Safe, presentation-only progress cards for the OpenWebUI Mail Agent."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Literal


ProgressStepState = Literal["pending", "active", "done"]


@dataclass(frozen=True, slots=True)
class MailProgressStep:
    label: str
    state: ProgressStepState = "pending"


@dataclass(frozen=True, slots=True)
class MailProgress:
    phase: str
    progress: int

    scanned: int | None = None
    matched: int | None = None
    read: int | None = None

    detail: str | None = None
    steps: tuple[MailProgressStep, ...] = ()
    done: bool = False
    failed: bool = False


def _progress_value(value: int) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = 0
    return max(0, min(100, normalized))


def _metric_value(value: int | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "—"
    if isinstance(value, int):
        return str(max(0, value))
    return escape(str(value))


def _step_markup(step: MailProgressStep) -> str:
    state = step.state if step.state in {"pending", "active", "done"} else "pending"
    icon = {"pending": "○", "active": "●", "done": "✓"}[state]
    return (
        f'<div class="step {state}">'
        f'<span class="step-icon" aria-hidden="true">{icon}</span>'
        f'<span class="step-label">{escape(str(step.label))}</span>'
        "</div>"
    )


def render_mail_progress(state: MailProgress) -> str:
    """Render a self-contained card without exposing mail content."""

    progress = _progress_value(state.progress)
    if state.failed:
        status = "ОШИБКА"
        status_class = "failed"
    elif state.done:
        status = "ГОТОВО"
        status_class = "done"
    else:
        status = "РАБОТАЕТ"
        status_class = "working"

    steps = "\n".join(_step_markup(step) for step in state.steps)
    steps_markup = f'<div class="steps">{steps}</div>' if steps else ""

    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* {{ box-sizing: border-box; }}

:root {{
  color-scheme: dark;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}

body {{
  margin: 0;
  padding: 8px;
  background: transparent;
  color: #f4f4f5;
}}

.card {{
  width: 100%;
  max-width: 720px;
  overflow: hidden;
  padding: 22px;
  border: 1px solid rgba(250, 204, 21, .20);
  border-radius: 22px;
  background:
    radial-gradient(circle at 92% 0%, rgba(250, 204, 21, .15), transparent 33%),
    linear-gradient(145deg, #18181b 0%, #0b0b0c 100%);
  box-shadow: 0 18px 55px rgba(0, 0, 0, .35);
}}

.header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}}

.brand {{
  color: #fafafa;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: .14em;
}}

.brand-mark {{
  margin-right: 7px;
  color: #facc15;
  text-shadow: 0 0 18px rgba(250, 204, 21, .45);
}}

.badge {{
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 10px;
  border: 1px solid rgba(250, 204, 21, .20);
  border-radius: 999px;
  color: #fde047;
  background: rgba(250, 204, 21, .08);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .10em;
}}

.badge::before {{
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 12px currentColor;
  content: "";
}}

.badge.working::before {{ animation: pulse 1.45s ease-in-out infinite; }}
.badge.done {{ color: #86efac; border-color: rgba(134, 239, 172, .22); background: rgba(34, 197, 94, .08); }}
.badge.failed {{ color: #fca5a5; border-color: rgba(248, 113, 113, .25); background: rgba(239, 68, 68, .10); }}

.phase {{
  margin-top: 23px;
  color: #fafafa;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -.025em;
}}

.detail {{
  min-height: 20px;
  margin-top: 7px;
  color: #a1a1aa;
  font-size: 13px;
  line-height: 1.45;
}}

.progress-row {{
  display: flex;
  align-items: center;
  gap: 13px;
  margin-top: 20px;
}}

.track {{
  flex: 1;
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #27272a;
}}

.bar {{
  height: 100%;
  width: {progress}%;
  border-radius: inherit;
  background: linear-gradient(90deg, #ca8a04, #fde047);
  box-shadow: 0 0 18px rgba(250, 204, 21, .35);
  transition: width .35s ease;
}}

.percent {{
  min-width: 43px;
  color: #fde047;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}}

.steps {{
  display: grid;
  gap: 9px;
  margin-top: 21px;
  padding: 14px 15px;
  border: 1px solid rgba(255, 255, 255, .055);
  border-radius: 15px;
  background: rgba(255, 255, 255, .028);
}}

.step {{
  display: flex;
  align-items: center;
  gap: 10px;
  color: #71717a;
  font-size: 12px;
  line-height: 1.35;
}}

.step.done {{ color: #d4d4d8; }}
.step.active {{ color: #fef08a; }}

.step-icon {{
  display: inline-grid;
  width: 17px;
  height: 17px;
  place-items: center;
  color: #52525b;
  font-size: 13px;
  font-weight: 800;
}}

.step.done .step-icon {{ color: #facc15; }}
.step.active .step-icon {{ color: #fde047; text-shadow: 0 0 12px rgba(250, 204, 21, .55); }}

.metrics {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
}}

.metric {{
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid rgba(255, 255, 255, .055);
  border-radius: 14px;
  background: rgba(255, 255, 255, .035);
}}

.value {{
  overflow: hidden;
  color: #fafafa;
  font-size: 20px;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}}

.label {{
  margin-top: 4px;
  color: #71717a;
  font-size: 10px;
  letter-spacing: .08em;
  text-transform: uppercase;
}}

@keyframes pulse {{
  0%, 100% {{ opacity: .45; transform: scale(.86); }}
  50% {{ opacity: 1; transform: scale(1); }}
}}

@media (max-width: 480px) {{
  .card {{ padding: 18px; }}
  .phase {{ font-size: 19px; }}
  .metrics {{ gap: 7px; }}
  .metric {{ padding: 10px; }}
  .value {{ font-size: 17px; }}
}}
</style>
</head>
<body>
<section class="card" aria-label="Mail Agent progress">
  <div class="header">
    <div class="brand"><span class="brand-mark">◆</span>MAIL AGENT</div>
    <div class="badge {status_class}">{escape(status)}</div>
  </div>

  <div class="phase">{escape(str(state.phase))}</div>
  <div class="detail">{escape(str(state.detail or ""))}</div>

  <div class="progress-row" aria-label="Progress {progress} percent">
    <div class="track"><div class="bar"></div></div>
    <div class="percent">{progress}%</div>
  </div>

  {steps_markup}

  <div class="metrics">
    <div class="metric">
      <div class="value">{_metric_value(state.scanned)}</div>
      <div class="label">проверено</div>
    </div>
    <div class="metric">
      <div class="value">{_metric_value(state.matched)}</div>
      <div class="label">найдено</div>
    </div>
    <div class="metric">
      <div class="value">{_metric_value(state.read)}</div>
      <div class="label">прочитано</div>
    </div>
  </div>
</section>
</body>
</html>
"""
