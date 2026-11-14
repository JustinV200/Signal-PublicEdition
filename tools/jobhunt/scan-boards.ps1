# scan-boards.ps1: scans company job boards for new-grad roles (tools/jobhunt).
#
# The job run (life/areas/job-search/runbook.md, section 1) calls this at
# discovery so a hundred-plus boards never enter its context: it reads only the
# candidates file this writes. Boards come from a CSV:
#   company,ats,token,wd,site
# ats is greenhouse, ashby, lever or workday. For workday, token is the tenant,
# wd its host number (e.g. wd5) and site the career site name; the others leave
# wd and site blank. A board that fails to load is a warning, never fatal.
#
#   powershell -Command "& .\tools\jobhunt\scan-boards.ps1 -Boards boards.csv -Locations 'new york|nyc','remote' [-Tracker a.csv,b.csv]"
#
# Use -Command, not -File: -File passes each list as one comma-joined string.
#
# -Locations is a priority-ordered list of case-insensitive regexes; a role must
# match one, and its priority is the first one it matches (1 = best).
# -Tracker takes CSVs with company,title (and optionally url) columns; rows
# already in them are dropped. Writes .logs/candidates-<timestamp>.csv
# (priority,company,title,location,url,ats,match) and prints its path and count.

param(
    [Parameter(Mandatory)][string]$Boards,
    [Parameter(Mandatory)][string[]]$Locations,
    [string[]]$Tracker = @(),
    [string]$Out = (Join-Path $PSScriptRoot ('.logs\candidates-{0}.csv' -f (Get-Date -Format 'yyyy-MM-dd-HHmm'))),
    [int]$TimeoutSec = 20,
    # The graduating class searched for: next year from July on, else this year.
    [int]$GradYear = $(if ((Get-Date).Month -ge 7) { (Get-Date).Year + 1 } else { (Get-Date).Year })
)

$ErrorActionPreference = 'Stop'
# Invoke-WebRequest's progress bar slows big downloads several times over in 5.1.
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Title filters. A role must look technical, must not be senior or an
# internship, and must say new grad in its title or its description.
$TechnicalTitle = 'engineer|developer|scien|data|machine learning|\bai\b|\bml\b|software|quant|deploy|solutions|research'
$ExcludedTitle = '\b(senior|sr\.?|staff|principal|lead|manager|director|head of|intern(ship)?s?|summer|co-?op|fellow(ship)?|phds?|vp|vice president|architect|sales|strategist|banker|investor|instructor|ii|iii|iv)\b'
$NewGradTitle = "new ?grad|university grad|graduate|early.career|$GradYear|entry|junior|campus|college|engineer,? (i|1)\b|emerging talent|residency|apprentice"
# Description matches catch roles a title filter misses. Any body (title match
# or not) that asks for more experience or says it isn't for new grads is dropped.
$NewGradText = "new grad(uate)?s?\b|recent grad|entry.level|early.career|class of $GradYear|(?<!\d)0\s*[-\u2013]\s*2 years"
# \u2013 is an en dash (kept as an escape: PowerShell 5.1 reads BOM-less files as ANSI).
# A count of 2+ years (10+, 3+, 1-3+, "3 years of experience"), but not a
# range starting at 0 such as 0-2 years.
$YearsCount = '(?<!\b0\s*[-\u2013]\s*)\b([2-9]|[1-9]\d)'
$ExperiencedText = "$YearsCount\+\s*years|$YearsCount\s*(or more\s+)?years?(\s+of)?(\s+\w+){0,3}\s+experience|not (a |an )?(new.grad|entry.level)"
$WorkdayPageSize = 20
# Workday has no description text, so its search box does the new-grad part.
$WorkdaySearch = @('new grad software engineer', "software engineer $GradYear", 'early career')

