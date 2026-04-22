$port = if ($env:PORT) { $env:PORT } else { 3001 }
$root = Join-Path $PSScriptRoot "public"
$dataFile = Join-Path $PSScriptRoot "data\alphabet.json"

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$port/")
$listener.Start()
Write-Host "🌴 الأبجدية السعودية: http://localhost:$port/"

function Get-Data {
    $content = [IO.File]::ReadAllText($dataFile, [System.Text.Encoding]::UTF8)
    return $content | ConvertFrom-Json
}
function Save-Data($data) {
    $json = $data | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($dataFile, $json, [System.Text.Encoding]::UTF8)
}
function Send-Json($res, $obj, $code=200) {
    $json = $obj | ConvertTo-Json -Depth 10 -Compress
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    $res.StatusCode = $code
    $res.ContentType = "application/json; charset=utf-8"
    $res.ContentLength64 = $bytes.Length
    $res.OutputStream.Write($bytes, 0, $bytes.Length)
    $res.Close()
}
function Send-Static($res, $filePath) {
    $bytes = [IO.File]::ReadAllBytes($filePath)
    $res.ContentLength64 = $bytes.Length
    if    ($filePath -match '\.html$') { $res.ContentType = 'text/html; charset=utf-8' }
    elseif($filePath -match '\.js$')   { $res.ContentType = 'application/javascript' }
    elseif($filePath -match '\.css$')  { $res.ContentType = 'text/css' }
    elseif($filePath -match '\.json$') { $res.ContentType = 'application/json' }
    else                               { $res.ContentType = 'application/octet-stream' }
    $res.OutputStream.Write($bytes, 0, $bytes.Length)
    $res.Close()
}

while ($listener.IsListening) {
    $ctx = $listener.GetContext()
    $req = $ctx.Request
    $res = $ctx.Response
    $res.Headers.Add("Access-Control-Allow-Origin", "*")

    $path = $req.Url.LocalPath

    # Handle OPTIONS (CORS preflight)
    if ($req.HttpMethod -eq 'OPTIONS') {
        $res.Headers.Add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        $res.Headers.Add("Access-Control-Allow-Headers", "Content-Type")
        $res.StatusCode = 200
        $res.Close()
        continue
    }

    # ===== API ROUTES =====
    if ($path -eq '/api/alphabet' -and $req.HttpMethod -eq 'GET') {
        $data = Get-Data
        Send-Json $res $data

    } elseif ($path -eq '/api/submit' -and $req.HttpMethod -eq 'POST') {
        $bodyRaw = New-Object IO.StreamReader $req.InputStream
        $body = $bodyRaw.ReadToEnd() | ConvertFrom-Json
        $data = Get-Data
        $idx = [int]$body.letterIndex
        if ($idx -lt 0 -or $idx -ge $data.letters.Count) {
            Send-Json $res @{error='حرف غير صحيح'} 400
        } elseif ($data.letters[$idx].status -ne 'empty') {
            Send-Json $res @{error='هذا الحرف مأخوذ بالفعل'} 400
        } elseif (-not $body.word -or $body.word.Trim().Length -lt 2) {
            Send-Json $res @{error='الكلمة قصيرة جداً'} 400
        } else {
            $letter = $data.letters[$idx]
            $letter.status    = 'pending'
            $letter.word      = $body.word.Trim()
            $letter.emoji     = if ($body.emoji) { $body.emoji } else { '✨' }
            $letter.submitter = if ($body.submitter) { $body.submitter } else { 'مجهول' }
            $letter.votes     = 0
            $letter.upvotes   = 0
            $letter.downvotes = 0
            $activity = @{text="$($letter.submitter) اقترح كلمة `"$($letter.word)`" للحرف $($letter.letter) 🟡"; time='منذ لحظة'}
            $data.activity = @($activity) + @($data.activity | Select-Object -First 19)
            Save-Data $data
            Send-Json $res @{success=$true; letter=$letter}
        }

    } elseif ($path -eq '/api/vote' -and $req.HttpMethod -eq 'POST') {
        $bodyRaw = New-Object IO.StreamReader $req.InputStream
        $body = $bodyRaw.ReadToEnd() | ConvertFrom-Json
        $data = Get-Data
        $idx = [int]$body.letterIndex
        if ($idx -lt 0 -or $idx -ge $data.letters.Count) {
            Send-Json $res @{error='حرف غير صحيح'} 400
        } elseif ($data.letters[$idx].status -ne 'pending') {
            Send-Json $res @{error='لا يوجد اقتراح للتصويت عليه'} 400
        } else {
            $letter = $data.letters[$idx]
            if ($body.vote -eq 'up') {
                $letter.upvotes = [int]$letter.upvotes + 1
                if ([int]$letter.upvotes -ge 3) {
                    $letter.status = 'approved'
                    $act = @{text="تم اعتماد كلمة `"$($letter.word)`" للحرف $($letter.letter) ✅"; time='منذ لحظة'}
                    $data.activity = @($act) + @($data.activity | Select-Object -First 19)
                }
            } else {
                $letter.downvotes = [int]$letter.downvotes + 1
                if ([int]$letter.downvotes -ge 3) {
                    $rejected = $letter.word
                    $letter.status = 'empty'; $letter.word = ''; $letter.emoji = ''
                    $letter.submitter = ''; $letter.votes = 0; $letter.upvotes = 0; $letter.downvotes = 0
                    $act = @{text="تم رفض كلمة `"$rejected`" ❌"; time='منذ لحظة'}
                    $data.activity = @($act) + @($data.activity | Select-Object -First 19)
                }
            }
            Save-Data $data
            Send-Json $res @{success=$true; letter=$letter}
        }

    # ===== STATIC FILES =====
    } else {
        $p = $path.TrimStart('/')
        if ($p -eq '' -or $p -eq '/') { $p = 'index.html' }
        $fp = Join-Path $root $p
        if (Test-Path $fp -PathType Leaf) {
            Send-Static $res $fp
        } else {
            # Fallback to index.html (SPA)
            $index = Join-Path $root 'index.html'
            if (Test-Path $index) { Send-Static $res $index }
            else {
                $res.StatusCode = 404
                $res.Close()
            }
        }
    }
}
