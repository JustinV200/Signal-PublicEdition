# Calendar tool setup (one time, about 5 minutes)

This lets the `calendar` tool read the calendars on your personal Gmail address (`owner@example.com` in these steps), the one you connected to the mail tool first, and add, change and delete events on them. It reuses the Google Cloud project and Desktop OAuth client you made for the mail tool ([tools/mail/SETUP.md](../mail/SETUP.md)), so do that first. There's no new client file to download.

## 1. Turn on the Calendar API

1. Go to https://console.cloud.google.com and sign in as **owner@example.com**.
2. Check that the project picker at the top left shows the mail tool's project (**Signal mail**). If not, click it and pick it.
3. Open https://console.cloud.google.com/apis/library/calendar-json.googleapis.com, or go to ☰ → **APIs & Services** → **Library**, search for "Google Calendar API" and click it. Click **Enable**.

## 2. Add the two scopes to the consent screen

1. Open https://console.cloud.google.com/auth/scopes, or go to **Google Auth Platform** → **Data Access**.
2. Click **Add or remove scopes**. Under "Manually add scopes", paste this line, then click **Add to table**, **Update**, and **Save**:
   ```
   https://www.googleapis.com/auth/calendar.events,https://www.googleapis.com/auth/calendar.calendarlist.readonly
   ```
3. Leave the app **In production** (it already is from the mail setup). If the console asks you to verify the app, ignore it; you're its only user.

The tool only ever asks for these two scopes. `calendar.events` lets it add, change and delete events (never calendars themselves); `calendar.calendarlist.readonly` only lists your calendars. If an older setup added `calendar.events.readonly`, you can remove it from the table once you've signed in again (step 3).

## 3. Sign in once

From `C:\src\Signal`:

```
uv run --project tools/calendar calendar setup
uv run --project tools/calendar calendar add
```

`setup` should say `OAuth client file: OK`. `add` opens a sign-in tab in your default browser and waits up to 5 minutes. Do the sign-in in a normal browser window (plain Edge is fine). Google refuses sign-ins in the browser tool's automated Edge window, so if that's what opened, close it and paste the URL the terminal printed into a plain Edge window instead.

1. **Choose an account**: pick **owner@example.com** (it's pre-selected). If you pick another account, the tool saves nothing and tells you.
2. **"Google hasn't verified this app"**: click **Advanced**, then **Go to Signal mail (unsafe)**.
3. **"Signal mail wants access to your Google Account"**: tick **both** boxes (or **Select all**), "View and edit events on all your calendars" and "See the list of Google calendars you're subscribed to", then **Continue**.
4. The tab says "Signed in to the Signal calendar tool", and the terminal prints `Saved the calendar sign-in for owner@example.com.`

Check it:

```
uv run --project tools/calendar calendar agenda
```

## 4. Turn on the 10-minute refresh

From `C:\src\Signal` in PowerShell:

```powershell
.\tools\calendar\schedule\register.ps1 -RunNow
```

See [schedule/README.md](schedule/README.md) to remove it again.

## 5. Let Claude use it

Setup's **Add to Claude Code** puts the `calendar` server in `.mcp.json`. Restart Claude Code so it loads. Changing an event the tool didn't add opens an Allow/Deny dialog on your PC; to turn that off, see Security in [README.md](README.md).

## Later

**Signed in before the tool could write?** A sign-in made with the old `calendar.events.readonly` scope keeps reading, but any change says "This calendar sign-in is read-only ... Re-run `calendar add`". Do step 2 with the new scope line, then step 3 again.

To disconnect, delete `tools/calendar/.state/token.bin` and remove "Signal mail" at https://myaccount.google.com/permissions (that also removes the mail tool's access, so re-run its `mail add` lines afterwards). If the agenda ever says "Re-run `calendar add`", do step 3 again.

## Where the console may differ (unverified)

I couldn't open the live console while writing this. Older consoles call **Data Access** the "Scopes" page of the **OAuth consent screen**, and the Library URL may redirect. The scope strings themselves don't change.
