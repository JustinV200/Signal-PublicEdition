# Mail tool setup (one time, about 15 minutes)

This connects `owner@example.com`, `owner.alt@example.com` and `owner@school.example.edu` to Claude's `mail` tool. You'll make a private Google Cloud "app" that only you use, download its client file, and then sign each account in once.

Google renames console pages often. The names below match the console as of late 2026; the section at the end lists where it may look different.

## 1. Create a project and turn on the Gmail API

1. Go to https://console.cloud.google.com and sign in as **owner@example.com**. Use a personal account, because the school may not let its accounts create projects.
2. If a terms-of-service box appears, tick it and click **Agree and continue**.
3. Open https://console.cloud.google.com/projectcreate.
   - Project name: `Signal mail`.
   - Location: leave it as **No organization**.
   - Click **Create**.
4. Wait for the "Creating project" notification (bell icon, top right). Check that the project picker at the top left says **Signal mail**; if it doesn't, click it and pick Signal mail.
5. Open https://console.cloud.google.com/apis/library/gmail.googleapis.com, or go to ☰ menu → **APIs & Services** → **Library**, search for "Gmail API" and click it. Click **Enable**.

## 2. Set up the consent screen ("Google Auth Platform")

1. Go to ☰ → **APIs & Services** → **OAuth consent screen**, or open https://console.cloud.google.com/auth/overview. You'll land on **Google Auth Platform**. Click **Get started**.
2. Fill in the wizard:
   - **App information**: App name `Signal mail`, and User support email `owner@example.com`. Click **Next**.
   - **Audience**: choose **External**. Click **Next**.
   - **Contact information**: `owner@example.com`. Click **Next**.
   - **Finish**: tick "I agree to the Google API Services: User Data Policy", click **Continue**, then click **Create**.
3. In the left menu click **Audience**, or open https://console.cloud.google.com/auth/audience.
   - Under **Test users** click **+ Add users**, add all three addresses (`owner@example.com`, `owner.alt@example.com`, `owner@school.example.edu`), and click **Save**.
   - Under **Publishing status** (it says "Testing") click **Publish app**, then **Confirm**. The status should now say **In production**.
   - **This matters.** While the app is "Testing", Google expires every sign-in after 7 days and you'd have to re-run `mail add` each week. In production, sign-ins last until you revoke them.
   - Don't submit the app for verification. You're its only user, and the warning described in step 4 is how Google handles unverified personal apps.
4. Optional: in the left menu click **Data Access** → **Add or remove scopes**. Under "Manually add scopes", paste the line below, click **Add to table**, **Update**, then **Save**:
   ```
   https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.compose
   ```
   The tool asks for exactly these two scopes when it signs in, so it works without this step. Listing them here only makes the console show what the app uses. If the console then asks you to verify the app, ignore it.

## 3. Create the Desktop client and download it

1. In the left menu click **Clients**, or open https://console.cloud.google.com/auth/clients. Click **+ Create client**.
2. Application type: **Desktop app**. Name: `Signal mail desktop`. Click **Create**.
3. In the "OAuth client created" box, click **Download JSON**. Do it now: Google may only let you download the client secret at this moment. If you miss it, open the client, add a new secret, and download again.
4. Move the file into place. In PowerShell:
   ```powershell
   New-Item -ItemType Directory -Force C:\src\Signal\tools\mail\.state
   Move-Item $HOME\Downloads\client_secret_*.json C:\src\Signal\tools\mail\.state\google_client.json
   ```
5. Check it from `C:\src\Signal`:
   ```
   uv run --project tools/mail mail setup
   ```
   The last line should say `OAuth client file: OK (Desktop app client, ...)`.

`tools/mail/.state/` is gitignored, so the client file and the saved sign-ins never reach git.

## 4. Sign in each account

From `C:\src\Signal`, run these one at a time:

```
uv run --project tools/mail mail add personal --email owner@example.com
uv run --project tools/mail mail add alt --email owner.alt@example.com
uv run --project tools/mail mail add school --email owner@school.example.edu
```

Each command opens a browser tab and waits up to 5 minutes:

1. **Choose an account**: the right one is pre-selected. If the browser is signed in to a different account, pick or add the right one. If the account you sign in with doesn't match `--email`, the tool saves nothing and tells you.
2. **"Google hasn't verified this app"**: this is expected, because the app is yours and unverified. Click **Advanced** (small link, bottom left), then **Go to Signal mail (unsafe)**. "Unsafe" here only means Google hasn't reviewed it.
3. **"Signal mail wants access to your Google Account"**: tick **both** boxes (or **Select all**):
   - read your email
   - manage drafts and send email

   Then click **Continue**. If you leave a box unticked, the tool stops and asks you to run it again.
4. The tab says "Signed in to the Signal mail tool", and the terminal prints `Saved 'personal' (owner@example.com).`

Then check all three:

```
uv run --project tools/mail mail accounts
```

Each should say `ok`. If one ever says `needs re-auth`, run its `mail add` line again.

To disconnect an account later, run `mail remove <alias>` and also revoke "Signal mail" at https://myaccount.google.com/permissions.

## 5. If the school says "Access blocked"

the school runs Google Workspace, and its admins decide whether outside apps may read the school mail. If step 4 for `school` ends in a page saying "Access blocked: Signal mail is not approved by the school", "This app is blocked", or `Error 400: admin_policy_enforced`, nothing on your side can fix it. You have two options:

- **Forward the school mail to a personal Gmail** (the simplest fallback):
  1. In the school Gmail, go to ⚙ → **See all settings** → **Forwarding and POP/IMAP** → **Add a forwarding address**, and enter `owner@example.com` (or `owner.alt@example.com`).
  2. Confirm with the code Google emails to that address.
  3. Choose **Forward a copy of incoming mail** and **Save Changes**.

  Claude then reads it there, for example `mail_search personal "to:owner@school.example.edu"`. Some schools also turn off forwarding; if the option is missing, that's why. Replies drafted this way come from the personal account, not the school.
- **Ask the school IT** to allow the app by its client ID. It's the `client_id` value in `google_client.json`, which isn't secret.

## Where the console may differ (unverified)

I couldn't open the live console while writing this. Check these points:

- **Page names.** Older consoles call "Google Auth Platform" the **OAuth consent screen** (with a 4-page form) and call **Clients** "Credentials → Create credentials → OAuth client ID". The choices are the same: External, test users, Publish app, Desktop app.
- **Download timing.** The download-only-at-creation rule for client secrets started rolling out in 2025. Your console may still let you download later.
- **Restricted scopes.** `gmail.readonly` and `gmail.compose` are "restricted". Google lets an unverified app in production use them behind the warning screen, with a lifetime cap of 100 users. If the consent page refuses outright instead of showing **Advanced**, the policy has changed. Switch **Publish app** back to Testing; that keeps working, but you'd re-run `mail add` weekly.
- **the school.** Whether it blocks the app depends on its admin settings, which I can't see.
