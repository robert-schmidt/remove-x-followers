# remove-x-followers

A daemon that automatically removes all followers from your X (formerly Twitter) account. Runs continuously, polling every 5 seconds and silently removing every new follower it finds.

**Why does this exist?** Read below.

---

## Why I'm Going Ghost Mode on X

### I watched X become a propaganda machine

I was there when Twitter was a place for open conversation. I watched it get deliberately turned into a disinformation pipeline. Under Elon Musk's ownership, X became a megaphone for lies, conspiracy theories, and political manipulation — with the owner himself being the platform's [most prolific disinformation spreader](https://www.poynter.org/fact-checking/2023/elon-musk-misinformation-twitter-x/). The man with the loudest microphone on Earth uses it to amplify falsehoods to hundreds of millions of people, and the algorithm he controls makes sure they see it. I'm not going to be part of that audience anymore.

### The algorithm turned my feed into an outrage farm

I used to find interesting people and good conversations on here. Now my feed is engineered to make me angry, afraid, or addicted. Rage bait gets boosted. Thoughtful content gets buried. The platform has been re-engineered to maximize my time-on-screen at the expense of truth, nuance, and my own mental health. Engagement is the product. I was the raw material. Not anymore.

### I reported hundreds of spam accounts. Nothing happened.

I've reported bots. I've reported coordinated spam networks. I've reported fake profiles running scams. Every single time — nothing. X's "Trust & Safety" team, what's left of it, is either unwilling or unable to act. Spam accounts operate freely, impersonate real people, and flood every reply section with garbage. The report button is theater. It exists to make me feel like I did something while the platform does nothing.

### I watched people get ruined by crypto scams that X facilitates

X has become ground zero for cryptocurrency pump-and-dump schemes. I've seen influencer accounts with millions of followers openly shill worthless tokens, coordinated bot networks amplify them, and regular people get liquidated when the rug gets pulled. The platform doesn't just tolerate this — it profits from it. The same reporting system that ignores spam ignores financial fraud. I reported these too. Nothing.

### The app barely works anymore

I remember when Twitter was fast and reliable. Then they fired 80% of the engineering team and the product fell apart. X is slow. It's buggy. Features break randomly. My timeline refreshes and I lose my place. Notifications don't load. Search is degraded. Basic functionality that worked fine for a decade now fails regularly. This isn't growing pains — it's what happens when you gut the people who built the platform and pretend everything is fine.

### They killed the developer ecosystem and charged for the corpse

I'm a developer. I used to build things with the Twitter API. Now X charges exorbitant prices for API access that barely works. The Basic tier is $100/month for rate limits so restrictive that building anything meaningful is nearly impossible. The "Pro" tier is $5,000/month. For context: I get 15 follower-list requests per 15 minutes. The documentation is outdated, endpoints break without notice, and the developer community has been abandoned. They turned a thriving ecosystem into a cash grab, then delivered a broken product in return.

---

### So I built this

Since X won't let me disable followers, and won't give me meaningful control over my own account, I built this tool to do it for me. It watches my account and silently removes every new follower using X's internal GraphQL API — the same one x.com uses when you click "Remove this follower" in the browser. No developer account needed. No paid API tier. Just your browser cookies.

I'm going ghost. Zero followers. Zero engagement. Just a profile that exists to remind me why I left.

If you want to do the same, the code is below.

---

## Setup

### Requirements

- Python 3.9+
- Your browser session cookies from x.com

### Install

```bash
git clone https://github.com/robert-schmidt/remove-x-followers.git
cd remove-x-followers
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
```

Your `.env` file needs 2 values from your browser cookies:

1. Open [x.com](https://x.com) and make sure you're logged in
2. Open DevTools (F12) → Application tab → Cookies → `https://x.com`
3. Copy these two cookie values:

```
X_AUTH_TOKEN=your_auth_token_cookie
X_CT0=your_ct0_cookie
```

**Note:** Session cookies expire when you log out or when X rotates them. If the daemon starts failing with auth errors, grab fresh cookies from your browser and update the `.env`.

### Run

```bash
venv/bin/python main.py
```

### Deploy as a systemd service (VPS)

```bash
# Copy files to your server
scp -r . user@your-vps:/opt/x-follower-remover/

# On the server:
cd /opt/x-follower-remover
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env  # fill in both values

sudo cp x-follower-remover.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now x-follower-remover

# Check logs
sudo journalctl -u x-follower-remover -f
```

### How it works

The daemon uses X's internal GraphQL API exclusively — the same endpoints that x.com uses in the browser. It fetches your followers list via the `Followers` query and removes them via the `RemoveFollower` mutation, polling every 5 seconds. No public API access or developer account required.

Followers are silently removed without being blocked. They can still see your profile, but if they follow again, they'll be removed again within seconds.

All removals are logged to `removals.log` with timestamps.

## License

Do whatever you want with this. [Unlicense](https://unlicense.org/).
