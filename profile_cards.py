"""Генерирует цветные SVG-карточки статистики для профиля GitHub.

Запускается из GitHub Actions (.github/workflows/profile.yml).
Берёт данные через GitHub GraphQL API и кладёт карточки в папку dist/:
  stats-dark.svg / stats-light.svg     — общая статистика
  streak-dark.svg / streak-light.svg   — серия дней с коммитами
  langs-dark.svg / langs-light.svg     — языки по репозиториям
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from html import escape

USER = os.environ.get("GH_USER", "Hametova00")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = os.environ.get("OUT_DIR", "dist")

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

# Яркая палитра — одинаково хорошо видна на тёмной и светлой теме
ACCENTS = ["#fe428e", "#f8d847", "#ff8c42", "#c86dd7", "#ff6b6b", "#ffffff"]
# Цвета для языков — без синего и зелёного

# Палитра в стиле темы «radical»: тёмно-фиолетовый фон, розовый, жёлтый, бирюзовый
RADICAL = {"bg": "#141321", "border": "#141321", "title": "#fe428e", "icon": "#f8d847",
           "text": "#ffffff", "muted": "#c8c3d4", "ring": "#fe428e", "track": "#2a2740"}
THEMES = {"dark": RADICAL, "light": RADICAL}

FONT = "font-family=\"'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif\""


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def streaks(days):
    days = sorted(days, key=lambda d: d["date"])
    longest = cur = 0
    best_range = cur_start = None
    for d in days:
        if d["contributionCount"] > 0:
            if cur == 0:
                cur_start = d["date"]
            cur += 1
            if cur > longest:
                longest, best_range = cur, (cur_start, d["date"])
        else:
            cur = 0
    # текущая серия: сегодняшний день без коммитов серию не обрывает
    current = 0
    today = date.today().isoformat()
    for d in reversed(days):
        if d["contributionCount"] > 0:
            current += 1
        elif d["date"] == today and current == 0:
            continue
        else:
            break
    return current, longest, best_range


def defs():
    stops = "".join(
        f'<stop offset="{i / (len(ACCENTS) - 2):.2f}" stop-color="{c}"/>' for i, c in enumerate(ACCENTS[:3])
    )
    return f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0">{stops}</linearGradient></defs>'


def frame(w, h, t, body, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" {FONT}>'
        f"{defs()}"
        f'<clipPath id="card"><rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12"/></clipPath>'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>'
        f'<text x="25" y="38" font-size="18" font-weight="600" fill="{t["title"]}">{escape(title)}</text>'
        f"{body}</svg>"
    )


def icon(kind, x, y, c):
    """Простые иконки 16x16 в стиле карточек статистики."""
    g = f'<g transform="translate({x},{y})" fill="none" stroke="{c}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
    shapes = {
        "star": '<path d="M8 1.5l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.3l-3.8 2 .7-4.3-3.1-3 4.3-.6z"/>',
        "clock": '<circle cx="8" cy="8" r="6.2"/><path d="M8 4.5V8l2.4 1.6"/>',
        "pr": '<circle cx="4" cy="3.5" r="1.7"/><circle cx="4" cy="12.5" r="1.7"/><circle cx="12" cy="12.5" r="1.7"/>'
              '<path d="M4 5.2v5.6M12 10.8V6.5a2 2 0 0 0-2-2H7.5"/><path d="M9 3l-1.5 1.5L9 6"/>',
        "issue": '<circle cx="8" cy="8" r="6.2"/><circle cx="8" cy="8" r="1" fill="' + c + '"/>',
        "repo": '<path d="M3 2.5h8.5a1 1 0 0 1 1 1v9.5H4.5A1.5 1.5 0 0 1 3 11.5z"/><path d="M3 11.5A1.5 1.5 0 0 1 4.5 10h8"/>',
    }
    return g + shapes[kind] + "</g>"


def stats_card(u, t):
    cc = u["contributionsCollection"]
    stars = sum(r["stargazerCount"] for r in u["repositories"]["nodes"])
    rows = [
        ("star", "Звёзды", stars),
        ("clock", "Коммиты за год", cc["totalCommitContributions"]),
        ("pr", "Pull requests", cc["totalPullRequestContributions"]),
        ("issue", "Issues", cc["totalIssueContributions"]),
        ("repo", "Репозитории", u["repositories"]["totalCount"]),
    ]
    body = ""
    for i, (ic, label, val) in enumerate(rows):
        y = 70 + i * 25
        body += (
            f'<g>'
            f'{icon(ic, 24, y - 13, t["icon"])}'
            f'<text x="48" y="{y}" font-size="14" font-weight="600" fill="{t["text"]}">{label}:</text>'
            f'<text x="250" y="{y}" font-size="14" font-weight="700" fill="{t["text"]}">{val}</text></g>'
        )
    total = cc["contributionCalendar"]["totalContributions"]
    r, cx, cy = 48, 400, 110
    circ = 2 * 3.14159 * r
    body += (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t["track"]}" stroke-width="9"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t["ring"]}" stroke-width="9" stroke-linecap="round"'
        f' stroke-dasharray="{circ:.1f}" stroke-dashoffset="0" transform="rotate(-90 {cx} {cy})">'
        f'<animate attributeName="stroke-dashoffset" from="{circ:.1f}" to="0" dur="1.2s"/></circle>'
        f'<text x="{cx}" y="{cy + 2}" text-anchor="middle" font-size="24" font-weight="800" fill="{t["text"]}">{total}</text>'
        f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" font-size="11" fill="{t["muted"]}">вклад за год</text>'
    )
    return frame(495, 200, t, body, f"Статистика {USER} на GitHub")


def fmt(d):
    months = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
    y, m, dd = map(int, d.split("-"))
    return f"{dd} {months[m - 1]}"


def streak_card(u, t):
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    current, longest, rng = streaks(days)
    rng_txt = f"{fmt(rng[0])} — {fmt(rng[1])}" if rng else "пока нет"
    cols = [
        (110, str(cal["totalContributions"]), "Всего вклада", "за последний год", t["text"]),
        (300, str(current), "Текущая серия", "дней подряд", t["ring"]),
        (490, str(longest), "Лучшая серия", rng_txt, t["icon"]),
    ]
    body = ""
    for i, (x, num, label, sub, col) in enumerate(cols):
        body += (
            f'<g>'
            f'<circle cx="{x}" cy="95" r="34" fill="none" stroke="{col}" stroke-width="5"/>'
            f'<text x="{x}" y="104" text-anchor="middle" font-size="26" font-weight="800" fill="{t["text"]}">{num}</text>'
            f'<text x="{x}" y="152" text-anchor="middle" font-size="14" font-weight="600" fill="{col}">{label}</text>'
            f'<text x="{x}" y="172" text-anchor="middle" font-size="11" fill="{t["muted"]}">{escape(sub)}</text></g>'
        )
        if i < 2:
            body += f'<line x1="{x + 95}" y1="65" x2="{x + 95}" y2="175" stroke="{t["track"]}"/>'
    return frame(600, 195, t, body, "Серия коммитов")


def langs_card(u, t):
    sizes, colors = {}, {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            sizes[n] = sizes.get(n, 0) + e["size"]
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:6]
    colors = {name: ACCENTS[i] for i, (name, _) in enumerate(top)}
    total = sum(v for _, v in top) or 1
    body = ""
    x = 25.0
    bar_w = 445
    body += f'<clipPath id="bar"><rect x="25" y="58" width="{bar_w}" height="10" rx="5"/></clipPath><g clip-path="url(#bar)">'
    for name, v in top:
        w = bar_w * v / total
        body += f'<rect x="{x:.1f}" y="58" width="{w + 0.5:.1f}" height="10" fill="{colors[name]}"/>'
        x += w
    body += "</g>"
    for i, (name, v) in enumerate(top):
        cx = 30 + (i % 2) * 225
        cy = 98 + (i // 2) * 28
        body += (
            f'<g>'
            f'<circle cx="{cx}" cy="{cy - 4}" r="6" fill="{colors[name]}"/>'
            f'<text x="{cx + 14}" y="{cy}" font-size="13" fill="{t["text"]}">{escape(name)}'
            f'<tspan fill="{t["muted"]}"> {100 * v / total:.1f}%</tspan></text></g>'
        )
    if not top:
        body += f'<text x="25" y="100" font-size="13" fill="{t["muted"]}">Пока нет данных</text>'
    return frame(495, 190, t, body, "Самые используемые языки")


def main():
    os.makedirs(OUT, exist_ok=True)
    if os.environ.get("DEMO_JSON"):
        u = json.load(open(os.environ["DEMO_JSON"]))
    else:
        u = fetch()
    for name, t in THEMES.items():
        for card, fn in (("stats", stats_card), ("streak", streak_card), ("langs", langs_card)):
            with open(os.path.join(OUT, f"{card}-{name}.svg"), "w", encoding="utf-8") as f:
                f.write(fn(u, t))
    print("cards written to", OUT)


if __name__ == "__main__":
    main()
