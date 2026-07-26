#!/usr/bin/env python3
"""Quick test: scan 3 videos from each channel to verify extraction works."""
import json, subprocess, sys, re

CHANNELS = {
    "indiehackernews": "https://www.youtube.com/@indiehackernews/videos",
    "githubawesome": "https://www.youtube.com/@GithubAwesome/videos",
    "hyperautomationlabs": "https://www.youtube.com/@hyperautomationlabs1045/videos",
}

GITHUB_RE = re.compile(r'https?://github\.com/([a-zA-Z0-9._-]+)/([a-zA-Z0-9._-]+?)(?:/|\.git)?(?:\s|$|[)\]}>])')

for name, url in CHANNELS.items():
    print(f"\n=== {name} ===")
    r = subprocess.run(["yt-dlp", "--quiet", "--flat-playlist", "--dump-json", url], capture_output=True, text=True, timeout=60)
    videos = [json.loads(l) for l in r.stdout.strip().split("\n") if l.strip()]
    print(f"Total videos in feed: {len(videos)}")
    
    for v in videos[:3]:
        r2 = subprocess.run(["yt-dlp", "--quiet", "--print", "description", f"https://www.youtube.com/watch?v={v['id']}"], capture_output=True, text=True, timeout=60)
        desc = r2.stdout or ""
        repos = set()
        for m in GITHUB_RE.finditer(desc):
            repos.add(f"{m.group(1).lower()}/{m.group(2).lower()}")
        print(f"  {v['title'][:50]}... → {len(repos)} repos: {', '.join(list(repos)[:5])}")
