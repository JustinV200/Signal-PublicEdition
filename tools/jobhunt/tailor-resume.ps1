# tailor-resume.ps1: makes a tailored copy of the base resume from a JSON edit
# list, through Word (COM), and exports it to PDF (tools/jobhunt, used by
# life/areas/job-search/runbook.md section 4, "Tailored resume").
# Windows only: it needs Microsoft Word. Without Word it fails, and the run
# uploads the base resume instead.
#
# The text edits are chosen by the run's tailoring subagent; this script only
# applies them, so the base .docx's layout and fonts stay as they are.
# It refuses (exit 1, no output left behind) if an edit's text isn't found
# exactly once or the result is longer than one page.
#
#   tailor-resume.ps1 -Base resume.docx -List                                 # base paragraphs, exact text
#   tailor-resume.ps1 -Base resume.docx -Spec edits.json -Name 2026-11-13-acme-swe
#
# -Base is the Word file the owner's resume PDF was made from (profile.md,
# "Resume Word file"). edits.json: {"edits": [ ... ]}, applied in order. Each
# edit has "find", a unique snippet (at most 255 characters) of the current
# text, and one of:
#   "replace": "t"       replace just the snippet; keeps its formatting (use this
#                        on lines with mixed bold/plain text or links)
#   "paragraph": "t"     replace the whole paragraph holding the snippet
#   "insertAfter": "t"   add a paragraph with the same style after that one
#   "delete": true       remove that paragraph
# Writes resume/tailored/<Name>.docx and .pdf and prints the PDF path.

param(
    # Not Mandatory: a missing one would prompt and hang an unattended run.
    [string]$Base,
    [switch]$List,
    [string]$Spec,
    [string]$Name,
    [string]$OutDir = (Join-Path $PSScriptRoot '..\..\life\areas\job-search\resume\tailored')
)

$ErrorActionPreference = 'Stop'

# Word constants (WdUnits, WdFindWrap, WdCollapseDirection, WdStatistic,
# WdSaveFormat, WdAlertLevel).
$wdCharacter = 1
$wdFindStop = 0
$wdCollapseEnd = 0
$wdStatisticPages = 2
$wdFormatPDF = 17
$wdAlertsNone = 0
# Word's Find.Text limit.
$maxFindLength = 255
$maxPages = 1

function Find-Unique($Doc, [string]$Text) {
    # Returns the Range of the one match of $Text (case-sensitive, literal).
    # Throws if it's too long, missing, or matches more than once.
    if ($Text.Length -eq 0 -or $Text.Length -gt $maxFindLength) {
        throw "find must be 1-$maxFindLength characters: '$Text'"
    }
    $found = @()
    $range = $Doc.Content
    $find = $range.Find
    $find.ClearFormatting()
    # '^' starts Word's special codes (^p etc.), so a literal one is doubled.
    $find.Text = $Text.Replace('^', '^^')
    $find.MatchCase = $true
    $find.MatchWildcards = $false
    $find.Forward = $true
    $find.Wrap = $wdFindStop
    while ($find.Execute()) {
        $found += $Doc.Range($range.Start, $range.End)
        $range.Collapse($wdCollapseEnd)
    }
    if ($found.Count -ne 1) { throw "found $($found.Count) times (need 1): '$Text'" }
    return $found[0]
}

function Get-TextRange($Paragraph) {
    # The paragraph's range without its closing paragraph mark.
    $range = $Paragraph.Range
    [void]$range.MoveEnd($wdCharacter, -1)
    return $range
}

