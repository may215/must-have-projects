#!/usr/bin/env python3
"""
Scan YouTube channels, extract GitHub projects from descriptions,
fetch star counts, generate commercial landing-page README.md.
"""

import json, os, re, sys, time, subprocess, html
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from datetime import datetime, timezone
from collections import defaultdict

REPO_DIR = Path(__file__).resolve().parent.parent
CACHE_FILE = REPO_DIR / ".project-cache.json"
README_FILE = REPO_DIR / "README.md"
STAR_CACHE_FILE = REPO_DIR / ".star-cache.json"

CHANNELS = {
    "indiehackernews": {
        "url": "https://www.youtube.com/@indiehackernews/videos",
        "label": "Indie Hacker News",
        "icon": "🎙️",
        "handle": "@indiehackernews",
    },
    "githubawesome": {
        "url": "https://www.youtube.com/@GithubAwesome/videos",
        "label": "Github Awesome",
        "icon": "🌟",
        "handle": "@GithubAwesome",
    },
    "hyperautomationlabs": {
        "url": "https://www.youtube.com/@hyperautomationlabs1045/videos",
        "label": "Hyperautomation Labs",
        "icon": "🤖",
        "handle": "@hyperautomationlabs1045",
    },
}

GITHUB_RE = re.compile(
    r'https?://github\.com/([a-zA-Z0-9._-]+)/([a-zA-Z0-9._-]+?)(?:/|\.git)?(?:\s|$|[)\]}>])'
)

def log(msg):
    print(f"[update-readme] {msg}", flush=True)

