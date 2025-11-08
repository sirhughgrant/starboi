import os, time, sys, requests, random

TOKEN = os.environ["GITHUB_TOKEN"]
SOURCE_USER = os.environ.get("SOURCE_USER", "granolacowboy")
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "100"))
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"

S = requests.Session()
S.headers.update({
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "star-sync-action"
})

API = "https://api.github.com"

def paged(url, params=None):
    while url:
        r = S.get(url, params=params)
        handle_rate(r)
        r.raise_for_status()
        data = r.json()
        yield data
        url = None
        if "link" in r.headers:
            for part in r.headers["link"].split(","):
                if 'rel="next"' in part:
                    url = part[part.find("<")+1:part.find(">")]
                    break
        params = None

def handle_rate(r):
    if r.status_code == 403 and "Retry-After" in r.headers:
        time.sleep(int(r.headers["Retry-After"]) + 1)

def list_starred(user):
    out, url, params = [], f"{API}/users/{user}/starred", {"per_page": 100}
    for page in paged(url, params):
        out.extend([item["full_name"] for item in page])
    return set(out)

def list_my_starred():
    out, url, params = [], f"{API}/user/starred", {"per_page": 100}
    for page in paged(url, params):
        out.extend([item["full_name"] for item in page])
    return set(out)

def star_repo(full_name):
    owner, repo = full_name.split("/", 1)
    r = S.put(f"{API}/user/starred/{owner}/{repo}", data=b"")
    if r.status_code in (204, 304):
        return True
    if r.status_code == 403 and "Retry-After" in r.headers:
        handle_rate(r)
        return star_repo(full_name)
    r.raise_for_status()
    return True

def gentle_backoff(i):
    time.sleep(0.9 + random.random()*0.4 + min(i*0.01, 0.6))

def main():
    source = list_starred(SOURCE_USER)
    mine = list_my_starred()
    missing = sorted(source - mine)
    if not missing:
        print("No new repos to star.")
        return
    batch = missing[:MAX_PER_RUN]
    print(f"Found {len(missing)} missing; processing {len(batch)} (MAX_PER_RUN={MAX_PER_RUN}). DRY_RUN={DRY_RUN}")

    done = 0
    for i, full in enumerate(batch, 1):
        if DRY_RUN:
            print(f"[dry-run] would star {full}")
        else:
            try:
                star_repo(full)
                done += 1
                if i % 25 == 0:
                    print(f"Progress: {i} done")
            except requests.HTTPError as e:
                print(f"Skip {full}: {e}", file=sys.stderr)
        gentle_backoff(i)

    print(f"Completed. Starred {done} repo(s).")

if __name__ == "__main__":
    main()
