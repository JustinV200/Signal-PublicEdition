# scan-boards.Tests.ps1: Pester 3 tests for scan-boards.ps1 (tools/jobhunt).
# No network: Invoke-WebRequest is mocked with fake replies in each ATS's shape.
#
#   powershell -NoProfile -Command "Invoke-Pester tools\jobhunt\scan-boards.Tests.ps1"

$script = Join-Path $PSScriptRoot 'scan-boards.ps1'
$locations = @('new york|nyc', 'remote')

# The same jobs on every board. `need` is the requirements text: Lever puts it
# in lists[] (HTML), the others in the description. Workday has no
# description text, so only the title-based rules apply there.
$fakeJobs = @(
    @{ title = 'Software Engineer, New Grad'; location = 'New York, NY'; text = 'Build things.' },
    @{ title = 'Senior Software Engineer'; location = 'New York, NY'; text = 'New grads welcome.' },
    @{ title = 'Software Engineer, New Grad'; location = 'San Francisco, CA'; text = 'Build things.' },
    @{ title = 'Backend Engineer'; location = 'Remote'; text = 'Great for new grads.' },
    @{ title = 'Platform Engineer'; location = 'New York, NY'; text = 'New grads apply.'; need = 'Needs 3+ years of Go.' },
    @{ title = 'Data Engineer'; location = 'New York, NY'; text = 'New graduates welcome.'; need = '1-3+ years of SQL.' },
    @{ title = 'Software Developer'; location = 'New York, NY'; text = 'New graduates welcome.'; need = '3 years of professional experience.' },
    @{ title = 'Quant Developer'; location = 'New York, NY'; text = 'New graduates welcome.'; need = '10+ years in markets.' },
    @{ title = 'ML Engineer'; location = 'New York, NY'; text = 'New graduates welcome.'; need = '0-2 years of experience.' },
    # A new-grad title doesn't override a body asking for 3+ years.
    @{ title = 'Infra Engineer, New Grad'; location = 'New York, NY'; text = 'Build things.'; need = '3+ years of Linux.' },
    # Title noise: "AI" alone isn't an engineering role.
    @{ title = 'AI Strategist, New Grad'; location = 'New York, NY'; text = 'Build things.' },
    # A named non-US place plus a Remote workplace type is not a remote match.
    @{ title = 'Software Engineer, Early Career'; location = 'Toronto, Canada'; workplace = 'Remote'; text = 'Build things.' },
    # No url (skipped, not fatal) on the boards that give one.
    @{ title = 'Software Engineer, Junior'; location = 'New York, NY'; text = 'Build things.'; noUrl = $true }
)

function New-FakeJob([string]$Ats, $Job, [int]$Index) {
    # One fake job in an ATS's shape. Greenhouse urls differ only by gh_jid, as
    # on some real boards (regression: dropping the whole query string merged them).
    $url = if ($Job.noUrl) { $null } elseif ($Ats -eq 'greenhouse') { "https://example.com/careers?gh_jid=$Index" } else { "https://example.com/$Ats/$Index" }
    $workplace = if ($Job.workplace) { $Job.workplace } else { 'OnSite' }
    $text = "$($Job.text) $($Job.need)"
    switch ($Ats) {
        'greenhouse' { @{ title = $Job.title; location = @{ name = $Job.location }; absolute_url = $url
            content = [Net.WebUtility]::HtmlEncode("<p>$text</p>") } }
        'ashby' { @{ title = $Job.title; location = $Job.location; secondaryLocations = @(); workplaceType = $workplace
            jobUrl = $url; descriptionPlain = $text } }
        'lever' { @{ text = $Job.title; categories = @{ location = $Job.location; allLocations = @($Job.location) }
            workplaceType = $workplace; hostedUrl = $url; descriptionPlain = $Job.text
            lists = @(@{ text = 'Requirements'; content = "<li>$($Job.need)</li>" }) } }
        'workday' { @{ title = $Job.title; locationsText = $Job.location; externalPath = "/job/$($Job.location -replace '\W', '-')/x_$Index" } }
    }
}