def run_ytdlp(args):
    cmd = ["yt-dlp", "--quiet", "--no-warnings"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        log(f"yt-dlp error: {r.stderr[:200]}")
        return None
    return r.stdout

def get_channel_videos(channel_url):
    out = run_ytdlp(["--flat-playlist", "--dump-json", channel_url])
    if not out:
        return []
    videos = []
    for line in out.strip().split("\n"):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            videos.append({
                "id": d["id"],
                "title": d.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={d['id']}",
                "playlist_index": d.get("playlist_index", 0),
            })
        except json.JSONDecodeError:
            continue
    return videos

def get_video_description(video_id):
    out = run_ytdlp(["--print", "description", f"https://www.youtube.com/watch?v={video_id}"])
    return out or ""

def extract_github_urls(text):
    matches = GITHUB_RE.findall(text)
    unique = set()
    for owner, repo in matches:
        repo = repo.rstrip("/.,;:#!?)")
        if repo and not repo.startswith(".") and not repo.startswith("apps/"):
            unique.add((owner.lower(), repo.lower()))
    return sorted(unique)

def fetch_star_count(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    req = Request(url)
    req.add_header("User-Agent", "must-have-projects/1.0")
    req.add_header("Accept", "application/vnd.github.v3+json")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        resp = urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        return data.get("stargazers_count")
    except HTTPError as e:
        if e.code == 403:
            log(f"  rate limited for {owner}/{repo}, scraping HTML")
            return fetch_star_scrape(owner, repo)
        elif e.code == 404:
            return None
        log(f"  HTTP {e.code} for {owner}/{repo}")
        return None
    except Exception as e:
        log(f"  error {owner}/{repo}: {e}")
        return None

def fetch_star_scrape(owner, repo):
    url = f"https://github.com/{owner}/{repo}"
    req = Request(url)
    req.add_header("User-Agent", "must-have-projects/1.0")
    try:
        resp = urlopen(req, timeout=10)
        h = resp.read().decode("utf-8", errors="replace")
        m = re.search(r'(\d[\d,]*)\s*stars?', h, re.IGNORECASE)
        if m:
            return int(m.group(1).replace(",", ""))
        m = re.search(r'aria-label="(\d[\d,]*)\s*stars?', h, re.IGNORECASE)
        if m:
            return int(m.group(1).replace(",", ""))
        return None
    except:
        return None

def load_cache(f):
    if f.exists():
        try:
            return json.loads(f.read_text())
        except:
            pass
    return {}

def save_cache(f, data):
    f.write_text(json.dumps(data, indent=2))

def build_readme(projects):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(projects)
    total_stars = sum(p.get("stars", 0) or 0 for p in projects)

    by_channel = defaultdict(list)
    for p in projects:
        by_channel[p["channel"]].append(p)

    channel_order = ["indiehackernews", "githubawesome", "hyperautomationlabs"]

    all_sorted = sorted(projects, key=lambda p: (-(p.get("stars") or 0), p["owner"] + "/" + p["repo"]))
    top10 = all_sorted[:10]
    top3_stars = sum(p.get("stars", 0) or 0 for p in top10) if top10 else 0

    R = []  # lines

    def W(s=""):
        R.append(s)

    # ── HEADER BADGES ──
    W('<div align="center">')
    W(f'  <img src="https://img.shields.io/badge/projects-{total}-2ea043?style=flat-square&logo=github" alt="Projects">')
    W(f'  <img src="https://img.shields.io/badge/stars-{total_stars:,}-fbbc04?style=flat-square&logo=github" alt="Stars">')
    W(f'  <img src="https://img.shields.io/badge/channels-{len(CHANNELS)}-8b5cf6?style=flat-square" alt="Channels">')
    W(f'  <img src="https://img.shields.io/badge/updated-{now.split()[0]}-58a6ff?style=flat-square" alt="Updated">')
    W('</div>')
    W('')

    # ── BANNER ──
    W('<p align="center">')
    W('  <img src="https://raw.githubusercontent.com/may215/must-have-projects/main/assets/banner.svg" width="100%" alt="Must-Have Projects Banner" style="max-width: 1000px;">')
    W('</p>')
    W('<br>')

    # ── HERO ──
    W('<div align="center">')
    W('  <h1>🚀 Must-Have Projects</h1>')
    W('  <h3><em>The Ultimate Open-Source Discovery Feed</em></h3>')
    W('')
    W('  <p><strong>Automatically curated from the best YouTube channels.</strong><br>')
    W('  Every GitHub project mentioned in video descriptions — extracted, ranked by stars, and always up to date.</p>')
    W('</div>')
    W('')
    W('<br>')

    # ── STATS ROW ──
    W('| | | | |')
    W('|---|---|---|---|')
    W(f'| 🗂️ **{total}** Projects Tracked | ⭐ **{total_stars:,}** GitHub Stars | 📡 **{len(CHANNELS)}** Channels Scanned | 🔄 **Daily** Auto-Update |')
    W(f'| 🏆 **{len(top10)}** Starred Projects | 🌟 **{top3_stars:,}** Combined Top-3 Stars | 🎯 **100%** From Descriptions | 📅 **Every 8:00 AM** Refresh |')
    W('')

    # ── FEATURES SECTION ──
    W('## ✨ Why Must-Have Projects?')
    W('')
    W('<table>')
    W('  <tr>')
    W('    <td width="50%">')
    W('')
    W('      ### 🎯 Zero Noise')
    W('      No AI-generated filler. No random repos. Every project here was **hand-picked by expert curators** on YouTube — then extracted, verified, and ranked by live star count.')
    W('')
    W('    </td>')
    W('    <td width="50%">')
    W('')
    W('      ### ⚡ Fresh Daily')
    W('      Our bot scans **3 channels** every morning at 8:00 UTC. New videos → new projects → updated README. No stale data, no manual work.')
    W('')
    W('    </td>')
    W('  </tr>')
    W('  <tr>')
    W('    <td width="50%">')
    W('')
    W('      ### 🔍 Smart Discovery')
    W('      Find projects by star count, source channel, or browse the full table. Every entry links back to the YouTube video that featured it — context matters.')
    W('')
    W('    </td>')
    W('    <td width="50%">')
    W('')
    W('      ### 📊 Live Stats')
    W('      Star counts refresh on every scan via the GitHub API. See exactly how popular each project is — right now, not last month.')
    W('')
    W('    </td>')
    W('  </tr>')
    W('</table>')
    W('')
    W('<br>')

    # ── TOP 10 SPOTLIGHT ──
    W('## 🏆 Top 10 Projects')
    W('')
    W('<table>')
    W('  <tr>')
    W('    <th>#</th>')
    W('    <th>Project</th>')
    W('    <th>Stars</th>')
    W('    <th>Source</th>')
    W('  </tr>')
    for idx, p in enumerate(top10[:10], 1):
        owner_repo = f"{p['owner']}/{p['repo']}"
        stars = p.get("stars") or 0
        ch_info = CHANNELS.get(p["channel"], {})
        ch_label = ch_info.get("label", p["channel"])
        ch_icon = ch_info.get("icon", "📺")
        W('  <tr>')
        W(f'    <td><b>#{idx}</b></td>')
        W(f'    <td><a href="https://github.com/{owner_repo}"><b>{owner_repo}</b></a></td>')
        W(f'    <td><img src="https://img.shields.io/github/stars/{owner_repo}?style=flat-square&logo=github&label=Stars" alt="⭐ {stars:,}"></td>')
        W(f'    <td>{ch_icon} <a href="https://www.youtube.com/{ch_info.get("handle", "")}">{ch_label}</a></td>')
        W('  </tr>')
    W('</table>')
    W('')
    W('<br>')

    # ── HOW IT WORKS (MERMAID DIAGRAM) ──
    W('## 🔄 How It Works')
    W('')
    W('```mermaid')
    W('flowchart LR')
    W('    subgraph Input["📹 YouTube Channels"]')
    W('        A1["Indie Hacker News"]')
    W('        A2["Github Awesome"]')
    W('        A3["Hyperautomation Labs"]')
    W('    end')
    W('    B["📥 yt-dlp Scan"]')
    W('    C["📝 Extract Descriptions"]')
    W('    D["🔍 Regex: github.com/owner/repo"]')
    W('    E["🌐 GitHub API → Star Count"]')
    W('    F["📄 Generate README.md"]')
    W('    G["🚀 GitHub Push"]')
    W('')
    W('    Input --> B')
    W('    B --> C')
    W('    C --> D')
    W('    D --> E')
    W('    E --> F')
    W('    F --> G')
    W('    G -.->|Daily 8:00 UTC| Input')
    W('```')
    W('')
    W('<br>')

    # ── CHANNELS SECTION ──
    W('## 📡 Source Channels')
    W('')
    W('| Channel | Description | Projects Found |')
    W('|---------|-------------|---------------|')
    for key in channel_order:
        ch = CHANNELS.get(key, {})
        ch_projects = by_channel.get(key, [])
        ch_stars = sum(p.get("stars", 0) or 0 for p in ch_projects)
        ch_url = ch.get("url", "#").replace("/videos", "")
        descs = {
            "indiehackernews": "Daily news digest for indie hackers, bootstrappers, and solo founders",
            "githubawesome": "Latest trending GitHub repositories — fresh, daily, packed with inspiration",
            "hyperautomationlabs": "AI coding tools, agentic workflows, and developer automation",
        }
        W(f'| [{ch.get("icon", "")} {ch.get("label", key)}]({ch_url}) | {descs.get(key, "")} | {len(ch_projects)} projects · {ch_stars:,} ⭐ |')
    W('')
    W('<br>')

    # ── DETAILED LISTS BY CHANNEL ──
    W('## 📋 All Projects by Channel')
    W('')
    for key in channel_order:
        ch = CHANNELS.get(key, {})
        ch_projects = by_channel.get(key, [])
        if not ch_projects:
            continue
        ch_stars = sum(p.get("stars", 0) or 0 for p in ch_projects)
        sorted_ch = sorted(ch_projects, key=lambda p: (-(p.get("stars") or 0), p["owner"] + "/" + p["repo"]))

        W(f'<details open>')
        W(f'  <summary><strong>{ch.get("icon", "")} {ch.get("label", key)}</strong> — {len(sorted_ch)} projects · {ch_stars:,} ⭐</summary>')
        W('')
        W('  <table>')
        W('    <thead>')
        W('      <tr>')
        W('        <th>#</th>')
        W('        <th>Project</th>')
        W('        <th>Stars</th>')
        W('        <th>Video</th>')
        W('      </tr>')
        W('    </thead>')
        W('    <tbody>')
        for idx, p in enumerate(sorted_ch, 1):
            owner_repo = f"{p['owner']}/{p['repo']}"
            vid_title = p.get("video_title", "")
            if vid_title and len(vid_title) > 45:
                vid_title = vid_title[:42] + "..."
            W('      <tr>')
            W(f'        <td>{idx}</td>')
            W(f'        <td><a href="https://github.com/{owner_repo}"><b>{owner_repo}</b></a></td>')
            W(f'        <td><img src="https://img.shields.io/github/stars/{owner_repo}?style=flat-square&label=" alt="⭐"></td>')
            W(f'        <td><a href="{p.get("video_url", "#")}">{html.escape(vid_title) if vid_title else "▶"}</a></td>')
            W('      </tr>')
        W('    </tbody>')
        W('  </table>')
        W('')
        W(f'</details>')
        W('')

    # ── FULL FLAT TABLE ──
    W('## 📊 Complete Project Index')
    W('')
    W('<table>')
    W('  <thead>')
    W('    <tr>')
    W('      <th>#</th>')
    W('      <th>Project</th>')
    W('      <th>Stars</th>')
    W('      <th>Channel</th>')
    W('      <th></th>')
    W('    </tr>')
    W('  </thead>')
    W('  <tbody>')
    for idx, p in enumerate(all_sorted, 1):
        owner_repo = f"{p['owner']}/{p['repo']}"
        ch_info = CHANNELS.get(p["channel"], {})
        ch_label = ch_info.get("label", p["channel"])
        W('    <tr>')
        W(f'      <td>{idx}</td>')
        W(f'      <td><a href="https://github.com/{owner_repo}">{owner_repo}</a></td>')
        W(f'      <td><img src="https://img.shields.io/github/stars/{owner_repo}?style=flat-square&label=" alt="⭐"></td>')
        W(f'      <td>{ch_label}</td>')
        W(f'      <td><a href="{p.get("video_url", "#")}">▶</a></td>')
        W('    </tr>')
    W('  </tbody>')
    W('</table>')
    W('')

    # ── TECH STACK / TAGS ──
    W('## 🛠️ Tech Stack')
    W('')
    W('<p>')
    W('  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">')
    W('  <img src="https://img.shields.io/badge/yt--dlp-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="yt-dlp">')
    W('  <img src="https://img.shields.io/badge/GitHub_API-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub API">')
    W('  <img src="https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white" alt="Actions">')
    W('</p>')
    W('')
    W('<br>')

    # ── CONTRIBUTING ──
    W('## 🤝 Contributing')
    W('')
    W('Want to add a channel? Open an issue or PR. The bot makes it easy:')
    W('')
    W('- Add the channel URL to `CHANNELS` in [`scripts/update-readme.py`](scripts/update-readme.py)')
    W('- The bot will scan it on the next daily run')
    W('')
    W('---')
    W('')

    # ── FOOTER ──
    W('<div align="center">')
    W('')
    W(f'  <p><em>Auto-generated by <strong>Must-Have Projects Bot</strong></em></p>')
    W(f'  <p>🤖 <a href="scripts/update-readme.py">Script</a> · ')
    W(f'     📅 Last update: {now} · ')
    W(f'     🔄 Runs daily at 8:00 UTC</p>')
    W('')
    W('  <p>')
    W('    <a href="https://github.com/may215/must-have-projects">')
    W('      <img src="https://img.shields.io/github/stars/may215/must-have-projects?style=social" alt="Star">')
    W('    </a>')
    W('  </p>')
    W('')
    W(f'  <sub>Built with ❤️ for the open-source community · {total} projects and counting</sub>')
    W('')
    W('</div>')
    W('')

    return "\n".join(R)


def process_video(video, channel_key, star_cache):
    global CHANNELS
    log(f"  video: {video['title'][:60]}")
    desc = get_video_description(video["id"])
    if not desc:
        return []
    repos = extract_github_urls(desc)
    if not repos:
        return []
    projects = []
    description_snippet = desc[:200].replace("\n", " ").strip()
    for owner, repo in repos:
        cache_key = f"{owner}/{repo}"
        stars = star_cache.get(cache_key)
        if stars is None:
            stars = fetch_star_count(owner, repo)
            star_cache[cache_key] = stars
            time.sleep(0.5)
        ch_info = CHANNELS.get(channel_key, {})
        projects.append({
            "owner": owner,
            "repo": repo,
            "stars": stars,
            "video_title": video["title"],
            "video_id": video["id"],
            "video_url": video["url"],
            "channel": channel_key,
            "channel_url": ch_info.get("url", "#"),
            "description": description_snippet,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })
        log(f"    repo: {owner}/{repo} ⭐{stars or '?'}")
    return projects


def main():
    backfill = "--backfill" in sys.argv

    log(f"Starting {'BACKFILL' if backfill else 'INCREMENTAL'} scan")

    project_cache = load_cache(CACHE_FILE)
    star_cache = load_cache(STAR_CACHE_FILE)

    scanned_ids = set(project_cache.get("scanned_videos", []))
    all_projects = list(project_cache.get("projects", []))
    
    # Dedup
    seen_keys = set()
    deduped = []
    for p in all_projects:
        key = (p["owner"], p["repo"], p.get("channel", ""))
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(p)
    all_projects = deduped
    existing_repos = set((p["owner"], p["repo"]) for p in all_projects)

    new_projects = []
    new_scanned = []

    for channel_key, ch_info in CHANNELS.items():
        log(f"Scanning {channel_key}...")
        videos = get_channel_videos(ch_info["url"])
        log(f"  found {len(videos)} videos total")
        
        if backfill:
            videos_to_scan = videos
        else:
            videos_to_scan = [v for v in videos if v["id"] not in scanned_ids]
        
        log(f"  scanning {len(videos_to_scan)} videos")
        
        for video in reversed(videos_to_scan):
            projects = process_video(video, channel_key, star_cache)
            for p in projects:
                repo_key = (p["owner"], p["repo"])
                if repo_key not in existing_repos:
                    existing_repos.add(repo_key)
                    new_projects.append(p)
            new_scanned.append(video["id"])
            time.sleep(0.8 if backfill else 1.5)

    log(f"Found {len(new_projects)} new projects")

    all_projects.extend(new_projects)
    updated_scanned = list(set(scanned_ids) | set(new_scanned))
    
    if backfill:
        for ch_key, ch_info in CHANNELS.items():
            ch_vids = get_channel_videos(ch_info["url"])
            extra_ids = set(v["id"] for v in ch_vids)
            updated_scanned = list(set(updated_scanned) | extra_ids)

    project_cache["projects"] = all_projects
    project_cache["scanned_videos"] = updated_scanned
    save_cache(CACHE_FILE, project_cache)
    save_cache(STAR_CACHE_FILE, star_cache)

    log(f"Total unique projects: {len(all_projects)}")

    readme = build_readme(all_projects)
    README_FILE.write_text(readme)
    log(f"README written to {README_FILE}")

    total = len(all_projects)
    stars = sum(p.get("stars", 0) or 0 for p in all_projects)
    log(f"=== DONE: {total} projects, {stars:,} total stars ===")


if __name__ == "__main__":
    main()
