"""Edge command-line switches for the browser container (docker backend guest).

Copied from Playwright 1.64.0's curated `chromiumSwitches` (coreBundle.js in the
driver), so the container's Edge behaves like the one the local backend
launches. Taken out, because they turn off protections an `allow_all` guest
wants (refdocs/research/docker-browser.md section 3):
- --disable-background-networking, --disable-component-update,
  --disable-client-side-phishing-detection and --disable-popup-blocking;
- "HttpsUpgrades" from the --disable-features list, so HTTPS upgrades stay on.

Never add --no-sandbox or --remote-allow-origins here.
"""

DISABLED_FEATURES = [
    "AvoidUnnecessaryBeforeUnloadCheckSync",
    "DestroyProfileOnBrowserClose",
    "DialMediaRouteProvider",
    "GlobalMediaControls",
    "LensOverlay",
    "MediaRouter",
    "PaintHolding",
    "ThirdPartyStoragePartitioning",
    "BlockOriginHeaderModificationOnRedirect",
    "AvoidCorsURLLoaderRestartOnRedirect",
    "Translate",
    "AutoDeElevate",
    "OptimizationHints",
    "NetworkTimeServiceQuerying",
    "AimEnabled",
    "msForceBrowserSignIn",
    "msEdgeUpdateLaunchServicesPreferredVersion",
]

EDGE_SWITCHES = [
    "--disable-field-trial-config",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-back-forward-cache",
    "--disable-breakpad",
    "--disable-component-extensions-with-background-pages",
    "--no-default-browser-check",
    "--disable-default-apps",
    # Chromium writes shared memory to /tmp instead, so no --shm-size is needed.
    "--disable-dev-shm-usage",
    "--disable-edgeupdater",
    "--disable-extensions",
    "--disable-features=" + ",".join(DISABLED_FEATURES),
    "--enable-features=CDPScreenshotNewSurface",
    "--allow-pre-commit-input",
    "--disable-hang-monitor",
    "--disable-ipc-flooding-protection",
    "--disable-prompt-on-repost",
    "--disable-renderer-backgrounding",
    "--disable-updater-scheduler",
    "--force-color-profile=srgb",
    "--metrics-recording-only",
    "--no-first-run",
    "--password-store=basic",
    "--use-mock-keychain",
    "--no-service-autorun",
    "--export-tagged-pdf",
    "--disable-search-engine-choice-screen",
    "--unsafely-disable-devtools-self-xss-warnings",
    "--edge-skip-compat-layer-relaunch",
    "--disable-infobars",
    "--disable-sync",
    # The container has no proxy; going direct keeps --host-resolver-rules in force.
    "--no-proxy-server",
]
