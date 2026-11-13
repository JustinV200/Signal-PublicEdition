"""Settings dataclasses with their defaults. One frozen class per TOML table.

Every value here is documented in tools/browser/browser.example.toml; keep the two
in step. The loader (loader.py) builds these from TOML; other packages only read them.
"""

from dataclasses import dataclass, field

from browser_tool.config.confirm_categories import ALL_CATEGORIES


@dataclass(frozen=True)
class BrowserSettings:
    """How the browser is launched and how long actions may take."""

    channel: str = "msedge"
    headless: bool = False
    # Relative paths resolve against tools/browser. Both folders are gitignored.
    profile_dir: str = ".profile"
    screenshot_dir: str = ".screenshots"
    # The desktop browser saves its cookies here on a clean close (DPAPI,
    # owner-only) and adds its session cookies back at launch; visit mode
    # borrows them (browser_tool.cookie_store). Never used by docker jobs.
    cookie_file: str = ".state/cookies.bin"
    navigation_timeout_s: float = 30.0
    action_timeout_s: float = 10.0
    # Snapshot page size: longer snapshots come in pages, to keep tool results a sane size.
    max_snapshot_chars: int = 40_000
    # Off by default: behind a proxy, Edge doesn't resolve hosts itself, so the
    # DNS-level redirect block (--host-resolver-rules) would not apply.
    use_system_proxy: bool = False
    # Docker backend only: end the job (its container) after this many minutes
    # without a tool call. The next call starts a fresh one.
    idle_close_min: float = 15.0


@dataclass(frozen=True)
class PolicySettings:
    """Domain allow/deny patterns: "example.com" (exact) or "*.example.com" (subdomains).

    An empty allowlist blocks everything. allow_all = true allows every host
    (navigations are logged) and ignores `allow`. The denylist always wins.
    """

    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()
    allow_all: bool = False


@dataclass(frozen=True)
class GateSettings:
    """Which actions need the owner's yes, and how long to wait for it.

    Only config sets these: no tool and no page can change them while running.
    """

    # Categories (see confirm_categories.py) whose actions wait for the owner's
    # Allow. Every other action runs on its own and is logged.
    always_confirm: tuple[str, ...] = ALL_CATEGORIES
    # The owner's own extra regexes: a target whose text matches one always asks.
    patterns: tuple[str, ...] = ()
    # Unanswered confirmations are treated as "no" after this many seconds.
    confirm_timeout_s: float = 120.0
    # Origins (e.g. "https://chat.example.com") where Enter in a message box
    # needs no OK. Pattern, form, Control+Enter and Delete key rules still apply.
    no_confirm_origins: tuple[str, ...] = ()
    # True lets type_text type into password and one-time-code fields. Only for
    # the job runner's dedicated job-site accounts (browser-jobs.toml); keep it
    # off everywhere else. Values typed there are still redacted and scrubbed.
    allow_secret_fields: bool = False


