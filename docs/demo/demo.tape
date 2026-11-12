# The README recording. Re-record after UI changes, from the repo root:
#   uv run python docs/demo/render.py
# That runs this tape with vhs, adds the caption bar from the `#>` lines
# and writes docs/demo/demo.gif. Needs vhs
# (https://github.com/charmbracelet/vhs), ffmpeg and gifsicle.
#
# Caption lines: `#> keys | what they do`, shown from that point until the
# next caption. In keys, [x] draws a key cap; other words show as typed text.
# render.py times them from the commands below, so keep every pause an
# explicit Sleep.

Output docs/demo/raw.gif

Set Shell bash
Set FontSize 18
Set Width 1440
Set Height 800
Set Padding 14
Set TypingSpeed 55ms
Set Framerate 10

# Setup, not recorded: demo logs in a temp folder, a throwaway history
# folder (the real search history is never read or written), and a writer
# that appends new lines to api.jsonl later, for the follow-mode part.
Hide
Type "R=$PWD; D=$(mktemp -d); export XDG_DATA_HOME=$(mktemp -d) PATH=$R/.venv/bin:$PATH PS1='$ '"
Enter
Type "python $R/docs/demo/make_demo_logs.py $D && cd $D"
Enter
Type "(sleep 24; python $R/docs/demo/make_demo_logs.py $D --append) >/dev/null 2>&1 & disown; clear"
Enter
Sleep 500ms
Show

#> jlv api.jsonl worker.jsonl | Two log files, merged by time; rows coloured by level
Type "jlv api.jsonl worker.jsonl"
Sleep 300ms
Enter
Sleep 1.8s

#> [c] | Choose columns
Type "c"
Sleep 900ms

#> [space] [↓] | Pick @file, @timestamp, @level, @message
Space
Sleep 250ms
Down
Space
Sleep 250ms
Down
Space
Sleep 250ms
Down
Space
Sleep 500ms

#> [enter] | Columns line up both services, whatever they call the fields
Enter
Sleep 1.7s

#> [/] level:error http.status>=500 | Filter: a field match AND a number comparison
Type "/"
Sleep 300ms
Type@85ms "level:error http.status>=500"
Sleep 600ms

#> [enter] | Only the matching lines stay
Enter
Sleep 1.6s

#> [enter] | Detail view: the whole log as highlighted JSON
Enter
Sleep 2s

#> [k] | Previous log, without leaving the detail view
Type "k"
Sleep 1.3s

#> [esc] [/] failed [enter] | Full-text search
Escape
Sleep 300ms
Type "/"
Sleep 200ms
Ctrl+U
Type@85ms "failed"
Sleep 300ms
Enter
Sleep 700ms

#> [m] | Highlight mode: every line stays, matches stand out
Type "m"
Sleep 1.3s

#> [n] | Jump to the next match
Type "g"
Sleep 300ms
Type "n"
Sleep 600ms
Type "n"
Sleep 600ms
Type "n"
Sleep 500ms

#> [/] [ctrl+u] [enter] | Clear the query
Type "/"
Sleep 200ms
Ctrl+U
Sleep 300ms
Enter
Sleep 700ms

#> [f] | Follow mode: new lines stream in as they're written
Type "m"
Type "G"
Type "f"
Sleep 2.1s

#> [k] | Scrolled up to read: a badge counts the new lines
Type "kkkkk"
Sleep 2.4s

#> [G] | Back to the end
Type "G"
Sleep 1.6s
