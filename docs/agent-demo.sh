#!/usr/bin/env bash
# Regenerates docs/agent-demo.gif: a coding agent's commit is blocked by
# ratchet's git hook, and the agent stops to ask the human instead of
# cutting code.
#
# Two phases:
#   capture  build a tiny demo repo, install ratchet + its git hook, and run
#            a REAL headless Claude Code session (`claude -p`) asked to
#            "commit these changes". Every command's output and every agent
#            turn is saved verbatim to docs/agent-demo.jsonl.
#   play     replay docs/agent-demo.jsonl at reading speed inside an
#            asciinema recording, then render the gif with agg. Nothing on
#            screen is typed by hand: it is all from the capture.
#
# Requires on PATH: claude (capture only), jq, curl, asciinema, agg.
#
# Usage: docs/agent-demo.sh            # capture, then render
#        docs/agent-demo.sh --replay   # render from the committed capture
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="$REPO_ROOT/docs/agent-demo.jsonl"
GIF="$REPO_ROOT/docs/agent-demo.gif"
HOOK_URL="https://raw.githubusercontent.com/krishansubudhi/ratchet/main/integrations/git/pre-commit"
TOOLS=("Bash(git:*)" "Bash(ratchet budget:*)" "Bash(ratchet check:*)")

rec() { jq -nc --arg k "$1" --arg t "$2" '{k: $k, t: $t}' >> "$LOG"; }

# run a human's command in the demo repo and record it with its real output
run() {
  local out
  out="$(RATCHET_AGENT=0 bash -c "$1" 2>&1)" || true
  rec cmd "$1"
  [ -n "$out" ] && rec out "$out"
  return 0
}

# run one agent turn and record its tool calls, tool output and replies
agent() {
  local prompt="$1"; shift
  rec user "$prompt"
  env -u CLAUDECODE claude -p "$prompt" "$@" --model "${AGENT_MODEL:-sonnet}" \
      --allowedTools "${TOOLS[@]}" --output-format stream-json --verbose \
    > "$WORK/turn.jsonl"
  jq -c 'select(.type == "assistant" or .type == "user") | .message.content[]?
    | select(type == "object")
    | if .type == "text" then {k: "say", t: .text}
      elif .type == "tool_use" then {k: "tool", t: .input.command}
      elif .type == "tool_result" then {k: "result",
        t: (.content | if type == "array" then map(.text) | join("") else . end)}
      else empty end' "$WORK/turn.jsonl" >> "$LOG"
  SESSION="$(jq -r 'select(.type == "result") | .session_id' "$WORK/turn.jsonl")"
}

capture() {
  python3 -m venv "$WORK/venv"
  "$WORK/venv/bin/pip" install --quiet "ratchet-size==${RATCHET_VERSION:-0.2.1}"
  export PATH="$WORK/venv/bin:$PATH"

  mkdir -p "$WORK/demo/app" "$WORK/demo/tests"
  cd "$WORK/demo"
  git init -q && git config user.name "Demo User" && git config user.email demo@example.com
  printf 'def greet(name):\n    return f"hello, {name}"\n\n\ndef farewell(name):\n    return f"bye, {name}"\n' > app/greet.py
  printf 'from app.greet import greet\n\n\ndef test_greet():\n    assert greet("a") == "hello, a"\n' > tests/test_greet.py

  : > "$LOG"
  rec title "a coding agent hits ratchet's git hook"
  run "ratchet init"
  run "curl -so .git/hooks/pre-commit $HOOK_URL && chmod +x .git/hooks/pre-commit"
  run "git add -A && git commit -qm 'add ratchet'"

  # the pending change the user wants committed: one line past the ceiling
  sed -i 's/^    return f"hello, {name}"/    name = name.strip()\n&/' app/greet.py
  rec note "# an uncommitted change adds 1 line of code. ask an agent to commit it:"
  agent "commit these changes"

  rec note "# the human decides the line is worth it, and grants it:"
  run "ratchet grant +1 --group source --reason 'greet() strips whitespace'"
  agent "I ran the grant. Commit it." --resume "$SESSION"
  run "ratchet check"
}

# --- play: replay the capture inside the recording ---------------------------

dim=$'\033[2m'; bold=$'\033[1m'; cyan=$'\033[1;36m'; off=$'\033[0m'

typeit() { local s="$1" i; for ((i = 0; i < ${#s}; i += 3)); do printf '%s' "${s:i:3}"; sleep 0.02; done; }

paint() {  # colour ratchet's verdict lines; leave the rest as captured
  sed -e $'s/^\\(ratchet: commit blocked.*\\)/\033[1;31m\\1\033[0m/' \
      -e $'s/^\\(ratchet: ok.*\\)/\033[1;32m\\1\033[0m/'
}

result() {  # a refusal in full, anything else trimmed the way Claude Code does
  local body
  if grep -q '^ratchet: commit blocked' <<< "$1"; then
    body="$(sed -n '/^ratchet:/,/^Refused again/p' <<< "$1")"
  else
    body="$(head -n 3 <<< "$1")"
    local n; n=$(( $(wc -l <<< "$1") - 3 ))
    [ "$n" -gt 0 ] && body+=$'\n'"… +$n lines"
  fi
  fold -s -w 74 <<< "$body" | paint | sed -e "1s/^/  ${dim}⎿${off}  /" -e '2,$s/^/     /'
}

play() {
  local line k t
  clear
  while IFS= read -r line; do
    k="$(jq -r .k <<< "$line")"; t="$(jq -r .t <<< "$line")"
    case "$k" in
      title)  printf '%s%s%s\n\n' "$bold" "$t" "$off"; sleep 1 ;;
      note)   printf '\n%s%s%s\n' "$dim" "$t" "$off"; sleep 0.8 ;;
      cmd)    printf '%s$%s ' "$cyan" "$off"; typeit "$t"; printf '\n'; sleep 0.2 ;;
      out)    paint <<< "$t"; sleep 0.8 ;;
      user)   printf '\n%s> %s' "$bold" "$off"; typeit "$t"; printf '\n\n'; sleep 0.4 ;;
      tool)   printf '%s●%s %sBash%s(%s)\n' $'\033[32m' "$off" "$bold" "$off" \
                "$(head -n 1 <<< "$t" | cut -c 1-62)"; sleep 0.3 ;;
      result) result "$t"
              if grep -q '^ratchet: commit blocked' <<< "$t"; then sleep 4; else sleep 0.3; fi ;;
      say)    printf '\n'; fold -s -w 76 <<< "$t" | sed -e "1s/^/${bold}●${off} /" -e '2,$s/^/  /'
              printf '\n'
              if grep -q 'ratchet grant' <<< "$t"; then sleep 6; else sleep 0.8; fi ;;
    esac
  done < "$LOG"
  sleep 2.5
}

if [ "${1:-}" = "--play" ]; then play; exit 0; fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
if [ "${1:-}" != "--replay" ]; then
  echo "capturing a real agent run into docs/agent-demo.jsonl ..."
  (capture)
fi

echo "recording ..."
TERM=xterm-256color asciinema rec --quiet --cols 80 --rows 30 \
  --command "bash '$REPO_ROOT/docs/agent-demo.sh' --play" -y "$WORK/agent.cast"
echo "rendering gif ..."
agg --font-size 20 --cols 80 --rows 30 --theme asciinema --speed 1.3 --idle-time-limit 6 "$WORK/agent.cast" "$GIF"
ls -la "$GIF"
