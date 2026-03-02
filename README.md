# remove-x-followers

A daemon that automatically removes all followers from your X (formerly Twitter) account. Runs continuously, polling every 60 seconds and soft-blocking every new follower it finds.

**Why does this exist?** Read below.

---

## A Manifesto: Why We're Leaving X

### X is a propaganda machine

What was once a platform for open discourse has been deliberately transformed into a disinformation pipeline. Under Elon Musk's ownership, X has become a megaphone for lies, conspiracy theories, and political manipulation — with the owner himself being the platform's [most prolific disinformation spreader](https://www.poynter.org/fact-checking/2023/elon-musk-misinformation-twitter-x/). The man with the loudest microphone on Earth uses it to amplify falsehoods to hundreds of millions of people, and the algorithm he controls makes sure they see it.

### The algorithm rewards outrage, not truth

X's algorithm is an engagement-farming machine by design. It doesn't surface what's accurate, important, or valuable — it surfaces what makes you angry, afraid, or addicted. Rage bait and ragebait merchants are systematically boosted while thoughtful, factual content is buried. The platform has been re-engineered to maximize time-on-screen at the expense of truth, nuance, and mental health. Engagement is the product. You are the raw material.

### Spam and bot reports go nowhere

Report an account that's clearly a bot? An account running coordinated spam? A network of fake profiles pushing scams? Nothing happens. X's "Trust & Safety" team — what's left of it — is either unwilling or unable to act. Spam accounts operate freely, impersonate real people, and flood replies with garbage. The reporting system exists only as theater, a button that makes you feel like you did something while the platform does nothing.

### X is a casino for crypto pump-and-dump schemes

X has become the primary coordination platform for cryptocurrency pump-and-dump schemes. Influencer accounts with millions of followers openly shill worthless tokens, coordinated bot networks amplify them, and regular users get liquidated when the rug is pulled. The platform not only tolerates this — it profits from it. The same reporting mechanisms that ignore spam ignore financial fraud.

### The app is broken and getting worse

When you fire 80% of your engineering team, the product falls apart. X is slow. It's buggy. Features break randomly. The timeline refreshes and loses your place. Notifications don't load. Search is degraded. The API is unreliable. Basic functionality that worked fine for a decade under previous ownership now fails regularly. This isn't growing pains — it's what happens when you gut the people who built and maintained the platform, then pretend everything is fine.

### The developer platform is a joke

X charges developers exorbitant prices for API access that barely works. The Basic tier costs $100/month for rate limits so restrictive that building anything meaningful is nearly impossible. The "Pro" tier is $5,000/month. For context: you get 15 follower-list requests per 15 minutes. The documentation is outdated, endpoints break without notice, and the developer community has been abandoned. They turned a thriving ecosystem of third-party apps and integrations into a cash grab, then delivered a broken product in return.

---

### What this tool does

Since X won't let you disable followers, and won't give you meaningful control over your own account, this tool does it for you. It watches your account and automatically removes every new follower by blocking and immediately unblocking them (the only method X's API supports — there's no "remove follower" endpoint, because of course there isn't).

It's a small act of digital autonomy on a platform designed to strip it from you.

---

## Setup

### Requirements

- Python 3.9+
- X Developer account with an app that has **Read and Write** permissions
- OAuth 1.0a credentials (Consumer Key, Consumer Secret, Access Token, Access Token Secret)

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
# Edit .env with your credentials
```

Your `.env` file:
```
API_KEY=your_consumer_key
API_KEY_SECRET=your_consumer_key_secret
ACCESS_TOKEN=your_access_token
ACCESS_TOKEN_SECRET=your_access_token_secret
```

Get these from the [X Developer Console](https://developer.x.com) → Apps → your app → Keys and tokens.

### Run

```bash
venv/bin/python main.py
```

### Deploy as a systemd service (VPS)

```bash
# Copy files to your server
scp -r . deploy@your-vps:/opt/x-follower-remover/

# On the server:
cd /opt/x-follower-remover
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env  # fill in credentials

sudo cp x-follower-remover.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now x-follower-remover

# Check logs
sudo journalctl -u x-follower-remover -f
```

### Rate limits

| Action | Limit |
|---|---|
| Fetch followers | 15 requests / 15 min |
| Block | 50 requests / 15 min |
| Unblock | 50 requests / 15 min |

The tool auto-sleeps when hitting rate limits. Realistically it removes ~50 followers per 15 minutes.

## License

Do whatever you want with this. [Unlicense](https://unlicense.org/).