function New-FakeReply([string]$Ats) {
    # $fakeJobs as one ATS's API reply, wrapped like an Invoke-WebRequest result.
    $i = 0
    $jobs = foreach ($job in $fakeJobs) { $i++; New-FakeJob $Ats $job $i }
    $reply = switch ($Ats) { 'greenhouse' { @{ jobs = @($jobs) } } 'ashby' { @{ jobs = @($jobs) } }
        'lever' { , @($jobs) } 'workday' { @{ jobPostings = @($jobs) } } }
    $bytes = [Text.Encoding]::UTF8.GetBytes((ConvertTo-Json $reply -Depth 6))
    return [pscustomobject]@{ RawContentStream = New-Object IO.MemoryStream (, $bytes) }
}

function Invoke-Scan([string]$Dir, [string]$BoardsCsv, [string[]]$Tracker = @()) {
    # Writes the boards CSV, runs the scanner and returns its candidate rows.
    $boards = Join-Path $Dir 'boards.csv'
    Set-Content $boards ("company,ats,token,wd,site`n" + $BoardsCsv) -Encoding utf8
    $out = Join-Path $Dir 'candidates.csv'
    & $script -Boards $boards -Locations $locations -Tracker $Tracker -Out $out 3>$null | Out-Null
    return @(Import-Csv $out)
}

function Format-Rows($Rows) {
    # Candidate rows as one sorted 'priority|match|title' string, order-independent.
    return (@($Rows | ForEach-Object { "$($_.priority)|$($_.match)|$($_.title)" }) | Sort-Object) -join ';'
}

Describe 'scan-boards.ps1' {
    Mock Invoke-WebRequest {
        if ($Uri -match 'broken') { throw 'connection refused' }
        $ats = switch -Regex ($Uri) { 'greenhouse' { 'greenhouse' } 'ashby' { 'ashby' } 'lever' { 'lever' } default { 'workday' } }
        New-FakeReply $ats
    }

    $withText = @('1|desc: New graduates|ML Engineer', '1|title|Software Engineer, New Grad', '2|desc: new grads|Backend Engineer')
    $cases = @(
        @{ ats = 'greenhouse'; row = 'Acme,greenhouse,acme,,'; expected = $withText },
        @{ ats = 'ashby'; row = 'Acme,ashby,acme,,'; expected = $withText },
        @{ ats = 'lever'; row = 'Acme,lever,acme,,'; expected = $withText },
        # Workday has no body text (Infra stays) and always a url (Junior stays).
        @{ ats = 'workday'; row = 'Acme,workday,acme,wd5,External'; expected = @('1|title|Infra Engineer, New Grad', '1|title|Software Engineer, Junior', '1|title|Software Engineer, New Grad') }
    )
    foreach ($case in $cases) {
        It "keeps only new-grad roles in the given locations, ranked, on $($case.ats)" {
            Format-Rows (Invoke-Scan $TestDrive $case.row) | Should Be ($case.expected -join ';')
        }
    }

    It 'drops jobs already in a tracker, by url or by company and title' {
        $tracker = Join-Path $TestDrive 'applications.csv'
        # One row by url (lowercase, other query values and trailing slash ignored), one by
        # company + title with case and punctuation ignored.
        Set-Content $tracker @(
            'date,company,title,location,url,ats,status,notes',
            '2026-11-01,Other,Other role,,https://EXAMPLE.com/careers/?ref=list&gh_jid=1,greenhouse,applied,',
            '2026-11-01,ACME Inc,backend engineer,,,greenhouse,applied,'
        ) -Encoding utf8
        $rows = Invoke-Scan $TestDrive 'Acme Inc,greenhouse,acme,,' @($tracker)
        @($rows | ForEach-Object title) -join ';' | Should Be 'ML Engineer'
    }

    It 'warns about a failing board and still scans the rest' {
        $rows = Invoke-Scan $TestDrive "Broken,ashby,broken,,`nAcme,lever,acme,,"
        @($rows | ForEach-Object company | Select-Object -Unique) -join ';' | Should Be 'Acme'
        $rows.Count | Should Be 3
    }
}