function Invoke-Edit($Doc, $Edit) {
    # Applies one edit (see the header for the kinds).
    $match = Find-Unique $Doc ([string]$Edit.find)
    $paragraph = $match.Paragraphs.Item(1)
    if ($null -ne $Edit.replace) { $match.Text = [string]$Edit.replace; return }
    if ($null -ne $Edit.paragraph) { (Get-TextRange $paragraph).Text = [string]$Edit.paragraph; return }
    if ($null -ne $Edit.insertAfter) {
        # A new paragraph after this one inherits its style and bullet. It's found
        # by position: on the document's last paragraph, Next() comes back null.
        $end = $paragraph.Range.End
        $paragraph.Range.InsertParagraphAfter()
        (Get-TextRange $Doc.Range($end, $end).Paragraphs.Item(1)).Text = [string]$Edit.insertAfter
        return
    }
    if ($Edit.delete -eq $true) { $paragraph.Range.Delete() | Out-Null; return }
    throw "edit has no replace, paragraph, insertAfter or delete: '$($Edit.find)'"
}

function Read-Edits([string]$Path) {
    # Loads and checks the edit list from the JSON spec file.
    $data = Get-Content -Raw -Encoding utf8 $Path | ConvertFrom-Json
    if ($null -eq $data.edits -or @($data.edits).Count -eq 0) { throw "no edits in $Path" }
    return @($data.edits)
}

function Write-Tailored($Word, [string]$DocxPath, [string]$PdfPath, $Edits) {
    # Edits the copy at $DocxPath in place, checks the page count, saves, exports PDF.
    $doc = $Word.Documents.Open($DocxPath)
    try {
        foreach ($edit in $Edits) { Invoke-Edit $doc $edit }
        $doc.Repaginate()
        $pages = $doc.ComputeStatistics($wdStatisticPages)
        if ($pages -gt $maxPages) { throw "tailored resume is $pages pages (max $maxPages)" }
        $doc.Save()
        $doc.SaveAs2($PdfPath, $wdFormatPDF)
    } finally {
        $doc.Close($false)
    }
}

function Show-Paragraphs($Word, [string]$Path) {
    # Prints each non-empty paragraph of $Path, so edits can quote exact text.
    # Open(FileName, ConfirmConversions = false, ReadOnly = true)
    $doc = $Word.Documents.Open($Path, $false, $true)
    try {
        foreach ($paragraph in $doc.Paragraphs) {
            $text = (Get-TextRange $paragraph).Text
            if ($text -and $text.Trim()) { Write-Output $text }
        }
    } finally {
        $doc.Close($false)
    }
}

if (-not $Base -or $Base -notmatch '\.docx$') { throw 'give -Base <the resume .docx>' }
if (-not $List -and (-not $Spec -or -not $Name)) { throw 'use -List, or -Spec <edits.json> -Name <file name>' }
# The name becomes a file name: keep it to a safe slug.
if ($Name -and $Name -notmatch '^[a-z0-9][a-z0-9-]{0,120}$') { throw "bad -Name '$Name' (lowercase letters, digits, hyphens)" }

$basePath = (Resolve-Path $Base).Path
# CreateObject gives a fresh Word instance, so Quit never touches the owner's open documents.
$word = New-Object -ComObject Word.Application
try {
    $word.Visible = $false
    $word.DisplayAlerts = $wdAlertsNone
    if ($List) {
        # UTF-8 so dashes and curly quotes come out exactly as Word has them.
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        Show-Paragraphs $word $basePath
        return
    }
    $edits = Read-Edits $Spec
    New-Item -ItemType Directory -Force $OutDir | Out-Null
    $docxPath = Join-Path (Resolve-Path $OutDir).Path "$Name.docx"
    $pdfPath = [System.IO.Path]::ChangeExtension($docxPath, '.pdf')
    if ((Test-Path $docxPath) -or (Test-Path $pdfPath)) { throw "$Name already exists in $OutDir" }
    Copy-Item $basePath $docxPath
    try {
        Write-Tailored $word $docxPath $pdfPath $edits
    } catch {
        # Leave nothing half-made: the run then uploads the base resume.
        Remove-Item $docxPath, $pdfPath -ErrorAction SilentlyContinue
        throw
    }
    Write-Output $pdfPath
} finally {
    $word.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
}
