# tailor-resume.Tests.ps1: Pester 3 tests for tailor-resume.ps1 (tools/jobhunt).
# Builds a small made-up base resume with Word, so no real resume is needed.
# Every case is skipped when Word isn't installed (e.g. Linux). Each case starts
# Word, so the file takes about a minute.
#
#   powershell -NoProfile -Command "Invoke-Pester tools\jobhunt\tailor-resume.Tests.ps1"

$script = Join-Path $PSScriptRoot 'tailor-resume.ps1'
Add-Type -AssemblyName System.IO.Compression.FileSystem

# Word's "save as .docx" format (WdSaveFormat.wdFormatDocumentDefault).
$wdFormatDocumentDefault = 16
# Made-up fixture lines; "Built" starts two of them on purpose (the ambiguous case).
$fixtureLines = @(
    'Projects',
    'Signal Parser | Python',
    'Built a log parser for build output.',
    'Built a small cache for API calls.',
    'Wrote integration tests for the CLI.',
    'Experience',
    'Data intern, Example Labs',
    'Cleaned survey data for a weekly report.'
)

function Test-Word {
    # True when Word's COM server can be started here.
    try {
        $word = New-Object -ComObject Word.Application
        $word.Quit()
        return $true
    } catch { return $false }
}

function New-FixtureResume([string]$Path) {
    # Writes a one-page .docx with the fixture lines and a bold project title.
    $word = New-Object -ComObject Word.Application
    try {
        $doc = $word.Documents.Add()
        $doc.Content.Text = $fixtureLines -join "`r"
        $title = $doc.Paragraphs.Item(2).Range
        $title.SetRange($title.Start, $title.Start + 'Signal Parser'.Length)
        $title.Bold = $true
        $doc.SaveAs2($Path, $wdFormatDocumentDefault)
        $doc.Close($false)
    } finally {
        $word.Quit()
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    }
}

function New-Spec([string]$Dir, $Edits) {
    # Writes an edits.json for the script and returns its path.
    $path = Join-Path $Dir 'edits.json'
    @{ edits = $Edits } | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 $path
    return $path
}

function Get-DocumentXml([string]$DocxPath) {
    # The raw word/document.xml of a .docx, to check runs and formatting.
    $zip = [System.IO.Compression.ZipFile]::OpenRead($DocxPath)
    try {
        $reader = New-Object System.IO.StreamReader($zip.GetEntry('word/document.xml').Open())
        try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
    } finally { $zip.Dispose() }
}

Describe 'tailor-resume.ps1' {
    $noWord = -not (Test-Word)
    $outDir = Join-Path $TestDrive 'tailored'
    $base = Join-Path $TestDrive 'base.docx'
    if (-not $noWord) { New-FixtureResume $base }

    It 'applies every edit kind, keeps formatting and writes a one-page PDF' -Skip:$noWord {
        $spec = New-Spec $TestDrive @(
            @{ find = 'Signal Parser'; replace = 'Signal Tool' },
            @{ find = 'Cleaned survey data'; paragraph = 'Rewritten bullet text.' },
            @{ find = 'Rewritten bullet text.'; insertAfter = 'Inserted bullet text.' },
            @{ find = 'Wrote integration tests'; delete = $true }
        )
        $pdf = & $script -Base $base -Spec $spec -Name 'case-ok' -OutDir $outDir
        $pdf | Should Be (Join-Path $outDir 'case-ok.pdf')
        Test-Path $pdf | Should Be $true
        $xml = Get-DocumentXml (Join-Path $outDir 'case-ok.docx')
        # The renamed project title is still in a bold run.
        $xml | Should Match '<w:b/>(?:(?!</w:r>).)*Signal Tool'
        $xml | Should Match 'Inserted bullet text\.'
        $xml | Should Not Match 'integration tests'
        $xml | Should Not Match 'survey data'
    }

    $failures = @(
        @{ label = 'missing text'; edits = @(@{ find = 'No such text anywhere'; replace = 'x' }) },
        @{ label = 'ambiguous text'; edits = @(@{ find = 'Built'; replace = 'Made' }) },
        @{ label = 'two pages'; edits = @(@{ find = 'Signal Parser'; insertAfter = ('Filler line. ' * 400) }) }
    )
    foreach ($case in $failures) {
        It "refuses and leaves no files on $($case.label)" -Skip:$noWord {
            $name = 'case-' + ($case.label -replace ' ', '-')
            $spec = New-Spec $TestDrive $case.edits
            { & $script -Base $base -Spec $spec -Name $name -OutDir $outDir } | Should Throw
            Test-Path (Join-Path $outDir "$name.docx") | Should Be $false
            Test-Path (Join-Path $outDir "$name.pdf") | Should Be $false
        }
    }
}