function Invoke-Json([string]$Uri, [string]$Body) {
    # GETs (or POSTs $Body as JSON) and parses the reply as UTF-8 JSON.
    # Invoke-RestMethod in PowerShell 5.1 reads replies without a charset as
    # Latin-1, which garbles dashes and accents in titles.
    $request = @{ Uri = $Uri; TimeoutSec = $TimeoutSec; UseBasicParsing = $true }
    if ($Body) { $request += @{ Method = 'Post'; Body = $Body; ContentType = 'application/json' } }
    $response = Invoke-WebRequest @request
    return [Text.Encoding]::UTF8.GetString($response.RawContentStream.ToArray()) | ConvertFrom-Json
}

function Get-BoardJobs($Board) {
    # Returns one board's jobs as @{title; location; url; text}. Throws on a
    # network or parse failure (the caller turns that into a warning).
    $token = $Board.token
    switch ($Board.ats) {
        'greenhouse' {
            $data = Invoke-Json "https://boards-api.greenhouse.io/v1/boards/$token/jobs?content=true"
            # content is HTML, itself HTML-escaped.
            foreach ($job in $data.jobs) {
                @{ title = $job.title; location = $job.location.name; url = $job.absolute_url
                   text = [Net.WebUtility]::HtmlDecode([Net.WebUtility]::HtmlDecode("$($job.content)")) -replace '<[^>]+>', ' ' }
            }
        }
        'ashby' {
            $data = Invoke-Json "https://api.ashbyhq.com/posting-api/job-board/$token"
            # isRemote is unreliable; workplaceType says Remote when it is.
            foreach ($job in $data.jobs) {
                $places = @($job.location) + @($job.secondaryLocations | ForEach-Object { $_.location })
                @{ title = $job.title; location = (Join-Places $places $job.workplaceType); url = $job.jobUrl; text = $job.descriptionPlain }
            }
        }
        'lever' {
            $data = Invoke-Json "https://api.lever.co/v0/postings/${token}?mode=json"
            # The requirements sit in lists[] (HTML) and additionalPlain.
            foreach ($job in $data) {
                $places = @($job.categories.location) + @($job.categories.allLocations)
                $text = (@($job.descriptionPlain, $job.additionalPlain) + @($job.lists | ForEach-Object { $_.content })) -join ' '
                @{ title = $job.text; location = (Join-Places $places $job.workplaceType); url = $job.hostedUrl
                   text = [Net.WebUtility]::HtmlDecode($text) -replace '<[^>]+>', ' ' }
            }
        }
        'workday' { Get-WorkdayJobs $Board }
        default { throw "unknown ats '$($Board.ats)'" }
    }
}

function Join-Places($Places, [string]$WorkplaceType) {
    # One location string. The workplace type (e.g. Remote) is used only when
    # there's no named place, so "Toronto, Canada" + Remote can't pass as remote.
    $named = @($Places | Where-Object { $_ } | Select-Object -Unique)
    if ($named.Count) { return $named -join '; ' }
    return $WorkplaceType
}

function Get-WorkdayJobs($Board) {
    # Workday's CXS search API: one page per search term, deduped by path.
    # locationsText can be "3 Locations", so the path's first segment (the
    # primary location) is added to the location.
    $hostName = "$($Board.token).$($Board.wd).myworkdayjobs.com"
    $api = "https://$hostName/wday/cxs/$($Board.token)/$($Board.site)/jobs"
    $seen = @{}
    foreach ($term in $WorkdaySearch) {
        $body = @{ appliedFacets = @{}; limit = $WorkdayPageSize; offset = 0; searchText = $term } | ConvertTo-Json
        $data = Invoke-Json $api $body
        foreach ($job in $data.jobPostings) {
            if ($seen.ContainsKey($job.externalPath)) { continue }
            $seen[$job.externalPath] = $true
            $primary = ($job.externalPath -split '/')[2] -replace '-', ' '
            @{ title = $job.title; location = "$($job.locationsText); $primary"; url = "https://$hostName/$($Board.site)$($job.externalPath)"; text = '' }
        }
    }
}

function Get-MatchReason($Job) {
    # Why a job is a new-grad candidate ('title' or 'desc: <phrase>'), or $null.
    # A body asking for 2+ years rules a job out even when its title says new grad.
    if ($Job.title -match $ExcludedTitle -or $Job.title -notmatch $TechnicalTitle) { return $null }
    if ($Job.text -match $ExperiencedText) { return $null }
    if ($Job.title -match $NewGradTitle) { return 'title' }
    if ($Job.text -match $NewGradText) { return "desc: $($Matches[0])" }
    return $null
}