@dataclass(frozen=True)
class DuoSettings:
    """How Duo two-factor prompts are announced to the owner and the model.

    The lockout (no acting tools on a Duo tab) and the notice to the model are
    always on and can't be switched off. voice_heads_up and the hub keys control
    the voice note to the audiohub hub; same_prompt_window_s decides when a
    return to Duo is a new prompt (a new notice and heads-up);
    min_heads_up_interval_s spaces out voice heads-ups across all tabs, and code
    notes per site. The code_* keys control reading Duo's Verified Push code out
    (read only, off by default).
    code_relay_sites patterns are checked when DuoWatch is built, like [policy]'s
    when ActionContext is (config imports nothing from the policy package).
    """

    voice_heads_up: bool = True
    # The audiohub kernel's notification server (tools/audiohub, [ipc] port).
    hub_host: str = "127.0.0.1"
    hub_port: int = 8765
    # Relative to tools/browser, like every config path. audiohub writes a new
    # token here each time the hub starts; no file means the hub isn't running.
    hub_token_file: str = "../audiohub/.cache/ipc-token"
    # A tab that leaves Duo and comes back within this many seconds is still the
    # same prompt (no second notice or heads-up); after that it's a new prompt.
    same_prompt_window_s: float = 10.0
    # At most one voice heads-up per this many seconds, across all tabs, so a page
    # that keeps embedding a Duo iframe can't keep telling the owner to approve.
    # Code notes are held to it per site instead.
    min_heads_up_interval_s: float = 60.0
    # Host patterns (as in [policy]) of the sites whose Duo Verified Push code is
    # read out to the owner and passed to the model. Empty = off. An attacker with
    # the owner's password could embed a real Duo prompt on their own page, so a
    # code is only relayed when the site around the prompt is listed here.
    code_relay_sites: tuple[str, ...] = ()
    # After a prompt starts, look for its code every code_poll_interval_s, for up
    # to code_relay_timeout_s.
    code_relay_timeout_s: float = 45.0
    code_poll_interval_s: float = 1.0
    # Owner-chosen names for login hosts, said instead of the hostname in Duo
    # heads-ups, notices and the signed-out note: exact hostname -> name, e.g.
    # {"sso.example.edu": "the school login"}. Names are letters, digits, spaces,
    # dots and hyphens, at most 40 characters (the loader checks). Only the tab's
    # own vetted hostname is looked up, never a page-supplied parameter.
    site_names: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DownloadSettings:
    """Desktop browser only: whether downloads are saved, where, and how big they may be.

    The docker backend always denies downloads, whatever these say.
    """

    enabled: bool = True
    # Relative to tools/browser, like every config path. Gitignored.
    folder: str = ".downloads"
    # A download bigger than this is cancelled and deleted.
    max_mb: float = 200.0


@dataclass(frozen=True)
class UploadSettings:
    """Desktop browser only: which local files upload_file may send, and how big.

    The docker backend always refuses uploads, whatever these say.
    """

    # Folders a file must be inside (after resolving, with no symlink or
    # junction on the way). Relative to tools/browser, like every config path:
    # the repo's life/ folder and the downloads folder.
    roots: tuple[str, ...] = ("../../life", ".downloads")
    # A file bigger than this many megabytes is refused.
    max_mb: float = 25.0


@dataclass(frozen=True)
class VisitSettings:
    """Visit mode only (browser-tool-visit, browser_tool.visit): the login and sign-in rules.

    The MCP server ignores this table. An empty login_host (the default) means the
    launch never fills a login; only the checker's Moodle config sets the login keys.
    """

    # The SSO login host a visit may fill on (CAS). Empty: no fill path at all.
    login_host: str = ""
    # A fill needs the target's host, and the host in the login URL's `service`
    # parameter, to be one of these (exact hosts).
    login_from_hosts: tuple[str, ...] = ()
    # The vault credential id filled on login_host, at most once per run.
    login_credential: str = ""
    # Landing on one of these hosts (exact) means a Google sign-in is needed:
    # nothing is filled or typed there.
    signin_hosts: tuple[str, ...] = ()
    # The school's SSO login host (exact, e.g. sso.example.edu). On a sign-in launch, a
    # failed navigation whose last hop went here means Google sent the account to SSO.
    sso_host: str = ""
    # The school's cookie domain (e.g. example.edu). A sign-in launch first clears every
    # cookie on it or its subdomains, so an SSO session a crashed run left can't meet a
    # SAML hop. Empty: nothing is cleared.
    school_domain: str = ""
    # After the fill, how long to wait for the tab to leave the login host and Duo.
    login_wait_s: float = 150.0
    # After each navigation, wait up to this long for the network to go quiet.
    settle_s: float = 8.0


@dataclass(frozen=True)
class Settings:
    """All browser-tool settings, one field per TOML table."""

    browser: BrowserSettings = field(default_factory=BrowserSettings)
    policy: PolicySettings = field(default_factory=PolicySettings)
    gates: GateSettings = field(default_factory=GateSettings)
    duo: DuoSettings = field(default_factory=DuoSettings)
    downloads: DownloadSettings = field(default_factory=DownloadSettings)
    uploads: UploadSettings = field(default_factory=UploadSettings)
    visit: VisitSettings = field(default_factory=VisitSettings)