function Get-LocationPriority([string]$Location) {
    # 1-based index of the first -Locations pattern the location matches, or 0.
    for ($i = 0; $i -lt $Locations.Count; $i++) {
        if ($Location -match $Locations[$i]) { return $i + 1 }
    }
    return 0
}

function ConvertTo-UrlKey([string]$Url) {
    # The runbook's url key (section 1): lowercase, no trailing slash, query
    # string dropped except a gh_jid value, kept as ?gh_jid=<id> (some
    # Greenhouse boards put the job id only there).
    $lowerUrl = $Url.ToLower()
    $jobId = if ($lowerUrl -match '[?&]gh_jid=(\d+)') { '?gh_jid=' + $Matches[1] } else { '' }
    return ($lowerUrl -replace '[?#].*$', '').TrimEnd('/') + $jobId
}

function ConvertTo-NameKey([string]$Company, [string]$Title) {
    # Company + title with case, spaces and punctuation ignored.
    return (($Company + '|' + $Title).ToLower() -replace '[^a-z0-9|]', '')
}

function Read-TrackerKeys([string[]]$Paths) {
    # Every url key and company+title key in the tracker CSVs.
    $keys = @{}
    foreach ($path in $Paths) {
        foreach ($row in (Import-Csv $path)) {
            if ($row.url) { $keys[(ConvertTo-UrlKey $row.url)] = $true }
            $keys[(ConvertTo-NameKey $row.company $row.title)] = $true
        }
    }
    return $keys
}

function Find-Candidates($BoardRows, $Seen) {
    # Scans every board and returns the candidate rows. $Seen holds the tracker
    # keys; candidates are added to it so a job listed twice comes out once.
    $failed = 0
    $rows = foreach ($board in $BoardRows) {
        try { $jobs = @(Get-BoardJobs $board) }
        catch {
            Write-Warning "board $($board.company) ($($board.ats)/$($board.token)) failed: $($_.Exception.Message)"
            $failed++
            continue
        }
        foreach ($job in $jobs) {
            if (-not $job.url) { continue }  # nothing to apply on or dedupe by
            $priority = Get-LocationPriority $job.location
            if ($priority -eq 0) { continue }
            $reason = Get-MatchReason $job
            if (-not $reason) { continue }
            $keys = @((ConvertTo-UrlKey $job.url), (ConvertTo-NameKey $board.company $job.title))
            if ($Seen.ContainsKey($keys[0]) -or $Seen.ContainsKey($keys[1])) { continue }
            $keys | ForEach-Object { $Seen[$_] = $true }
            [pscustomobject]@{ priority = $priority; company = $board.company; title = $job.title
                location = $job.location; url = $job.url; ats = $board.ats; match = $reason }
        }
    }
    return @{ rows = @($rows); failed = $failed }
}

# powershell -File doesn't split a,b into an array, so the patterns would
# arrive as one comma-joined string that matches nothing sensible. Refuse that
# loudly (so a lone pattern can't contain a comma; pass two or more instead).
if ($Locations.Count -eq 1 -and $Locations[0].Contains(',')) {
    throw "-Locations arrived as one string ($($Locations[0])); call the script with powershell -Command, not -File"
}
$boardRows = @(Import-Csv $Boards | Where-Object { $_.company -and $_.ats -and $_.token })
$result = Find-Candidates $boardRows (Read-TrackerKeys $Tracker)
New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null
$header = 'priority,company,title,location,url,ats,match'
if ($result.rows.Count) { $result.rows | Sort-Object priority, company | Export-Csv $Out -NoTypeInformation -Encoding utf8 }
else { Set-Content $Out $header -Encoding utf8 }  # Export-Csv writes nothing for no rows.
"$($result.rows.Count) candidates from $($boardRows.Count) boards ($($result.failed) failed) -> $Out"
